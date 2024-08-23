import json
import os
from .prompts import indexer_entities_system_prompt
from typing import Dict, List, Any
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from langchain.output_parsers import PydanticOutputParser


class EntityResponse(BaseModel):
    """Final answer to the user"""

    entities: str = Field(
        description="The final list of entities that we should design the indexer to track"
    )
    data: str = Field(
        description="Specific data that should be included for each entity"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


entity_response_parser = PydanticOutputParser(pydantic_object=EntityResponse)


def indexer_entities_agent_model():
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            indexer_entities_system_prompt,
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=entity_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        streaming=True,
    )

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.with_structured_output(EntityResponse)
    )

    return model


class IndexerEntitiesAgent:
    def __init__(self, model):
        self.model = model

    # This method is responsible for generating the final indexer logic code.
    def call_model(self, state):
        # Notify the user that the final indexer logic code generation is in progress
        print("Identify key entities")
        # Retrieve the current state information
        messages = state.messages  # List of messages exchanged during the process
        entity_schema = state.entity_schema
        iterations = (
            state.iterations
        )  # Number of iterations the process has gone through
        indexer_entities_description = (
            state.indexer_entities_description
        )  # Current indexer logic code (if any)

        # If this is the first iteration, add a message summarizing the JavaScript codes used so far
        if iterations == 0:  # Check if it's the first iteration
            new_message = SystemMessage(
                content=f"""
            Here is the schema parsed out from blocks: {entity_schema}
            """
            )
            messages.append(new_message)  # Append the new message to the messages list

        # Invoke the model with the current messages to generate/update the indexer logic code
        response = self.model.invoke(messages)
        indexer_entities_description = f"List of entities: {response.entities}. Entity specific data: {response.data}"  # Extract the JavaScript code from the response

        # Wrap the response in a system message for logging or further processing
        wrapped_message = SystemMessage(content=str(response))

        # Return the updated state including the new indexer logic code and incremented iteration count
        return {
            "messages": messages + [wrapped_message],
            "indexer_entities_description": indexer_entities_description,
            "iterations": iterations + 1,
            "should_continue": True,
        }
