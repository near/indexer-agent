import json
import ast
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage,HumanMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema
from langchain.output_parsers import PydanticOutputParser
from query_api_docs.examples import hardcoded_block_extractor_js

class JsResponse(BaseModel):
    """Final answer to the user"""

    js: str = Field(description="The final JS code that user requested")
    js_schema: str = Field(description="The schema of the result")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

jsreponse_parser = PydanticOutputParser(pydantic_object=JsResponse)

def __str__(self):
    js_formatted = self.js.replace('\\n', '\n')
    return f"""
js: ```{js_formatted}```

js_schema: ```{self.js_schema}```

explanation: {self.explanation}
"""

def sanitized_schema_for(block_height: int, js: str) -> str:
    res = json.dumps(run_js_on_block_only_schema(block_height, js))
    return res.replace('{', '{{').replace('}', '}}')

def block_extractor_agent_model(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
                JS function `extractData` that accepts a block object and returns a result. You can only use standard JavaScript functions
                and no TypeScript.
                
                To check if a receipt is successful, you can check whether receipt.status.SuccessValue key is present.
                
                To get a js_schema of the result, make sure to use a Run_Javascript_On_Block_Schema tool on 
                sample blocks that you can get using tool_get_block_heights in then past 5 days.
                by invoking generated JS function using `block` variable.
                
                Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make these strings valid for JSON.
                ''',
            ),
            (
                "system",
                "`block.actions()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.actions()'),
            ),
            (
                "system",
                "`block.receipts()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.receipts()'),
            ),
            (
                "system",
                "`block.header()` that has following schema:"
                + sanitized_schema_for(119688212, 'return block.header()'),
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    )

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]
    tools.append(convert_to_openai_function(JsResponse))

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model

def block_extractor_agent_model_v2(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
                JS function `extractData` that accepts a block object and returns a result. You can only use standard JavaScript functions
                and no TypeScript. Do not use forEach function.
                
                To check if a receipt is successful, you can check whether receipt.status.SuccessValue key is present.
                To get a js_schema of the result, make sure to use a Run_Javascript_On_Block_Schema tool on 
                sample blocks that you can get using tool_get_block_heights in the past 5 days.
                by invoking generated JS function using `block` variable. 
                
                Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
                Ensure that you output correct Javascript Code.
                 
                Use the below best practices:
                 
                1. Always use explicit boolean statements and avoid implicit conversions.
                2. Use array methods such as flatMap, map, and filter to efficiently transform and filter blockchain actions. These methods help create concise and expressive code, making it easier to manage and understand the flow of data processing.
                3. Implement thorough error handling and logging throughout your code. This practice is crucial for debugging and maintaining the application. By catching potential errors and logging them, you ensure that issues can be diagnosed and resolved without causing unexpected crashes.
                4. Validate the structure and content of data before processing it. This step is essential to ensure that the data meets the expected format and to prevent runtime errors. Proper data validation helps maintain data integrity and ensures that only the correct data is processed.
                5. Use asynchronous functions (async/await) to handle input/output operations, such as fetching data from the blockchain or interacting with a database. Asynchronous processing keeps the application responsive and allows it to handle multiple tasks concurrently without blocking the execution flow.
                6. Encapsulate specific functionalities into separate functions. This modular approach improves the readability and maintainability of your code. By breaking down complex processes into smaller, manageable functions, you make the code easier to test, debug, and extend.
                ''',
            ),
            (
                "system",
                '''Note the following schema for each block that will be useful for parsing out the data:
                `block.actions()` that has following schema:
                `{"type": "array", "items": {"type": "object", "properties": {"receiptId": {"type": "string"}, "predecessorId": {"type": "string"}, "receiverId": {"type": "string"}, "signerId": {"type": "string"}, "signerPublicKey": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object", "properties": {"Delegate": {"type": "object", "properties": {"delegateAction": {"type": "object", "properties": {"actions": {"type": "array", "items": {"type": "object", "properties": {"FunctionCall": {"type": "object", "properties": {"args": {"type": "string"}, "deposit": {"type": "string"}, "gas": {"type": "integer"}, "methodName": {"type": "string"}}}}}}, "maxBlockHeight": {"type": "integer"}, "nonce": {"type": "integer"}, "publicKey": {"type": "string"}, "receiverId": {"type": "string"}, "senderId": {"type": "string"}}}, "signature": {"type": "string"}}}}}}}}}`
                `block.receipts()` that has the following schema:
                `{"type": "array", "items": {"type": "object", "properties": {"receiptKind": {"type": "string"}, "receiptId": {"type": "string"}, "receiverId": {"type": "string"}, "predecessorId": {"type": "string"}, "status": {"type": "object", "properties": {"SuccessValue": {"type": "string"}}}, "executionOutcomeId": {"type": "string"}, "logs": {"type": "array"}}}}`
                `block.header()` that has following schema:
                `{"type": "object", "properties": {"height": {"type": "integer"}, "hash": {"type": "string"}, "prevHash": {"type": "string"}, "author": {"type": "string"}, "timestampNanosec": {"type": "string"}, "epochId": {"type": "string"}, "nextEpochId": {"type": "string"}, "gasPrice": {"type": "string"}, "totalSupply": {"type": "string"}, "latestProtocolVersion": {"type": "integer"}, "randomValue": {"type": "string"}, "chunksIncluded": {"type": "integer"}, "validatorProposals": {"type": "array"}}}`
            
                You will need to run multiple tool steps, after each step return the output and think about what to do next.
                1. Use the tool get_block_heights to pull the list of relevant block heights depending on the input receiver provided by the user.
                2. Use tool_infer_schema to generate a schema across block.actions(), block.receipts() and block.header() for block heights in the list.
                3. Run tool_js_on_block_schema_func for a sample block (use the first in the list from step 1) to return a sample schema of the block and show that the code is working.
                '''.replace('{','{{').replace('}','}}')
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=jsreponse_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model

def block_extractor_agent_model_v3(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. Your job is to run Javascript functions that accept a block
                and returns results. You will be supplied specific receiver and block_heights, and your job is to parse through them to identify
                what sorts of entities we would like to create for our data indexer.
                
                Output results in JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
                Ensure that you output correct Javascript Code using best practices:
                1. Always use explicit boolean statements and avoid implicit conversions.
                2. Use array methods such as flatMap, map, and filter to efficiently transform and filter blockchain actions. These methods help create concise and expressive code, making it easier to manage and understand the flow of data processing.
                3. Implement thorough error handling and logging throughout your code. This practice is crucial for debugging and maintaining the application. By catching potential errors and logging them, you ensure that issues can be diagnosed and resolved without causing unexpected crashes.
                4. Validate the structure and content of data before processing it. This step is essential to ensure that the data meets the expected format and to prevent runtime errors. Proper data validation helps maintain data integrity and ensures that only the correct data is processed.
                5. Use asynchronous functions (async/await) to handle input/output operations, such as fetching data from the blockchain or interacting with a database. Asynchronous processing keeps the application responsive and allows it to handle multiple tasks concurrently without blocking the execution flow.
                6. Encapsulate specific functionalities into separate functions. This modular approach improves the readability and maintainability of your code. By breaking down complex processes into smaller, manageable functions, you make the code easier to test, debug, and extend.
                ''',
            ),
            (
                "system",
                '''Note the following schema for each block that will be useful for parsing out the data:
                `block.actions()` that has following schema:
                `{"type": "array", "items": {"type": "object", "properties": {"receiptId": {"type": "string"}, "predecessorId": {"type": "string"}, "receiverId": {"type": "string"}, "signerId": {"type": "string"}, "signerPublicKey": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object", "properties": {"Delegate": {"type": "object", "properties": {"delegateAction": {"type": "object", "properties": {"actions": {"type": "array", "items": {"type": "object", "properties": {"FunctionCall": {"type": "object", "properties": {"args": {"type": "string"}, "deposit": {"type": "string"}, "gas": {"type": "integer"}, "methodName": {"type": "string"}}}}}}, "maxBlockHeight": {"type": "integer"}, "nonce": {"type": "integer"}, "publicKey": {"type": "string"}, "receiverId": {"type": "string"}, "senderId": {"type": "string"}}}, "signature": {"type": "string"}}}}}}}}}`
                `block.receipts()` that has the following schema:
                `{"type": "array", "items": {"type": "object", "properties": {"receiptKind": {"type": "string"}, "receiptId": {"type": "string"}, "receiverId": {"type": "string"}, "predecessorId": {"type": "string"}, "status": {"type": "object", "properties": {"SuccessValue": {"type": "string"}}}, "executionOutcomeId": {"type": "string"}, "logs": {"type": "array"}}}}`
                `block.header()` that has following schema:
                `{"type": "object", "properties": {"height": {"type": "integer"}, "hash": {"type": "string"}, "prevHash": {"type": "string"}, "author": {"type": "string"}, "timestampNanosec": {"type": "string"}, "epochId": {"type": "string"}, "nextEpochId": {"type": "string"}, "gasPrice": {"type": "string"}, "totalSupply": {"type": "string"}, "latestProtocolVersion": {"type": "integer"}, "randomValue": {"type": "string"}, "chunksIncluded": {"type": "integer"}, "validatorProposals": {"type": "array"}}}`

                You will need to run multiple tool steps, after each step return the output and think about what to do next.
                1. Use the tool get_block_heights to pull the list of relevant block heights depending on the input receiver provided by the user.
                2. Filter block.actions() down to receiver and call tool_infer_schema_of_js using all block_heights from step 1. Also add all fields from args that are decoded from base64-encoded.
                '''.replace('{','{{').replace('}','}}')
                #  tool_get_method_names to return a list of available method_names for that receiver
                # Here is an example of how you should attempt to parse block actions
                # block.actions
                #     .filter(a => a.receiverId === receiver)
                #     .flatMap(a => a.operations
                #         .map(op => op.FunctionCall)
                #     )
                #     .map(fc => {
                #         return {
                #             ...fc,
                #             args: base64decode(fc.args)
                #             <ADD ADDITIONAL FIELDS LIKE receiptID>
                #         };
                #     });
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=jsreponse_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.bind_tools(tools, tool_choice="any")
             )

    return model

class BlockExtractorAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        messages = state.messages
        error = state.error
        extract_block_data_code = state.extract_block_data_code
        if error != "":
            reflection_msg = f"""You tried to run the following Javascript function and returned an error. Change the javascript function code based on the feedback.
            Javascript function: {extract_block_data_code}
            Error: {error}"""
            messages += [HumanMessage(content=reflection_msg)]
        response = self.model.invoke(messages)
        return {"messages": messages + [response]}
    
    def call_tool(self, state):
        messages = state.messages
        iterations = state.iterations
        error = state.error
        block_schema = state.block_schema
        block_heights = state.block_heights
        extract_block_data_code = state.extract_block_data_code
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

            # Check the name of the function message to determine the type of data it contains
            if function_message.name == 'tool_get_block_heights':
                # If the function message is about retrieving block heights, store its content in block_heights variable
                try:
                    block_heights = ast.literal_eval(function_message.content)
                except (ValueError, SyntaxError):
                    block_heights = []
            elif function_message.name == 'tool_js_on_block_schema_func' or function_message.name == 'tool_infer_schema_of_js':
                # If the function message is related to JavaScript code on block schema functionality
                if function_message.content.startswith("Javascript code is incorrect"):
                    # If the content indicates an error in the JavaScript code, store the error message
                    error = function_message.content
                else:
                    # Otherwise, store the content as the block schema
                    block_schema = function_message.content
                # Extract the 'arguments' field from the tool call, which contains the JavaScript parsing arguments
                js_parse_args = tool_call['function']['arguments']
                # Convert the JSON string in js_parse_args to a Python dictionary and retrieve the JavaScript code
                extract_block_data_code = json.loads(js_parse_args)['js']

        return {"messages": messages, "block_schema":block_schema, "extract_block_data_code": extract_block_data_code, "block_heights":block_heights, "iterations":iterations+1,"error":error}