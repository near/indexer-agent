import sys
sys.path.append('..')
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langserve import add_routes
from dotenv import load_dotenv
from langchain_core.runnables import chain
from langchain_core.messages import HumanMessage
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
from graph.master_graph import create_graph_no_human_review
# workflow = create_graph() # INCLUDES HUMAN IN THE LOOP
workflow = create_graph_no_human_review()
compiled_graph = workflow.compile()


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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)