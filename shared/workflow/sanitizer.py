"""
JSON Sanitization Utilities for ComfyUI-DiscordSend

Provides comprehensive sanitization of sensitive data (webhook URLs, GitHub tokens)
from JSON data structures before export or sharing.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union


# Patterns for detecting sensitive data
WEBHOOK_PATTERNS = [
    r"discord\.com/api/webhooks",
    r"discordapp\.com/api/webhooks",
]

GITHUB_TOKEN_PREFIXES = [
    "ghp_",        # GitHub personal access token
    "github_pat_", # GitHub personal access token (new format)
    "gho_",        # GitHub OAuth token
    "ghs_",        # GitHub service token
    "ghu_",        # GitHub user-to-server token
]


def is_webhook_url(value: str) -> bool:
    """Check if a string appears to be a Discord webhook URL."""
    if not isinstance(value, str):
        return False
    
    for pattern in WEBHOOK_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    
    # Also check for generic webhook patterns in URLs
    if value.startswith("http") and ("webhook" in value.lower() or "discord" in value.lower()):
        return True
    
    return False


def is_github_token(value: str) -> bool:
    """Check if a string appears to be a GitHub token."""
    if not isinstance(value, str):
        return False
    
    for prefix in GITHUB_TOKEN_PREFIXES:
        if value.startswith(prefix):
            return True
    
    return False


def is_potential_token(value: str, context_type: str = "") -> bool:
    """Check if a string might be a token based on length and context."""
    if not isinstance(value, str):
        return False
    
    # Long alphanumeric strings in GitHub-related contexts
    if len(value) >= 40 and "github" in context_type.lower():
        if any(c.isalnum() for c in value):
            return True
    
    return False


def sanitize_string(value: str, context_type: str = "") -> str:
    """
    Sanitize a single string value.
    
    Args:
        value: The string to sanitize
        context_type: Optional context (e.g., node type) to help identify tokens
        
    Returns:
        Empty string if sensitive data detected, original value otherwise
    """
    if is_webhook_url(value):
        return ""
    
    if is_github_token(value):
        return ""
    
    if is_potential_token(value, context_type):
        return ""
    
    return value


def sanitize_widget_values(widgets: List, node_type: str = "") -> List:
    """
    Sanitize a list of widget values from a ComfyUI node.
    
    Args:
        widgets: List of widget values
        node_type: The type of node for context
        
    Returns:
        Sanitized list with sensitive values replaced with empty strings
    """
    result = []
    for value in widgets:
        if isinstance(value, str):
            result.append(sanitize_string(value, node_type))
        elif isinstance(value, dict):
            result.append(sanitize_dict(value))
        elif isinstance(value, list):
            result.append(sanitize_widget_values(value, node_type))
        else:
            result.append(value)
    return result


def sanitize_node_inputs(inputs: Dict, node_type: str = "") -> Dict:
    """
    Sanitize the inputs dictionary of a ComfyUI node.
    
    Args:
        inputs: Dictionary of node inputs
        node_type: The type of node for context
        
    Returns:
        Sanitized dictionary
    """
    result = {}
    for key, value in inputs.items():
        if key in ("webhook_url", "github_token"):
            result[key] = ""
        elif isinstance(value, str):
            result[key] = sanitize_string(value, node_type)
        elif isinstance(value, dict):
            result[key] = sanitize_node_inputs(value, node_type)
        elif isinstance(value, list):
            result[key] = sanitize_widget_values(value, node_type)
        else:
            result[key] = value
    return result


def sanitize_node(node: Dict) -> Dict:
    """
    Sanitize a single ComfyUI node.
    
    Args:
        node: The node dictionary
        
    Returns:
        Sanitized node dictionary
    """
    if not isinstance(node, dict):
        return node
    
    result = dict(node)
    node_type = result.get("type", "")
    
    # Sanitize inputs
    if "inputs" in result and isinstance(result["inputs"], dict):
        result["inputs"] = sanitize_node_inputs(result["inputs"], node_type)
    
    # Sanitize widget values
    if "widgets_values" in result and isinstance(result["widgets_values"], list):
        result["widgets_values"] = sanitize_widget_values(result["widgets_values"], node_type)
    
    return result


def sanitize_dict(data: Dict) -> Dict:
    """
    Recursively sanitize a dictionary.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    result = {}
    
    for key, value in data.items():
        # Handle known sensitive keys
        if key in ("webhook_url", "github_token"):
            result[key] = ""
            continue
        
        # Handle nested structures
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = sanitize_list(value)
        elif isinstance(value, str):
            result[key] = sanitize_string(value)
        else:
            result[key] = value
    
    # Special handling for ComfyUI workflow structure
    if "nodes" in result:
        nodes = result["nodes"]
        if isinstance(nodes, list):
            result["nodes"] = [sanitize_node(n) for n in nodes]
        elif isinstance(nodes, dict):
            result["nodes"] = {k: sanitize_node(v) for k, v in nodes.items()}
    
    return result


def sanitize_list(data: List) -> List:
    """
    Recursively sanitize a list.
    
    Args:
        data: List to sanitize
        
    Returns:
        Sanitized list
    """
    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(sanitize_dict(item))
        elif isinstance(item, list):
            result.append(sanitize_list(item))
        elif isinstance(item, str):
            result.append(sanitize_string(item))
        else:
            result.append(item)
    return result


def sanitize_json_for_export(json_data: Any) -> Any:
    """
    Remove sensitive webhook data and GitHub tokens from JSON data to protect user security.
    
    This is the main entry point for sanitization. It handles:
    - Discord webhook URLs (multiple formats)
    - GitHub personal access tokens (all variants)
    - Nested dictionaries and lists
    - ComfyUI workflow structures
    
    Args:
        json_data: The JSON data object (dict, list, or string) to sanitize
        
    Returns:
        The sanitized JSON data with sensitive information removed
    """
    if json_data is None:
        return None
    
    # Handle string input (may be JSON string or plain string)
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
            result = sanitize_json_for_export(data)
            return json.dumps(result)
        except json.JSONDecodeError:
            # Not valid JSON - check if it's sensitive data directly
            return sanitize_string(json_data)
    
    # Handle dictionary
    if isinstance(json_data, dict):
        return sanitize_dict(json_data)
    
    # Handle list
    if isinstance(json_data, list):
        return sanitize_list(json_data)
    
    # Return other types as-is
    return json_data
