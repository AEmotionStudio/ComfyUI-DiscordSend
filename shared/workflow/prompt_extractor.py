"""
Prompt Extraction Utilities for ComfyUI-DiscordSend

Extracts positive and negative prompts from ComfyUI workflow data.
"""

import json
from typing import Any, Dict, List, Optional, Tuple, Union


# Common negative prompt indicators
NEGATIVE_INDICATORS = [
    "bad quality", "deformed", "blurry", "low quality", "worst quality",
    "ugly", "disfigured", "low res", "poorly drawn", "mutation",
    "extra limbs", "bad anatomy", "watermark", "text", "signature"
]

# Node types that can contain prompts
PROMPT_NODE_TYPES = [
    "CLIPTextEncode",      # Standard SD 1.5 prompt node
    "SDXLPromptEncoder",   # SDXL prompt encoder
    "SDXLTextEncode",      # Another SDXL text node
]


def extract_prompts_from_workflow(workflow_data: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract positive and negative prompts from workflow data.

    Analyzes ComfyUI workflow structure to find prompt nodes (CLIPTextEncode,
    SDXLPromptEncoder, SDXLTextEncode, and other text encoding nodes) and
    determine which contains the positive vs negative prompt.

    Args:
        workflow_data: The workflow data dictionary or JSON string

    Returns:
        A tuple of (positive_prompt, negative_prompt) or (None, None) if not found
    """
    if workflow_data is None:
        return None, None
    
    # Convert string to dict if necessary
    if isinstance(workflow_data, str):
        try:
            data = json.loads(workflow_data)
        except json.JSONDecodeError:
            return None, None
    else:
        data = workflow_data
    
    if not isinstance(data, dict):
        return None, None
    
    positive_prompt = None
    negative_prompt = None
    
    # Find prompt nodes (CLIPTextEncode, SDXL nodes, etc.)
    if "nodes" in data:
        nodes = data["nodes"]
    else:
        # Check if it's API format (dict of nodes)
        nodes = data

    prompt_nodes = _find_prompt_nodes(nodes)

    if not prompt_nodes:
        return None, None
    
    # Determine positive/negative based on content and structure
    if len(prompt_nodes) == 1:
        # Single prompt node - assume it's the positive prompt
        positive_prompt = _get_prompt_text(prompt_nodes[0])
    elif len(prompt_nodes) >= 2:
        # Multiple prompt nodes - need to determine which is which
        positive_prompt, negative_prompt = _classify_prompts(prompt_nodes, data)
    
    # Ensure we return empty string for negative if we have positive but not negative
    if positive_prompt is not None and negative_prompt is None:
        negative_prompt = ""
    
    return positive_prompt, negative_prompt


def _find_prompt_nodes(nodes: Union[List, Dict]) -> List[Dict]:
    """Find all prompt nodes (CLIPTextEncode, SDXL nodes, etc.) in the workflow."""
    prompt_nodes = []

    if isinstance(nodes, list):
        for node in nodes:
            if _is_prompt_node(node):
                prompt_nodes.append(node)
    elif isinstance(nodes, dict):
        for node_id, node in nodes.items():
            if _is_prompt_node(node):
                node_copy = dict(node)
                node_copy["id"] = node_id
                prompt_nodes.append(node_copy)

    return prompt_nodes


def _is_prompt_node(node: Any) -> bool:
    """Check if a node is a prompt node (CLIPTextEncode, SDXL, etc.) with valid text."""
    if not isinstance(node, dict):
        return False

    # Handle both Workflow format (type) and API format (class_type)
    node_type = node.get("type") or node.get("class_type")

    # Check against known prompt node types
    if node_type not in PROMPT_NODE_TYPES:
        # Also check for dynamic text/prompt nodes (e.g., custom nodes)
        if node_type and ("Text" in node_type and ("Encode" in node_type or "Prompt" in node_type)):
            pass  # Allow these through
        else:
            return False

    # Check for text in either widgets_values (Workflow) or inputs (API)
    text = _get_prompt_text(node)
    return text is not None


def _get_prompt_text(node: Dict) -> Optional[str]:
    """Extract the prompt text from a prompt node."""
    # Workflow format (widgets_values)
    widgets = node.get("widgets_values", [])
    if isinstance(widgets, list) and len(widgets) > 0 and isinstance(widgets[0], str):
        return widgets[0]
        
    # API format (inputs.text)
    inputs = node.get("inputs", {})
    if isinstance(inputs, dict) and isinstance(inputs.get("text"), str):
        return inputs.get("text")
        
    return None


def _classify_prompts(prompt_nodes: List[Dict], workflow_data: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify which prompt nodes contain positive vs negative prompts.

    Uses multiple heuristics:
    1. Content analysis (negative prompts often contain quality-related terms)
    2. Connection analysis (traces connections to sampler nodes)
    """
    if not prompt_nodes:
        return None, None
        
    # First pass: Score all nodes based on content
    node_scores = []
    for node in prompt_nodes:
        prompt_text = _get_prompt_text(node)
        # Skip empty or None text
        if not prompt_text or not prompt_text.strip():
            continue
            
        prompt_lower = prompt_text.lower()
        score = sum(1 for indicator in NEGATIVE_INDICATORS if indicator in prompt_lower)
        node_scores.append((node, score, prompt_text))
    
    if not node_scores:
        return None, None

    # Sort by score descending (highest score first for negative)
    node_scores.sort(key=lambda x: x[1], reverse=True)
    
    positive_prompt = None
    negative_prompt = None
    
    # Highest score is likely negative (if score > 0)
    if node_scores[0][1] > 0:
        negative_prompt = node_scores[0][2]
        # The node with the lowest score is likely the positive prompt
        # Since it's sorted descending, pick the last one
        positive_prompt = node_scores[-1][2]
        
        # If we have more than 2 nodes and the last one is NOT the only zero-score node,
        # we might need more logic, but for 2 nodes, this is correct.
        # If positive and negative are the same (only 1 node with score > 0), clear positive.
        if positive_prompt == negative_prompt:
            positive_prompt = None
    else:
        # All scores are 0, use connection analysis
        positive_prompt, negative_prompt = _classify_by_connections(
            prompt_nodes, workflow_data, None, None
        )
        
    # Fallback: if we still can't determine, use first two nodes
    if positive_prompt is None and negative_prompt is None and len(prompt_nodes) >= 2:
        # Convention: assume first is positive, second is negative
        positive_prompt = _get_prompt_text(prompt_nodes[0])
        negative_prompt = _get_prompt_text(prompt_nodes[1])
    elif positive_prompt is None and negative_prompt is not None:
        # Find the other prompt
        for _, _, text in node_scores:
            if text != negative_prompt:
                positive_prompt = text
                break
    elif negative_prompt is None and positive_prompt is not None:
        # Find the other prompt
        for _, _, text in node_scores:
            if text != positive_prompt:
                negative_prompt = text
                break
    
    return positive_prompt, negative_prompt


def _classify_by_connections(
    prompt_nodes: List[Dict],
    workflow_data: Dict,
    existing_positive: Optional[str],
    existing_negative: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Try to classify prompts by analyzing node connections to samplers."""
    positive = existing_positive
    negative = existing_negative
    
    links = workflow_data.get("links", [])
    if not isinstance(links, list):
        return positive, negative
    
    nodes = workflow_data.get("nodes", [])
    
    # Find sampler nodes
    samplers = []
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict) and "KSampler" in node.get("type", ""):
                samplers.append(node)
    elif isinstance(nodes, dict):
        for node_id, node in nodes.items():
            if isinstance(node, dict) and "KSampler" in node.get("type", ""):
                node_copy = dict(node)
                node_copy["id"] = node_id
                samplers.append(node_copy)
    
    if not samplers:
        return positive, negative
    
    # Trace connections from CLIP nodes to samplers
    for link in links:
        if len(link) < 4:
            continue
        
        from_node_id = link[0]
        to_node_id = link[2]
        to_slot = link[3]
        
        # Find matching CLIP node and sampler
        for clip_node in prompt_nodes:
            clip_id = clip_node.get("id")
            if clip_id == from_node_id:
                for sampler in samplers:
                    if sampler.get("id") == to_node_id:
                        # Determine slot type
                        inputs = sampler.get("inputs", {})
                        if isinstance(inputs, dict):
                            input_keys = list(inputs.keys())
                            if to_slot < len(input_keys):
                                input_name = input_keys[to_slot].lower()
                                prompt_text = _get_prompt_text(clip_node)
                                
                                if "positive" in input_name and positive is None:
                                    positive = prompt_text
                                elif "negative" in input_name and negative is None:
                                    negative = prompt_text
    
    return positive, negative
