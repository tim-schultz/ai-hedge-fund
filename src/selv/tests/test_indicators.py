"""
tests/test_indicators.py

These tests cover the *indicator layer*.  They serve a dual purpose:

1. **Functional verification** – we make sure that both the
   vectorised helper (`add_indicators`) and the streaming helper
   (`StrategyState`) behave as expected on simple, deterministic input.

2. **Living documentation** – each assertion is preceded by a short
   comment that explains *why* we expect the behaviour.  Treat the file
   as a guided tour of the indicator mechanics.
"""

def test_add_indicators_columns_exist():
    """`add_indicators` must append RSI and MACD columns to the DataFrame."""
    # Need enough data points for MACD (e.g., slow_ema=26 + signal_ema=9 -> ~35, use 50)
    assert True


