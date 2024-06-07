import json
import os
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import ToolMessage,HumanMessage,SystemMessage
from tools.JavaScriptRunner import run_js_on_block_only_schema, run_js_on_block
from langchain.output_parsers import PydanticOutputParser
from query_api_docs.examples import get_example_indexer_logic, get_example_extract_block_code,hardcoded_block_extractor_js

class CodeReviewResponse(BaseModel):
    """Final answer to the user"""
    valid_code: bool = Field(description="The final boolean of whether the code is valid")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

code_review_response_parser = PydanticOutputParser(pydantic_object=CodeReviewResponse)

# Takes state and sequentially determines which code to review by checking backwards
def review_step(state):
    review_mappings = [
        ("Indexer Logic", state.indexer_logic, "JavaScript"),
        ("Data Upsertion", state.data_upsertion_code, "JavaScript"),
        ("Table Creation", state.table_creation_code, "PostgreSQL"),
        ("Extract Block Data", state.extract_block_data_code, "JavaScript")
    ]
    
    for step, code, code_type in review_mappings:
        if code != "":
            return step, code, code_type


def review_agent_model():
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a software code reviewer fluent in JavaScript and PostgreSQL building QueryAPI Indexers on NEAR Protocol. Your task is to 
                review incoming JavaScript and PostgreSQL code and only focus on whether the code has major issues or bugs and return a binary flag on whether to repeat. 
                If the code is not valid JavaScript or PostgreSQL provide feedback. Include specific code snippets or modification suggestions where possible

                For Javascript code, use standard JavaScript functions and no TypeScript. ensure the code uses modern practices (no var, proper scoping, etc.) 
                and handles asynchronous operations correctly. Check for common JavaScript errors like hoisting, incorrect use of 'this', and callback errors in asynchronous code.
                For PostgreSQL, ensure that the code is valid and follows the PostgreSQL syntax. Ensure that the code is consistent with the schema provided. 
                Point out any deviations or potential inefficiencies.

                When calling the tool tool_js_on_block_schema_func, because the data is highly nested, you will need to loop through actions and operations employing 
                Javascript functions. Do not use the function forEach, instead use map, flatMap, filter, find to extract and transform data. 
                You'll also need to decode base64 strings.

                Javascript Valid Exceptions:
                1. if the code is a mix of snake_case and camelCase at times because the code is mapping Javascript to PostgreSQL schema
                2. Assuming you don't need to define block and other subsequent actions based on the previous message context.
                3. Having a return statement outside of a function in JavaScript code.
                4. Decoding and parsing data as needed (e.g., base64 decoding) in the JavaScript code.
                5. Assume `block.actions()`,`block.receipts()`, and `block.header()` are valid.
                6. Its okay to include a `return block` call after the code as it is for code execution testing.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=code_review_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(CodeReviewResponse)
             )

    return model

class ReviewAgent:
    def __init__(self, model):
        # Initialize the ReviewAgent with a model for code review
        self.model = model

    def call_model(self, state):
        # Method to automatically review code based on the current state
        print("Reviewing code...")
        # Extract relevant information from the state
        messages = state.messages
        iterations = state.iterations
        extract_block_data_code = state.extract_block_data_code
        error = state.error
        block_schema = state.block_schema
        # Determine the current step, the code to review, and its type
        step, code, code_type = review_step(state)
        # Create a new message prompting for review of the code
        new_message = [HumanMessage(content=f"""Review this {code_type} code: {code}
            {error}""")]
        # Provide examples for guidance based on the review step
        if step == "Extract Block Data":
            # Example code for extracting block data
            example_benchmark_2 = get_example_extract_block_code().replace("\\n","\\\\n").replace("{","{{").replace("}","}}")
            new_message.append(HumanMessage(content=f"""Please use the following correctly working examples as
                guidline for reviewing JavaScript code:
                Example 2: {example_benchmark_2}
                """))
            error = "" # Reset error after providing examples
        elif step == "Indexer Logic":
            # Example code for indexer logic
            example_indexer = get_example_indexer_logic().replace("\\n","\\\\n").replace("{","{{").replace("}","}}")
            new_message.append(HumanMessage(content=f"""Please use the following correctly working examples as
                guidline for reviewing JavaScript code:
                Example: {example_indexer}
                """))
            error = "" # Reset error after providing examples
        # Update the messages with the new message
        messages = messages + new_message # testing out
        # Invoke the model with the updated messages for review
        response = self.model.invoke(messages)
        # Determine if the code review should continue based on the model's response
        should_continue = response.valid_code
        if should_continue != True:
            # If code is not valid, print a message and repeat the step
            print(f"Code is not valid. Repeating: {step}.")
        # Wrap the model's response in a system message
        wrapped_message = SystemMessage(content=str(response))

        # Return the updated state including the decision on whether to continue
        return {"messages": messages + [wrapped_message],"should_continue": should_continue, "extract_block_data_code":extract_block_data_code,"block_schema":block_schema, "error":error,"iterations":iterations}
    
    def human_review(self,state):
        # Method for manual human review of the code
        step, code, code_type = review_step(state)
        messages = state.messages
        block_schema = state.block_schema
        response = ""
        # Prompt for human review until a valid response ('yes' or 'no') is received
        if step == "Extract Block Data":
            # Print the block schema for reference during review
            print(f"Block Schema: {block_schema}")
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the {step}: {code}. Is it correct? (yes/no)")
            if response == "yes":
                # If the code is correct, continue without iterations
                return {"messages": messages, "should_continue":True, "iterations":0}
            elif response == "no":
                # If the code is incorrect, prompt for feedback and do not continue
                feedback = input(f"Please provide feedback on the {code_type} code: {code}")
                return {"messages": messages + [HumanMessage(content=feedback)], "should_continue":False, "iterations":0}