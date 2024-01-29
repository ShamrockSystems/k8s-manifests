def normalize_line_endings(data: str) -> str:
    return data.replace("\r\n", "\n").replace("\r", "\n")
