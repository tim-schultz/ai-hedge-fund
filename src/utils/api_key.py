from typing import Any, Dict, Optional


def get_api_key_from_state(state: Dict[str, Any], api_key_name: str) -> Optional[str]:
    """Get an API key from the state object."""
    if state and state.get("metadata", {}).get("request"):
        request = state["metadata"]["request"]
        if hasattr(request, "api_keys") and request.api_keys:
            return str(request.api_keys.get(api_key_name)) if request.api_keys.get(api_key_name) else None
    return None
