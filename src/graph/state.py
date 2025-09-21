from __future__ import annotations

import json
import operator
from typing import Any, Callable, Dict, List, Sequence, Tuple, Union

from langchain_core.messages import BaseMessage
from typing_extensions import Annotated, TypedDict


def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with b taking precedence."""
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    """State shared between agents in the graph."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[Dict[str, Any], merge_dicts]
    metadata: Annotated[Dict[str, Any], merge_dicts]


def show_agent_reasoning(output: Union[Dict[str, Any], List[Any], str], agent_name: str) -> None:
    """Display agent reasoning in a formatted way.

    Args:
        output: The agent's output to display
        agent_name: Name of the agent for the header
    """
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")

    def convert_to_serializable(obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if hasattr(obj, "to_dict"):  # Handle Pandas Series/DataFrame
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):  # Handle custom objects
            return obj.__dict__
        elif isinstance(obj, (int, float, bool, str, type(None))):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        else:
            return str(obj)  # Fallback to string representation

    if isinstance(output, (dict, list)):
        # Convert the output to JSON-serializable format
        serializable_output = convert_to_serializable(output)
        print(json.dumps(serializable_output, indent=2))
    else:
        try:
            # Parse the string as JSON and pretty print it
            parsed_output = json.loads(output)
            print(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            # Fallback to original string if not valid JSON
            print(output)

    print("=" * 48)
