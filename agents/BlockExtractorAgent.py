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

# def block_extractor_agent_model(tools):

#     # Define the prompt for the agent
#     prompt = ChatPromptTemplate.from_messages(
#         [
#             (
#                 "system",
#                 '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
#                 JS function `extractData` that accepts a block object and returns a result. You can only use standard JavaScript functions
#                 and no TypeScript.
                
#                 To check if a receipt is successful, you can check whether receipt.status.SuccessValue key is present.
                
#                 To get a js_schema of the result, make sure to use a Run_Javascript_On_Block_Schema tool on 
#                 sample blocks that you can get using tool_get_block_heights in then past 5 days.
#                 by invoking generated JS function using `block` variable.
                
#                 Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
#                 replaced with their escaped version (\\\\n) to make these strings valid for JSON.
#                 ''',
#             ),
#             (
#                 "system",
#                 "`block.actions()` that has following schema:"
#                 + sanitized_schema_for(119688212, 'return block.actions()'),
#             ),
#             (
#                 "system",
#                 "`block.receipts()` that has following schema:"
#                 + sanitized_schema_for(119688212, 'return block.receipts()'),
#             ),
#             (
#                 "system",
#                 "`block.header()` that has following schema:"
#                 + sanitized_schema_for(119688212, 'return block.header()'),
#             ),
#             MessagesPlaceholder(variable_name="messages", optional=True),
#         ]
#     )

#     # Create the OpenAI LLM
#     llm = ChatOpenAI(model="gpt-4", temperature=0, streaming=True,)

#     # Create the tools to bind to the model
#     tools = [convert_to_openai_function(t) for t in tools]
#     tools.append(convert_to_openai_function(JsResponse))

#     model = ({"messages": RunnablePassthrough()}
#              | prompt
#              | llm.bind_tools(tools, tool_choice="any")
#              )

#     return model

