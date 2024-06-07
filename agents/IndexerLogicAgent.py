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
                '''You are a JavaScript software engineer working with NEAR Protocol. Your task is to combine the Javascript for parsing block schem anad the Javascript code
                for moving data into PostgreSQL table to create JavaScript code that performs the filtering of blockchain transactions, transforming and saving the data to a database.
                You should ONLY output JavaScript. 
                
                Use standard JavaScript functions and no TypeScript. Do not omit any code or information for the final output.
                Ensure variable names are consistent across the code. Ensure that there is robust error handling and logging.
                
                The result should be an IndexerResponse and should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JSON.
                ''',
            ),
            (
            "system",
            "Here are example indexer javascript code to help you:" + query_api_examples,
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=indexer_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(IndexerResponse)
             )

    return model

class IndexerLogicAgent:
    def __init__(self, model):
        self.model = model

    def call_model(self, state):
        print("Generating Final Indexer Logic code")
        messages = state.messages
        last_message = messages[-1] # Only use the latest 2 messages to not lose the context
        extract_block_data_code = state.extract_block_data_code
        data_upsertion_code = state.data_upsertion_code
        iterations = state.iterations
        indexer_logic = state.indexer_logic
        new_message = HumanMessage(content=f"""
            Here is the javascript code that was used for parsing block data: {extract_block_data_code}   
            Here is the JavScript code for moving block data to that target PostgreSQL table: {data_upsertion_code}
            """)
        response = self.model.invoke([last_message,new_message])
        indexer_logic = response.js
        wrapped_message = SystemMessage(content=str(response))
        return {"messages": messages + [wrapped_message],"indexer_logic": indexer_logic, iterations:iterations+1}