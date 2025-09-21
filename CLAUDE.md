# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend Development
```bash
# Install dependencies
poetry install

# Run main hedge fund CLI
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# Run with local Ollama models
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# Run backtester
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# Run tests
poetry run pytest
poetry run pytest tests/backtesting/  # Test specific module
poetry run pytest -k "test_name"  # Run specific test

# Linting and formatting
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run flake8 src/ tests/

# Type checking
poetry run mypy src/
poetry run mypy src/ --strict  # Run with strict mode
poetry run mypy src/ --ignore-missing-imports  # Ignore missing type stubs
```

### Frontend Development
```bash
# Navigate to frontend
cd app/frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint
```

### Full Stack Application
```bash
# Quick start (from app directory)
cd app && ./run.sh  # Mac/Linux
cd app && run.bat   # Windows

# Or using npm
cd app && npm install && npm run setup

# Manual backend start (from app/backend)
poetry run uvicorn main:app --reload

# Manual frontend start (from app/frontend)
npm run dev
```

## Architecture

### Multi-Agent System
The hedge fund uses a LangGraph-based multi-agent architecture with specialized agents:

1. **Investor Agents** (in `src/agents/`):
   - Each mimics a famous investor's strategy (Warren Buffett, Peter Lynch, etc.)
   - Outputs JSON with investment thesis, conviction score, and analysis

2. **Analysis Agents**:
   - `valuation.py`: Calculates intrinsic value using DCF and comparative methods
   - `fundamentals.py`: Analyzes financial metrics and ratios
   - `sentiment.py`: Analyzes market sentiment from various sources
   - `technicals.py`: Analyzes price patterns and technical indicators

3. **Decision Agents**:
   - `risk_manager.py`: Calculates position sizing and portfolio risk metrics
   - `portfolio_manager.py`: Makes final trading decisions based on all signals

4. **Graph Orchestration** (in `src/graph/`):
   - `graph.py`: Defines agent workflow and message passing
   - `state.py`: Manages shared state between agents using TypedDict

### Data Flow
1. Financial data fetched via `src/data/` modules (free for AAPL, GOOGL, MSFT, NVDA, TSLA)
2. Agents process data in parallel using LangGraph
3. Results aggregated in `AgentState` with messages and metadata
4. Portfolio manager synthesizes all signals into trading decisions

### Backend API Structure
- FastAPI application in `app/backend/main.py`
- Routes in `app/backend/routes/` for hedge fund and backtesting endpoints
- Database models in `app/backend/models/`
- Services in `app/backend/services/` handle business logic

### Frontend Architecture
- React + Vite with TypeScript
- Uses @xyflow/react for visualizing agent workflows
- Shadcn/ui components for UI
- Real-time updates via API polling

## Key Implementation Details

- **Python Imports**: Use absolute imports from root (e.g., `from src.agents.warren_buffett import WarrenBuffettAgent`)
- **Agent Communication**: All agents return structured JSON responses that get merged in state
- **Error Handling**: Agents should handle API failures gracefully and return partial results
- **Testing**: Integration tests in `tests/backtesting/integration/` validate full workflows
- **Configuration**: API keys via `.env` file (OPENAI_API_KEY, FINANCIAL_DATASETS_API_KEY, etc.)
- **Supported LLMs**: OpenAI, Anthropic, Groq, DeepSeek, Ollama, Google Gemini, GigaChat, xAI

## Backtesting System

The backtester (`src/backtester.py` and `src/backtesting/`) simulates trading over historical data:
- Supports long-only, short-only, and long-short strategies
- Calculates Sharpe ratio, max drawdown, win rate, and other metrics
- Outputs detailed performance reports with visualizations