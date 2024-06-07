# External Libraries
import json
import operator
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage,ToolMessage
from langchain.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor,ToolInvocation

# Local Imports
from agents.BlockExtractorAgent import BlockExtractorAgent,block_extractor_agent_model_v2
from agents.DDLAgent import ddl_code_model_v2,DDLCodeAgent
from agents.DMLAgent import dml_code_model,dml_code_model_v2,DMLCodeAgent
from agents.IndexerLogicAgent import indexer_logic_agent_model,IndexerLogicAgent
from tools.NearLake import tool_get_block_heights
from tools.JavaScriptRunner import tool_js_on_block_schema_func,tool_infer_schema_of_js

# Define Graphstate
class GraphState(BaseModel):
    """
    Represents the state of our graph.

    Attributes:
        messages: With user questions, tracking plans, reasoning
        block_heights: Block heights of the blocks to be parsed
        js_code: Javascript code to be run on block schema
        block_schema: Extracted block schema from json of blocks 
        ddl_code: Data Definition Language code for creating tables
        dml_code: Data manipulation language code for inserting data using context.db
        iterations: Number of tries to generate the code
        error: error message if any
        should_continue: Binary flag for control flow to indicate whether to continue or not
    """

    messages: Sequence[BaseMessage] = Field(description="List of messages that track history interacting with agents")
    block_heights: Sequence[int] = Field(description="Block heights of the blocks to be parsed")
    block_schema: str = Field(description="Extracted block schema from blocks")
    js_code: str = Field(description="Javascript code used to extract block schema from blocks")
    ddl_code: str = Field(description="Data definition language used to create tables in PostgreSQL")
    dml_code: str = Field(description="Data manipulation language in Javascript used to insert data into tables using context.db")
    indexer_logic: str = Field(description="Final Javascript code used to load data into postgresql database from the blockchain")
    iterations: int = Field(description="Number of tries to generate the code")
    error: str = Field(description="Error message if any returned after attempting to execute code")
    should_continue: bool = Field(description="Boolean used to decide whether or not to continue to next step")


# Load agents & tools
# Block Extractor Agent
block_extractor_tools = [tool_js_on_block_schema_func, tool_infer_schema_of_js]
block_extractor_model = block_extractor_agent_model_v2(block_extractor_tools) # v2 adds the jsresponse parser to prompt
block_extractor_agent = BlockExtractorAgent(block_extractor_model,ToolExecutor(block_extractor_tools))

# DDL Agent
ddl_tools= []
ddl_code_agent_model = ddl_code_model_v2(ddl_tools)
ddl_code_agent = DDLCodeAgent(ddl_code_agent_model,ToolExecutor(ddl_tools))

# DML Agent
dml_tools = []
# dml_code_agent_model = dml_code_model(dml_tools)  # uses documentation
dml_code_agent_model = dml_code_model_v2(dml_tools) #v2 no documentation
dml_code_agent = DMLCodeAgent(dml_code_agent_model,ToolExecutor(dml_tools))

# Indexer Logic Agent
indexer_logic_agent_model = indexer_logic_agent_model()
indexer_logic_agent = IndexerLogicAgent(indexer_logic_agent_model)

# Define Logical Flow Functions
def agent_tool_router(state,max_iter=3):
    # Checks whether additional tools to call or continue
    last_message = state.messages[-1]
    iterations = state.iterations
    if hasattr(last_message, 'additional_kwargs'):
        if "tool_calls" in last_message.additional_kwargs:
            return "tool_calls"
        else:
            return "continue"
    elif iterations > max_iter:
        return "end"
    else:
        return "continue"

def human_review_router(state,max_iter=3):
    # After human has reviewed, checks whether has been approved
    iterations = state.iterations
    should_continue = state.should_continue
    if should_continue==True:
        return "continue"
    elif iterations > max_iter:
        return "end"
    else:
        return "repeat"

def check_code_generation_router(state):
    # Check to see if we have code, otherwise repeat generation step
    block_schema = state.block_schema
    ddl_code = state.ddl_code
    dml_code = state.dml_code
    if block_schema != "":
        return "review"
    elif ddl_code != "":
        return "review"
    elif dml_code != "":
        return "review"
    else:
        return "repeat"

# Define Graph

def create_graph():
    workflow = StateGraph(GraphState)

    # Agent Nodes
    workflow.add_node("extract_block_data_agent", block_extractor_agent.call_model)
    workflow.add_node("ddl_code_agent", ddl_code_agent.call_model)
    workflow.add_node("dml_code_agent", dml_code_agent.call_model)
    workflow.add_node("indexer_logic_agent", indexer_logic_agent.call_model) 

    # Tool Nodes
    workflow.add_node("tools_for_block_data_extraction",block_extractor_agent.call_tool)
    # workflow.add_node("tools_for_ddl_code_generation",ddl_code_agent.call_tool)
    # workflow.add_node("tools_for_dml_code_generation",dml_code_agent.call_tool)

    # Review Nodes
    workflow.add_node("review_extracted_block_data",block_extractor_agent.human_review)
    workflow.add_node("review_ddl_code",ddl_code_agent.human_review)
    workflow.add_node("review_dml_code",dml_code_agent.human_review)

    # Add Edges
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("dml_code_agent", "review_dml_code")
    workflow.add_edge("indexer_logic_agent", END)

    # Conditional Edges
    workflow.add_conditional_edges(
        "tools_for_block_data_extraction",
        check_code_generation_router,
        {
            "repeat":"extract_block_data_agent",
            "review": "review_extracted_block_data",
        }   
    )

    workflow.add_conditional_edges(
        "review_extracted_block_data",
        human_review_router,
        {
            "continue": "ddl_code_agent",
            "repeat": "extract_block_data_agent",
            "end": END,
        }   
    )
    workflow.add_conditional_edges(
        "ddl_code_agent",
        check_code_generation_router,
        {
            "review":"review_ddl_code",
            "repeat": "ddl_code_agent",
        }   
    )
    workflow.add_conditional_edges(
        "review_ddl_code",
        human_review_router,
        {
            "continue": "dml_code_agent",
            "repeat": "ddl_code_agent",
            "end": END,
        }   
    )
    workflow.add_conditional_edges(
        "review_dml_code",
        human_review_router,
        {
            "continue": "indexer_logic_agent",
            "repeat": "dml_code_agent",
            "end": END,
        }
    )

    return workflow