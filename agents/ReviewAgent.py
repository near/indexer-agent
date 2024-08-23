import json
import os
from .prompts import review_system_prompt
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema, run_js_on_block
from langchain.output_parsers import PydanticOutputParser
from query_api_docs.examples import (
    get_example_indexer_logic,
    get_example_extract_block_code,
    hardcoded_block_extractor_js,
)


class CodeReviewResponse(BaseModel):
    """
    Represents the response from the code review agent.

    Attributes:
        valid_code (bool): A boolean indicating whether the reviewed code is valid.
        explanation (str): An explanation detailing how the agent determined the validity of the code.
    """

    valid_code: bool = Field(
        description="The final boolean of whether the code is valid"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


code_review_response_parser = PydanticOutputParser(pydantic_object=CodeReviewResponse)


def review_step(state):
    """
    Determines which code section should be reviewed based on the current state.

    This function checks various parts of the state (such as data upsertion, table creation, etc.)
    and returns the step, code, and code type that needs to be reviewed.

    Args:
        state: The current state containing various code snippets to be reviewed.

    Returns:
        tuple: A tuple containing the review step name, code snippet, and code type.
    """
    review_mappings = [
        ("Data Upsertion", state.data_upsertion_code, "JavaScript"),
        ("Table Creation", state.table_creation_code, "PostgreSQL"),
        (
            "Indexer Entities",
            state.indexer_entities_description,
            "Entities Description",
        ),
        ("Extract Block Data", state.block_data_extraction_code, "JavaScript"),
    ]

    for step, code, code_type in review_mappings:
        if code != "":
            return step, code, code_type


def review_agent_model():
    """
    Constructs and returns the model pipeline for the code review agent.

    This function defines the prompt structure for the agent, configures the language model (GPT-4),
    and specifies the output format for code review.

    Returns:
        model: The constructed model pipeline for performing code reviews.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            review_system_prompt,
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=code_review_response_parser.get_format_instructions())

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        streaming=True,
    )

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.with_structured_output(CodeReviewResponse)
    )

    return model


class ReviewAgent:
    """
    An agent responsible for reviewing code (JavaScript, SQL, or schema) based on a defined process.

    Attributes:
        model: The language model used for code review, configured with a structured output.
    """

    def __init__(self, model):
        """
        Initializes the ReviewAgent with a provided model for code review.

        Args:
            model: The language model used to perform the code review.
        """
        self.model = model

    def call_model(self, state):
        """
        Automatically reviews the code based on the current state and provides feedback.

        The method invokes the language model to analyze code, offer suggestions, and determine
        whether the code is valid or needs further refinement.

        Args:
            state: The current state of the code review process, including code snippets and error messages.

        Returns:
            dict: The updated state after code review, including the decision to continue or iterate further.
        """

        print("Reviewing code...")
        messages = state.messages
        iterations = state.iterations
        block_data_extraction_code = state.block_data_extraction_code
        error = state.error
        entity_schema = state.entity_schema
        step, code, code_type = review_step(state)
        new_message = [
            HumanMessage(
                content=f"""Review this {code_type} code: {code}
            {error}"""
            )
        ]
        if step == "Extract Block Data":
            new_message.append(
                HumanMessage(
                    content=f"""Resulted in the following schema: {entity_schema}.
                If the entity schema is a simple array, attempt to parse the data again or use different block height.""".replace(
                        "{", "{{"
                    ).replace(
                        "}", "}}"
                    )
                )
            )
            error = ""
        elif step == "Indexer Logic":
            example_indexer = (
                get_example_indexer_logic()
                .replace("\\n", "\\\\n")
                .replace("{", "{{")
                .replace("}", "}}")
            )
            new_message.append(
                HumanMessage(
                    content=f"""Please use the following correctly working examples as
                guidline for reviewing JavaScript code:
                Example: {example_indexer}""".replace(
                        "{", "{{"
                    ).replace(
                        "}", "}}"
                    )
                )
            )
            error = ""
        elif step == "Data Upsertion":
            new_message.append(
                HumanMessage(
                    content=f"""Make sure the Javascript code has at least 1 context.db function for every table in the corresponding PostgreSQL code.
                Here is the corresponding PostgreSQL code: {state.table_creation_code}.
                If using an context.db upsert call, make sure that there is an explicit constraint specified and use the format: `context.db.TableName.upsert(Objects, [conflictColumn1,conflictColumn2], [updateColumn1,updateColumn2]);`
                where the Objects parameter is either one or an array of objects. The other two parameters are arrays of strings. The strings should correspond to column names for that table.
                Do not wrap the arrays in an object.""".replace(
                        "{", "{{"
                    ).replace(
                        "}", "}}"
                    )
                )
            )
            error = ""
        messages = messages + new_message
        response = self.model.invoke(messages)
        should_continue = response.valid_code
        if should_continue != True:
            print(f"Code is not valid. Repeating: {step}.")
            iterations += 1
            error = response.explanation
        else:
            iterations = 0
            error = ""
        wrapped_message = SystemMessage(content=str(response))
        return {
            "messages": messages + [wrapped_message],
            "should_continue": should_continue,
            "block_data_extraction_code": block_data_extraction_code,
            "entity_schema": entity_schema,
            "error": error,
            "iterations": iterations,
        }

    def human_review(self, state):
        """
        Manually prompts a human reviewer to check the code.

        This method facilitates a manual review of code by prompting the reviewer to provide feedback
        or confirm the correctness of the code.

        Args:
            state: The current state of the code review process, containing code snippets and schema.

        Returns:
            dict: The updated state based on the human review feedback, including the decision to continue or stop.
        """
        step, code, code_type = review_step(state)
        messages = state.messages
        entity_schema = state.entity_schema
        response = ""
        if step == "Extract Block Data":
            print(f"Entity Schema: {entity_schema}")
        while response != "yes" or response != "no":
            response = input(
                prompt=f"Please review the {step}: {code}. Is it correct? (yes/no)"
            )
            if response == "yes":
                return {"messages": messages, "should_continue": True, "iterations": 0}
            elif response == "no":
                feedback = input(f"Please provide feedback on the {code_type}: {code}")
                return {
                    "messages": messages + [HumanMessage(content=feedback)],
                    "should_continue": False,
                    "iterations": 0,
                }
