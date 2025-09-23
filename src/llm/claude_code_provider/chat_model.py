"""
Claude Code LangChain Chat Model

A LangChain-compatible chat model that uses Claude Code CLI under the hood.
"""

import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Type, Union

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field


class _ClaudeCodeStructuredOutputRunnable(Runnable[Any, Any]):
    """A runnable that wraps ClaudeCodeChatModel to provide structured output."""

    def __init__(
        self,
        chat_model: "ClaudeCodeChatModel",
        schema: Union[Dict[str, Any], Type[BaseModel]],
        method: str = "function_calling",
        **kwargs: Any,
    ):
        self.chat_model = chat_model
        self.schema = schema
        self.method = method
        self.kwargs = kwargs

    def invoke(self, input: Any, config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Invoke the chat model and parse the response to structured output."""
        # Get the response from the chat model
        response = self.chat_model.invoke(input, config, **kwargs)

        # Extract content from the response
        if hasattr(response, "content"):
            content = str(response.content)
        else:
            content = str(response)

        # Try to parse as JSON first
        try:
            # Look for JSON in markdown code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                if json_end != -1:
                    json_str = content[json_start:json_end].strip()
                    parsed_data = json.loads(json_str)
                else:
                    # If no closing ```, try to parse the rest as JSON
                    json_str = content[json_start:].strip()
                    parsed_data = json.loads(json_str)
            else:
                # Try to parse the entire content as JSON
                parsed_data = json.loads(content)

            # Create the Pydantic model instance
            if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                return self.schema(**parsed_data)
            else:
                return parsed_data

        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, try to extract JSON more aggressively
            try:
                # Look for { or [ in the content
                start_chars = ["{", "["]
                for start_char in start_chars:
                    start_idx = content.find(start_char)
                    if start_idx != -1:
                        # Find the matching closing character
                        end_char = "}" if start_char == "{" else "]"
                        depth = 0
                        for i, char in enumerate(content[start_idx:], start_idx):
                            if char == start_char:
                                depth += 1
                            elif char == end_char:
                                depth -= 1
                                if depth == 0:
                                    json_str = content[start_idx:i + 1]
                                    parsed_data = json.loads(json_str)
                                    if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                                        return self.schema(**parsed_data)
                                    else:
                                        return parsed_data
            except (json.JSONDecodeError, ValueError):
                pass

            # If all JSON parsing fails, create a default response
            if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                # Create default values for all fields
                default_values: Dict[str, Any] = {}
                for field_name, field in self.schema.model_fields.items():
                    if field.annotation == str:
                        default_values[field_name] = f"Error parsing response: {str(e)}"
                    elif field.annotation == float:
                        default_values[field_name] = 0.0
                    elif field.annotation == int:
                        default_values[field_name] = 0
                    elif hasattr(field.annotation, "__origin__") and getattr(field.annotation, "__origin__") == dict:
                        default_values[field_name] = {}
                    else:
                        # For other types (like Literal), try to use the first allowed value
                        if hasattr(field.annotation, "__args__") and getattr(field.annotation, "__args__"):
                            default_values[field_name] = getattr(field.annotation, "__args__")[0]
                        else:
                            default_values[field_name] = None
                return self.schema(**default_values)
            else:
                return {"error": f"Failed to parse response: {str(e)}", "raw_content": content}


class ClaudeCodeChatModel(BaseChatModel):
    """
    A LangChain chat model that uses Claude Code CLI.

    This model provides a LangChain-compatible interface to Claude Code,
    allowing it to be used as a drop-in replacement for other chat models.
    """

    model_name: str = Field(default="sonnet")
    temperature: float = Field(default=0.1)
    max_tokens: Optional[int] = Field(default=4000)

    @property
    def _llm_type(self) -> str:
        """Return identifier for the model type."""
        return "claude-code"

    def with_structured_output(
        self,
        schema: Union[Dict[str, Any], Type[BaseModel]],
        *,
        method: str = "function_calling",
        **kwargs: Any,
    ) -> Runnable[Any, Any]:
        """Return a runnable that outputs structured data."""
        return _ClaudeCodeStructuredOutputRunnable(chat_model=self, schema=schema, method=method, **kwargs)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using Claude Code CLI."""

        # Convert messages to a format suitable for Claude Code
        conversation = self._format_messages(messages)

        try:
            # Use Claude Code CLI to generate response
            response_text = self._call_claude_code(conversation)

            # Create the response message
            message = AIMessage(content=response_text)
            generation = ChatGeneration(message=message)

            return ChatResult(generations=[generation])

        except Exception as e:
            # Fallback to a basic response if Claude Code fails
            fallback_message = AIMessage(content=f"Claude Code is not available. Error: {str(e)}")
            generation = ChatGeneration(message=fallback_message)
            return ChatResult(generations=[generation])

    def _format_messages(self, messages: List[BaseMessage]) -> str:
        """Convert LangChain messages to a conversation string."""
        conversation_parts = []

        for message in messages:
            if isinstance(message, HumanMessage):
                conversation_parts.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                conversation_parts.append(f"Assistant: {message.content}")
            elif isinstance(message, SystemMessage):
                conversation_parts.append(f"System: {message.content}")
            else:
                conversation_parts.append(f"Unknown: {message.content}")

        return "\n\n".join(conversation_parts)

    def _call_claude_code(self, conversation: str) -> str:
        """
        Call Claude Code CLI to generate a response.

        This method attempts to use the Claude Code CLI. If it's not available,
        it falls back to using langchain-anthropic.
        """

        # Check if Claude Code CLI is available
        try:
            subprocess.run(["claude", "--version"], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # Claude Code CLI not available, fallback to langchain-anthropic
            return self._fallback_to_anthropic(conversation)

        try:
            # Call Claude Code CLI with --print flag and pass conversation as argument
            result = subprocess.run(
                ["claude", "--print", "--model", self.model_name, conversation],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # If Claude Code fails, fallback to anthropic
                return self._fallback_to_anthropic(conversation)

        except subprocess.TimeoutExpired:
            return self._fallback_to_anthropic(conversation)

    def _fallback_to_anthropic(self, conversation: str) -> str:
        """
        Fallback to using langchain-anthropic when Claude Code is not available.
        """
        try:
            from langchain_anthropic import ChatAnthropic

            # Map Claude Code model names to Anthropic model names
            model_mapping = {"sonnet": "claude-3-5-sonnet-20241022", "opus": "claude-3-opus-20240229"}

            model_name = model_mapping.get(self.model_name, "claude-3-5-sonnet-20241022")

            anthropic_model = ChatAnthropic(model=model_name)  # type: ignore

            # Convert conversation back to messages for anthropic
            human_message = HumanMessage(content=conversation)
            result = anthropic_model.invoke([human_message])

            return str(result.content)

        except ImportError:
            return "Error: Neither Claude Code nor langchain-anthropic is available."
        except Exception as e:
            return f"Error calling fallback model: {str(e)}"


def get_claude_code_model(model_name: str = "sonnet") -> ClaudeCodeChatModel:
    """
    Factory function to create a Claude Code chat model.

    Args:
        model_name: The Claude Code model to use ("sonnet" or "opus")

    Returns:
        A ClaudeCodeChatModel instance
    """
    return ClaudeCodeChatModel(model_name=model_name)
