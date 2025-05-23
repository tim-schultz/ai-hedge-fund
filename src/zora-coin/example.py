"""Example script demonstrating how to use the swap analysis components."""
from typing import Any, Dict, List, Optional
import json
from pathlib import Path

from .swap_graph import run_swap_analysis


def load_swap_data(file_path: str) -> List[Dict[str, Any]]:
    """Load swap data from a JSON file.

    Args:
        file_path: Path to the JSON file containing swap data

    Returns:
        List of swap data dictionaries
    """
    with open(file_path, "r") as f:
        return json.load(f)


def main() -> None:
    """Run the swap analysis example."""
    # Load the swap data
    data_path = Path(__file__).parent / "data" / "swap_data.json"
    swap_data = load_swap_data(str(data_path))

    # Run the analysis
    results = run_swap_analysis(swap_data, show_reasoning=True)

    # Print the results
    print("\nAnalysis Results:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main() 