import json
import random
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

class WorkflowBuilder:
    """Helper to manipulate ComfyUI workflow JSONs."""

    def __init__(self, workflow_json: Dict[str, Any]):
        self.workflow = workflow_json
        # Create lookups
        self._nodes = self.workflow
        if "nodes" in self.workflow and isinstance(self.workflow["nodes"], list):
             # Handle "graph" format vs "api" format if needed. 
             # But usually for API we stick to the {node_id: node_data} format.
             # If input is graph format, it might need conversion or distinct handling.
             # Assuming API format for now as that's what's sent to /prompt.
             pass

    @classmethod
    def from_json_string(cls, json_str: str) -> 'WorkflowBuilder':
        """Load from JSON int."""
        return cls(json.loads(json_str))

    def get_workflow(self) -> Dict[str, Any]:
        """Get the current workflow dict."""
        return self.workflow

    def set_prompt(self, positive: str, negative: Optional[str] = None) -> None:
        """
        Attempt to set positive and negative prompts.
        Heuristics:
        - Look for CLIPTextEncode nodes.
        - Often one is connected to KSampler 'positive' and one to 'negative'.
        - Or look for custom titles like 'Positive Prompt', 'Negative Prompt'.
        """
        # Simple heuristic: Find CLIPTextEncode nodes
        # If we have title/coloring, we can use that.
        # Otherwise, we might need graph traversal to see what connects to KSampler.
        
        # For MVP, let's assume standard ComfyUI structure or look for specific titles first
        
        positive_node_id = self._find_node_by_title("Positive Prompt")
        negative_node_id = self._find_node_by_title("Negative Prompt")
        
        # Fallback: Find KSampler and trace back
        if not positive_node_id or not negative_node_id:
            ksampler_id, ksampler = self._find_node_by_class("KSampler")
            if ksampler:
                # KSampler inputs: model, positive, negative, latent_image
                if not positive_node_id:
                    positive_node_id = self._trace_input(ksampler, "positive")
                if not negative_node_id:
                    negative_node_id = self._trace_input(ksampler, "negative")

        if positive_node_id:
            self._update_node_input(positive_node_id, "text", positive)
        else:
            logger.warning("Could not identify Positive Prompt node.")

        if negative and negative_node_id:
            self._update_node_input(negative_node_id, "text", negative)
        elif negative:
            logger.warning("Could not identify Negative Prompt node.")

    def set_seed(self, seed: int) -> int:
        """Set seed on KSampler nodes or Seed nodes."""
        # Find KSampler or anything with a 'seed' widget
        updated = False
        for node_id, node in self.workflow.items():
            if "inputs" in node:
                if "seed" in node["inputs"]:
                    # Ensure it's an int widget, not a link
                    if isinstance(node["inputs"]["seed"], (int, float)) or (isinstance(node["inputs"]["seed"], str) and node["inputs"]["seed"].isdigit()):
                        node["inputs"]["seed"] = seed
                        updated = True
                if "noise_seed" in node["inputs"]:
                     # Some nodes call it noise_seed
                     if isinstance(node["inputs"]["noise_seed"], (int, float)):
                        node["inputs"]["noise_seed"] = seed
                        updated = True
                        
        if not updated:
            logger.warning("Could not find any seed inputs to update.")
        return seed

    def set_image_dimensions(self, width: int, height: int) -> None:
        """Set width and height on EmptyLatentImage nodes."""
        node_id, _ = self._find_node_by_class("EmptyLatentImage")
        if node_id:
            self._update_node_input(node_id, "width", width)
            self._update_node_input(node_id, "height", height)

    def set_steps(self, steps: int) -> None:
        """Set steps on KSampler."""
        ksampler_ids = self._find_nodes_by_class("KSampler")
        for nid in ksampler_ids:
            self._update_node_input(nid, "steps", steps)

    def set_cfg(self, cfg: float) -> None:
        """Set CFG scale on KSampler."""
        ksampler_ids = self._find_nodes_by_class("KSampler")
        for nid in ksampler_ids:
            self._update_node_input(nid, "cfg", cfg)

    def _find_node_by_title(self, title: str) -> Optional[str]:
        """Find node by its custom title (`_meta.title`)."""
        for node_id, node in self.workflow.items():
            if "_meta" in node and node["_meta"].get("title") == title:
                return node_id
        return None

    def _find_node_by_class(self, class_type: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Find first node of a specific class type."""
        for node_id, node in self.workflow.items():
            if node.get("class_type") == class_type:
                return node_id, node
        return None, None

    def _find_nodes_by_class(self, class_type: str) -> List[str]:
        """Find all nodes of a specific class type."""
        ids = []
        for node_id, node in self.workflow.items():
            if node.get("class_type") == class_type:
                ids.append(node_id)
        return ids

    def _trace_input(self, node: Dict, input_name: str) -> Optional[str]:
        """
        Trace back an input link to find the source node.
        Input format in API JSON: "input_name": ["source_node_id", slot_index]
        """
        if "inputs" not in node or input_name not in node["inputs"]:
            return None
        
        link = node["inputs"][input_name]
        # Link structure: [node_id, slot_idx]
        if isinstance(link, list) and len(link) == 2:
            return str(link[0])
        return None

    def _update_node_input(self, node_id: str, input_name: str, value: Any) -> None:
        if node_id in self.workflow and "inputs" in self.workflow[node_id]:
            self.workflow[node_id]["inputs"][input_name] = value
