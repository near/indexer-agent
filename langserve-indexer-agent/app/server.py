import sys
sys.path.append('..')
from fastapi import FastAPI, Request, HTTPException, responses
from langserve import add_routes
from dotenv import load_dotenv
from langchain_core.runnables import chain, Runnable
from langchain_core.messages import HumanMessage, BaseMessage
from typing import List, Dict, Any, Optional, Sequence
from pydantic import BaseModel
import asyncio
import logging
import os

# Load .env file
load_dotenv('../.env',override=True)

# Set model variables
OPENAI_BASE_URL = "https://api.openai.com/v1"
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_ORGANIZATION"] = os.getenv("OPENAI_ORGANIZATION")

# Set environment variables
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# Create Langgraph
from graph.master_graph import create_graph_no_human_review,GraphState
def create_graph_with_defaults():
    defaults = {
        "block_heights":[],
        "entity_schema": "",
        "block_data_extraction_code":"",
        "table_creation_code":"",
        "data_upsertion_code": "",
        "indexer_entities_description":"",
        "iterations": 0,
        "error":"",
        "should_continue": False,
    }
    return create_graph_no_human_review(**defaults)

# workflow = create_graph() # INCLUDES HUMAN IN THE LOOP
workflow = create_graph_with_defaults()
compiled_graph = workflow.compile()

###### Code Only Section ######
# Define Input and Output Data Models
class InputData(BaseModel):
    original_prompt: str

class OutputData(BaseModel):
    ddl_code: str
    dml_code: str
    logs: List[str]

class CodeOnlyRunnable(Runnable):
    def __init__(self):
        self.logs=[]
    
    def log(self,message):
        self.logs.append(message)
        print(message)

    # def invoke(self, input_data: InputData)-> OutputData:
    def invoke(self, input_data: GraphState)-> OutputData:        
        self.logs = []
        self.log('Start')
        if isinstance(input_data, GraphState):
            state = input_data
        else:
            state = GraphState(**input_data)
        # state = GraphState(**input_data)
        self.log(f'Original prompt: {state.original_prompt}')
        workflow = create_graph_no_human_review()
        print('Starting workflow')
        result = workflow.compile().invoke(state)
        print('Compile and invoke workflow')
        output= {'ddl_code':result['data_upsertion_code'], 'dml_code':result['table_creation_code'], 'logs':self.logs}

        self.log("Fill in blank output")
        return {"output": output, "logs": self.logs}

code_only_runnable = CodeOnlyRunnable()

from typing import Callable, Any, AsyncGenerator
class RunnableLambda(Runnable):
    def __init__(self, func: Callable[..., Any]):
        self.func = func

    async def invoke(self, *args, **kwargs) -> AsyncGenerator:
        async for item in self.func(*args, **kwargs):
            yield item
### END OF CODE ONLY SECTION

# Setup App
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple api server using Langchain's Runnable interfaces",
)

add_routes(
    app,
    compiled_graph,
    # be_app, # testing purposes
    path="/indexer-agent",
)

# Route that simply runs the graph 
@app.post("/run")
async def root(request: Request):
    try:
        body = await request.json()
        print(body)
        input_data = body.get('input')
        print(input_data)
        output = code_only_runnable.invoke(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return output

# Route that does not stream data but prints out only the code at the end
async def code_only_runnable_adapter(input_data: GraphState):
    # Adapt the CodeOnlyRunnable.invoke method to work as an async generator
    code_only_runnable_instance = CodeOnlyRunnable()
    output = code_only_runnable_instance.invoke(input_data)
    yield output

add_routes(
    app,
    RunnableLambda(code_only_runnable_adapter),
    path='/code_only'
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)