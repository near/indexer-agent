# Define the response schema for our agent
import json

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function

from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor
from langchain.tools import BaseTool

from tools.JavaScriptRunner import run_js_on_block_only_schema
from tools.near_primitives_types import near_primitives_types

class JsResponse(BaseModel):
    """Final answer to the user"""

    js: str = Field(description="The final JS code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

def sanitized_schema_for(block_height: int, js: str) -> str:
    res = json.dumps(run_js_on_block_only_schema(block_height, js))
    return res.replace('{', '{{').replace('}', '}}')

def block_extractor_agent_model(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
                JS function that accepts a block object and returns a result. You can only use standard JavaScript functions
                and no TypeScript. Output result as a JsResponse format.
                ''',
            ),
            (
                "system",
                "`block.actions()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.actions()'),
            ),
            (
                "system",
                "`block.receipts()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.receipts()'),
            ),
            (
                "system",
                "`block.header()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.header()'),
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]
    tools.append(convert_to_openai_function(JsResponse))

    model = {"messages": RunnablePassthrough()} | prompt | llm.bind_tools(tools)
    return model