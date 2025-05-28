"""Swap analysis graph implementation using LangGraph."""
from typing import Any

from langgraph.graph import END, Graph
from swap_analyzer import AgentState, swap_analyzer_agent


def create_swap_analysis_graph() -> Graph:
    """Create a graph for swap analysis.

    Returns:
        Graph object for swap analysis workflow
    """
    # Create the graph
    workflow = Graph()

    # Add the swap analyzer node
    workflow.add_node("swap_analyzer", swap_analyzer_agent)

    # Set the entry point
    workflow.set_entry_point("swap_analyzer")

    # Add edges
    workflow.add_edge("swap_analyzer", END)

    # Compile the graph
    return workflow.compile()


def run_swap_analysis(
    swap_data: list[dict[str, Any]],
    show_reasoning: bool = True,
) -> dict[str, Any]:
    """Run the swap analysis workflow.

    Args:
        swap_data: List of swap data dictionaries
        show_reasoning: Whether to show agent reasoning

    Returns:
        Dictionary containing swap analysis results
    """
    # Create the graph
    graph = create_swap_analysis_graph()

    # Create initial state
    initial_state: AgentState = {
        "messages": [],
        "data": {"swap_data": swap_data},
        "metadata": {"show_reasoning": show_reasoning},
    }

    # Run the graph
    result = graph.invoke(initial_state)

    # Extract the analysis results
    analysis_results = result["data"].get("swap_analysis", {})

    return analysis_results
