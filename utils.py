def get_file_content(filename: str) -> str:
    with open(filename, 'r') as f:
        return f.read()


def generate_schema(obj):
    if isinstance(obj, dict):
        properties = {k: generate_schema(v) for k, v in obj.items()}
        return {"type": "object", "properties": properties}
    elif isinstance(obj, list):
        if obj:
            return {"type": "array", "items": generate_schema(obj[0])}
        else:
            return {"type": "array"}
    elif isinstance(obj, str):
        return {"type": "string"}
    elif isinstance(obj, int):
        return {"type": "integer"}
    elif isinstance(obj, float):
        return {"type": "number"}
    elif obj is None:
        return {"type": "null"}
    else:
        raise ValueError(f"Cannot generate schema for {obj}")


def flatten(xss):
    return [x for xs in xss for x in xs]