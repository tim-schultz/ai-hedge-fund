#  Free base URL
# curl -s https://api.developer.coinbase.com/rpc/v1/base/xVQ152Em3ymbtm6XgCqz2EDHdpL3jSGi -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}'

"""
Historical transaction and event querying utility for the Zora-Coin strategy.

Requires:
    * Ape Framework (https://github.com/ApeWorX/ape) with the Base plugin installed,
      e.g. `pip install eth-ape[base]`
    * A provider endpoint configured for the network alias `base:mainnet`.
      Example (in ~/.ape/config.yaml):

      networks:
        base:
          mainnet:
            alchemy:
              uri: ${ALCHEMY_BASE_MAINNET_RPC}
"""

import binascii
import glob
import os
import time

import cryo
import pandas as pd
from eth_abi import decode
from web3 import Web3

web3 = Web3(Web3.HTTPProvider(os.getenv("BASE_RPC_URL")))


def bytes_to_hexstr(x: dict | bytes | list[bytes]) -> str | list[str] | dict:
    """
    Converts bytes to hexstring
    """
    if isinstance(x, dict):
        new_dict = {}
        for k, v in x.items():
            new_dict[bytes_to_hexstr(k)] = bytes_to_hexstr(v)
        return new_dict
    if isinstance(x, list):
        return [bytes_to_hexstr(i) for i in x]
    if isinstance(x, bytes):
        return "0x" + binascii.hexlify(x).decode().lower()
    return x


def hexstr_to_bytes(x: any) -> list[bytes] | bytes:
    """
    Converts hexstring to bytes
    """
    if isinstance(x, dict):
        new_dict = {}
        for k, v in x.items():
            new_dict[hexstr_to_bytes(k)] = hexstr_to_bytes(v)
        return new_dict
    if isinstance(x, list):
        return [hexstr_to_bytes(i) for i in x]
    if isinstance(x, str):
        try:
            return bytes.fromhex(x.replace("0x", ""))
        except Exception:
            return x
    return x


COIN_FACTORY_ADDRESS = "0x777777751622c0d3258f214F9DF38E35BF45baF3"
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"
UNISWAP_V3_FACTORY = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"


base_provider = os.getenv("BASE_RPC_URL")


def chunk_number(number, chunk_size):
    for i in range(0, number, chunk_size):
        yield range(i, min(i + chunk_size, number))


def decode_coin_event(row):
    # event CoinCreated(
    #     address indexed caller,
    #     address indexed payoutRecipient,
    #     address indexed platformReferrer,
    #     address currency,
    #     string uri,
    #     string name,
    #     string symbol,
    #     address coin,
    #     address pool,
    #     string version
    # );
    try:
        param_types = ["address", "string", "string", "string", "address", "address", "string"]
        event_data_bytes = row["data"]
        return decode(param_types, event_data_bytes)
    except Exception as e:
        print(f"Error decoding event data: {e}")
        return None


def get_created_coins():
    """
    Get all coins created by the coin factory
    """

    coins = df_from_dir("coins")
    bytes_coin_event = hexstr_to_bytes("0x3d1462491f7fa8396808c230d95c3fa60fd09ef59506d0b9bd1cf072d2a03f56")
    coin_events = coins[coins["topic0"] == bytes_coin_event]

    columns = ["currency", "ipfs_hash", "name", "symbol", "coin", "pool", "version"]
    coin_events[columns] = coin_events.apply(decode_coin_event, axis=1, result_type="expand")
    return coin_events


def fetch_events(blocks: list[str], start: int, stop: int):
    """
    Fetch events from the coin factory
    """
    coins_created = cryo.collect(
        "logs",
        # include_columns=(["block_number", "output_data"]),
        to_address=[COIN_FACTORY_ADDRESS],
        output_format="pandas",
        blocks=blocks,
        no_verbose=True,
        rpc=base_provider,
        requests_per_second=12,
        max_concurrent_chunks=1,
        # event_signature="CoinCreated(address indexed caller, address indexed payoutRecipient, address indexed platformReferrer, address currency, string uri, string name, string symbol, address coin, address pool, string version)",
    )

    print("coins_created", blocks)
    coins_created.to_parquet(f"coins/coins_created_{start}_{stop}.parquet")


def df_from_dir(dir: str) -> pd.DataFrame:
    """
    Get all indexed parquet files
    """
    pattern = os.path.join(dir, "*.parquet")
    all_files = glob.glob(pattern)
    coins = pd.read_parquet(all_files)
    return coins


def latest_synched_block(dir: str) -> int:
    """
    Get the latest indexed block
    """
    deployment_block = 26828875
    df = df_from_dir(dir)
    if df.empty:
        return deployment_block
    latest_block = df.sort_values("block_number", ascending=False).iloc[0]["block_number"]
    return latest_block


def get_coin_events():
    last_indexed_block = latest_synched_block("coins")
    latest_block = web3.eth.get_block("latest")
    diff = latest_block.number - last_indexed_block

    max_attempts = 10

    for i in chunk_number(diff, 500):
        start = i.start + last_indexed_block
        stop = i.stop + last_indexed_block
        blocks = [f"{start}:{stop}"]

        for attempt in range(max_attempts):
            if attempt > 0:
                wait_time = 2**attempt
                print(f"Attempt {attempt + 1} of {max_attempts} for blocks {blocks}. Waiting {wait_time}s before retrying...")
                time.sleep(wait_time)
            try:
                fetch_events(blocks, start, stop)
                break
            except Exception as e:
                print(f"Error fetching events: {e}")
                if attempt == max_attempts - 1:
                    print("Max attempts reached. Moving to next chunk.")
                    break


def main() -> None:
    # get_coin_events()
    decoded_coins = get_created_coins()
    decoded_coins.to_parquet("coins/decoded_coins.parquet")


if __name__ == "__main__":
    main()
