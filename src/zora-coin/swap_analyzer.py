"""Swap analyzer agent for analyzing swap data using LangChain."""

import json
import operator
from collections.abc import Sequence
from typing import Annotated, Any, Literal, TypedDict

import numpy as np
import pandas as pd
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from swap_analyzer_tools import get_dataframe_tools


class AgentState(TypedDict):
    """Type definition for agent state."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, Any], operator.add]
    metadata: Annotated[dict[str, Any], operator.add]


class SwapAnalysis(BaseModel):
    """Schema for swap analysis output."""

    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(description="Confidence in the analysis, between 0.0 and 100.0")
    reasoning: str = Field(descripchecktion="Detailed reasoning for the analysis")
    metrics: dict[str, Any] = Field(description="Key metrics and statistics from the analysis")


def show_agent_reasoning(output: Any, agent_name: str) -> None:
    """Display the agent's reasoning in a formatted way.

    Args:
        output: The output to display
        agent_name: Name of the agent
    """
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")
    if isinstance(output, dict | list):
        print(json.dumps(output, indent=2))
    else:
        try:
            parsed_output = json.loads(str(output))
            print(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            print(output)
    print("=" * 48)


def preprocess_swap_data(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess the swap data to create meaningful features.

    Args:
        df: Input DataFrame with swap data

    Returns:
        Preprocessed DataFrame with additional features
    """
    # Ensure we have a datetime index
    if "block_number" in df.columns:
        df = df.set_index("block_number")

    # Convert string columns to numeric where possible
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass

    # Calculate basic metrics
    if "sqrtPriceX96" in df.columns:
        df["price"] = (df["sqrtPriceX96"].astype(float) / 2**96) ** 2
        df["price_change"] = df["price"].pct_change()
        df["volatility"] = df["price_change"].rolling(window=24).std()  # 24-block volatility

    if "liquidity" in df.columns:
        df["liquidity_change"] = df["liquidity"].pct_change()

    # Add time-based features
    df["hour"] = pd.to_datetime(df.index, unit="s").hour
    df["day_of_week"] = pd.to_datetime(df.index, unit="s").dayofweek

    return df


def get_data_summary(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a summary of the data for the LLM.

    Args:
        df: Input DataFrame to summarize

    Returns:
        Dictionary containing data summary statistics
    """
    summary: dict[str, Any] = {
        "total_rows": len(df),
        "time_range": {
            "start": df.index.min(),
            "end": df.index.max(),
        },
        "columns": list(df.columns),
        "numeric_stats": {},
    }

    # Add statistics for numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        summary["numeric_stats"][col] = {
            "mean": float(df[col].mean()),
            "std": float(df[col].std()),
            "min": float(df[col].min()),
            "max": float(df[col].max()),
        }

    return summary


def swap_analyzer_agent(state: AgentState) -> dict[str, Any]:
    """Analyze swap data using custom DataFrame tools and generate trading signals.

    Args:
        state: Current agent state containing swap data

    Returns:
        Updated agent state with analysis results
    """
    # Get the swap data from state
    swap_data: list[dict[str, Any]] | None = state["data"].get("swap_data")
    if not swap_data:
        return {
            "messages": state["messages"],
            "data": state["data"],
            "metadata": state["metadata"],
        }

    # Create pandas DataFrame from swap data
    df: pd.DataFrame = pd.DataFrame(swap_data)

    # Preprocess the data
    df = preprocess_swap_data(df)

    # Get data summary
    data_summary: dict[str, Any] = get_data_summary(df)

    # Sample the data if it's too large (e.g., take every 100th row)
    if len(df) > 1000:
        df = df.iloc[::100].copy()

    # Get our custom DataFrame tools
    tools = get_dataframe_tools(df)

    # Create the agent
    agent = create_openai_functions_agent(
        ChatOpenAI(
            model="o4-mini-2025-04-16",
            # api_key=getenv("OPENROUTER_API_KEY"),
            # base_url=getenv("OPENROUTER_BASE_URL")
        ),
        tools,
        ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a swap data analysis expert. Use the available tools to analyze the data and provide insights.
            Focus on:
            - Recent pool activity
            - Price trends and volatility
            - Liquidity patterns
            - Time-based patterns
            """,
                ),
                ("human", "{input}"),
                ("ai", "{agent_scratchpad}"),
            ]
        ),
    )

    # Create the agent executor
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # Print available tools
    print("\nAvailable Tools:")
    print("=" * 50)
    for tool in tools:
        print(f"\nTool: {tool.name}")
        print(f"Description: {tool.description}")
        print("-" * 50)

    # Define analysis prompts
    analysis_prompts: list[str] = [
        f"""Given this data summary: {json.dumps(data_summary, indent=2)}
        Analyze the swap data and provide insights about:
        1. Recent pool activity
        2. Price trends and volatility
        3. Liquidity patterns
        4. Time-based patterns
        """,
    ]

    # Initialize analysis results
    analysis_results: dict[str, Any] = {}

    # Run analysis for each prompt
    for prompt in analysis_prompts:
        try:
            result = agent_executor.invoke({"input": prompt})
            analysis_results[prompt] = result["output"]
        except Exception as e:
            print(f"Error analyzing {prompt}: {e!s}")
            analysis_results[prompt] = f"Error: {e!s}"

    # Generate trading signal based on analysis
    signal_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a trading signal generator analyzing swap data.
                Based on the provided analysis and data summary, generate a trading signal with confidence and reasoning.
                Consider factors like:
                - Liquidity trends
                - Price movements
                - Volume patterns
                - Market impact
                """,
            ),
            (
                "human",
                """Here is the data summary:
                {data_summary}

                And here is the swap data analysis:
                {analysis_results}

                Generate a trading signal.""",
            ),
        ],
    )

    # Get the signal from the LLM
    signal_result = signal_prompt.invoke(
        {
            "data_summary": json.dumps(data_summary, indent=2),
            "analysis_results": json.dumps(analysis_results, indent=2),
        },
    )

    # Create the swap analysis message
    message = HumanMessage(
        content=json.dumps(
            {
                "data_summary": data_summary,
                "analysis": analysis_results,
                "signal": signal_result,
            },
        ),
        name="swap_analyzer",
    )

    # Show reasoning if enabled
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(analysis_results, "Swap Analyzer Agent")

    # Update state with analysis results
    state["data"]["swap_analysis"] = {
        "data_summary": data_summary,
        "analysis": analysis_results,
        "signal": signal_result,
    }

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
        "metadata": state["metadata"],
    }
