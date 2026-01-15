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


def extract_prompts_from_workflow(workflow_data: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract positive and negative prompts from workflow data.
    
    Analyzes ComfyUI workflow structure to find CLIPTextEncode nodes and
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
    
    # Find CLIPTextEncode nodes
    if "nodes" not in data:
        return None, None
    
    nodes = data["nodes"]
    clip_nodes = _find_clip_text_encode_nodes(nodes)
    
    if not clip_nodes:
        return None, None
    
    # Determine positive/negative based on content and structure
    if len(clip_nodes) == 1:
        # Single CLIP node - assume it's the positive prompt
        positive_prompt = _get_prompt_text(clip_nodes[0])
    elif len(clip_nodes) >= 2:
        # Multiple CLIP nodes - need to determine which is which
        positive_prompt, negative_prompt = _classify_prompts(clip_nodes, data)
    
    # Ensure we return empty string for negative if we have positive but not negative
    if positive_prompt is not None and negative_prompt is None:
        negative_prompt = ""
    
    return positive_prompt, negative_prompt


def _find_clip_text_encode_nodes(nodes: Union[List, Dict]) -> List[Dict]:
    """Find all CLIPTextEncode nodes in the workflow."""
    clip_nodes = []
    
    if isinstance(nodes, list):
        for node in nodes:
            if _is_clip_text_encode(node):
                clip_nodes.append(node)
    elif isinstance(nodes, dict):
        for node_id, node in nodes.items():
            if _is_clip_text_encode(node):
                node_copy = dict(node)
                node_copy["id"] = node_id
                clip_nodes.append(node_copy)
    
    return clip_nodes


def _is_clip_text_encode(node: Any) -> bool:
    """Check if a node is a CLIPTextEncode node with valid text."""
    if not isinstance(node, dict):
        return False
    
    if node.get("type") != "CLIPTextEncode":
        return False
    
    widgets = node.get("widgets_values", [])
    if not isinstance(widgets, list) or len(widgets) == 0:
        return False
    
    # Must have a string value at position 0
    if not isinstance(widgets[0], str):
        return False
    
    return True


def _get_prompt_text(node: Dict) -> Optional[str]:
    """Extract the prompt text from a CLIP node."""
    widgets = node.get("widgets_values", [])
    if widgets and isinstance(widgets[0], str):
        return widgets[0]
    return None


def _classify_prompts(clip_nodes: List[Dict], workflow_data: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify which CLIP nodes contain positive vs negative prompts.
    
    Uses multiple heuristics:
    1. Content analysis (negative prompts often contain quality-related terms)
    2. Connection analysis (traces connections to sampler nodes)
    """
    positive_prompt = None
    negative_prompt = None
    
    # First pass: content-based classification
    for node in clip_nodes:
        prompt_text = _get_prompt_text(node)
        if prompt_text is None:
            continue
        
        prompt_lower = prompt_text.lower()
        
        # Count negative indicators
        negative_matches = sum(1 for indicator in NEGATIVE_INDICATORS if indicator in prompt_lower)
        
        if negative_matches >= 3:
            # Likely a negative prompt
            if negative_prompt is None:
                negative_prompt = prompt_text
        else:
            # Assume positive
            if positive_prompt is None:
                positive_prompt = prompt_text
    
    # Second pass: connection-based classification (if needed)
    if positive_prompt is None or negative_prompt is None:
        positive_prompt, negative_prompt = _classify_by_connections(
            clip_nodes, workflow_data, positive_prompt, negative_prompt
        )
    
    # Fallback: if we still can't determine, use first two nodes
    if positive_prompt is None and negative_prompt is None and len(clip_nodes) >= 2:
        # Convention: assume first is positive, second is negative
        positive_prompt = _get_prompt_text(clip_nodes[0])
        negative_prompt = _get_prompt_text(clip_nodes[1])
    elif positive_prompt is None and negative_prompt is not None:
        # Find the other prompt
        for node in clip_nodes:
            text = _get_prompt_text(node)
            if text != negative_prompt:
                positive_prompt = text
                break
    elif negative_prompt is None and positive_prompt is not None:
        # Find the other prompt
        for node in clip_nodes:
            text = _get_prompt_text(node)
            if text != positive_prompt:
                negative_prompt = text
                break
    
    return positive_prompt, negative_prompt


def _classify_by_connections(
    clip_nodes: List[Dict],
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
        for clip_node in clip_nodes:
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
