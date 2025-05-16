"""
Stream-decode CoinCreated events without blowing up memory.

Usage:
    poetry run python src/zora-coin/decode_data_streaming.py
"""
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
from eth_abi import decode
from utils import hexstr_to_bytes

# ────────────────────────────────────────────────────────────
_EVENT_SIG = hexstr_to_bytes(
    "0x3d1462491f7fa8396808c230d95c3fa60fd09ef59506d0b9bd1cf072d2a03f56"
)
_PARAM_TYPES = [
    "address",  # currency
    "string",   # ipfs / URI
    "string",   # name
    "string",   # symbol
    "address",  # coin
    "address",  # pool
    "string",   # version
]
_OUT_PATH = Path("coins/decoded_coins.parquet")
_BATCH_SIZE = 50_000          # rows per Arrow record-batch

columns = ["currency", "ipfs_hash", "name", "symbol",
           "coin", "pool", "version"]


def _decode_coin_event(row) -> tuple:
    try:
        return decode(_PARAM_TYPES, row["data"])
    except Exception as exc:           # bad decode → all-None row
        print(f"Decoding error: {exc}")
        return (None,) * len(_PARAM_TYPES)


def main() -> None:
    shard_files = sorted(Path("coins").glob("coins_created_*.parquet"))
    if not shard_files:
        raise FileNotFoundError("No shards matching coins_created_*.parquet found")

    writer: pq.ParquetWriter | None = None

    for fpath in shard_files:
        print(f"→ processing {fpath.name}")
        pf = pq.ParquetFile(fpath)

        for batch in pf.iter_batches(batch_size=_BATCH_SIZE,
                                     columns=["topic0", "data"]):
            df = batch.to_pandas(types_mapper=pd.ArrowDtype)

            filtered = df[df["topic0"] == _EVENT_SIG]
            if filtered.empty:
                continue

            decoded = filtered.apply(_decode_coin_event,
                                     axis=1, result_type="expand")
            decoded.columns = columns

            table = pa.Table.from_pandas(decoded, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(
                    _OUT_PATH,
                    table.schema,
                    compression="zstd",
                    write_statistics=True,
                )
            writer.write_table(table)

    if writer is None:
        print("⚠️  No matching CoinCreated events found.")
    else:
        writer.close()
        print(f"✅ Wrote {_OUT_PATH} (streaming mode)")


if __name__ == "__main__":
    main()