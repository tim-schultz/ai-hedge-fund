"""
Download raw CoinCreated logs in chunks and store them in coins/*.parquet
"""
from __future__ import annotations

import time
from collections.abc import Sequence

import cryo

from utils import (
    BASE_RPC_URL,
    COIN_FACTORY_ADDRESS,
    chunk_number,
)

# =============================================================================
BASE_PROVIDER = BASE_RPC_URL   # short alias

def _fetch_events(block_span: Sequence[str], start: int, stop: int) -> None:
    tbl = cryo.collect(
        "logs",
        to_address=[COIN_FACTORY_ADDRESS],
        output_format="polars",           # keep as Arrow
        blocks=block_span,
        no_verbose=True,
        rpc=BASE_RPC_URL,
        requests_per_second=12,
        event_signature=(
           "CoinCreated(address indexed caller, address indexed payoutRecipient, address indexed platformReferrer, address currency, string uri, string name, string symbol, address coin, address pool, string version)"
        ),
    )

    tbl.write_parquet(
        f"coins/coins_created_{start}_{stop}.parquet"
    )

def get_coin_events(chunk_size: int = 500, retries: int = 10) -> None:
    """Incrementally sync all CoinCreated events to disk."""

    # last_indexed = latest_synched_block("coins")
    last_indexed = 28999876
    latest_chain = 29828876  #web3.eth.get_block("latest").number
    missing      = latest_chain - last_indexed

    for span in chunk_number(missing, chunk_size):
        start, stop   = span.start + last_indexed, span.stop + last_indexed
        block_filters = [f"{start}:{stop}"]
        print(f"→ Fetching {block_filters} …")

        for attempt in range(retries):
            if attempt:
                wait = 2 ** attempt
                print(f"Retry {attempt}/{retries} for {block_filters} … sleeping {wait}s")
                time.sleep(wait)
            try:
                _fetch_events(block_filters, start, stop)
                break
            except Exception as exc:
                print(f"Error: {exc}")
                if attempt == retries - 1:
                    print("Giving up on this span.")
    print("✅ Finished log download")

if __name__ == "__main__":
    get_coin_events()
