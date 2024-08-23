import json
import operator
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain.pydantic_v1 import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor, ToolInvocation
from agents.BlockExtractorAgent import BlockExtractorAgent, block_extractor_agent_model
from agents.TableCreationAgent import table_creation_code_model, TableCreationAgent
from agents.DataUpsertionAgent import data_upsertion_code_model, DataUpsertionCodeAgent
from agents.IndexerEntitiesAgent import (
    indexer_entities_agent_model,
    IndexerEntitiesAgent,
    EntityResponse,
)
from agents.ReviewAgent import review_agent_model, ReviewAgent, review_step
from tools.database import tool_run_sql_ddl
from tools.NearLake import tool_get_block_heights
from tools.JavaScriptRunner import tool_js_on_block_schema_func, tool_infer_schema_of_js


class GraphState(BaseModel):
    """
    Represents the state of the workflow graph used to manage the code generation process.

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

    # Required Fields
    original_prompt: str = Field(description="Prompt of the beginning of the workflow")
    block_limit: int = Field(
        default=10,
        description="Limit on number of blocks to be parsed, default 10 blocks",
    )
    previous_day_limit: int = Field(
        default=5,
        description="Limit on number of previous days to pull block from, default 5 days",
    )

    # Optional Fields
    messages: Optional[Sequence[BaseMessage]] = Field(
        default=[],
        description="List of messages that track history interacting with agents",
    )
    block_heights: Optional[Sequence[int]] = Field(
        default=[], description="Block heights of the blocks to be parsed"
    )
    entity_schema: Optional[str] = Field(
        default="",
        description="Extracted entity schema derived from parsing data from blocks",
    )
    block_data_extraction_code: Optional[str] = Field(
        default="",
        description="Javascript code used to extract entity schema from blocks",
    )
    table_creation_code: Optional[str] = Field(
        default="",
        description="Data definition language used to create tables in PostgreSQL",
    )
    data_upsertion_code: Optional[str] = Field(
        default="",
        description="Data manipulation language in Javascript used to insert data into tables using context.db",
    )
    indexer_entities_description: Optional[str] = Field(
        default="",
        description="Description of entities the indexer is meant to track, including specific data and reasoning for each",
    )
    iterations: Optional[int] = Field(
        default=0, description="Number of tries to generate the code"
    )
    error: Optional[str] = Field(
        default="",
        description="Error message if any returned after attempting to execute code",
    )
    should_continue: Optional[bool] = Field(
        default=False,
        description="Boolean used to decide whether or not to continue to next step",
    )
    code_iterations_limit: Optional[int] = Field(
        default=3,
        description="Number of iterations during automated code generation and review to prevent infinite recursion, default 3",
    )
    human_approval_flag: Optional[str] = Field(
        default="",
        description="Yes/no flag for whether human reviewed code should continue",
    )
    human_feedback: Optional[str] = Field(
        default="", description="If human approval is flagged as no, add in feedback"
    )


# Load Agents & Tools
block_extractor_tools = [
    tool_js_on_block_schema_func,
    tool_infer_schema_of_js,
    tool_get_block_heights,
]
block_extractor_model = block_extractor_agent_model(block_extractor_tools)
block_extractor_agent = BlockExtractorAgent(
    block_extractor_model, ToolExecutor(block_extractor_tools)
)
indexer_entities_model = indexer_entities_agent_model()
indexer_entities_agent = IndexerEntitiesAgent(indexer_entities_model)
table_creation_tools = [tool_run_sql_ddl]
table_creation_code_agent_model = table_creation_code_model(table_creation_tools)
table_creation_code_agent = TableCreationAgent(
    table_creation_code_agent_model, ToolExecutor(table_creation_tools)
)
data_upsertion_code_agent_model = data_upsertion_code_model()  # v2 no documentation
data_upsertion_code_agent = DataUpsertionCodeAgent(data_upsertion_code_agent_model)
review_agent_model = review_agent_model()
review_agent = ReviewAgent(review_agent_model)


def block_extractor_agent_router(state):
    """
    Routes the workflow depending on whether the entity schema has been successfully extracted.

    Args:
        state (GraphState): The current state of the workflow.

    Returns:
        str: A string indicating whether to continue to the next step or repeat the extraction process.
    """
    entity_schema = state.entity_schema
    if entity_schema != "":
        return "continue"
    else:
        return "repeat"


def should_review(state):
    """
    Decides whether the workflow should proceed to the review step based on the value of the should_continue flag.

    Args:
        state (GraphState): The current state of the workflow.

    Returns:
        str: A string indicating whether to continue to the review step or repeat the previous step.
    """
    should_continue = state.should_continue
    if should_continue == True:
        return "continue"
    else:
        return "repeat"


def code_review_router(state, max_iter=3):
    """
    Routes the workflow after code review based on the review results and the number of iterations.

    Args:
        state (GraphState): The current state of the workflow.
        max_iter (int): The maximum number of iterations allowed to avoid infinite looping, default is 3.

    Returns:
        str: A string indicating whether to continue, repeat a step, or end the process after code review.
    """
    should_continue = state.should_continue
    max_iter = state.code_iterations_limit
    iterations = state.iterations
    step, _, _ = review_step(state)
    if should_continue:
        print(f"Completed {step}")
        return f"Completed {step}"
    elif iterations > max_iter + 1:
        print("Completed 3 Iterations: Exiting to avoid infinite looping.")
        return "end"
    else:
        return f"Repeat {step}"


def human_review_router(state, max_iter=3):
    """
    Routes the workflow after human review based on the approval flag and the number of iterations.

    Args:
        state (GraphState): The current state of the workflow.
        max_iter (int): The maximum number of iterations allowed to avoid infinite looping, default is 3.

    Returns:
        str: A string indicating whether to continue, repeat a step, or end the process after human review.
    """
    iterations = state.iterations
    should_continue = state.should_continue
    max_iter = state.code_iterations_limit
    step, _, _ = review_step(state)
    if should_continue == True:
        return f"Completed {step}"
    elif iterations > max_iter + 1:
        return "end"
    else:
        return f"Repeat {step}"


# Define Graph
def create_graph():
    """
    Initializes the workflow graph for automated code generation and review.

    The graph includes nodes for various agents (block extraction, entity identification, table creation, and data upsertion),
    tool nodes for executing tasks, and review nodes for automated and manual (human) review.

    Returns:
        StateGraph: The initialized workflow graph.
    """
    workflow = StateGraph(GraphState)

    # Nodes
    workflow.add_node("extract_block_data_agent", block_extractor_agent.call_model)
    workflow.add_node("indexer_entities_agent", indexer_entities_agent.call_model)
    workflow.add_node("table_creation_code_agent", table_creation_code_agent.call_model)
    workflow.add_node("data_upsertion_code_agent", data_upsertion_code_agent.call_model)
    workflow.add_node(
        "tools_for_block_data_extraction", block_extractor_agent.call_tool
    )
    workflow.add_node("tools_for_table_creation", table_creation_code_agent.call_tool)
    workflow.add_node("review_agent", review_agent.call_model)
    workflow.add_node("human_review", review_agent.human_review)

    # Edges
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("table_creation_code_agent", "tools_for_table_creation")
    workflow.add_edge("data_upsertion_code_agent", "review_agent")
    workflow.add_edge("indexer_entities_agent", "human_review")
    workflow.add_conditional_edges(
        "tools_for_block_data_extraction",
        block_extractor_agent_router,
        {
            "continue": "review_agent",
            "repeat": "extract_block_data_agent",
        },
    )

    workflow.add_conditional_edges(
        "tools_for_table_creation",
        should_review,
        {
            "continue": "review_agent",
            "repeat": "table_creation_code_agent",
        },
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
        },
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
        },
    )

    return workflow


def create_graph_no_human_review(**kwargs):
    """
    Initializes the workflow graph for automated code generation and review without human intervention.

    The graph includes nodes for various agents (block extraction, entity identification, table creation, and data upsertion),
    tool nodes for executing tasks, and review nodes for automated code review. Human review is omitted. Used for langserve.

    Returns:
        StateGraph: The initialized workflow graph without human review.
    """
    workflow = StateGraph(GraphState)

    # Nodes
    workflow.add_node("extract_block_data_agent", block_extractor_agent.call_model)
    workflow.add_node("indexer_entities_agent", indexer_entities_agent.call_model)
    workflow.add_node("table_creation_code_agent", table_creation_code_agent.call_model)
    workflow.add_node("data_upsertion_code_agent", data_upsertion_code_agent.call_model)
    workflow.add_node(
        "tools_for_block_data_extraction", block_extractor_agent.call_tool
    )
    workflow.add_node("tools_for_table_creation", table_creation_code_agent.call_tool)
    workflow.add_node("review_agent", review_agent.call_model)
    workflow.add_node("clear_messages", lambda state: setattr(state, "messages", []))
    workflow.add_node(
        "print_final",
        lambda state: (
            print(
                f"""Table Creation Code:
        {state.table_creation_code}
        Data Upsertion Code: 
        {state.data_upsertion_code}"""
            )
        ),
    )

    # Edges
    workflow.set_entry_point("extract_block_data_agent")
    workflow.add_edge("extract_block_data_agent", "tools_for_block_data_extraction")
    workflow.add_edge("table_creation_code_agent", "tools_for_table_creation")
    workflow.add_edge("data_upsertion_code_agent", "review_agent")
    workflow.add_edge("indexer_entities_agent", "table_creation_code_agent")
    workflow.add_edge("clear_messages", "print_final")
    workflow.add_edge("print_final", END)
    workflow.add_conditional_edges(
        "tools_for_block_data_extraction",
        block_extractor_agent_router,
        {
            "continue": "review_agent",
            "repeat": "extract_block_data_agent",
        },
    )

    workflow.add_conditional_edges(
        "tools_for_table_creation",
        should_review,
        {
            "continue": "review_agent",
            "repeat": "table_creation_code_agent",
        },
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
        },
    )

    return workflow
