import json
import os
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage,HumanMessage,SystemMessage
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
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_examples += f.read()
    return query_api_examples.replace('{', '{{').replace('}', '}}')

def indexer_logic_agent_model():
    print('fetching queryapi docs')
    query_api_tutorials = fetch_query_api_examples('./query_api_docs/tutorials')
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. Your task is to combine the Javascript for parsing block schem and the Javascript code
                for moving data into PostgreSQL table to create 1 final JavaScript function that performs the filtering of blockchain transactions, transforming and saving the data to a database.
                You should ONLY output JavaScript, create a function and include a line to invoke this function on a variable called block
                
                Use standard JavaScript functions and no TypeScript. Do not omit any code or information for the final output. 
                Ensure variable names are consistent across the code, but note that the context.db functions must use PascalCase. Ensure that there is robust error handling and logging.
                Only declare functions as async if they perform asynchronous operations using await. Optimize the code so that it does not require extraneous queries, but you do not
                need to define the database connection.. Implement comprehensive error handling that includes retry logic for recoverable errors and specific responses for different error types.
                Validate and verify the existence of properties in data objects before using them. Implement fallbacks or error handling for missing properties to prevent runtime errors.
                Always use parameterized queries when interacting with databases to safeguard against SQL injection attacks. Avoid constructing queries with raw user input or template literals directly.
                Refactor duplicate code into reusable functions or modules. 
                
                The result should be an IndexerResponse and should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JSON.
                ''',
            ),
            (
                "system",
                "Here are several tutorials from documentation on how to define indexing logic filtering blockchain transactions and saving the data to the database:" + query_api_tutorials,
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=indexer_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(IndexerResponse)
             )

    return model

class IndexerLogicAgent:
    def __init__(self, model):
        self.model = model

    # This method is responsible for generating the final indexer logic code.
    def call_model(self, state):
        # Notify the user that the final indexer logic code generation is in progress
        print("Generating Final Indexer Logic code")
        # Retrieve the current state information
        messages = state.messages  # List of messages exchanged during the process
        extract_block_data_code = state.extract_block_data_code  # JavaScript code for parsing block data
        data_upsertion_code = state.data_upsertion_code  # JavaScript code for moving data to PostgreSQL
        iterations = state.iterations  # Number of iterations the process has gone through
        indexer_logic = state.indexer_logic  # Current indexer logic code (if any)
        
        # If this is the first iteration, add a message summarizing the JavaScript codes used so far
        if iterations == 0:  # Check if it's the first iteration
            new_message = HumanMessage(content=f"""
            Here is the javascript code that was used for parsing block data: {extract_block_data_code}   
            Here is the JavScript code for moving block data to that target PostgreSQL table: {data_upsertion_code}
            """)
            messages.append(new_message)  # Append the new message to the messages list
        
        # Invoke the model with the current messages to generate/update the indexer logic code
        response = self.model.invoke(messages)
        indexer_logic = response.js  # Extract the JavaScript code from the response
        
        # Wrap the response in a system message for logging or further processing
        wrapped_message = SystemMessage(content=str(response))
        
        # Return the updated state including the new indexer logic code and incremented iteration count
        return {"messages": messages + [wrapped_message], "indexer_logic": indexer_logic, "iterations": iterations + 1}