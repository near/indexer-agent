# Define the response schema for our agent
import json
import os
from prompts import (
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
    """Final DataUpsertion answer to the user"""

    data_upsertion_code: str = Field(
        description="The final javascript DataUpsertion code that user requested"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


DataUpsertion_parser = PydanticOutputParser(pydantic_object=DataUpsertionResponse)


def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), "r") as f:
                    query_api_docs += f.read()
    return query_api_docs.replace("{", "{{").replace("}", "}}")


def data_upsertion_code_model():
    # Define the prompt for the agent
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

    # Create the OpenAI LLM
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        streaming=True,
    )

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.with_structured_output(DataUpsertionResponse)
    )  # .bind_tools(tools)
    return model


# Define a class for handling the generation of data upsertion code


class DataUpsertionCodeAgent:
    def __init__(self, model):
        # Initialize the agent with a model for generating code
        self.model = model

    def call_model(self, state):
        # Start the process of generating data upsertion code
        print("Generating Data Upsertion Code")

        # Retrieve necessary information from the state
        messages = state.messages  # All messages exchanged in the process
        table_creation_code = state.table_creation_code  # SQL code for creating tables
        # Current data upsertion code (if any)
        data_upsertion_code = state.data_upsertion_code
        # JavaScript code for extracting block data
        block_data_extraction_code = state.block_data_extraction_code
        entity_schema = state.entity_schema  # Schema of the block data
        iterations = (
            state.iterations
        )  # Number of iterations the process has gone through

        # On the first iteration, append a message with relevant context for the model
        if iterations == 0:  # Check if it's the first iteration
            upsert_messages = [messages[0]]  # only take the original message
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

        # Invoke the model with the current messages to generate/update the data upsertion code
        response = self.model.invoke(upsert_messages)
        # Wrap the response in a system message for logging or further processing
        wrapped_message = SystemMessage(content=str(response))
        # Update the data upsertion code with the response from the model
        data_upsertion_code = response.data_upsertion_code

        # Return the updated state including the new data upsertion code and incremented iteration count
        return {
            "messages": messages + [wrapped_message],
            "data_upsertion_code": data_upsertion_code,
            "should_continue": False,
            "iterations": iterations + 1,
        }
