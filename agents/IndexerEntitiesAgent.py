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
    """
    Represents the final response containing the list of entities and the specific data to track.

    Attributes:
        entities (str): The final list of entities to be tracked by the indexer.
        data (str): The specific data points to include for each entity.
        explanation (str): A detailed explanation of how the agent arrived at this list of entities and data points.
    """

    entities: str = Field(
        description="The final list of entities that we should design the indexer to track"
    )
    data: str = Field(
        description="Specific data that should be included for each entity"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


entity_response_parser = PydanticOutputParser(pydantic_object=EntityResponse)


def indexer_entities_agent_model():
    """
    Constructs and returns the model pipeline for generating indexer entities.

    This function defines the prompts, sets up the OpenAI language model, and
    configures the model to generate structured output related to entities for the indexer.

    Returns:
        model: The constructed model pipeline for generating indexer entities and their associated data.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            indexer_entities_system_prompt,
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=entity_response_parser.get_format_instructions())

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
    """
    Agent responsible for identifying and generating the logic for tracking indexer entities.

    Attributes:
        model: The language model used to generate the indexer logic and entity tracking details.
    """

    def __init__(self, model):
        """
        Initializes the IndexerEntitiesAgent with the provided model for generating indexer logic.

        Args:
            model: The language model used for entity identification and indexer logic generation.
        """
        self.model = model

    def call_model(self, state):
        """
        Generates the indexer logic and identifies key entities based on the current state.

        This method processes the entity schema from the state, invokes the model to
        generate or update the indexer logic, and returns the updated state with the key entities and data.

        Args:
            state: The current state containing the entity schema, messages, and iteration count.

        Returns:
            dict: The updated state with new indexer logic, entities description, and iteration count.
        """
        print("Identify key entities")
        messages = state.messages
        entity_schema = state.entity_schema
        iterations = state.iterations
        indexer_entities_description = state.indexer_entities_description

        if iterations == 0:
            new_message = SystemMessage(
                content=f"""
            Here is the schema parsed out from blocks: {entity_schema}
            """
            )
            messages.append(new_message)

        response = self.model.invoke(messages)
        indexer_entities_description = f"List of entities: {response.entities}. Entity specific data: {response.data}"

        wrapped_message = SystemMessage(content=str(response))

        return {
            "messages": messages + [wrapped_message],
            "indexer_entities_description": indexer_entities_description,
            "iterations": iterations + 1,
            "should_continue": True,
        }
