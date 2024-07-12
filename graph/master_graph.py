# External Libraries
import json
import operator
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage,ToolMessage,SystemMessage
from langchain.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor,ToolInvocation

# Local Imports
from agents.BlockExtractorAgent import BlockExtractorAgent,block_extractor_agent_model_v3
from agents.TableCreationAgent import table_creation_code_model_v2,TableCreationAgent
from agents.DataUpsertionAgent import data_upsertion_code_model,DataUpsertionCodeAgent
from agents.IndexerEntitiesAgent import indexer_entities_agent_model,IndexerEntitiesAgent,EntityResponse
from agents.ReviewAgent import review_agent_model,ReviewAgent,review_step
from tools.database import tool_run_sql_ddl
from tools.NearLake import tool_get_block_heights
from tools.JavaScriptRunner import tool_js_on_block_schema_func,tool_infer_schema_of_js

# Define Graphstate
class GraphState(BaseModel):
    """
    Represents the state of our graph.

    Attributes:
        original_prompt: [Required] Original prompt of the beginning of the workflow
        block_limit: Limit on number of blocks to be parsed, default 10 blocks
        previous_day_limit: Limit on number of previous days to pull block from, default 5 days

        messages: With user questions, tracking plans, reasoning
        block_heights: Block heights of the blocks to be parsed
        block_data_extraction_code: Javascript code used to extract entity schema from blocks
        entity_schema: Extracted entity schema derived from parsing data from blocks
        table_creation_code: Data Definition Language code for creating tables
        data_upsertion_code: Data manipulation language code for inserting data using context.db
        iterations: Number of tries to generate the code
        indexer_entities_description: Description of entities the indexer is meant to track, including specific data and reasoning for each
        error: error message if any
        should_continue: Binary flag for control flow to indicate whether to continue or not
        code_iterations_limit: Number of iterations during automated code generation and review to prevent infinite recursion, default 3
        human_approval_flag: Yes/no flag for whether human reviewed code should continue
        human_feedback: If human approval is flagged as no, add in feedback
    """

    # Required to run
    original_prompt: str = Field(description = "Prompt of the beginning of the workflow")
    block_limit: int = Field(default=10,description="Limit on number of blocks to be parsed, default 10 blocks")
    previous_day_limit: int = Field(default=5,description="Limit on number of previous days to pull block from, default 5 days")

    # Optional
    messages: Optional[Sequence[BaseMessage]] = Field(default=[],description="List of messages that track history interacting with agents")
    block_heights: Optional[Sequence[int]] = Field(default=[],description="Block heights of the blocks to be parsed")
    entity_schema: Optional[str] = Field(default="",description="Extracted entity schema derived from parsing data from blocks")
    block_data_extraction_code: Optional[str] = Field(default="",description="Javascript code used to extract entity schema from blocks")
    table_creation_code: Optional[str] = Field(default="",description="Data definition language used to create tables in PostgreSQL")
    data_upsertion_code: Optional[str] = Field(default="",description="Data manipulation language in Javascript used to insert data into tables using context.db")
    indexer_entities_description: Optional[str] = Field(default="",description="Description of entities the indexer is meant to track, including specific data and reasoning for each")
    iterations: Optional[int] = Field(default=0,description="Number of tries to generate the code")
    error: Optional[str] = Field(default="",description="Error message if any returned after attempting to execute code")
    should_continue: Optional[bool] = Field(default=False,description="Boolean used to decide whether or not to continue to next step")
    code_iterations_limit: Optional[int] = Field(default=3,description="Number of iterations during automated code generation and review to prevent infinite recursion, default 3")
    human_approval_flag: Optional[str] = Field(default="",description="Yes/no flag for whether human reviewed code should continue")
    human_feedback: Optional[str] = Field(default="",description="If human approval is flagged as no, add in feedback")


# Load agents & tools
# Block Extractor Agent
block_extractor_tools = [tool_js_on_block_schema_func, tool_infer_schema_of_js]
block_extractor_model = block_extractor_agent_model_v3(block_extractor_tools) # v2 adds the jsresponse parser to prompt
block_extractor_agent = BlockExtractorAgent(block_extractor_model,ToolExecutor(block_extractor_tools))

# Indexer Entities Agent
indexer_entities_model = indexer_entities_agent_model()
indexer_entities_agent = IndexerEntitiesAgent(indexer_entities_model)

