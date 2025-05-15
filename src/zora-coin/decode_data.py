"""
Read the on-disk parquet shards, decode the CoinCreated payload,
and return a ready-to-use pandas DataFrame.
"""
import pandas as pd
from eth_abi import decode

from utils import df_from_dir, hexstr_to_bytes

# ────────────────────────────────────────────────────────────
_EVENT_SIG = hexstr_to_bytes("0x3d1462491f7fa8396808c230d95c3fa60fd09ef59506d0b9bd1cf072d2a03f56")
_PARAM_TYPES = [
    "address",  # currency
    "string",   # ipfs / URI
    "string",   # name
    "string",   # symbol
    "address",  # coin
    "address",  # pool
    "string",   # version
]

def _decode_coin_event(row) -> tuple:
    try:
        return decode(_PARAM_TYPES, row["data"])
    except Exception as exc:                       # noqa: BLE001
        print(f"Decoding error: {exc}")
        return (None,) * len(_PARAM_TYPES)

def get_created_coins() -> pd.DataFrame:
    coins = df_from_dir("coins", prefix="coins_created_")
    filtered = coins[coins["topic0"] == _EVENT_SIG]
    columns = ["currency", "ipfs_hash", "name", "symbol", "coin", "pool", "version"]
    decoded = filtered.apply(_decode_coin_event, axis=1, result_type="expand")
    decoded.columns = columns
    return decoded

if __name__ == "__main__":
    df = get_created_coins()
    df.to_parquet("coins/decoded_coins.parquet")
    print("✅ Wrote coins/decoded_coins.parquet")