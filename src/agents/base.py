"""Base classes and protocols for agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from langchain_core.language_models import BaseChatModel

from src.graph.state import AgentState
from src.domain_types import AgentAnalysis, InvestorAgentOutput, OrderSide, Score, TimeFrame


class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(self, llm: Optional[BaseChatModel] = None) -> None:
        """Initialize the agent.

        Args:
            llm: Language model to use for analysis
        """
        self.llm = llm

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the agent's name."""
        ...

    @abstractmethod
    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """Analyze market data and return recommendations.

        Args:
            state: Current agent state with market data

        Returns:
            Analysis results to be merged into state
        """
        ...


class BaseInvestorAgent(BaseAgent):
    """Base class for investor-style agents."""

    @property
    @abstractmethod
    def investment_philosophy(self) -> str:
        """Return the agent's investment philosophy."""
        ...

    @property
    def default_time_horizon(self) -> TimeFrame:
        """Default investment time horizon."""
        return "1y"

    def format_analysis(
        self,
        ticker: str,
        recommendation: OrderSide,
        conviction_score: Score,
        analysis: str,
        key_points: list[str],
        risks: list[str],
        investment_thesis: str,
        position_sizing: Optional[float] = None,
        catalysts: Optional[list[str]] = None,
    ) -> InvestorAgentOutput:
        """Format analysis into standard output format.

        Args:
            ticker: Stock ticker
            recommendation: Buy/sell/hold recommendation
            conviction_score: Confidence in recommendation (0-1)
            analysis: Detailed analysis text
            key_points: Key supporting points
            risks: Identified risks
            investment_thesis: Overall investment thesis
            position_sizing: Suggested position size as percentage
            catalysts: Potential catalysts for the investment

        Returns:
            Formatted investor agent output
        """
        agent_analysis: AgentAnalysis = {
            "ticker": ticker,
            "recommendation": recommendation,
            "conviction_score": conviction_score,
            "analysis": analysis,
            "key_points": key_points,
            "risks": risks,
            "catalysts": catalysts,
        }

        output: InvestorAgentOutput = {
            "agent_name": self.name,
            "analysis": agent_analysis,
            "investment_thesis": investment_thesis,
            "time_horizon": self.default_time_horizon,
            "position_sizing": position_sizing,
        }

        return output


class BaseAnalysisAgent(BaseAgent):
    """Base class for analysis agents (fundamental, technical, sentiment)."""

    @abstractmethod
    def get_analysis_type(self) -> str:
        """Return the type of analysis this agent performs."""
        ...

    def format_signals(
        self,
        ticker: str,
        signals: Dict[str, Any],
        recommendation: OrderSide,
        confidence: Score,
    ) -> Dict[str, Any]:
        """Format analysis signals into standard output.

        Args:
            ticker: Stock ticker
            signals: Analysis signals/metrics
            recommendation: Overall recommendation
            confidence: Confidence in analysis (0-1)

        Returns:
            Formatted analysis output
        """
        return {
            "ticker": ticker,
            "analysis_type": self.get_analysis_type(),
            "signals": signals,
            "recommendation": recommendation,
            "confidence": confidence,
        }


class BaseDecisionAgent(BaseAgent):
    """Base class for decision-making agents (risk manager, portfolio manager)."""

    @abstractmethod
    def make_decision(
        self,
        analyses: list[Dict[str, Any]],
        portfolio_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make a decision based on analyses and portfolio state.

        Args:
            analyses: List of analyses from other agents
            portfolio_state: Current portfolio state

        Returns:
            Decision output
        """
        ...
