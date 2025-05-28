"""
Shared helpers/constants for the Zora-Coin strategy.
Put this file next to historical.py (…/src/zora-coin/utils.py)
"""
import binascii
import glob
import os
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq
from web3 import Web3

# ────────────────────────────────────────────────────────────
# Network configuration & canonical contract addresses
# ────────────────────────────────────────────────────────────
BASE_RPC_URL: str | None = os.getenv("BASE_RPC_URL")
BASE_ALCHEMY_RPC_URL: str | None = os.getenv("BASE_ALCHEMY_RPC_URL")
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

def df_from_dir(
    directory: str,
    prefix: str | None = None,
    *,
    batch_size: int = 50_000,
) -> pd.DataFrame:
    """
    Stream‑load all *.parquet files in *directory* into a single DataFrame.

    Each Parquet shard is read in Arrow *record batches* of ``batch_size`` rows,
    so we never materialise the entire dataset in RAM. Every batch is converted
    to pandas and appended to a list, then concatenated once at the end.

    Parameters
    ----------
    directory
        Folder containing parquet shards.
    prefix
        Optionally filter shards whose basename starts with this prefix.
    batch_size
        Arrow record‑batch size (higher → faster, lower → smaller peak RAM).
    """
    files = sorted(glob.glob(os.path.join(directory, "*.parquet")))
    if prefix:
        files = [fp for fp in files if Path(fp).name.startswith(prefix)]

    if not files:
        return pd.DataFrame()

    dfs: list[pd.DataFrame] = []
    for fp in files:
        try:
            pf = pq.ParquetFile(fp)
            for batch in pf.iter_batches(batch_size=batch_size):
                dfs.append(batch.to_pandas(types_mapper=pd.ArrowDtype))
        except Exception:  # skip corrupt/unreadable shard
            continue

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def latest_synched_block(directory: str) -> int:
    """
    Return the highest ``block_number`` seen in any shard within *directory*.

    Scans the Parquet shards column‑wise via Arrow so memory use stays tiny.
    """
    files = sorted(glob.glob(os.path.join(directory, "*.parquet")))
    if not files:
        return DEPLOYMENT_BLOCK

    max_block = DEPLOYMENT_BLOCK
    for fp in files:
        try:
            pf = pq.ParquetFile(fp)
            for batch in pf.iter_batches(columns=["block_number"], batch_size=100_000):
                col = batch.column(0)
                batch_max = pc.max(col).as_py()
                if batch_max is not None and batch_max > max_block:
                    max_block = batch_max
        except Exception:
            continue

    return int(max_block)

TRYAGGREGATE_4b = hexstr_to_bytes("0xbce38bd7")

def df_from_dir(dir: str) -> pd.DataFrame:
    """
    Get all indexed parquet files
    """
    pattern = os.path.join(dir, "*.parquet")
    all_files = glob.glob(pattern)
    coins = pd.read_parquet(all_files)
    return coins
