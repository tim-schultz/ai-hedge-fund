from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing_extensions import Literal

from src.agents.base import BaseDecisionAgent
from src.graph.state import AgentState, show_agent_reasoning
from src.domain_types import (
    OrderSide,
    PortfolioDecision,
    PositionType,
    RiskMetrics,
    Ticker,
)
from src.utils.llm import call_llm
from src.utils.progress import progress


class PortfolioManagerOutput(BaseModel):
    decisions: Dict[Ticker, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


class PortfolioManagerAgent(BaseDecisionAgent):
    """Portfolio management agent that makes final trading decisions."""

    @property
    def name(self) -> str:
        return "Portfolio Manager"

    def analyze(self, state: AgentState) -> Dict[str, Any]:
        """Analyze all signals and make portfolio decisions."""
        return portfolio_management_analysis(state, self)

    def make_decision(
        self,
        analyses: List[Dict[str, Any]],
        portfolio_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make portfolio decisions based on all analyses."""
        # This would be implemented for more complex decision making
        return {}


def portfolio_management_analysis(state: AgentState, agent: PortfolioManagerAgent) -> Dict[str, Any]:
    """Makes final trading decisions and generates orders for multiple tickers"""

    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers: List[Ticker] = state["data"]["tickers"]

    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status(agent.name, ticker, "Processing analyst signals")

        # Find the corresponding risk manager for this portfolio manager
        if agent.name.startswith("portfolio_manager_"):
            suffix = agent.name.split("_")[-1]
            risk_manager_id = f"risk_management_agent_{suffix}"
        else:
            risk_manager_id = "risk_management_agent"  # Fallback for CLI

        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0.0)
        current_prices[ticker] = float(risk_data.get("current_price", 0.0))

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] // current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Compress analyst signals to {sig, conf}
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if not agent.startswith("risk_management_agent") and ticker in signals:
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                if sig is not None and conf is not None:
                    ticker_signals[agent] = {"sig": sig, "conf": conf}
        signals_by_ticker[ticker] = ticker_signals

    state["data"]["current_prices"] = current_prices

    progress.update_status(agent.name, None, "Generating trading decisions")

    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        agent_name=agent.name,
        state=state,
    )
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent.name,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}, "Portfolio Manager")

    progress.update_status(agent.name, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def compute_allowed_actions(
    tickers: list[str],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict[str, float],
) -> dict[str, dict[str, int]]:
    """Compute allowed actions and max quantities for each ticker deterministically."""
    allowed = {}
    cash = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {}) or {}
    margin_requirement = float(portfolio.get("margin_requirement", 0.5))
    margin_used = float(portfolio.get("margin_used", 0.0))
    equity = float(portfolio.get("equity", cash))

    for ticker in tickers:
        price = float(current_prices.get(ticker, 0.0))
        pos = positions.get(
            ticker,
            {"long": 0, "long_cost_basis": 0.0, "short": 0, "short_cost_basis": 0.0},
        )
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        max_qty = int(max_shares.get(ticker, 0) or 0)

        # Start with zeros
        actions = {"buy": 0, "sell": 0, "short": 0, "cover": 0, "hold": 0}

        # Long side
        if long_shares > 0:
            actions["sell"] = long_shares
        if cash > 0 and price > 0:
            max_buy_cash = int(cash // price)
            max_buy = max(0, min(max_qty, max_buy_cash))
            if max_buy > 0:
                actions["buy"] = max_buy

        # Short side
        if short_shares > 0:
            actions["cover"] = short_shares
        if price > 0 and max_qty > 0:
            if margin_requirement <= 0.0:
                # If margin requirement is zero or unset, only cap by max_qty
                max_short = max_qty
            else:
                available_margin = max(0.0, (equity / margin_requirement) - margin_used)
                max_short_margin = int(available_margin // price)
                max_short = max(0, min(max_qty, max_short_margin))
            if max_short > 0:
                actions["short"] = max_short

        # Hold always valid
        actions["hold"] = 0

        # Prune zero-capacity actions to reduce tokens, keep hold
        pruned = {"hold": 0}
        for k, v in actions.items():
            if k != "hold" and v > 0:
                pruned[k] = v

        allowed[ticker] = pruned

    return allowed


def _compact_signals(signals_by_ticker: dict[str, dict]) -> dict[str, dict]:
    """Keep only {agent: {sig, conf}} and drop empty agents."""
    out = {}
    for t, agents in signals_by_ticker.items():
        if not agents:
            out[t] = {}
            continue
        compact = {}
        for agent, payload in agents.items():
            sig = payload.get("sig") or payload.get("signal")
            conf = payload.get("conf") if "conf" in payload else payload.get("confidence")
            if sig is not None and conf is not None:
                compact[agent] = {"sig": sig, "conf": conf}
        out[t] = compact
    return out


def generate_trading_decision(
    tickers: List[str],
    signals_by_ticker: Dict[str, Dict[str, Any]],
    current_prices: Dict[str, float],
    max_shares: Dict[str, int],
    portfolio: Dict[str, float],
    agent_name: str,
    state: AgentState,
) -> PortfolioManagerOutput:
    """Get decisions from the LLM with deterministic constraints and a minimal prompt."""

    # Deterministic constraints
    allowed_actions_full = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)

    # Pre-fill pure holds to avoid sending them to the LLM at all
    prefilled_decisions: dict[str, PortfolioDecision] = {}
    tickers_for_llm: list[str] = []
    for t in tickers:
        aa = allowed_actions_full.get(t, {"hold": 0})
        # If only 'hold' key exists, there is no trade possible
        if set(aa.keys()) == {"hold"}:
            prefilled_decisions[t] = PortfolioDecision(action="hold", quantity=0, confidence=100.0, reasoning="No valid trade available")
        else:
            tickers_for_llm.append(t)

    if not tickers_for_llm:
        return PortfolioManagerOutput(decisions=prefilled_decisions)

    # Build compact payloads only for tickers sent to LLM
    compact_signals = _compact_signals({t: signals_by_ticker.get(t, {}) for t in tickers_for_llm})
    compact_allowed = {t: allowed_actions_full[t] for t in tickers_for_llm}

    # Minimal prompt template
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a portfolio manager.\n" "Inputs per ticker: analyst signals and allowed actions with max qty (already validated).\n" "Pick one allowed action per ticker and a quantity ≤ the max. " "Keep reasoning very concise (max 100 chars). No cash or margin math. Return JSON only."),
            ("human", "Signals:\n{signals}\n\n" "Allowed:\n{allowed}\n\n" "Format:\n" "{{\n" '  "decisions": {{\n' '    "TICKER": {{"action":"...","quantity":int,"confidence":int,"reasoning":"..."}}\n' "  }}\n" "}}"),
        ]
    )

    prompt_data = {
        "signals": json.dumps(compact_signals, separators=(",", ":"), ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, separators=(",", ":"), ensure_ascii=False),
    }
    prompt = template.invoke(prompt_data)

    # Default factory fills remaining tickers as hold if the LLM fails
    def create_default_portfolio_output():
        # start from prefilled
        decisions = dict(prefilled_decisions)
        for t in tickers_for_llm:
            decisions[t] = PortfolioDecision(action="hold", quantity=0, confidence=0.0, reasoning="Default decision: hold")
        return PortfolioManagerOutput(decisions=decisions)

    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_name,
        state=state,
        default_factory=create_default_portfolio_output,
    )

    # Merge prefilled holds with LLM results
    merged = dict(prefilled_decisions)
    merged.update(llm_out.decisions)
    return PortfolioManagerOutput(decisions=merged)


# Legacy function for backward compatibility
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager") -> Dict[str, Any]:
    """Legacy function that maintains compatibility with existing workflow."""
    agent = PortfolioManagerAgent()
    return agent.analyze(state)
