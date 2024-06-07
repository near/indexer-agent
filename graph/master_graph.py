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
from agents.TableCreationAgent import table_creation_code_model_v2,TableCreationAgent
from agents.DataUpsertionAgent import data_upsertion_code_model,DataUpsertionCodeAgent
from agents.IndexerLogicAgent import indexer_logic_agent_model,IndexerLogicAgent
from agents.ReviewAgent import review_agent_model,ReviewAgent,review_step
from tools.NearLake import tool_get_block_heights
from tools.JavaScriptRunner import tool_js_on_block_schema_func,tool_infer_schema_of_js

# Define Graphstate
class GraphState(BaseModel):
    """
    Represents the state of our graph.

    Attributes:
        messages: With user questions, tracking plans, reasoning
        block_heights: Block heights of the blocks to be parsed
        extract_block_data_code: Javascript code to be run on block schema
        block_schema: Extracted block schema from json of blocks 
        table_creation_code: Data Definition Language code for creating tables
        data_upsertion_code: Data manipulation language code for inserting data using context.db
        iterations: Number of tries to generate the code
        error: error message if any
        should_continue: Binary flag for control flow to indicate whether to continue or not
    """

    messages: Sequence[BaseMessage] = Field(description="List of messages that track history interacting with agents")
    block_heights: Sequence[int] = Field(description="Block heights of the blocks to be parsed")
    block_schema: str = Field(description="Extracted block schema from blocks")
    extract_block_data_code: str = Field(description="Javascript code used to extract block schema from blocks")
    table_creation_code: str = Field(description="Data definition language used to create tables in PostgreSQL")
    data_upsertion_code: str = Field(description="Data manipulation language in Javascript used to insert data into tables using context.db")
    indexer_logic: str = Field(description="Final Javascript code used to load data into postgresql database from the blockchain")
    iterations: int = Field(description="Number of tries to generate the code")
    error: str = Field(description="Error message if any returned after attempting to execute code")
    should_continue: bool = Field(description="Boolean used to decide whether or not to continue to next step")


# Load agents & tools
# Block Extractor Agent
block_extractor_tools = [tool_js_on_block_schema_func, tool_infer_schema_of_js]
block_extractor_model = block_extractor_agent_model_v2(block_extractor_tools) # v2 adds the jsresponse parser to prompt
block_extractor_agent = BlockExtractorAgent(block_extractor_model,ToolExecutor(block_extractor_tools))

# TableCreation Agent
table_creation_code_agent_model = table_creation_code_model_v2()
table_creation_code_agent = TableCreationAgent(table_creation_code_agent_model)

# DataUpsertion Agent
data_upsertion_code_agent_model = data_upsertion_code_model() #v2 no documentation
data_upsertion_code_agent = DataUpsertionCodeAgent(data_upsertion_code_agent_model)

# Review Agent
review_agent_model = review_agent_model()
review_agent = ReviewAgent(review_agent_model)

# Indexer Logic Agent
indexer_logic_agent_model = indexer_logic_agent_model()
indexer_logic_agent = IndexerLogicAgent(indexer_logic_agent_model)

# Define Logical Flow Functions

def block_extractor_agent_router(state):
    # Check if the block schema has been successfully extracted
    block_schema = state.block_schema
    # If block schema is available, proceed to the next step
    if block_schema != "":
        return "continue"
    else:
        # If block schema is not available, repeat the extraction process
        return "repeat"
    
def code_review_router(state, max_iter=3):
    # Determines the next step based on code review status and iteration count
    should_continue = state.should_continue
    iterations = state.iterations
    step, _, _ = review_step(state)
    # If review is positive, continue the workflow
    if should_continue:
        return "continue"
    elif iterations > max_iter:
        # Limit the number of iterations to avoid infinite loops
        print("Completed 3 Iterations: Exiting to avoid infinite looping.")
        return "end"
    else:
        # If review is negative and iteration limit not reached, repeat the step
        return f"Repeat {step}"
    
def human_review_router(state, max_iter=3):
    # Manages the flow after human review, checking for approval and iteration count
    iterations = state.iterations
    should_continue = state.should_continue
    step, _, _ = review_step(state)
    # If human review is approved, proceed
    if should_continue == True:
        return f"Completed {step}"
    elif iterations > max_iter:
        # End the process if maximum iterations are reached
        return "end"
    else:
        # If not approved and max iterations not reached, repeat the step
        return f"Repeat {step}"

# Define Graph

def create_graph():
    # Initializes the workflow graph with various agents and review steps
    workflow = StateGraph(GraphState)

    # Agent Nodes - these nodes represent different agents handling specific tasks
    workflow.add_node("extract_block_data_agent", block_extractor_agent.call_model)
    workflow.add_node("table_creation_code_agent", table_creation_code_agent.call_model)
    workflow.add_node("data_upsertion_code_agent", data_upsertion_code_agent.call_model)
    workflow.add_node("indexer_logic_agent", indexer_logic_agent.call_model)

    # Tool Nodes - nodes for calling specific tools during the block data extraction process
    workflow.add_node("tools_for_block_data_extraction", block_extractor_agent.call_tool)

    # Review Nodes - nodes for reviewing the code automatically and manually (human review)
    workflow.add_node("review_agent", review_agent.call_model)
    workflow.add_node("human_review", review_agent.human_review)

    # Add Edges - defines the flow between different nodes based on the task completion
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("table_creation_code_agent", "review_agent")
    workflow.add_edge("data_upsertion_code_agent", "review_agent")
    workflow.add_edge("indexer_logic_agent", "review_agent")

    # Conditional Edges - these edges define the flow based on conditions evaluated at runtime
    workflow.add_conditional_edges(
        "tools_for_block_data_extraction",
        block_extractor_agent_router,
        {
            "continue": "review_agent",
            "repeat": "extract_block_data_agent",
        }   
    )

    workflow.add_conditional_edges(
        "review_agent",
        code_review_router,
        {
            "continue": "human_review",
            "Repeat Extract Block Data": "extract_block_data_agent",
            "Repeat Table Creation": "table_creation_code_agent",
            "Repeat Data Upsertion": "data_upsertion_code_agent",
            "Repeat Indexer Logic": "indexer_logic_agent",
            "end": END,
        }   
    )

    workflow.add_conditional_edges(
        "human_review",
        human_review_router,
        {
            "Completed Extract Block Data": "table_creation_code_agent",
            "Completed Table Creation": "data_upsertion_code_agent",
            "Completed Data Upsertion": "indexer_logic_agent",
            "Completed Indexer Logic": END,
            "Repeat Extract Block Data": "extract_block_data_agent",
            "Repeat Table Creation": "table_creation_code_agent",
            "Repeat Data Upsertion": "data_upsertion_code_agent",
            "Repeat Indexer Logic": "indexer_logic_agent",
            "end": END,
        }   
    )

    return workflow