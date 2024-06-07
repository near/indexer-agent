# Define the response schema for our agent
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import SystemMessage
from langchain.output_parsers import PydanticOutputParser

class TableCreationAgentResponse(BaseModel):
    """Final answer to the user"""
    code: str = Field(description="The TableCreation Script for Postgres Database code that user requested")
    def __str__(self):
        return f"""ddl: ```
{self.code}
```"""

def ddl_generator_agent_model():
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

def table_creation_code_model_v2():

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a Postgres SQL engineer working with a Javascript Developer.
                
                Based on this schema, generate a TableCreation script for a Postgres database to create a 
                table that can store the result. Be sure to include and define a primary key, when in doubt fallback on receipt_id.
                
                Convert all field names to snake case and don't remove any words from them.
                
                Output result in a TableCreationAgentResponse format where 'ddl' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for PostgreSQL.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=ddl_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(TableCreationResponse)
    return model

class TableCreationAgent:
    def __init__(self, model):
        self.model = model

    def call_model(self, state):
        print("Generating Table Creation Code")
        messages = state.messages
        table_creation_code = state.table_creation_code
        block_schema = state.block_schema
        iterations = state.iterations
        # Only take the latest messages for the agent to avoid losing context
        table_creation_msgs = messages[(-1-iterations*2):]
        table_creation_msgs.append(SystemMessage(content=f"Here is the Block Schema: {block_schema}"))
        response = self.model.invoke(table_creation_msgs)
        table_creation_code = response.table_creation_code
        wrapped_message = SystemMessage(content=str(response))
        return {"messages": messages + [wrapped_message],"table_creation_code":table_creation_code, "should_continue": False, "iterations":iterations+1}