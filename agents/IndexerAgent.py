# Define the response schema for our agent
from langchain_core.pydantic_v1 import BaseModel, Field


class Response(BaseModel):
    """Final answer to the user"""

    js: str = Field(description="The final JS code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )


from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function

from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor
from langchain.tools import BaseTool
from tools.near_primitives_types import near_primitives_types


def indexer_agent_model(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. 
                You use various block heights 119688211, 119688186, 119688185 to understand the structure of the blocks by running JavaScript code on them.
                For example, you can run `return block.actions().filter(a => a.receiverId==='receiver.near')` to get all the actions in a block to receiver.near. 
                Start with this example on how you can extract function calls from the block, filtered by receiver 'receiver.near': 
                return block.actions()
                    .filter(a => a.receiverId==='receiver.near')
                    .flatMap(a => a.operations.filter(op => !!op.FunctionCall)).map(op => op.FunctionCall).

                Start by filtering the block actions by receiver requested by the user.
                Then, extract the function calls from the operations.

                Run this code, take the output in JSON and keep adjusting previous code before you receive satisfactory results.
                Do not use 'instanceOf' and other TypeScript specific functions.
                

                Before returning it, make sure it returns result by calling Run_Javascript_On_Block
                ''',
            ),
            # TODO: below should be replaced with a vector database that indexes GitHub repository or npm package types
            (
                "system", 
                "Here are the type definitions of the block object to help you navigate the block:" + near_primitives_types(),
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]
    tools.append(convert_to_openai_function(Response))

    model = {"messages": RunnablePassthrough()} | prompt | llm.bind_tools(tools)
    return model

def tool_executor(tools):
    tool_executor = ToolExecutor(tools=tools)
    return tool_executor