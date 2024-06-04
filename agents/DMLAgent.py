# Define the response schema for our agent
import json

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function

from langchain_core.prompts import (
    ChatPromptTemplate,
)
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.messages import ToolMessage

class DMLResponse(BaseModel):
    """Final DML answer to the user"""

    dml: str = Field(description="The final javascript DML code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )


def dml_code_model(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
                JS function that accepts a JSON schema and PostgreSQL DDL and writes DML for inserting data from blockchain to the table. 
                You can only use standard JavaScript functions and no TypeScript.
                ''',
            ),
        ]
    )

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = {"messages": RunnablePassthrough()} | prompt | llm.bind_tools(tools).with_structured_output(DMLResponse)
    return model

class DMLCodeAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        messages = state['messages']
        ddl_code = state['ddl_code']
        response = self.model.invoke(ddl_code)
        dml_code = response.dml
        return {"messages": messages + [response],"dml_code": dml_code, "should_continue": False}
    
    def human_review(self,state):
        messages = state["messages"]
        last_tool_call = messages[-2]
        # get_block_schema_call =  last_tool_call.additional_kwargs["tool_calls"][0]["function"]["arguments"]
        dml_code = state["dml_code"]
        error = state["error"]
        response=""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the block schema: {dml_code}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages, "should_continue": True}
            elif response == "no":
                feedback = input(f"Please provide feedback on the DML code: {dml_code}")
                return {"messages": messages + [feedback], "should_continue": False}