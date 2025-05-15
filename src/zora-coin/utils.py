"""
Shared helpers/constants for the Zora-Coin strategy.
Put this file next to historical.py (…/src/zora-coin/utils.py)
"""
import os, glob, time, binascii
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import pandas as pd
from web3 import Web3

# ────────────────────────────────────────────────────────────
# Network configuration & canonical contract addresses
# ────────────────────────────────────────────────────────────
BASE_RPC_URL: str | None = os.getenv("BASE_RPC_URL")
web3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))

COIN_FACTORY_ADDRESS = "0x777777751622c0d3258f214F9DF38E35BF45baF3"
MULTICALL3_ADDRESS   = "0xcA11bde05977b3631167028862bE2a173976CA11"
UNISWAP_V3_FACTORY   = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
DEPLOYMENT_BLOCK     = 26_828_875  # first block we care about

# ────────────────────────────────────────────────────────────
# Convenience helpers
# ────────────────────────────────────────────────────────────
def bytes_to_hexstr(x):
    if isinstance(x, dict):
        return {bytes_to_hexstr(k): bytes_to_hexstr(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [bytes_to_hexstr(i) for i in x]
    if isinstance(x, bytes):
        return "0x" + binascii.hexlify(x).decode().lower()
    return x

def hexstr_to_bytes(x):
    if isinstance(x, dict):
        return {hexstr_to_bytes(k): hexstr_to_bytes(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [hexstr_to_bytes(i) for i in x]
    if isinstance(x, str):
        try:
            return bytes.fromhex(x.removeprefix("0x"))
        except ValueError:
            return x
    return x

def chunk_number(n_blocks: int, chunk_size: int) -> Iterator[range]:
    """Yield consecutive `range` objects of size ≤ `chunk_size`."""
    for start in range(0, n_blocks, chunk_size):
        yield range(start, min(start + chunk_size, n_blocks))

def df_from_dir(directory: str, prefix: str | None = None) -> pd.DataFrame:
    """
    Load every *.parquet file in ``directory`` into a single DataFrame.

    Parameters
    ----------
    directory : str
        Folder containing parquet shards.
    prefix : str | None, optional
        If provided, only parquet files whose **basename** starts with
        this prefix will be included (e.g. prefix="coins_created_").
    """
    # Collect *.parquet paths, then optionally filter by prefix.
    files = sorted(glob.glob(os.path.join(directory, "*.parquet")))
    if prefix is not None:
        files = [fp for fp in files if Path(fp).name.startswith(prefix)]

    if not files:
        return pd.DataFrame()

    # Use Arrow's unified-schema read; fall back to per‑file concat if needed.
    try:
        return pd.read_parquet(
            files,
            engine="pyarrow",
            dataset={"unify_schemas": True},
        )
    except Exception:  # noqa: BLE001
        dfs = []
        for fp in files:
            try:
                shard = pd.read_parquet(fp)
                if not shard.empty:
                    dfs.append(shard)
            except Exception:
                # Skip unreadable shards silently; could log here if desired.
                continue
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def latest_synched_block(directory: str) -> int:
    df = df_from_dir(directory)
    if df.empty:
        return DEPLOYMENT_BLOCK
    return int(df.sort_values("block_number", ascending=False).iloc[0]["block_number"])