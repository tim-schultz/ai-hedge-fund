# This should be enough. sqrtPriceX96, liquidity, tick are after swap for the pool
# emit Swap(msg.sender, recipient, amount0, amount1, state.sqrtPriceX96, state.liquidity, state.tick);
import pandas as pd
import utils
import cryo
from eth_abi import encode, decode

if __name__ == "__main__":
    print("Starting data fetching process...")
    all_coins = pd.read_parquet("coins/decoded_coins.parquet")
    # Multicall liquidity() on each pool and filter out > 0 liquidity
    pools = all_coins['pool']
    liquidity_sig = utils.hexstr_to_bytes("0x1a686502")
    inner_calldata = [[pool, liquidity_sig] for pool in pools]
    m3_calldata_bytes = encode(
        ["bool", "(address,bytes)[]"], [False, inner_calldata]
    )
    m3_calldata = utils.bytes_to_hexstr(utils.TRYAGGREGATE_4b + m3_calldata_bytes)

    df = cryo.collect(
        "eth_calls",
        include_columns=(["block_number", "output_data"]),
        to_address=[utils.MULTICALL3_ADDRESS],
        call_data=[m3_calldata],
        output_format="pandas",
        blocks=["-1:latest"],
        no_verbose=True,
        rpc=utils.BASE_RPC_URL,
        requests_per_second=12,
    )


    first_row = df.iloc[-1]
    output_data = first_row['output_data']
    block_number = first_row['block_number']

    # Decode the data, only care about the return data
    [decoded_data] = decode(["(bool,bytes)[]"], output_data)
    return_data = [decode(["(uint128)"], x[1])[0][0] for x in decoded_data]
    all_coins['liquidity'] = return_data
    coins_with_liquidity = all_coins[all_coins['liquidity'] > 0]

    
    print("Finished data fetching process.", coins_with_liquidity.head())