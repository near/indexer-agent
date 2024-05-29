from utils import *

def near_primitives_types():
    block = get_file_content("tools/near_primitives_types/block.d.ts")
    receipts = get_file_content("tools/near_primitives_types/receipts.d.ts")
    events = get_file_content("tools/near_primitives_types/events.d.ts")

    code = block + receipts + events

    code = code.replace('{', '{{')
    code = code.replace('}', '}}')

    return code
