import json
from .prompts import table_creation_system_prompt, table_creation_near_social_prompt

# Define the response schema for our agent
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, ToolMessage, HumanMessage
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from langchain.output_parsers import PydanticOutputParser


class TableCreationResponse(BaseModel):
    """
    Final response from the agent for table creation, including both the DDL script and the explanation.

    Attributes:
        table_creation_code (str): The DDL script for creating the table in the Postgres database.
        explanation (str): An explanation of how the agent derived the table creation code.
    """

    table_creation_code: str = Field(
        description="The TableCreation Script for Postgres Database code that user requested"
    )
    explanation: str = Field(description="How did the agent come up with this answer?")


ddl_parser = PydanticOutputParser(pydantic_object=TableCreationResponse)


def table_creation_code_model(tools):
    """
    Constructs and returns the model pipeline for generating table creation SQL code.

    This function sets up the system prompts, configures the language model, and binds tools to the model.

    Args:
        tools (list): List of tools to be used by the model for generating SQL code.

    Returns:
        model: The constructed model pipeline for generating the table creation code.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            table_creation_system_prompt,
            table_creation_near_social_prompt[0],
            table_creation_near_social_prompt[1],
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=ddl_parser.get_format_instructions())

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        streaming=True,
    )

    tools = [convert_to_openai_function(t) for t in tools]

    model = (
        {"messages": RunnablePassthrough()}
        | prompt
        | llm.bind_tools(tools, tool_choice="any")
    )

    return model


class TableCreationAgent:
    """
    An agent responsible for generating SQL code for table creation based on an entity schema.

    Attributes:
        model: The language model responsible for generating the table creation SQL code.
        tool_executor (ToolExecutor): The executor for running tools that validate the generated SQL code.
    """

    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        """
        Generates SQL DDL for table creation based on the provided schema and state information.

        This method processes the entity schema and relevant state data to generate or update
        the SQL table creation script.

        Args:
            state: An object representing the current state of the table creation process.

        Returns:
            dict: The updated state containing the new table creation code, iteration count, and any error messages.
        """
        print("Generating Table Creation Code")
        messages = state.messages
        table_creation_code = state.table_creation_code
        indexer_entities_description = state.indexer_entities_description
        entity_schema = state.entity_schema
        iterations = state.iterations
        error = state.error

        if error == "":
            table_creation_msgs = [messages[0]]
            table_creation_msgs.append(
                HumanMessage(
                    content=f"Here is the Entity Schema: {entity_schema} and the Entities to create tables for: {indexer_entities_description}"
                )
            )
        else:
            table_creation_msgs = messages[(-1 - iterations * 2) :]

        response = self.model.invoke(table_creation_msgs)

        return {
            "messages": messages + [response],
            "table_creation_code": table_creation_code,
            "should_continue": False,
            "iterations": iterations + 1,
        }

    def call_tool(self, state):
        """
        Tests the generated SQL DDL statement using the tool executor and updates the state based on the result.

        This method executes the generated DDL statement to validate correctness, logs any errors,
        and updates the state accordingly.

        Args:
            state: The current state of the process including messages, DDL code, and errors.

        Returns:
            dict: The updated state including validation results, iteration count, and any errors.
        """
        print("Test SQL DDL Statement")
        messages = state.messages
        iterations = state.iterations
        error = state.error
        table_creation_code = state.table_creation_code
        should_continue = state.should_continue
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

        if messages[-1].content == "DDL statement executed successfully.":
            table_creation_code = tool_call["function"]["arguments"]
            should_continue = True
        else:
            error = (
                "An error occurred while running the SQL DDL statement. "
                + messages[-1].content
            )

        return {
            "messages": messages,
            "table_creation_code": table_creation_code,
            "iterations": iterations + 1,
            "error": error,
            "should_continue": should_continue,
        }
