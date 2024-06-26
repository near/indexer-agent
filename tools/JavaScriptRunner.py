import base64

import requests
import javascript
import os.path
from pathlib import Path
import json
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool, tool
from typing import Union,Any

from tools.bitmap_indexer_client import get_block_heights
from utils import generate_schema, flatten
from genson import SchemaBuilder


def fetch_block(height: int) -> str:
    Path(".blockcache").mkdir(exist_ok=True)
    filename = f'.blockcache/{height}.json'
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


def run_js_on_block(block_height: int, js: str) -> Union[Any, Exception]:
    streamer_message = fetch_block(block_height)
    primitives = javascript.require("@near-lake/primitives")
    try:
        block = primitives.Block.fromStreamerMessage(json.loads(streamer_message))
        result = javascript.eval_js(js)
        if hasattr(result, 'valueOf'):
            result = result.valueOf()
    except Exception as e:
        return e
    return result


def run_js_on_block_only_schema(block_height: int, js: str) -> str:
    json_res = run_js_on_block(block_height, js)
    if isinstance(json_res, Exception):
        return f"Javascript code is incorrect, here is the exception: {json_res}"
    return generate_schema(json_res)


def run_js_on_blocks_only_schema(block_heights: [int], js: str) -> str:
    schema_builder = SchemaBuilder(schema_uri=None)
    results = [run_js_on_block(height, js) for height in block_heights]
    for s in results:
        schema_builder.add_object(s)
    return schema_builder.to_json(indent=2)


def infer_schema_of_js(receiver: str, js: str, from_days_ago=100, limit=10, block_heights=[]) -> str:
    if len(block_heights) == 0:
        block_heights = get_block_heights(receiver, from_days_ago, limit)
    schema_builder = SchemaBuilder(schema_uri=None)
    cur_schema = None
    for height in block_heights:
        # print(f"Inferring schema for {js} on block height {height}")
        js_res = run_js_on_block(height, js)
        if isinstance(js_res, Exception):
            return f"Javascript code is incorrect on block height {height}, here is the exception: {js_res}"
        schema_builder.add_object(js_res)
        new_schema = schema_builder.to_json(indent=2)
        if cur_schema != new_schema:
            cur_schema = new_schema
        # else:
        #     return generate_schema(cur_schema)
    return cur_schema


@tool
def tool_infer_schema_of_js(receiver: str, js: str, from_days_ago=100, limit=10, block_heights=[]) -> str:
    """
    Infers JSON schema of the result of execution of a javascript code on
    block heights where receipts to 'receiver' are present in the last 'from_days_ago' days.
    :param receiver: receiver smart contract for the exact match
    :param js: Javascript code to run that starts with 'return '
    :param from_days_ago: from how many days ago to start the search
    :param limit: limit the number of results, default is 10
    :param block_heights: list of block heights to run the code on
    
    Returns:
    str: JSON schema of the result.
    """
    return infer_schema_of_js(receiver, js, from_days_ago, limit, block_heights)


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

@tool
def tool_get_block_heights(receiver: str, from_days_ago:int,limit:int) -> [int]:
    """
    Get list of block heights for a given receiver id over 'from_days_ago' days
    To use it, pass the receiver_id, the number of days previous, and limit of blocks

    Parameters:
    receiver (int): receiver smart contract for the exact match
    from_days_ago (int): The code of a Javascript function to run on a block.
    limit (int): the limit in number of block heights to return

    Returns:
    [int]: List of block heights.
    """    
    return get_block_heights(receiver, from_days_ago, limit)

@tool
def tool_get_method_names(block_height: int, js:str) -> str:
    """
    Return the method names of the result of execution of a javascript code on a given block height
    To use it, pass the block height and the javascript statement to run.

    Parameters:
    block_height (int): Block height.
    js (str): Javascript code to run that starts with 'return '.

    Returns:
    str: method names that parsed out from the block
    """
    return run_js_on_block(block_height, js)

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

    decoded_function_calls = [{**call, 'args': base64.b64decode(call['args']).decode('utf-8')} for call in function_calls]

    return json.dumps(decoded_function_calls)
