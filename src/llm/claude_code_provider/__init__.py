"""
Claude Code LangChain Provider

This module provides a LangChain-compatible interface to Claude Code.
"""

from .chat_model import ClaudeCodeChatModel, get_claude_code_model

__all__ = ["ClaudeCodeChatModel", "get_claude_code_model"]
