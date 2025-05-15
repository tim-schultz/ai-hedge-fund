# This should be enough. sqrtPriceX96, liquidity, tick are after swap for the pool
# emit Swap(msg.sender, recipient, amount0, amount1, state.sqrtPriceX96, state.liquidity, state.tick);
import pandas as pd
import utils
import cryo
from eth_abi import encode, decode

import logging

from pathlib import Path

import os
from web3 import Web3

# --- configuration for chunked slot0 fetching ---
BLOCK_STRIDE = 900      # ≈ 30 minutes (900 blocks × 2 s)
CHUNK_SIZE   = 100_000  # fetch at most this many blocks per cryo query

LIQ_CACHE = Path("coins_with_liquidity.parquet")
SLOT0_CACHE = Path("slot0_timeseries.parquet")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ABI type string for the Uniswap V3 slot0 return struct
SLOT0_TYPES = "(uint160,int24,uint16,uint16,uint16,uint8,bool)"

def _decode_slot0_outputs(output_bytes):
    """
    Decode the Multicall3 aggregated result for slot0() calls.

    Returns a list parallel to `pools`, where each element is either:
    * the 7‑tuple `(sqrtPriceX96, tick, obsIndex, obsCardinality, obsCardinalityNext, feeProtocol, unlocked)`
    * None if the call reverted or returned an unexpected byte length.
    """
    from eth_abi.exceptions import InsufficientDataBytes

    try:
        # Aggregate is an array of (bool success, bytes returnData)
        [aggregated] = decode(["(bool,bytes)[]"], output_bytes)
    except Exception as err:
        logger.error("Could not ABI‑decode Multicall wrapper: %s", err)
        return [None] * len(pools)

    decoded_vals = []
    for idx, (success, ret) in enumerate(aggregated):
        if not success or len(ret) < 224:  # 7 static values × 32 bytes
            if success and len(ret) == 0:
                logger.warning(
                    "slot0() for pool %s succeeded but returned 0 bytes (skipping)",
                    pools.iloc[idx],
                )
            decoded_vals.append(None)
            continue

        try:
            decoded_vals.append(decode([SLOT0_TYPES], ret)[0])
        except InsufficientDataBytes:
            logger.warning(
                "slot0() for pool %s returned insufficient bytes (len=%d)",
                pools.iloc[idx],
                len(ret),
            )
            decoded_vals.append(None)
        except Exception as err:
            logger.warning(
                "slot0() for pool %s failed to decode: %s",
                pools.iloc[idx],
                err,
            )
            decoded_vals.append(None)

    return decoded_vals

