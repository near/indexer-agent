# External Libraries
import json
import operator
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage,ToolMessage
from langchain.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor,ToolInvocation

# Local Imports
from agents.BlockExtractorAgent import BlockExtractorAgent,block_extractor_agent_model_v3
from agents.TableCreationAgent import table_creation_code_model_v2,TableCreationAgent
from agents.DataUpsertionAgent import data_upsertion_code_model,DataUpsertionCodeAgent
from agents.IndexerEntitiesAgent import indexer_entities_agent_model,IndexerEntitiesAgent,EntityResponse
from agents.ReviewAgent import review_agent_model,ReviewAgent,review_step
from tools.NearLake import tool_get_block_heights
from tools.JavaScriptRunner import tool_js_on_block_schema_func,tool_infer_schema_of_js

# Define Graphstate
class GraphState(BaseModel):
    """
    Represents the state of our graph.

    Attributes:
        messages: With user questions, tracking plans, reasoning
        original_prompt: Original prompt of the beginning of the workflow
        block_heights: Block heights of the blocks to be parsed
        block_data_extraction_code: Javascript code used to extract entity schema from blocks
        entity_schema: Extracted entity schema derived from parsing data from blocks
        table_creation_code: Data Definition Language code for creating tables
        data_upsertion_code: Data manipulation language code for inserting data using context.db
        iterations: Number of tries to generate the code
        indexer_entities_description: Description of entities the indexer is meant to track, including specific data and reasoning for each
        error: error message if any
        should_continue: Binary flag for control flow to indicate whether to continue or not
    """

    messages: Sequence[BaseMessage] = Field(description="List of messages that track history interacting with agents")
    original_prompt: str = Field(description = "Prompt of the beginning of the workflow")
    block_heights: Sequence[int] = Field(description="Block heights of the blocks to be parsed")
    entity_schema: str = Field(description="Extracted entity schema derived from parsing data from blocks")
    block_data_extraction_code: str = Field(description="Javascript code used to extract entity schema from blocks")
    table_creation_code: str = Field(description="Data definition language used to create tables in PostgreSQL")
    data_upsertion_code: str = Field(description="Data manipulation language in Javascript used to insert data into tables using context.db")
    indexer_entities_description: str = Field(description="Description of entities the indexer is meant to track, including specific data and reasoning for each")
    iterations: int = Field(description="Number of tries to generate the code")
    error: str = Field(description="Error message if any returned after attempting to execute code")
    should_continue: bool = Field(description="Boolean used to decide whether or not to continue to next step")


# Load agents & tools
# Block Extractor Agent
block_extractor_tools = [tool_js_on_block_schema_func, tool_infer_schema_of_js]
block_extractor_model = block_extractor_agent_model_v3(block_extractor_tools) # v2 adds the jsresponse parser to prompt
block_extractor_agent = BlockExtractorAgent(block_extractor_model,ToolExecutor(block_extractor_tools))

# Indexer Entities Agent
indexer_entities_model = indexer_entities_agent_model()
indexer_entities_agent = IndexerEntitiesAgent(indexer_entities_model)

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
# indexer_logic_agent_model = indexer_logic_agent_model()
# indexer_logic_agent = IndexerEntitiesAgent(indexer_logic_agent_model)

# Define Logical Flow Functions

def block_extractor_agent_router(state):
    # Check if the entity schema has been successfully extracted
    entity_schema = state.entity_schema
    # If entity schema is available, proceed to the next step
    if entity_schema != "":
        return "continue"
    else:
        # If entity schema is not available, repeat the extraction process
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
    workflow.add_node("indexer_entities_agent", indexer_entities_agent.call_model)
    workflow.add_node("table_creation_code_agent", table_creation_code_agent.call_model)
    workflow.add_node("data_upsertion_code_agent", data_upsertion_code_agent.call_model)

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
    workflow.add_edge("indexer_entities_agent", "human_review") # Because indexer entities is just a string, does not need to code review

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
            "Repeat Indexer Entities": "indexer_entities_agent",
            "Repeat Table Creation": "table_creation_code_agent",
            "Repeat Data Upsertion": "data_upsertion_code_agent",
            "end": END,
        }   
    )

    workflow.add_conditional_edges(
        "human_review",
        human_review_router,
        {
            "Completed Extract Block Data": "indexer_entities_agent",
            "Completed Indexer Entities": "table_creation_code_agent",
            "Completed Table Creation": "data_upsertion_code_agent",
            "Completed Data Upsertion": END,
            "Repeat Extract Block Data": "extract_block_data_agent",
            "Repeat Indexer Entities": "indexer_entities_agent",
            "Repeat Table Creation": "table_creation_code_agent",
            "Repeat Data Upsertion": "data_upsertion_code_agent",
            "end": END,
        }   
    )

    return workflow