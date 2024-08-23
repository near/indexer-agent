import json
import os
from prompts import review_system_prompt
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema, run_js_on_block
from langchain.output_parsers import PydanticOutputParser
from query_api_docs.examples import get_example_indexer_logic, get_example_extract_block_code, hardcoded_block_extractor_js


class CodeReviewResponse(BaseModel):
    """Final answer to the user"""
    valid_code: bool = Field(
        description="The final boolean of whether the code is valid")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )


code_review_response_parser = PydanticOutputParser(
    pydantic_object=CodeReviewResponse)

# Takes state and sequentially determines which code to review by checking backwards


def review_step(state):
    review_mappings = [
        ("Data Upsertion", state.data_upsertion_code, "JavaScript"),
        ("Table Creation", state.table_creation_code, "PostgreSQL"),
        ("Indexer Entities", state.indexer_entities_description, "Entities Description"),
        ("Extract Block Data", state.block_data_extraction_code, "JavaScript")
    ]

    for step, code, code_type in review_mappings:
        if code != "":
            return step, code, code_type


def review_agent_model():
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            review_system_prompt,
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=code_review_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(CodeReviewResponse)
             )

    return model


class ReviewAgent:
    def __init__(self, model):
        # Initialize the ReviewAgent with a model for code review
        self.model = model

    def call_model(self, state):
        # Method to automatically review code based on the current state
        print("Reviewing code...")
        # Extract relevant information from the state
        messages = state.messages
        iterations = state.iterations
        block_data_extraction_code = state.block_data_extraction_code
        error = state.error
        entity_schema = state.entity_schema

        # Determine the current step, the code to review, and its type
        step, code, code_type = review_step(state)

        # Create a new message prompting for review of the code
        new_message = [HumanMessage(content=f"""Review this {code_type} code: {code}
            {error}""")]

        # Provide examples for guidance based on the review step
        if step == "Extract Block Data":
            # Example code for extracting block data
            new_message.append(HumanMessage(content=f"""Resulted in the following schema: {entity_schema}.
                If the entity schema is a simple array, attempt to parse the data again or use different block height.""".replace('{', '{{').replace('}', '}}')))
            error = ""  # Reset error after providing examples
        elif step == "Indexer Logic":
            # Example code for indexer logic
            example_indexer = get_example_indexer_logic().replace(
                "\\n", "\\\\n").replace("{", "{{").replace("}", "}}")
            new_message.append(HumanMessage(content=f"""Please use the following correctly working examples as
                guidline for reviewing JavaScript code:
                Example: {example_indexer}""".replace('{', '{{').replace('}', '}}')))
            error = ""  # Reset error after providing examples
        elif step == "Data Upsertion":
            new_message.append(HumanMessage(content=f"""Make sure the Javascript code has at least 1 context.db function for every table in the corresponding PostgreSQL code.
                Here is the corresponding PostgreSQL code: {state.table_creation_code}.
                If using an context.db upsert call, make sure that there is an explicit constraint specified and use the format: `context.db.TableName.upsert(Objects, [conflictColumn1,conflictColumn2], [updateColumn1,updateColumn2]);`
                where the Objects parameter is either one or an array of objects. The other two parameters are arrays of strings. The strings should correspond to column names for that table.
                Do not wrap the arrays in an object.""".replace('{', '{{').replace('}', '}}')))
            error = ""  # Reset error after providing examples
        # Update the messages with the new message
        messages = messages + new_message  # testing out
        # Invoke the model with the updated messages for review
        response = self.model.invoke(messages)
        # Determine if the code review should continue based on the model's response
        should_continue = response.valid_code
        if should_continue != True:
            # If code is not valid, print a message and repeat the step
            print(f"Code is not valid. Repeating: {step}.")
            # Increment iterations
            iterations += 1
            # Update error with the latest explanation
            error = response.explanation
        else:
            # Reset iterations and error message
            iterations = 0
            error = ""
        # Wrap the model's response in a system message
        wrapped_message = SystemMessage(content=str(response))

        # Return the updated state including the decision on whether to continue
        return {"messages": messages + [wrapped_message], "should_continue": should_continue, "block_data_extraction_code": block_data_extraction_code, "entity_schema": entity_schema, "error": error, "iterations": iterations}

    def human_review(self, state):
        # Method for manual human review of the code
        step, code, code_type = review_step(state)
        messages = state.messages
        entity_schema = state.entity_schema
        response = ""
        # Prompt for human review until a valid response ('yes' or 'no') is received
        if step == "Extract Block Data":
            # Print the entity schema for reference during review
            print(f"Entity Schema: {entity_schema}")
        while response != "yes" or response != "no":
            response = input(
                prompt=f"Please review the {step}: {code}. Is it correct? (yes/no)")
            if response == "yes":
                # If the code is correct, continue without iterations
                return {"messages": messages, "should_continue": True, "iterations": 0}
            elif response == "no":
                # If the code is incorrect, prompt for feedback and do not continue
                feedback = input(
                    f"Please provide feedback on the {code_type}: {code}")
                return {"messages": messages + [HumanMessage(content=feedback)], "should_continue": False, "iterations": 0}
