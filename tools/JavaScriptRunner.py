import requests
import javascript
import os.path
import json
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool, tool

from utils import generate_schema


def flatten(xss):
    return [x for xs in xss for x in xs]


def fetch_block(height: int) -> str:
    filename = f'{height}.json'
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            return f.read()
    streamer_message = requests.get(f'https://70jshyr5cb.execute-api.eu-central-1.amazonaws.com/block/{height}')
    with open(filename, 'w') as f:
        f.write(streamer_message.text)
    return streamer_message.text


class TestJavascriptOnBlock(BaseModel):
    block_height: int = Field(..., title="Block height")
    js: str = Field(..., title="Javascript code to run that starts with 'return '")


def run_js_on_block(block_height: int, js: str) -> str:
    streamer_message = fetch_block(block_height)
    primitives = javascript.require("@near-lake/primitives")
    try:
        block = primitives.Block.fromStreamerMessage(json.loads(streamer_message))
        result = javascript.eval_js(js)
        if hasattr(result, 'valueOf'):
            result = result.valueOf()
    except Exception as e:
        return str(e)
    return result


def run_js_on_block_only_schema(block_height: int, js: str) -> str:
    json_res = run_js_on_block(block_height, js)
    return generate_schema(json_res)


@tool
def tool_js_on_block_schema(block_height: int, js: str) -> str:
    """
    Get JSON Schema of the result of execution of a javascript code on a given block height
    To use it, pass the block height and the javascript statement to run.

    Parameters:
    block_height (int): Block height.
    js (str): Javascript code to run that starts with 'return '.

    Returns:
    str: JSON schema of the result.
    """
    return run_js_on_block_only_schema(block_height, js)


@tool
def tool_js_on_block_schema_func(block_height: int, js: str, func_name: str) -> str:
    """
    Get JSON Schema of the result of execution of a javascript function code
    and its name on a given block height.

    Parameters:
    block_height (int): Block height.
    js (str): The code of a Javascript function to run on a block.
    func_name (str): the name of the function.

    Returns:
    str: JSON schema of the result.
    """
    code = f"""{js}
    
return {func_name}(block)"""
    return run_js_on_block_only_schema(block_height, code)


tool_js_on_block = StructuredTool.from_function(
    func=run_js_on_block,
    name="Run_Javascript_On_Block",
    description="""
    Executes any javascript code on a block to check if it works correctly and get the result 
    To use it, pass the block height and the javascript statement to run.
    Add a 'return ' before the statement to get the result.
    The result is returned as a JSON string""",
    args_schema=TestJavascriptOnBlock,
    return_direct=False,
)


####################################################################################################
# we probably won't need these functions, but it is an example of a mix of python and javascipt code

def make_function_call(operation: dict, action: dict) -> dict:
    return {
        **action,
        **operation
    }


def get_function_calls_from_block(block_height: int, receiver: str) -> str:
    streamer_message = fetch_block(block_height)
    primitives = javascript.require("@near-lake/primitives")
    block = primitives.Block.fromStreamerMessage(json.loads(streamer_message))
    operations = flatten([
        [make_function_call(op.valueOf(), a.valueOf()) for op in a.operations if op['FunctionCall']]
        for a in block.actions() if a.receiverId == receiver])

    function_calls = [op['FunctionCall'] for op in operations if op['FunctionCall']]

    #    decoded_function_calls = [{**call, 'args': base64.b64decode(call['args']).decode('utf-8')} for call in function_calls]

    return json.dumps(function_calls)
