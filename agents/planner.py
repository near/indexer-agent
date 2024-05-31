import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.messages import ToolMessage

def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_docs += f.read()
    return query_api_docs.replace('{', '{{').replace('}', '}}')

def planner_init(tools):
    query_api_docs = fetch_query_api_docs('./query-api-docs')
    prompt =  ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a planning agent. Your goal is to oversee the creation of a NEAR Protocol blockchain data indexer
            from inception to completion. Users will provide you with a smart contract account id and a data question
            and you will create a plan to create an indexer to track relevant data. 
            
            You also have access to tools for getting block data and running JavaScript code on blocks which you should use
            """,
        ),
        (
            "system",
            "Here is the documentation of how to build an indexer to help you plan:" + query_api_docs,
        ),
        MessagesPlaceholder(variable_name="messages", optional=True),
    ])
    tools = [convert_to_openai_function(t) for t in tools]
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0,streaming=True,)
    model = {"messages": RunnablePassthrough()} | prompt | llm.bind_tools(tools)
    return model

class PlannerAgent:
    def __init__(self,model, tool_executor: ToolExecutor):
        # pass
        self.model = model
        self.tool_executor = tool_executor

    def plan_execution(self,state):
        """
        Plan execution using indexer documentation
        """

        messages = state["messages"]
        # UNECESSARY FOR THIS FUNCTION BUT JUST KEEPING HERE FOR REFERENCE
        iterations = state["iterations"]
        block_schema = state["block_schema"]
        error = state["error"]
        
        # query_api_docs = fetch_query_api_docs('./query-api-docs')
        # prompt =  ChatPromptTemplate.from_messages(
        # [
        #     (
        #         "system",
        #         """You are a planning agent. Your goal is to oversee the creation of a NEAR Protocol blockchain data indexer
        #         from inception to completion. Users will provide you with a smart contract account id and a data question
        #         and you will create a plan to create an indexer to track relevant data.""",
        #     ),
        #     (
        #         "system",
        #         "Here is the documentation of how to build an indexer to help you plan:" + query_api_docs,
        #     ),
        #     # MessagesPlaceholder(variable_name="messages", optional=True),
        # ])
        # llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0,streaming=True,)
        # model = {"messages": RunnablePassthrough()} | prompt | llm
        response = self.model.invoke(messages)
        # return messages
        return {"messages": messages + [response]}



    def get_block_schema(self,state):
        messages = state["messages"]
        block_schema = state["block_schema"]
        last_message = messages[-1]
        iterations = state["iterations"]

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
            # Add the schema to the schema
            block_schema = function_message.content

        # We return a list, because this will get added to the existing list
        return {"messages": messages,"block_schema":block_schema, "iterations":iterations+1}

    def human_review(self,state):
        messages = state["messages"]
        last_tool_call = messages[-2]
        get_block_schema_call =  last_tool_call.additional_kwargs["tool_calls"][0]["function"]["arguments"]
        block_schema = state["block_schema"]
        error = state["error"]
        response=""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the block schema: {block_schema}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages}
            elif response == "no":
                feedback = input(f"Please provide feedback on the javascript call: {get_block_schema_call}")
                feedback += "Retry using tool Run_Javascript_On_Block_Schema with the updated javascript call"
                return {"messages": messages + [feedback], "block_schema": "","error": "Block schema is incorrect. Please review and try again"}


#     we need to add human feedback in your architecture. After the indexer code and the schema is generated and the planner is happy with the result, we should present it to the user to get feedback.
# The user could give feedback on the field names, types of data to extract and the sql schema itself

    # def query_blocks():
    #     pass