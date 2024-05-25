from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor,ToolInvocation
import json
from langchain_core.messages import ToolMessage


class AgentState(TypedDict):
    messages: Sequence[BaseMessage]


# Define the function that determines whether to continue or not
def should_continue(state):
    last_message = state["messages"][-1]
    # If there are no tool calls, then we finish
    if "tool_calls" not in last_message.additional_kwargs:
        return "end"
    # If there is a Response tool call, then we finish
    elif any(
        tool_call["function"]["name"] == "Response"
        for tool_call in last_message.additional_kwargs["tool_calls"]
    ):
        return "end"
    # Otherwise, we continue
    else:
        return "continue"
    
class IndexerAgentGraphBuilder(object):
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor
    
    # Define the function that calls the model
    def call_model(self, state):
        messages = state["messages"]
        response = self.model.invoke(messages)
        return {"messages": messages + [response]}


    # Define the function to execute tools
    def call_tool(self, state):
        messages = state["messages"]
        # We know the last message involves at least one tool call
        last_message = messages[-1]

        # We loop through all tool calls and append the message to our message log
        for tool_call in last_message.additional_kwargs["tool_calls"]:
            action = ToolInvocation(
                tool=tool_call["function"]["name"],
                tool_input=json.loads(tool_call["function"]["arguments"]),
                id=tool_call["id"],
            )

            # We call the tool_executor and get back a response
            response = self.tool_executor.invoke(action)
            # We use the response to create a FunctionMessage
            function_message = ToolMessage(
                content=str(response), name=action.tool, tool_call_id=tool_call["id"]
            )

            # Add the function message to the list
            messages.append(function_message)

        # We return a list, because this will get added to the existing list

        return {"messages": messages}
    
    def graph(self):
        # Initialize a new graph
        graph = StateGraph(AgentState)

        # Define the two Nodes we will cycle between
        graph.add_node("agent", self.call_model)
        graph.add_node("action", self.call_tool)

        # Set the Starting Edge
        graph.set_entry_point("agent")

        # Set our Contitional Edges
        graph.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )

        # Set the Normal Edges
        graph.add_edge("action", "agent")

        # Compile the workflow
        app = graph.compile()
        return app