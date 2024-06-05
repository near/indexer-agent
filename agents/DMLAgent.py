# Define the response schema for our agent
import json
import os
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.messages import ToolMessage,SystemMessage,HumanMessage
from langchain.output_parsers import PydanticOutputParser

class DMLResponse(BaseModel):
    """Final DML answer to the user"""

    dml: str = Field(description="The final javascript DML code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

dml_parser = PydanticOutputParser(pydantic_object=DMLResponse)

def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_docs += f.read()
    return query_api_docs.replace('{', '{{').replace('}', '}}')

def dml_code_model(tools):
    query_api_docs = fetch_query_api_docs('./query-api-docs')
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates DML for inserting data from the blockchain into the 
                specified table.

                Output result in a DMLResponse format where 'dml' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.

                Requirements:

                Standard JavaScript Only:
                - Do not use TypeScript.
                - Use only standard JavaScript functions.
                Parse Blockchain Data:
                - Use the provided JavaScript function to extract relevant data from the blockchain block.
                - Decode and parse the data as needed (e.g., base64 decoding).
                Data Mapping and Upserting:
                - Dynamically map the parsed blockchain data to the fields specified in the given PostgreSQL schema.
                - Use async/await for database interactions.
                - Handle various types of blockchain data operations such as creation, updating, and deleting records.
                Error Handling and Logging:
                - Implement robust error handling for database operations.
                - Log success and error messages for tracking purposes.
                NEAR Primitives and Context:
                - Begin the script with: import * as primitives from "@near-lake/primitives";
                - Utilize near-lake primitives and context.db for upserts.
                - getBlock(block, context) applies your custom logic to a Block on Near and commits the data to a database.
                - context is a global variable that contains helper methods, including context.db for database interactions.
                ''',
            ),
            (
            "system",
            "Here is the documentation of how to build an indexer to help you plan:" + query_api_docs,
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=dml_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DMLResponse) #.bind_tools(tools)
    return model

def dml_code_model_v2(tools):
    # Define the prompt for the agent

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates DML for inserting data from the blockchain into the 
                specified table.

                Convert function names to PascalCase when calling database functions. Do not use a for loop to insert data. 
                Instead, map the data variables and feed them into the upsert function.

                Output result in a DMLResponse format where 'dml' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.
                '''
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=dml_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DMLResponse) #.bind_tools(tools)
    return model

class DMLCodeAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        messages = state['messages']
        dml_code = state['dml_code']
        iterations = state['iterations']
        response = self.model.invoke(messages)
        wrapped_message = SystemMessage(content=str(response))
        dml_code = response.dml
        return {"messages": messages + [wrapped_message],"dml_code": dml_code, "should_continue": False,"iterations":iterations+1}
    
    def human_review(self,state):
        messages = state["messages"]
        # last_tool_call = messages[-2]
        # get_block_schema_call =  last_tool_call.additional_kwargs["tool_calls"][0]["function"]["arguments"]
        dml_code = state["dml_code"]
        error = state["error"]
        response=""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the DML code: {dml_code}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages, "should_continue": True}
            elif response == "no":
                feedback = input(f"Please provide feedback on the DML code: {dml_code}")
                return {"messages": messages + [HumanMessage(content=feedback)], "should_continue": False}