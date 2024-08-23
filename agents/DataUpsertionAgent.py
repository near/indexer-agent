# Define the response schema for our agent
import json
import os
from .prompts import (
    data_upsertion_system_prompt,
    data_upsertion_nearcrowd_prompt,
    data_upsertion_near_social_prompt,
    data_upsertion_queryapi_prompt,
)
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langchain.output_parsers import PydanticOutputParser


class DataUpsertionResponse(BaseModel):
    """
    Represents the final response from the agent, including the generated data upsertion code and an explanation.

    Attributes:
        data_upsertion_code (str): The final JavaScript data upsertion code requested by the user.
        explanation (str): An explanation of how the agent generated the data upsertion code.
    """

    data_upsertion_code: str = Field(
        description="The final javascript DataUpsertion code that user requested"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


DataUpsertion_parser = PydanticOutputParser(pydantic_object=DataUpsertionResponse)


def fetch_query_api_docs(directory):
    """
    Fetches the query API documentation from the specified directory.

    This function walks through the directory and reads the contents of all `.txt` files,
    concatenating them into a single string while sanitizing curly braces for safe formatting.

    Args:
        directory (str): The path to the directory containing the documentation files.

    Returns:
        str: A sanitized string of concatenated documentation.
    """
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), "r") as f:
                    query_api_docs += f.read()
    return query_api_docs.replace("{", "{{").replace("}", "}}")


def data_upsertion_code_model():
    """
    Constructs and returns the model pipeline for generating data upsertion JavaScript code.

    This function defines the system prompts, configures the language model, and binds the
    necessary tools to generate structured output related to data upsertion code.

    Returns:
        model: The constructed model pipeline for generating data upsertion code.
    """
    query_api_docs = fetch_query_api_docs("./query_api_docs")
    prompt = ChatPromptTemplate.from_messages(
        [
            data_upsertion_system_prompt,
            (
                "system",
                "Here is the documentation of how to use context.db methods to modify data in the table which you should use:"
                + query_api_docs,
            ),
            data_upsertion_nearcrowd_prompt[0],
            data_upsertion_nearcrowd_prompt[1],
            data_upsertion_near_social_prompt[0],
            data_upsertion_near_social_prompt[1],
            data_upsertion_queryapi_prompt[0],
            data_upsertion_queryapi_prompt[1],
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=DataUpsertion_parser.get_format_instructions())

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        streaming=True,
    )

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.with_structured_output(DataUpsertionResponse)
    )
    return model


class DataUpsertionCodeAgent:
    """
    An agent responsible for generating and refining JavaScript data upsertion code based on provided schema and context.

    Attributes:
        model: The language model used to generate the data upsertion code.
    """

    def __init__(self, model):
        """
        Initializes the DataUpsertionCodeAgent with a provided language model.

        Args:
            model: The language model responsible for generating the data upsertion code.
        """

        self.model = model

    def call_model(self, state):
        """
        Generates or updates JavaScript data upsertion code based on the current process state.

        This method retrieves relevant context from the state, invokes the model to generate or update
        the data upsertion code, and returns the updated state.

        Args:
            state: The current state of the data upsertion process, including messages, schema, and code snippets.

        Returns:
            dict: The updated state containing the new data upsertion code, messages, and incremented iteration count.
        """
        print("Generating Data Upsertion Code")
        messages = state.messages
        table_creation_code = state.table_creation_code
        data_upsertion_code = state.data_upsertion_code
        block_data_extraction_code = state.block_data_extraction_code
        entity_schema = state.entity_schema
        iterations = state.iterations
        if iterations == 0:
            upsert_messages = [messages[0]]
            upsert_messages.append(
                HumanMessage(
                    content=f"""Here is the relevant context code:
            Postgresql schema: {table_creation_code}
            Javascript Function: {block_data_extraction_code}
            Entity Schema: {entity_schema}"""
                )
            )
        else:
            upsert_messages = messages[(-1 - iterations * 2) :]
        response = self.model.invoke(upsert_messages)
        wrapped_message = SystemMessage(content=str(response))
        data_upsertion_code = response.data_upsertion_code
        return {
            "messages": messages + [wrapped_message],
            "data_upsertion_code": data_upsertion_code,
            "should_continue": False,
            "iterations": iterations + 1,
        }