# Table Creation Agent
table_creation_tools = [tool_run_sql_ddl]
table_creation_code_agent_model = table_creation_code_model_v2(table_creation_tools)
table_creation_code_agent = TableCreationAgent(table_creation_code_agent_model,ToolExecutor(table_creation_tools))

# DataUpsertion Agent
data_upsertion_code_agent_model = data_upsertion_code_model() #v2 no documentation
data_upsertion_code_agent = DataUpsertionCodeAgent(data_upsertion_code_agent_model)

# Review Agent
review_agent_model = review_agent_model()
review_agent = ReviewAgent(review_agent_model)

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

def should_review(state):
    should_continue = state.should_continue
    # If block schema is no longer null we review schema
    if should_continue == True:
        return "continue"
    else:
        return "repeat"
    
def code_review_router(state, max_iter=3):
    # Determines the next step based on code review status and iteration count
    should_continue = state.should_continue
    max_iter = state.code_iterations_limit
    iterations = state.iterations
    step, _, _ = review_step(state)
    # If review is positive, continue the workflow
    if should_continue:
        print(f"Completed {step}")
        return f"Completed {step}"
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
    max_iter = state.code_iterations_limit
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
    workflow.add_node("tools_for_table_creation", table_creation_code_agent.call_tool)

    # Review Nodes - nodes for reviewing the code automatically and manually (human review)
    workflow.add_node("review_agent", review_agent.call_model)
    workflow.add_node("human_review", review_agent.human_review)

    # Add Edges - defines the flow between different nodes based on the task completion
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("table_creation_code_agent", "tools_for_table_creation")
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
        "tools_for_table_creation",
        should_review,
        {
            "continue": "review_agent",
            "repeat": "table_creation_code_agent",
        }   
    )

    workflow.add_conditional_edges(
        "review_agent",
        code_review_router,
        {
            "Completed Extract Block Data": "human_review",
            "Completed Indexer Entities": "human_review",
            "Completed Table Creation": "human_review",
            "Completed Data Upsertion": "human_review",
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

# Create a version without human review for langserve
def create_graph_no_human_review(**kwargs):
    # Initializes the workflow graph with various agents and review steps
    workflow = StateGraph(GraphState)

    # Agent Nodes - these nodes represent different agents handling specific tasks
    workflow.add_node("extract_block_data_agent", block_extractor_agent.call_model)
    workflow.add_node("indexer_entities_agent", indexer_entities_agent.call_model)
    workflow.add_node("table_creation_code_agent", table_creation_code_agent.call_model)
    workflow.add_node("data_upsertion_code_agent", data_upsertion_code_agent.call_model)

    # Tool Nodes - nodes for calling specific tools during the block data extraction process
    workflow.add_node("tools_for_block_data_extraction", block_extractor_agent.call_tool)
    workflow.add_node("tools_for_table_creation", table_creation_code_agent.call_tool)

    # Review Nodes - nodes for reviewing the code automatically and manually (human review)
    workflow.add_node("review_agent", review_agent.call_model)

    # Print Final End State
    workflow.add_node("clear_messages", lambda state: setattr(state, 'messages', []))
    workflow.add_node("print_final", lambda state: (print(f"""Table Creation Code:
        {state.table_creation_code}
        Data Upsertion Code: 
        {state.data_upsertion_code}""")))

    # Add Edges - defines the flow between different nodes based on the task completion
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("table_creation_code_agent", "tools_for_table_creation")
    workflow.add_edge("data_upsertion_code_agent", "review_agent")
    workflow.add_edge("indexer_entities_agent", "table_creation_code_agent")
    workflow.add_edge("clear_messages", "print_final")
    workflow.add_edge("print_final", END)

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
        "tools_for_table_creation",
        should_review,
        {
            "continue": "review_agent",
            "repeat": "table_creation_code_agent",
        }   
    )

    workflow.add_conditional_edges(
        "review_agent",
        code_review_router,
        {
            "Completed Extract Block Data": "indexer_entities_agent",
            "Completed Table Creation": "data_upsertion_code_agent",
            "Completed Data Upsertion": "clear_messages",
            "Repeat Extract Block Data": "extract_block_data_agent",
            "Repeat Indexer Entities": "indexer_entities_agent",
            "Repeat Table Creation": "table_creation_code_agent",
            "Repeat Data Upsertion": "data_upsertion_code_agent",
            "end": END,
        }   
    )

    return workflow