# Define the response schema for our agent
import json

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.messages import ToolMessage,SystemMessage,HumanMessage
from langchain.output_parsers import PydanticOutputParser

class DDLAgentResponse(BaseModel):
    """Final answer to the user"""
    code: str = Field(description="The DDL Script for Postgres Database code that user requested")
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
                a DDL script for a Postgres database to create a table that can store the result.
                
                Convert all field names to snake case and don't remove any words from them.
                
                Output result in a DDLAgentResponse format where 'code' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JSON.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    llm = ChatOpenAI(model="gpt-4", temperature=0, streaming=True, )

    tools = [convert_to_openai_function(DDLAgentResponse)]

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model


class DDLResponse(BaseModel):
    """Final DDL answer to the user"""

    ddl: str = Field(description="The DDL Script for Postgres Database code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

ddl_parser = PydanticOutputParser(pydantic_object=DDLResponse)

def ddl_code_model_v2(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a Postgres SQL engineer working with a Javascript Developer.
                
                Based on this schema, generate a DDL script for a Postgres database to create a 
                table that can store the result. Be sure to include and define a primary key, when in doubt fallback on receipt_id.
                
                Convert all field names to snake case and don't remove any words from them.
                
                Output result in a DDLAgentResponse format where 'ddl' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for PostgreSQL.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=ddl_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    # # Create the tools to bind to the model
    # tools = [convert_to_openai_function(DDLAgentResponse)]

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DDLResponse) #.bind_tools(tools,tool_choice="any")
    return model

class DDLCodeAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        print("Generating DDL Code")
        messages = state.messages
        ddl_code = state.ddl_code
        block_schema = state.block_schema
        messages.append(SystemMessage(content=f"Here is the Block Schema: {block_schema}"))
        response = self.model.invoke(messages)
        ddl_code = response.ddl
        wrapped_message = SystemMessage(content=str(response))
        return {"messages": messages + [wrapped_message],"ddl_code":ddl_code, "should_continue": False, "iterations":0}
    
    def call_tool(self, state):
        messages = state.messages
        block_schema = state.block_schema
        block_heights = state.block_heights
        js_code = state.js_code
        # We know the last message involves at least one tool call
        last_message = messages[-1]

        # We loop through all tool calls and append the message to our message log
        for tool_call in last_message.additional_kwargs["tool_calls"]:
            action = ToolInvocation(
                tool=tool_call["function"]["name"],
                tool_input=json.loads(tool_call["function"]["arguments"]),
                id=tool_call["id"],
            )

            # We call the tool_executor and get back a response
            response = self.tool_executor.invoke(action)
            # We use the response to create a FunctionMessage
            function_message = ToolMessage(
                content=str(response), name=action.tool, tool_call_id=tool_call["id"]
            )

            # Add the function message to the list
            messages.append(function_message)

            if function_message.name == 'tool_get_block_heights':
                block_heights = function_message.content
            elif function_message.name == 'tool_js_on_block_schema':
                block_schema = function_message.content
                js_parse_args = tool_call['function']['arguments']
                js_code = json.loads(js_parse_args)['js']

        # We return a list, because this will get added to the existing list

        return {"messages": messages, "block_schema":block_schema, "js_code": js_code, "block_heights":block_heights}
    
    def human_review(self,state):
        messages = state.messages
        ddl_code = state.ddl_code
        response=""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the DDL Code: {ddl_code}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages, "should_continue":True,"iterations":0}
            elif response == "no":
                feedback = input(f"Please provide feedback on the ddl code: {ddl_code}")
                feedback += "Retry the DDL code generation with the correct schema"
                return {"messages": messages + [HumanMessage(content=feedback)]}