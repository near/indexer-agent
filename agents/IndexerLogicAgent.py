import json
import os
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage,HumanMessage,SystemMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema
from langchain.output_parsers import PydanticOutputParser

class IndexerResponse(BaseModel):
    """Final answer to the user"""

    js: str = Field(description="The final JS code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

indexer_response_parser = PydanticOutputParser(pydantic_object=IndexerResponse)

def fetch_query_api_examples(directory):
    query_api_examples = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".js"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_examples += f.read()
    return query_api_examples.replace('{', '{{').replace('}', '}}')

def indexer_logic_agent_model():
    query_api_examples = fetch_query_api_examples('./query-api-docs/example_indexers')
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. Your task is to create an asynchronous function getBlock that processes blockchain data 
                and imports it into a pre-determined SQL table. I will provide 4 pieces of information, the javascript for parsing
                block schema, that block schema parsed, the DDL code for creating the table and the DML code for inserting data into the table.
                You can only use standard JavaScript functions and no TypeScript. Do not omit any code or information for the final output.
                
                Use NEAR primitives like primitives.Block. Ensure variable names are consistent across the code. The function should:
                - Initialize: Set up an empty array to store parsed data.
                - Retrieve and Filter Actions: Focus on actions targeting a specified contract and filter FunctionCall operations.
                - Upserts: Implement upsert logic to insert or update data in the SQL table from the data manipulation language.
                - Decode and Parse Arguments: Validate and extract necessary data.
                - Log Parsed Data: If data is found, log it along with block metadata (height and timestamp).
                - Asynchronously Process Data: Process each piece of data asynchronously.
                - Error Handling and Logging: Ensure robust error handling and logging.
                Output: The result should be an IndexerResponse and should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JSON.
                ''',
            ),
            # (
            # "system",
            # "Here are example indexer javascript code to help you:" + query_api_examples,
            # ),
            # MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=indexer_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(IndexerResponse)
             )

    return model

class IndexerLogicAgent:
    def __init__(self, model):
        self.model = model

    def call_model(self, state):
        print("Generating final Indexer Logic code")
        messages = state.messages
        last_message = messages[-1] # Only use the latest message to not lose the context
        js_code = state.js_code
        dml_code = state.dml_code
        ddl_code = state.ddl_code
        block_schema = state.block_schema
        indexer_logic = state.indexer_logic
        new_message = SystemMessage(content=f"""Here is the javascript code that is useful for parsing out block data: {js_code}
            Here is the block schema that is parsed using the javascript code: {block_schema}
            Here is the data manipulation code for inserting into the table: {dml_code}
            Here is the data definition language for the data you will insert into postgreSQL table: {ddl_code}    
            """)
        response = self.model.invoke([last_message,new_message])
        indexer_logic = response.js
        wrapped_message = SystemMessage(content=str(response))
        return {"messages": messages + [wrapped_message],"indexer_logic": indexer_logic}
    
    # def reflection(self, state):
    #     messages = state.messages
    #     iterations = state.iterations
    #     indexer_logic = state.indexer_logic
    #     messages.append(SystemMessage(content=f"""
    #         Please review the following Javascript code and ensure:
    #             1. The code is pure javascript
    #             2. Has sufficient checks for error handling including try-catch blocks and logging errors to deal with unexpected situations
    #             3. Properly calls NEAR primitives like primitives.Block to process blockchain data
    #             Output: The result should be an IndexerResponse and should have newlines (\\n) 
    #             replaced with their escaped version (\\\\n) to make the string valid for JSON.
    #             Here is the generated Indexer Logic code: {indexer_logic}
    #         """))
    #     response = self.model.invoke(messages)
    #     indexer_logic = response.js
    #     wrapped_message = [SystemMessage(content=str(response))]
    #     return {"messages": messages + [wrapped_message],"indexer_logic": indexer_logic, iterations:iterations+1}