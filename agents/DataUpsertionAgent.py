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

class DataUpsertionResponse(BaseModel):
    """Final DataUpsertion answer to the user"""

    data_upsertion_code: str = Field(description="The final javascript DataUpsertion code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

DataUpsertion_parser = PydanticOutputParser(pydantic_object=DataUpsertionResponse)

def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_docs += f.read()
    return query_api_docs.replace('{', '{{').replace('}', '}}')

def data_upsertion_code_model():
    # Define the prompt for the agent
    query_api_docs = fetch_query_api_docs('./query-api-docs')
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates Javascript for inserting data from the blockchain into the 
                specified table. Return only valid JavaScript code and use only standard JavaScript functions. Do not use Typescript. 

                The provided JavaScript function extracts relevant data from the blockchain block into the specificed schema. 
                Dynamically map the parsed blockchain data to the fields specified in the given PostgreSQL schema.
                Decode and parse the data as needed (e.g., base64 decoding). Convert function names to PascalCase when calling 
                database functions. Do not use a for loop to insert data. Instead, map the data variables and feed them into the upsert function.
    
                Use async/await for database interactions to handle various types of blockchain data operations such as creation, 
                updating, and deleting records. Implement robust error handling for database operations. Log success and error messages for tracking purposes.
                Utilize near-lake primitives and context.db for upserts. Context is a global variable that contains helper methods, 
                including context.db for database interactions.

                Output result in a DataUpsertionResponse format where 'DataUpsertion' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.
                '''
            ),
            (
                "system",
                "Here is the documentation of how to use context.db methods to modify data in the table which you should use:" + query_api_docs,
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=DataUpsertion_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DataUpsertionResponse) #.bind_tools(tools)
    return model

class DataUpsertionCodeAgent:
    def __init__(self, model):
        self.model = model

    def call_model(self, state):
        print("Generating Data Upsertion Code")
        messages = state.messages
        table_creation_code = state.table_creation_code
        data_upsertion_code = state.data_upsertion_code
        extract_block_data_code = state.extract_block_data_code
        block_schema = state.block_schema
        iterations = state.iterations
        # Only take the latest messages for the agent to avoid losing context
        upsert_messages = state.messages[(-1-iterations*2):]
        if iterations == 0: # Only on the first time through append the system message
            upsert_messages.append(HumanMessage(content=f"""Here is the relevant context code:
            Postgresql schema: {table_creation_code}
            Javascript Function: {extract_block_data_code}
            Block Schema: {block_schema}"""))
        response = self.model.invoke(upsert_messages)
        wrapped_message = SystemMessage(content=str(response))
        data_upsertion_code = response.data_upsertion_code
        return {"messages": messages + [wrapped_message],"data_upsertion_code": data_upsertion_code, "should_continue": False,"iterations":iterations+1}