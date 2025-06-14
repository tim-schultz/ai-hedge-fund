"""Custom tools for DataFrame manipulation in swap analysis."""

from typing import Any

import pandas as pd
from langchain_core.tools import BaseTool
from pydantic import Field


class DataFrameTool(BaseTool):
    """Base class for DataFrame manipulation tools."""

    df: pd.DataFrame = Field(description="The DataFrame to operate on")

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool."""
        raise NotImplementedError("Subclasses must implement _run")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool asynchronously."""
        raise NotImplementedError("Async not implemented")


class GetRecentActivityTool(DataFrameTool):
    """Tool to identify pools with recent activity."""

    name: str = "get_recent_activity"
    description: str = "Identify pools that have had recent activity and return them in descending order by activity"

    def _run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Get recent activity for pools.

        Returns:
            Dictionary containing pool activity information
        """
        # Group by pool and calculate activity metrics
        pool_activity = self.df.groupby("pool").agg({"price": ["count", "mean", "std"], "liquidity": ["mean", "std"], "volatility": "mean"}).round(4)

        # Flatten column names
        pool_activity.columns = ["_".join(col).strip() for col in pool_activity.columns.values]

        # Sort by transaction count (activity)
        pool_activity = pool_activity.sort_values("price_count", ascending=False)

        return pool_activity.to_dict()


class AnalyzePriceTrendsTool(DataFrameTool):
    """Tool to analyze price trends."""

    name: str = "analyze_price_trends"
    description: str = "Analyze price trends and volatility for pools"

    def _run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Analyze price trends.

        Returns:
            Dictionary containing price trend analysis
        """
        # Calculate price trends
        price_trends = self.df.groupby("pool").agg({"price": ["mean", "std", "min", "max"], "price_change": ["mean", "std"], "volatility": "mean"}).round(4)

        # Flatten column names
        price_trends.columns = ["_".join(col).strip() for col in price_trends.columns.values]

        return price_trends.to_dict()


class AnalyzeLiquidityTool(DataFrameTool):
    """Tool to analyze liquidity patterns."""

    name: str = "analyze_liquidity"
    description: str = "Analyze liquidity patterns and changes"

    def _run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Analyze liquidity patterns.

        Returns:
            Dictionary containing liquidity analysis
        """
        # Calculate liquidity metrics
        liquidity_analysis = self.df.groupby("pool").agg({"liquidity": ["mean", "std", "min", "max"], "liquidity_change": ["mean", "std"]}).round(4)

        # Flatten column names
        liquidity_analysis.columns = ["_".join(col).strip() for col in liquidity_analysis.columns.values]

        return liquidity_analysis.to_dict()


class GetTimeBasedMetricsTool(DataFrameTool):
    """Tool to analyze time-based metrics."""

    name: str = "get_time_metrics"
    description: str = "Get time-based metrics like hourly and daily patterns"

    def _run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Get time-based metrics.

        Returns:
            Dictionary containing time-based metrics
        """
        # Calculate hourly patterns
        hourly_patterns = self.df.groupby(["pool", "hour"]).agg({"price": ["count", "mean"], "liquidity": "mean"}).round(4)

        # Calculate daily patterns
        daily_patterns = self.df.groupby(["pool", "day_of_week"]).agg({"price": ["count", "mean"], "liquidity": "mean"}).round(4)

        return {"hourly_patterns": hourly_patterns.to_dict(), "daily_patterns": daily_patterns.to_dict()}


def get_dataframe_tools(df: pd.DataFrame) -> list[DataFrameTool]:
    """Get all DataFrame manipulation tools.

    Args:
        df: The DataFrame to analyze

    Returns:
        List of DataFrame tools
    """
    return [GetRecentActivityTool(df=df), AnalyzePriceTrendsTool(df=df), AnalyzeLiquidityTool(df=df), GetTimeBasedMetricsTool(df=df)]