if __name__ == "__main__":
    logger.info("Starting data fetching process…")
    all_coins = pd.read_parquet("coins/decoded_coins.parquet")
    # Multicall liquidity() on each pool and filter out > 0 liquidity
    if LIQ_CACHE.exists():
        coins_with_liquidity = pd.read_parquet(LIQ_CACHE)
        # liquidity was stored as string to avoid 128‑bit overflow; convert back to Python int
        if coins_with_liquidity["liquidity"].dtype == "string":
            coins_with_liquidity["liquidity"] = coins_with_liquidity["liquidity"].apply(int)
        logger.info(
            "Loaded cached liquidity dataframe (%d pools)", len(coins_with_liquidity)
        )
    else:
        pools = all_coins["pool"]
        liquidity_sig = utils.hexstr_to_bytes("0x1a686502")
        inner_calldata = [[pool, liquidity_sig] for pool in pools]
        m3_calldata_bytes = encode(
            ["bool", "(address,bytes)[]"], [False, inner_calldata]
        )
        m3_calldata = utils.bytes_to_hexstr(utils.TRYAGGREGATE_4b + m3_calldata_bytes)

        liquidity = cryo.collect(
            "eth_calls",
            include_columns=(["block_number", "output_data"]),
            to_address=[utils.MULTICALL3_ADDRESS],
            call_data=[m3_calldata],
            output_format="pandas",
            blocks=["-1:latest"],
            no_verbose=True,
            rpc=utils.BASE_ALCHEMY_RPC_URL,
            requests_per_second=12,
        )

        first_row = liquidity.iloc[-1]
        output_data = first_row["output_data"]

        [decoded_data] = decode(["(bool,bytes)[]"], output_data)
        return_data = [decode(["(uint128)"], x[1])[0][0] for x in decoded_data]
        all_coins["liquidity"] = return_data
        coins_with_liquidity = all_coins[all_coins["liquidity"] > 0]
        # Store liquidity as string so parquet won't overflow on 128‑bit ints
        coins_with_liquidity["liquidity"] = coins_with_liquidity["liquidity"].astype("string")
        coins_with_liquidity.to_parquet(LIQ_CACHE)
        logger.info(
            "Fetched liquidity for %d pools; %d have non‑zero liquidity. Cached to %s",
            len(all_coins),
            len(coins_with_liquidity),
            LIQ_CACHE,
        )

    

    # --- slot0 time‑series (sqrtPriceX96) ---
    if  SLOT0_CACHE.exists():
        slot0_timeseries = pd.read_parquet(SLOT0_CACHE)
        logger.info(
            "Loaded cached slot0 time‑series from %s (shape=%s)",
            SLOT0_CACHE,
            slot0_timeseries.shape,
        )
    else:
        # --- fetch slot0 in manageable block chunks ---
        w3 = Web3(Web3.HTTPProvider(utils.BASE_ALCHEMY_RPC_URL))
        latest_block = w3.eth.block_number

        slot0_sig = utils.hexstr_to_bytes("0x3850c7bd")
        pools = coins_with_liquidity["pool"]
        inner_calldata = [[pool, slot0_sig] for pool in pools]
        m3_calldata_bytes = encode(
            ["bool", "(address,bytes)[]"], [False, inner_calldata]
        )
        m3_calldata = utils.bytes_to_hexstr(
            utils.TRYAGGREGATE_4b + m3_calldata_bytes
        )

        slot0_rows = []
        os.makedirs("slot0_chunks", exist_ok=True)

        start_block = utils.DEPLOYMENT_BLOCK
        while start_block <= latest_block:
            end_block = min(start_block + CHUNK_SIZE - 1, latest_block)
            block_selector = f"{start_block}:{end_block}/{BLOCK_STRIDE}"
            logger.info("Fetching slot0 data for %s", block_selector)

            data_chunk = cryo.collect(
                "eth_calls",
                include_columns=(["block_number", "output_data"]),
                to_address=[utils.MULTICALL3_ADDRESS],
                call_data=[m3_calldata],
                output_format="pandas",
                blocks=[block_selector],
                no_verbose=True,
                rpc=utils.BASE_ALCHEMY_RPC_URL,
                requests_per_second=12,
            )

            if data_chunk.empty:
                start_block = end_block + 1
                continue

            # Decode and build rows for this chunk
            for _, row in data_chunk.iterrows():
                per_pool_vals = _decode_slot0_outputs(row["output_data"])
                slot0_rows.append(
                    {
                        "block_number": row["block_number"],
                        **{
                            str(pool): vals[0] if vals is not None else None
                            for pool, vals in zip(pools, per_pool_vals)
                        },
                    }
                )

            # Persist the chunk for resumability
            chunk_df = (
                pd.DataFrame(slot0_rows[-len(data_chunk):])
                .set_index("block_number")
                .sort_index()
            )
            # Cast large uint values (sqrtPriceX96) to string to avoid Arrow int overflow
            chunk_df = chunk_df.apply(lambda col: col.astype("string"))
            chunk_path = Path("slot0_chunks") / f"slot0_{start_block}_{end_block}.parquet"
            chunk_df.to_parquet(chunk_path)
            logger.info("Wrote slot0 chunk %s (rows=%d)", chunk_path, len(chunk_df))

            start_block = end_block + 1  # move to next window

        # Consolidate all rows into final DataFrame
        slot0_timeseries = (
            pd.DataFrame(slot0_rows).set_index("block_number").sort_index()
        )
        # Convert bigint columns to string so pyarrow can write without overflow
        slot0_timeseries = slot0_timeseries.apply(lambda col: col.astype("string"))
        slot0_timeseries.to_parquet(SLOT0_CACHE)
        logger.info(
            "Saved consolidated slot0 time‑series to %s (shape=%s)",
            SLOT0_CACHE,
            slot0_timeseries.shape,
        )

    logger.info(
        "Finished data fetching process.\nCoins with liquidity head:\n%s\nslot0_timeseries head:\n%s",
        coins_with_liquidity.head(),
        slot0_timeseries.head(),
    )