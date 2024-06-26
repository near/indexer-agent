import json
import os
from typing import Dict, List, Any
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage,HumanMessage,SystemMessage
from langchain.output_parsers import PydanticOutputParser

class EntityResponse(BaseModel):
    """Final answer to the user"""
    entities: str = Field(description="The final list of entities that we should design the indexer to track")
    data: str = Field(description="Specific data that should be included for each entity")
    explanation: str = Field(description="How did the agent come up with this answer?")

# class EntityResponse(BaseModel):
#     """Final answer to the user"""
#     entities: Dict[str, Dict[str, Any]] = Field(default_factory=dict,description="The final list of entities that we should design the indexer to track, along with specific data and reasoning for each")

entity_response_parser = PydanticOutputParser(pydantic_object=EntityResponse)

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
                '''You are a developer working NEAR Protocol. Your task is to design architecture that takes input schema and identifies key entities to index.
                
                Consider the following details:
                1. Function Calls: Pay particular attention to schemas related to function calls.
                2. Entities Identification: If the user input does not explicitly define key entities, infer them as best you can falling back on typical blockchain structures such as receipts, accounts, and function calls.
                3. Performance Considerations: The indexer will be used to design tables in a PostgreSQL database. Ensure the design is optimized for performance and scalability.

                The result should be an EntityResponse. Ensure all nested structures are converted to strings.
                ''',
            ),
            # (
            #     "system",
            #     "Here are several tutorials from documentation on how to define indexing logic filtering blockchain transactions and saving the data to the database:" + query_api_tutorials,
            # ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=entity_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(EntityResponse)
             )

    return model

class IndexerLogicAgent:
    def __init__(self, model):
        self.model = model

    # This method is responsible for generating the final indexer logic code.
    def call_model(self, state):
        # Notify the user that the final indexer logic code generation is in progress
        print("Identify key entities")
        # Retrieve the current state information
        messages = state.messages  # List of messages exchanged during the process
        extract_block_data_code = state.extract_block_data_code  # JavaScript code for parsing block data
        block_schema = state.block_schema 
        iterations = state.iterations  # Number of iterations the process has gone through
        indexer_logic = state.indexer_logic  # Current indexer logic code (if any)
        
        # If this is the first iteration, add a message summarizing the JavaScript codes used so far
        if iterations == 0:  # Check if it's the first iteration
            new_message = SystemMessage(content=f"""
            Here is the schema parsed out from blocks: {block_schema}
            """)
            messages.append(new_message)  # Append the new message to the messages list
        
        # Invoke the model with the current messages to generate/update the indexer logic code
        response = self.model.invoke(messages)
        indexer_logic = f"List of entities: {response.entities}. Entity specific data: {response.data}"  # Extract the JavaScript code from the response
        
        # Wrap the response in a system message for logging or further processing
        wrapped_message = SystemMessage(content=str(response))
        
        # Return the updated state including the new indexer logic code and incremented iteration count
        return {"messages": messages + [wrapped_message], "indexer_logic": indexer_logic, "iterations": iterations + 1}