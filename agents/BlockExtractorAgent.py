import json
import ast
import os
from .prompts import (
    block_extractor_system_prompt,
    block_extractor_js_prompt,
    block_extractor_near_social_prompt,
)
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage, HumanMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema
from langchain.output_parsers import PydanticOutputParser
from query_api_docs.examples import hardcoded_block_extractor_js


class JsResponse(BaseModel):
    """Final answer to the user

    Attributes:
        js (str): The final JS code that user requested.
        js_schema (str): The schema of the result.
        explanation (str): How did the agent come up with this answer?
    """

    js: str = Field(description="The final JS code that user requested")
    js_schema: str = Field(description="The schema of the result")
    explanation: str = Field(description="How did the agent come up with this answer?")


jsreponse_parser = PydanticOutputParser(pydantic_object=JsResponse)


def __str__(self):
    """
    Returns a formatted string representation of the JsResponse object.

    The output includes the final JavaScript code, the schema, and the explanation.

    Returns:
        str: A formatted string representation of the JsResponse object.
    """
    js_formatted = self.js.replace("\\n", "\n")
    return f"""
js: ```{js_formatted}```

js_schema: ```{self.js_schema}```

explanation: {self.explanation}
"""


def sanitized_schema_for(block_height: int, js: str) -> str:
    """
    Sanitizes and returns the schema for a specific block height and JavaScript code.

    Replaces curly braces with double curly braces to prevent code execution errors.

    Args:
        block_height (int): The block height for which the schema is generated.
        js (str): The JavaScript code for which the schema is sanitized.

    Returns:
        str: A sanitized version of the schema as a string.
    """
    res = json.dumps(run_js_on_block_only_schema(block_height, js))
    return res.replace("{", "{{").replace("}", "}}")


def block_extractor_agent_model(tools):
    """
    Creates the block extractor agent model pipeline.

    This function sets up the system prompt, configures the language model (GPT-4),
    and binds the provided tools to the model.

    Args:
        tools (list): A list of tools that will be utilized by the model.

    Returns:
        model: The constructed pipeline that processes the block extraction.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(
        base_dir, "node_modules/@near-lake/primitives/dist/src/types/block.js"
    )
    with open(file_path, "r") as file:
        block_primitive = file.read()
    prompt = ChatPromptTemplate.from_messages(
        [
            block_extractor_system_prompt,
            (
                "system",
                f"""Note the following block primitive from near lake: {block_primitive}""".replace(
                    "{", "{{"
                ).replace(
                    "}", "}}"
                ),
            ),
            block_extractor_js_prompt[0],
            block_extractor_js_prompt[1],
            block_extractor_near_social_prompt[0],
            block_extractor_near_social_prompt[1],
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=jsreponse_parser.get_format_instructions())

    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True)

    tools = [convert_to_openai_function(t) for t in tools]

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.bind_tools(tools, tool_choice="any")
    )

    return model


class BlockExtractorAgent:
    """
    A class representing an agent for extracting block data and generating JavaScript code.

    Attributes:
        model: The language model used to generate block extraction code.
        tool_executor (ToolExecutor): The executor responsible for running external tools.
    """

    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        """
        Executes the language model to generate block extraction code based on the current state.

        The method processes the provided state information, passes it to the language model,
        and retrieves updated code or error messages.

        Args:
            state: An object representing the current state of the block extraction process.

        Returns:
            dict: The updated state containing the new code, schema, and messages.
        """
        messages = state.messages
        iterations = state.iterations
        block_heights = state.block_heights
        entity_schema = state.entity_schema
        table_creation_code = state.table_creation_code
        data_upsertion_code = state.data_upsertion_code
        indexer_entities_description = state.indexer_entities_description
        should_continue = state.should_continue
        error = state.error
        block_data_extraction_code = state.block_data_extraction_code
        block_limit = state.block_limit
        previous_day_limit = state.previous_day_limit

        if iterations == None:
            block_heights = []
            entity_schema = ""
            block_data_extraction_code = ""
            table_creation_code = ""
            data_upsertion_code = ""
            indexer_entities_description = ""
            iterations = 0
            error = ""
            should_continue = False
        if len(messages) == 0:
            messages = [
                HumanMessage(
                    content=f"{state.original_prompt}. Pull block_heights for the last {previous_day_limit} days with a max of {block_limit} blocks"
                )
            ]
        if error != "":
            reflection_msg = f"""You tried to run the following Javascript function and returned an error. Change the javascript function code based on the feedback.
            Javascript function: {block_data_extraction_code}
            Error: {error}"""
            messages += [HumanMessage(content=reflection_msg)]
        response = self.model.invoke(messages)
        return {
            "messages": messages + [response],
            "iterations": iterations,
            "block_heights": block_heights,
            "entity_schema": entity_schema,
            "block_data_extraction_code": block_data_extraction_code,
            "table_creation_code": table_creation_code,
            "data_upsertion_code": data_upsertion_code,
            "indexer_entities_description": indexer_entities_description,
            "error": error,
            "should_continue": should_continue,
        }

    def call_tool(self, state):
        """
        Executes the relevant tools to perform block extraction and schema inference.

        This method uses the tool executor to run the block extraction code and processes the
        resulting data or errors to update the state.

        Args:
            state: The current state containing messages, block heights, and code.

        Returns:
            dict: The updated state including any errors, code, and processed block heights.
        """
        messages = state.messages
        iterations = state.iterations
        error = state.error
        entity_schema = state.entity_schema
        block_heights = state.block_heights
        block_data_extraction_code = state.block_data_extraction_code
        last_message = messages[-1]

        for tool_call in last_message.additional_kwargs["tool_calls"]:
            action = ToolInvocation(
                tool=tool_call["function"]["name"],
                tool_input=json.loads(tool_call["function"]["arguments"]),
                id=tool_call["id"],
            )
            print(f'Calling tool: {tool_call["function"]["name"]}')
            response = self.tool_executor.invoke(action)
            function_message = ToolMessage(
                content=str(response), name=action.tool, tool_call_id=tool_call["id"]
            )

            messages.append(function_message)

            if function_message.name == "tool_get_block_heights":
                try:
                    block_heights.extend(ast.literal_eval(function_message.content))
                except (ValueError, SyntaxError):
                    block_heights = []
            elif (
                function_message.name == "tool_js_on_block_schema_func"
                or function_message.name == "tool_infer_schema_of_js"
            ):
                if function_message.content.startswith("Javascript code is incorrect"):
                    error = function_message.content
                else:
                    entity_schema = function_message.content
                js_parse_args = tool_call["function"]["arguments"]
                block_data_extraction_code = json.loads(js_parse_args)["js"]
                iterations += 1

        return {
            "messages": messages,
            "entity_schema": entity_schema,
            "block_data_extraction_code": block_data_extraction_code,
            "block_heights": block_heights,
            "iterations": iterations,
            "error": error,
        }
