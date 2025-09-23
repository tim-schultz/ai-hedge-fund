"""Core type definitions for the AI Hedge Fund system."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Protocol, TypeAlias, TypedDict, Union

import pandas as pd
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

# Type aliases for common patterns
JSON: TypeAlias = Dict[str, Any]
Ticker: TypeAlias = str
Price: TypeAlias = float
Quantity: TypeAlias = int
Score: TypeAlias = float  # 0.0 to 1.0
Percentage: TypeAlias = float  # 0.0 to 100.0

# Trading types
OrderSide: TypeAlias = Literal["buy", "sell", "hold"]
PositionType: TypeAlias = Literal["long", "short", "flat"]
TimeFrame: TypeAlias = Literal["1d", "1w", "1m", "3m", "6m", "1y"]

# DataFrame types
PriceDataFrame: TypeAlias = pd.DataFrame  # Expected columns: date, open, high, low, close, volume
FinancialDataFrame: TypeAlias = pd.DataFrame  # Financial metrics DataFrame


class MarketData(TypedDict):
    """Market data for a ticker."""

    ticker: str
    current_price: float
    volume: int
    market_cap: float
    pe_ratio: Optional[float]
    dividend_yield: Optional[float]
    beta: Optional[float]


class FinancialMetrics(TypedDict):
    """Financial metrics for fundamental analysis."""

    revenue: float
    earnings: float
    free_cash_flow: float
    debt_to_equity: float
    return_on_equity: float
    gross_margin: float
    operating_margin: float
    net_margin: float


class TechnicalIndicators(TypedDict):
    """Technical indicators for analysis."""

    sma_20: float
    sma_50: float
    sma_200: float
    rsi: float
    macd: float
    macd_signal: float
    bollinger_upper: float
    bollinger_lower: float
    volume_avg: float


class AgentAnalysis(TypedDict):
    """Standard output format for agent analysis."""

    ticker: str
    recommendation: OrderSide
    conviction_score: Score
    analysis: str
    key_points: List[str]
    risks: List[str]
    catalysts: Optional[List[str]]


class InvestorAgentOutput(TypedDict):
    """Output format for investor agents."""

    agent_name: str
    analysis: AgentAnalysis
    investment_thesis: str
    time_horizon: TimeFrame
    position_sizing: Optional[float]  # Suggested position size as percentage


class ValuationOutput(TypedDict):
    """Output from valuation agent."""

    ticker: str
    intrinsic_value: float
    current_price: float
    margin_of_safety: Percentage
    valuation_method: str
    confidence_level: Score
    assumptions: Dict[str, Any]


class RiskMetrics(TypedDict):
    """Risk metrics for position."""

    ticker: str
    position_size: float
    var_95: float  # Value at Risk at 95% confidence
    sharpe_ratio: float
    max_drawdown: float
    beta: float
    correlation_to_portfolio: float


class PortfolioDecision(TypedDict):
    """Final portfolio management decision."""

    ticker: str
    action: OrderSide
    quantity: int
    position_type: PositionType
    target_allocation: Percentage
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: str
    risk_metrics: RiskMetrics


class BacktestResult(TypedDict):
    """Backtesting results."""

    total_return: Percentage
    annualized_return: Percentage
    sharpe_ratio: float
    max_drawdown: Percentage
    win_rate: Percentage
    trades_count: int
    best_trade: Dict[str, Any]
    worst_trade: Dict[str, Any]


# Protocols for type checking
class DataProvider(Protocol):
    """Protocol for data providers."""

    def get_price_data(self, ticker: str, start_date: datetime, end_date: datetime) -> PriceDataFrame:
        """Fetch price data for a ticker."""
        ...

    def get_financial_data(self, ticker: str) -> FinancialMetrics:
        """Fetch financial data for a ticker."""
        ...


class Agent(Protocol):
    """Protocol for all agents in the system."""

    @property
    def name(self) -> str:
        """Agent name."""
        ...

    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market data and return recommendations."""
        ...


class InvestorAgent(Agent):
    """Protocol for investor agents."""

    @abstractmethod
    def get_investment_philosophy(self) -> str:
        """Return the agent's investment philosophy."""
        ...


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    def invoke(self, prompt: str) -> str:
        """Invoke the LLM with a prompt."""
        ...

    def stream(self, prompt: str) -> Any:
        """Stream LLM responses."""
        ...


# Pydantic models for API
class TradeRequest(BaseModel):
    """API request for trade execution."""

    ticker: str
    action: OrderSide
    quantity: int
    order_type: Literal["market", "limit"]
    limit_price: Optional[float] = None


class BacktestRequest(BaseModel):
    """API request for backtesting."""

    tickers: List[str]
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    strategy: Literal["long_only", "short_only", "long_short"] = "long_only"


class BacktestResponse(BaseModel):
    """API response for backtesting."""

    results: BacktestResult
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]


# Type guards
def is_valid_ticker(value: Any) -> bool:
    """Check if value is a valid ticker symbol."""
    return isinstance(value, str) and value.isupper() and 1 <= len(value) <= 5


def is_valid_score(value: Any) -> bool:
    """Check if value is a valid score (0.0 to 1.0)."""
    return isinstance(value, (int, float)) and 0 <= value <= 1


def is_valid_percentage(value: Any) -> bool:
    """Check if value is a valid percentage (0.0 to 100.0)."""
    return isinstance(value, (int, float)) and 0 <= value <= 100
