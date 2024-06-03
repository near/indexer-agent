
def get_tool_call_arguments(messages, cls, message_index=-1):
    message = messages[message_index]
    tool_calls = message.additional_kwargs["tool_calls"]
    args = [cls.parse_raw(tool_call["function"]["arguments"]) for tool_call in tool_calls if
            tool_call["function"]["name"] == cls.__name__]
    return args[0]
