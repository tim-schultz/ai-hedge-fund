import json
import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from swap_data import safe_read_parquet
from swap_graph import run_swap_analysis


def main() -> None:
    # Load environment variables
    load_dotenv()

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables")
        print("Please set your OpenAI API key using:")
        print("export OPENAI_API_KEY='your-api-key'")
        return

    # Load the swap data
    print("Loading swap data...")
    swap_data: pd.DataFrame = safe_read_parquet("slot0_timeseries.parquet")

    if swap_data.empty:
        print("Error: No swap data found in slot0_timeseries.parquet")
        return

    print(f"Loaded {len(swap_data)} rows of swap data")

    # Convert the DataFrame to a dictionary format
    swap_data_dict: dict[str, Any] = swap_data.to_dict(orient='records')

    # Run the analysis
    print("\nRunning swap analysis...")
    try:
        result: dict[str, Any] = run_swap_analysis(swap_data_dict)

        # Print the results
        print("\nSwap Analysis Results:")
        print("=" * 50)
        for message in result["messages"]:
            if message.name == "swap_analyzer":
                # Parse and pretty print the content
                content: dict[str, Any] = json.loads(message.content)
                print("\nData Summary:")
                print(json.dumps(content["data_summary"], indent=2))
                print("\nAnalysis:")
                print(json.dumps(content["analysis"], indent=2))
                print("\nTrading Signal:")
                print(json.dumps(content["signal"], indent=2))

    except Exception as e:
        print(f"Error during analysis: {e!s}")
        return

if __name__ == "__main__":
    main()