def block_extractor_agent_model_v2(tools):

    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a JavaScript software engineer working with NEAR Protocol. You are only writing pure
                JS function `extractData` that accepts a block object and returns a result. You can only use standard JavaScript functions
                and no TypeScript. Do not use forEach function.

                Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make these strings valid for JSON. Ensure that you output correct Javascript Code.
                To check if a receipt is successful, you can check whether receipt.status.SuccessValue key is present.
                To get a js_schema of the result, make sure to use a Run_Javascript_On_Block_Schema tool on 
                sample blocks that you can get using tool_get_block_heights in the past 5 days.
                by invoking generated JS function using `block` variable. 
                 
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

                You will need to run multiple tool steps, after each step return the output and think about what to do next.
                1. Use the tool get_block_heights to pull the list of relevant block heights depending on the input receiver provided by the user.
                2. Use tool_infer_schema to generate a schema across block.actions() for block heights in the list.
                
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
                2. Filter block.actions() down to receiver and call tool_infer_schema_of_js on all block_heights from step 1. Also add all fields from args that are decoded from base64-encoded.

                '''.replace('{','{{').replace('}','}}')
            ),
            (
                "human",
                '''
                instructions for parsing out a block when using tool_infer_schema_of_js
                1. Extract Actions from the Block: Call block.actions() to retrieve the actions included in the block. Check if there are any actions. If not, log a message and exit.
                2. Filter Actions by Receiver: Filter the actions to include only those where receiverId matches the target contract (e.g., social.near). If no contract-specific actions are found, log a message and exit.
                3. Process Actions: Perform a flatMap operation on the filtered actions to transform and flatten the results. Use map to extract FunctionCall operations from each action.
                4. (optional) Filter Function Calls: Filter the FunctionCall operations to include only those with the specific method name (e.g., set).
                5. Decode arguments: Use base64decode to decode the arguments of each FunctionCall operation.
                '''
            ),
            ( # One shot example
                "human",
                """
                Provide the javascript code for parsing out actions and decoded arguments from block actions and filter down to only successful receipts using the receiverId 'receiver'. 
                Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
                Ensure that you output correct Javascript Code.
                """
            ),
            (
                "ai",
                """
                js: 
                `function base64decode(encodedValue) {
                    let buff = Buffer.from(encodedValue, "base64");
                    return JSON.parse(buff.toString("utf-8"));
                }
                const successfulReceipts = block.receipts()
                    .filter(receipt => receipt.receiverId === 'receiver') 
                    .filter(receipt => receipt.status.SuccessValue !== undefined)
                    .map(receipt => receipt.receiptId);

                let decodedActions = block.actions()
                    .filter(action => successfulReceipts.includes(action.receiptId))
                    .map(action => {
                        let updatedAction = { ...action, operations: action.operations.map(op => {
                            if (op.FunctionCall) {
                                try {
                                    let updatedFunctionCall = { ...op.FunctionCall };
                                    updatedFunctionCall.args = base64decode(op.FunctionCall.args);
                                    return { ...op, FunctionCall: updatedFunctionCall }; 
                                } catch (error) {
                                    return op;
                                }
                            }
                            return op;
                        })};
                        return updatedAction;
                    });
                return decodedActions`
                js_schema: 
                    `{
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                            "receiptId": {
                                "type": "string"
                            },
                            "predecessorId": {
                                "type": "string"
                            },
                            "receiverId": {
                                "type": "string"
                            },
                            "signerId": {
                                "type": "string"
                            },
                            "signerPublicKey": {
                                "type": "string"
                            },
                            "operations": {
                                "type": "array",
                                "items": {
                                "type": "object",
                                "properties": {
                                    "FunctionCall": {
                                    "type": "object",
                                    "properties": {
                                        "args": {
                                        "anyOf": [
                                            {
                                            "type": "string"
                                            },
                                            {
                                            "type": "object",
                                            "properties": {
                                                "amount": {
                                                "type": "string"
                                                }
                                            }
                                            }
                                        ]
                                        },
                                        "deposit": {
                                        "type": "string"
                                        },
                                        "gas": {
                                        "type": "integer"
                                        },
                                        "methodName": {
                                        "type": "string"
                                        }
                                    },
                                    "required": [
                                        "args",
                                        "deposit",
                                        "gas",
                                        "methodName"
                                    ]
                                    },
                                    "Stake": {
                                    "type": "object",
                                    "properties": {
                                        "publicKey": {
                                        "type": "string"
                                        },
                                        "stake": {
                                        "type": "string"
                                        }
                                    },
                                    "required": [
                                        "publicKey",
                                        "stake"
                                    ]
                                    }
                                }
                                }
                            }
                            },
                            "required": [
                            "operations",
                            "predecessorId",
                            "receiptId",
                            "receiverId",
                            "signerId",
                            "signerPublicKey"
                            ]
                        }
                    }`
                explanation: "
                The selected JavaScript code snippet is designed to decode and process blockchain action data. Here's a step-by-step description of what it does:
                Define a base64decode function: This function takes a base64 encoded string as input, decodes it to a buffer, and then parses the buffer as a JSON object. This is useful for decoding encoded blockchain data that is often stored in base64 format.
                Filter and Map block.actions(): The code starts by calling block.actions() to retrieve a list of actions from a blockchain block. It then filters these actions to only include those where the receiverId matches a specified receiver. This is likely filtering actions to focus on those relevant to a specific account or contract.
                Process Each Action: For each filtered action, the code creates a new object (updatedAction) that copies all properties from the original action. It specifically focuses on processing the operations array within each action.
                Process Each Operation in an Action: For each operation in the operations array of an action, the code checks if the operation is a FunctionCall. If it is, the code attempts to decode the args property of the FunctionCall using the previously defined base64decode function. This decoded args object replaces the original encoded args in a new updatedFunctionCall object, which is then used to create a new operation object that includes the decoded arguments. This new operation object replaces the original operation object in the operations array of the updatedAction.
                Error Handling: If an error occurs during the decoding of the args property (for example, if the encoded data is not valid JSON), the original operation object is returned unchanged. This ensures that the process can continue even if some data cannot be decoded.
                Return Processed Actions: Finally, the code returns a list of decodedActions, where each action has its operations potentially modified to include decoded arguments for any FunctionCall operations.
                "
                """.replace('{','{{').replace('}','}}')
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
        block_data_extraction_code = state.block_data_extraction_code
        if error != "":
            reflection_msg = f"""You tried to run the following Javascript function and returned an error. Change the javascript function code based on the feedback.
            Javascript function: {block_data_extraction_code}
            Error: {error}"""
            messages += [HumanMessage(content=reflection_msg)]
        response = self.model.invoke(messages)
        return {"messages": messages + [response]}
    
    def call_tool(self, state):
        messages = state.messages
        iterations = state.iterations
        error = state.error
        entity_schema = state.entity_schema
        block_heights = state.block_heights
        block_data_extraction_code = state.block_data_extraction_code
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
                # If the function message is related to JavaScript code on entity schema functionality
                if function_message.content.startswith("Javascript code is incorrect"):
                    # If the content indicates an error in the JavaScript code, store the error message
                    error = function_message.content
                else:
                    # Otherwise, store the content as the entity schema
                    entity_schema = function_message.content
                # Extract the 'arguments' field from the tool call, which contains the JavaScript parsing arguments
                js_parse_args = tool_call['function']['arguments']
                # Convert the JSON string in js_parse_args to a Python dictionary and retrieve the JavaScript code
                block_data_extraction_code = json.loads(js_parse_args)['js']
                iterations += 1

        return {"messages": messages, "entity_schema":entity_schema, "block_data_extraction_code": block_data_extraction_code, "block_heights":block_heights, "iterations":iterations,"error":error}