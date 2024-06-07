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
from agents.BlockExtractorAgent import hardcoded_js


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

# Hardcoded answer


def review_agent_model():
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''You are a software code reviewer fluent in JavaScript and PostgreSQL building QueryAPI Indexers on NEAR Protocol. Your task is to 
                review incoming JavaScript and PostgreSQL code and only focus on whether the code has major issues or bugs and return a binary flag on whether to repeat. 
                If the code is not valid JavaScript or PostgreSQL provide feedback on how to improve the code.

                When viewing Javascript code, use standard JavaScript functions and no TypeScript. Ensure variable names are consistent across the code, 
                When viewing PostgreSQL code, ensure that the code is valid and follows the PostgreSQL syntax. Ensure that the code is consistent with the schema provided.

                Javascript Valid Exceptions:
                1. if the code is a mix of snake_case and camelCase at times because the code is mapping Javascript to PostgreSQL schema
                2. Assuming you don't need to define block and other subsequent actions based on the previous message context.
                3. Having a return statement outside of a function in JavaScript code.
                4. Decoding and parsing data as needed (e.g., base64 decoding) in the JavaScript code.
                ''',
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=code_review_response_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True,)

    model = ({"messages": RunnablePassthrough()}
             | prompt
             | llm.with_structured_output(CodeReviewResponse)
             )

    return model

class ReviewAgent:
    def __init__(self, model):
        self.model = model

    def call_model(self, state):
        print("Reviewing code...")
        messages = state.messages
        extract_block_data_code = state.extract_block_data_code
        block_schema = state.block_schema
        step, code, code_type = review_step(state)
        new_message = [HumanMessage(content=f"""Review this {code_type} code: {code}""")]
        response = self.model.invoke(new_message)
        should_continue = response.valid_code
        if step == "Extract Block Data":  # HARDCODE THE ANSWER FOR NOW FOR FIRST STEP
            print("HARDCODING ANSWER FOR EXTRACT BLOCK DATA")
            extract_block_data_code = str(hardcoded_js())
            code = extract_block_data_code
            block_schema = json.dumps(run_js_on_block(119688212, hardcoded_js()))
            should_continue=True
        wrapped_message = SystemMessage(content=str(response))

        return {"messages": messages + [wrapped_message],"should_continue": should_continue, "extract_block_data_code":extract_block_data_code,"block_schema":block_schema}
    
    def human_review(self,state):
        step, code, code_type = review_step(state)
        messages = state.messages
        response = ""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the {step}: {code}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages, "should_continue":True, "iterations":0}
            elif response == "no":
                feedback = input(f"Please provide feedback on the {code_type} code: {code}")
                if step == "Extract Block Data":  # HARDCODE THE ANSWER FOR NOW FOR FIRST STEP
                    print("Giving feedback to hardcode answer for Extract Block Data")
                    feedback = f"Use EXACTLY this Javascript to run tool_js_on_block_schema_func: {hardcoded_js()}"
                return {"messages": messages + [HumanMessage(content=feedback)], "should_continue":False, "iterations":0}