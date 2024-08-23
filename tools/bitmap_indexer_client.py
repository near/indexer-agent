import requests
import json
from datetime import datetime, timedelta
import numpy as np
import base64
from utils import flatten


def get_block_heights(receiver: str, from_days_ago: int = 7, limit=10) -> [int]:
    """
    Get sample block heights for the given receiver from the last from_days_ago days limiting to limit number of results
    :param receiver: the name of a smart contract for the exact match (e.g. pool.near)
    :param from_days_ago: from how many days ago to start the search
    :param limit: limit the number of results, default is 10
    :return:
    """
    date_seven_days_ago = datetime.now() - timedelta(days=from_days_ago)

    print(
        f"Getting block heights from bitmap indexer for receiver={receiver} from_days_ago={from_days_ago} limit={limit}"
    )
    block_heights = graphql_query(receiver, date_seven_days_ago.date().isoformat())
    return block_heights[:limit]


def graphql_query(receiver: str, starting_block_date: str):
    url = "https://near-queryapi.dev.api.pagoda.co/v1/graphql"
    headers = {"Content-Type": "application/json", "x-hasura-role": "darunrs_near"}

    query = f"""
    query Bitmap {{
      darunrs_near_bitmap_v5_actions_index(
        where: {{
            block_date: {{_gte: "{starting_block_date}"}}
            receiver: {{
                receiver: {{_eq: "{receiver}"}}
            }}
        }}
      ) {{
        bitmap
        block_date
        first_block_height
      }}
    }}
    """
    response = requests.post(url, headers=headers, data=json.dumps({"query": query}))

    if response.status_code == 200:
        bitmaps = response.json()["data"]["darunrs_near_bitmap_v5_actions_index"]
        result = [
            compressed_base64_to_heights(b["first_block_height"], b["bitmap"])
            for b in bitmaps
            if b["bitmap"]
        ]
        return flatten(result)
    else:
        raise Exception(f"Request failed with status code {response.status_code}")


def compressed_base64_to_heights(first_block_height, compressed_base64):
    compressed_bytes = np.frombuffer(
        base64.b64decode(compressed_base64), dtype=np.uint8
    )
    bitmap = decompress_to_bitmap_array(compressed_bytes)
    heights = []
    current_height = first_block_height
    for i in range(len(bitmap) * 8):
        if get_bit_in_byte_array(bitmap, i):
            heights.append(current_height + i)

    return heights


def decode_elias_gamma_entry_from_bytes(bytes_array, start_bit=0):
    if bytes_array is None or len(bytes_array) == 0:
        return {"x": 0, "last_bit": 0}

    idx = index_of_first_bit_in_byte_array(bytes_array, start_bit)
    if idx < 0:
        return {"x": 0, "last_bit": -1}

    n = idx - start_bit
    remainder = 0 if n == 0 else get_number_between_bits(bytes_array, idx + 1, idx + n)
    return {"x": 2**n + remainder, "last_bit": idx + n}


def decompress_to_bitmap_array(compressed_bytes):
    compressed_bit_length = len(compressed_bytes) * 8
    cur_bit = (compressed_bytes[0] & 0b10000000) > 0
    result = np.zeros(11000, dtype=np.uint8)
    compressed_bit_idx = 1
    result_bit_idx = 0

    while compressed_bit_idx < compressed_bit_length:
        x, last_bit = decode_elias_gamma_entry_from_bytes(
            compressed_bytes, compressed_bit_idx
        ).values()
        compressed_bit_idx = last_bit + 1
        if x == 0:
            break

        for i in range(x):
            if cur_bit:
                result = set_bit_in_bitmap(result, result_bit_idx + i, True)
        result_bit_idx += x
        cur_bit = not cur_bit

    buffer_length = (result_bit_idx + 7) // 8
    return result[:buffer_length]


def get_bit_in_byte_array(bytes_array, bit_index):
    byte_index = bit_index // 8
    bit_index_inside_byte = bit_index % 8
    return (bytes_array[byte_index] & (1 << (7 - bit_index_inside_byte))) > 0


def get_number_between_bits(bytes_array, start, end):
    result = 0
    for bit_index in range(end, start - 1, -1):
        if get_bit_in_byte_array(bytes_array, bit_index):
            result |= 1 << (end - bit_index)
    return result


def index_of_first_bit_in_byte_array(bytes_array, start_bit):
    first_bit = start_bit % 8
    for i_byte in range(start_bit // 8, len(bytes_array)):
        if bytes_array[i_byte] > 0:
            for i_bit in range(first_bit, 8):
                if bytes_array[i_byte] & (1 << (7 - i_bit)):
                    return i_byte * 8 + i_bit
        first_bit = 0
    return -1


def set_bit_in_bitmap(uint8_array, bit_index, bit_value, write_zero=False):
    new_len = (bit_index // 8) + 1
    if len(uint8_array) < new_len:
        result = np.zeros(new_len, dtype=np.uint8)
        result[: len(uint8_array)] = uint8_array
    else:
        result = uint8_array.copy()

    if not bit_value and write_zero:
        result[bit_index // 8] &= ~(1 << (7 - (bit_index % 8)))
    elif bit_value:
        result[bit_index // 8] |= 1 << (7 - (bit_index % 8))

    return result
