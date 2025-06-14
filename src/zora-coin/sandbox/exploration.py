"""Langgraph agent for exploring time series data."""

from pathlib import Path
from typing import TypedDict

import polars as pl
from langgraph.graph import Graph, StateGraph


class AgentState(TypedDict):
    """State for the agent.

    Attributes:
        df: The polars DataFrame containing the time series data
        messages: List of messages for tracking agent progress
    """

    df: pl.DataFrame
    messages: list[str]


def load_data(state: AgentState) -> AgentState:
    """Load data from parquet file into a polars DataFrame.

    Args:
        state: Current agent state

    Returns:
        Updated agent state with loaded DataFrame
    """
    parquet_path = Path("slot0_timeseries.parquet")
    df = pl.read_parquet(parquet_path)

    return {"df": df, "messages": state["messages"] + [f"Loaded DataFrame with shape: {df.shape}"]}


def create_agent() -> Graph:
    """Create the langgraph agent.

    Returns:
        Configured langgraph agent
    """
    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Add the load_data node
    workflow.add_node("load_data", load_data)

    # Set the entry point
    workflow.set_entry_point("load_data")

    # Compile the graph
    return workflow.compile()


if __name__ == "__main__":
    # Initialize the agent
    agent = create_agent()

    # Run the agent with initial state
    result = agent.invoke(
        {
            "df": pl.DataFrame(),  # Empty DataFrame as initial state
            "messages": [],  # Empty messages list as initial state
        }
    )

    # Print the results
    print("\n".join(result["messages"]))
