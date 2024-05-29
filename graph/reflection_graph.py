from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor, ToolInvocation
import json
from langchain_core.messages import ToolMessage
from typing import Dict, TypedDict, List


class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        error : Binary flag for control flow to indicate whether test error was tripped
        messages : With user question, error messages, reasoning
        generation : Code solution
        iterations : Number of tries
    """
    error: str
    messages: List
    generation: str
    iterations: int


class ReflectionGraphBuilder(object):
    def __init__(self, model, tool_executor: ToolExecutor, max_iterations: int, flag: str):
        self.model = model
        self.tool_executor = tool_executor

    def generate(self, state: GraphState):
        """
        Generate a code solution

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation
        """

        print("---GENERATING CODE SOLUTION---")

        # State
        messages = state["messages"]
        iterations = state["iterations"]
        error = state["error"]

        # We have been routed back to generation with an error
        if error == "yes":
            messages += [
                (
                    "user",
                    "Now, try again. Invoke the code tool to structure the output with a prefix, imports, and code block:",
                )
            ]

        # Solution
        code_solution = code_gen_chain.invoke(
            {"context": concatenated_content, "messages": messages}
        )
        messages += [
            (
                "assistant",
                f"{code_solution.prefix} \n Imports: {code_solution.imports} \n Code: {code_solution.code}",
            )
        ]

        # Increment
        iterations = iterations + 1
        return {"generation": code_solution, "messages": messages, "iterations": iterations}


    def code_check(state: GraphState):
        """
        Check code

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, error
        """

        print("---CHECKING CODE---")

        # State
        messages = state["messages"]
        code_solution = state["generation"]
        iterations = state["iterations"]

        # Get solution components
        prefix = code_solution.prefix
        imports = code_solution.imports
        code = code_solution.code

        # Check imports
        try:
            exec(imports)
        except Exception as e:
            print("---CODE IMPORT CHECK: FAILED---")
            error_message = [("user", f"Your solution failed the import test: {e}")]
            messages += error_message
            return {
                "generation": code_solution,
                "messages": messages,
                "iterations": iterations,
                "error": "yes",
            }

        # Check execution
        try:
            exec(imports + "\n" + code)
        except Exception as e:
            print("---CODE BLOCK CHECK: FAILED---")
            error_message = [("user", f"Your solution failed the code execution test: {e}")]
            messages += error_message
            return {
                "generation": code_solution,
                "messages": messages,
                "iterations": iterations,
                "error": "yes",
            }

        # No errors
        print("---NO CODE TEST FAILURES---")
        return {
            "generation": code_solution,
            "messages": messages,
            "iterations": iterations,
            "error": "no",
        }


    def reflect(state: GraphState):
        """
        Reflect on errors

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation
        """

        print("---GENERATING CODE SOLUTION---")

        # State
        messages = state["messages"]
        iterations = state["iterations"]
        code_solution = state["generation"]

        # Prompt reflection
        reflection_message = [
            (
                "user",
                """You tried to solve this problem and failed a unit test. Reflect on this failure
                                        given the provided documentation. Write a few key suggestions based on the 
                                        documentation to avoid making this mistake again.""",
            )
        ]

        # Add reflection
        reflections = code_gen_chain.invoke(
            {"context": concatenated_content, "messages": messages}
        )
        messages += [("assistant", f"Here are reflections on the error: {reflections}")]
        return {"generation": code_solution, "messages": messages, "iterations": iterations}


    ### Edges


    def decide_to_finish(state: GraphState):
        """
        Determines whether to finish.

        Args:
            state (dict): The current graph state

        Returns:
            str: Next node to call
        """
        error = state["error"]
        iterations = state["iterations"]

        if error == "no" or iterations == max_iterations:
            print("---DECISION: FINISH---")
            return "end"
        else:
            print("---DECISION: RE-TRY SOLUTION---")
            if flag == "reflect":
                return "reflect"
            else: