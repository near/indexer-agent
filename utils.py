def get_file_content(filename: str) -> str:
    with open(filename, 'r') as f:
        return f.read()