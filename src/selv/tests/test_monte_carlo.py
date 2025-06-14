# """
# tests/test_monte_carlo.py

# Unit tests for the Monte-Carlo driver.  Highlights:

# * We run a *tiny* simulation (N_PATHS=3) so tests remain fast.
# * Every synthetic path must be reproducible when the same
#   `(SEED + worker_id)` is used.
# * Generated prices are strictly positive and of the correct length.
# """

# import numpy as np

# from src.selv.monte_carlo import (
#     simulate_path,
#     horizon,
#     SEED,
# )  # re-use objects from the module


# def test_simulate_path_reproducible():
#     """Same seed → identical path."""
#     rng1 = np.random.default_rng(SEED + 1)
#     rng2 = np.random.default_rng(SEED + 1)
#     p1 = simulate_path(10.0, rng1)
#     p2 = simulate_path(10.0, rng2)
#     assert np.allclose(p1, p2), "simulate_path not reproducible for same seed"


# def test_simulate_path_shape_and_positive():
#     """Synthetic path must have correct length and only positive prices."""
#     rng = np.random.default_rng(SEED + 99)
#     path = simulate_path(100.0, rng)
#     assert len(path) == horizon, "Path length mismatch"
#     assert (path > 0).all(), "GBM generated non-positive prices"


# def test_small_monte_carlo_run_returns_non_empty_stats():
#     """
#     Run the main pipeline with three paths for a single strategy
#     to ensure it returns metrics with expected keys - acts as a smoke test
#     without heavy runtime.
#     """
#     from src.selv.monte_carlo import simulate_and_run_strategy, STRATEGIES

#     # Pick a strategy for testing, e.g., the original default
#     strategy_name_to_test = "MACD_RSI_Confirm"
#     strategy_funcs = STRATEGIES[strategy_name_to_test]

#     args_list = [
#         (
#             i,
#             strategy_name_to_test,
#             strategy_funcs["long_entry_fun"],
#             strategy_funcs["short_entry_fun"],
#         )
#         for i in range(3)  # Test with 3 paths
#     ]

#     results = [simulate_and_run_strategy(args) for args in args_list]
#     for res in results:
#         assert "equity" in res and "sharpe" in res and "max_dd" in res
#         assert res["strategy_name"] == strategy_name_to_test
