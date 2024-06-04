from langchain.tools import tool

from tools.bitmap_indexer_client import get_block_heights


@tool
def tool_get_block_heights(receiver: str, from_days_ago: int = 7, limit=10) -> [int]:
    """
    Get block heights for the given receiver from the last from_days_ago days limiting to limit number of results
    :param receiver: the name of a smart contract for the exact match (e.g. pool.near)
    :param from_days_ago: from how many days ago to start the search
    :param limit: limit the number of results, default is 10
    :return: list of block heights
    """
    return get_block_heights(receiver, from_days_ago, limit)