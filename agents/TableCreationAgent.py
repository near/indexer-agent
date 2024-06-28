import json
# Define the response schema for our agent
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import SystemMessage,ToolMessage
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain.output_parsers import PydanticOutputParser

class TableCreationAgentResponse(BaseModel):
    """Final answer to the user"""
    code: str = Field(description="The TableCreation Script for Postgres Database code that user requested")
    def __str__(self):
        return f"""ddl: ```
{self.code}
```"""

def ddl_generator_agent_model(tools):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a Postgres SQL engineer working with a Javascript Developer.
                
                You will get a schema of the result by running the JS function. Based on this schema, generate 
                a TableCreation script for a Postgres database to create a table that can store the result.
                
                Convert all field names to snake case and don't remove any words from them.
                
                Output result in a TableCreationAgentResponse format where 'code' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JSON.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    llm = ChatOpenAI(model="gpt-4", temperature=0, streaming=True, )

    tools = [convert_to_openai_function(TableCreationAgentResponse)]

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model


class TableCreationResponse(BaseModel):
    """Final TableCreation answer to the user"""

    table_creation_code: str = Field(description="The TableCreation Script for Postgres Database code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

ddl_parser = PydanticOutputParser(pydantic_object=TableCreationResponse)

def table_creation_code_model_v2(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a Postgres SQL engineer working with a Javascript Developer.
                
                Based on schema and entities, generate a TableCreation script for a Postgres database to create 
                tables that can store the results. Each table must have a primary key, generally based on available ID columns.
                For receipt based tables, 'receipt_id' is a default, otherwise create a column 'id' as a serial and constrain as primary key.
                When possible, implement database normalization best practices in order to optimize storage and retrieval.
                Ensure that for any attributes containing nested data, such data is decomposed into separate tables to achieve normalization.
                
                Convert all field names to snake case and don't remove any words from them.
                For typing, default to VARCHAR for strings and BIGINT for numbers as many fields will be of undetermined length.
                
                Output result in a TableCreationAgentResponse format where 'ddl' field is valid PostgreSQL.
                Put all SQL code into 1 tool call.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=ddl_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    # model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(TableCreationResponse)
    tools = [convert_to_openai_function(t) for t in tools]

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model

# Define a class responsible for generating SQL code for table creation based on entity schema
class TableCreationAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        # Begin the process of generating table creation SQL code
        print("Generating Table Creation Code")
        # Extract necessary information from the state
        messages = state.messages  # All messages exchanged in the process
        table_creation_code = state.table_creation_code  # Current table creation code (if any)
        indexer_entities_description = state.indexer_entities_description
        entity_schema = state.entity_schema  # Schema of the block data
        iterations = state.iterations  # Number of iterations the process has gone through
        error = state.error  # Error message (if any)

        # Focus on the latest messages to maintain context relevance
        # This helps in providing the model with the most recent and relevant information
        # table_creation_msgs = messages[(-1-iterations*2):]
        if error == "":
            table_creation_msgs = [messages[0]] # only take the original message
            # Append a system message with the block schema for context
            table_creation_msgs.append(SystemMessage(content=f"Here is the Block Schema: {entity_schema} and the Entities to create tables for: {indexer_entities_description}"))
        else:
            table_creation_msgs = messages[(-1-iterations*2):]

        # Invoke the model with the current messages to generate/update the table creation code
        response = self.model.invoke(table_creation_msgs)
        
        # Update the table creation code with the response from the model
        # table_creation_code = response.table_creation_code

        # Wrap the response in a system message for logging or further processing
        # wrapped_message = SystemMessage(content=str(response))

        # Return the updated state including the new table creation code and incremented iteration count
        return {"messages": messages + [response], "table_creation_code": table_creation_code, "should_continue": False, "iterations": iterations + 1}
    
    def call_tool(self, state):
        print("Test SQL DDL Statement")
        messages = state.messages
        iterations = state.iterations
        error = state.error
        table_creation_code = state.table_creation_code
        should_continue = state.should_continue
        # We know the last message involves at least one tool call
        last_message = messages[-1]

        # We loop through all tool calls and append the message to our message log
        for tool_call in last_message.additional_kwargs["tool_calls"]:
            action = ToolInvocation(
                tool=tool_call["function"]["name"],
                tool_input=json.loads(tool_call["function"]["arguments"]),
                id=tool_call["id"],
            )
            print(f'Calling tool: {tool_call["function"]["name"]}')
            # We call the tool_executor and get back a response
            response = self.tool_executor.invoke(action)
            # We use the response to create a FunctionMessage
            function_message = ToolMessage(
                content=str(response), name=action.tool, tool_call_id=tool_call["id"]
            )

            # Add the function message to the list
            messages.append(function_message)

        # If the tool call was successful, we update the state, otherwise we set an error message
        if messages[-1].content == "DDL statement executed successfully.":
            table_creation_code = tool_call['function']['arguments']
            should_continue=True
        else:
            error = "An error occurred while running the SQL DDL statement. " + messages[-1].content

        return {"messages": messages, "table_creation_code":table_creation_code, "iterations":iterations+1,"error":error,"should_continue":should_continue}