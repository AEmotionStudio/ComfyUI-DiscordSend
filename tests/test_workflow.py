import unittest
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discordsend_utils.workflow_builder import WorkflowBuilder
from discordsend_utils.prompt_extractor import extract_prompts_from_workflow

class TestWorkflowBuilder(unittest.TestCase):
    """Tests for the WorkflowBuilder class."""

    def setUp(self):
        # A simple standard ComfyUI API JSON format
        self.basic_api_json = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 123,
                    "steps": 20,
                    "cfg": 8,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "original positive prompt",
                    "clip": ["4", 1]
                },
                "_meta": {"title": "Positive Prompt"}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "original negative prompt",
                    "clip": ["4", 1]
                },
                "_meta": {"title": "Negative Prompt"}
            }
        }

    def test_set_prompt_by_title(self):
        """Should update prompts based on node titles."""
        builder = WorkflowBuilder(self.basic_api_json)
        builder.set_prompt("new positive", "new negative")
        
        workflow = builder.get_workflow()
        self.assertEqual(workflow["6"]["inputs"]["text"], "new positive")
        self.assertEqual(workflow["7"]["inputs"]["text"], "new negative")

    def test_set_seed(self):
        """Should update seed in KSampler node."""
        builder = WorkflowBuilder(self.basic_api_json)
        builder.set_seed(999)
        
        workflow = builder.get_workflow()
        self.assertEqual(workflow["3"]["inputs"]["seed"], 999)

    def test_set_steps(self):
        """Should update steps in KSampler node."""
        builder = WorkflowBuilder(self.basic_api_json)
        builder.set_steps(50)
        
        workflow = builder.get_workflow()
        self.assertEqual(workflow["3"]["inputs"]["steps"], 50)

    def test_set_cfg(self):
        """Should update cfg in KSampler node."""
        builder = WorkflowBuilder(self.basic_api_json)
        builder.set_cfg(12.5)
        
        workflow = builder.get_workflow()
        self.assertEqual(workflow["3"]["inputs"]["cfg"], 12.5)

    def test_trace_input_fallback(self):
        """Should update prompts by tracing KSampler inputs if titles are missing."""
        # Remove titles
        api_json = json.loads(json.dumps(self.basic_api_json))
        del api_json["6"]["_meta"]
        del api_json["7"]["_meta"]
        
        builder = WorkflowBuilder(api_json)
        builder.set_prompt("traced positive", "traced negative")
        
        workflow = builder.get_workflow()
        self.assertEqual(workflow["6"]["inputs"]["text"], "traced positive")
        self.assertEqual(workflow["7"]["inputs"]["text"], "traced negative")

class TestPromptExtractor(unittest.TestCase):
    """Tests for the extract_prompts_from_workflow function."""

    def test_extract_from_api_format(self):
        """Should extract prompts from API-style JSON."""
        api_data = {
            "6": {
                "type": "CLIPTextEncode",
                "widgets_values": ["vibrant sunset over ocean"]
            },
            "7": {
                "type": "CLIPTextEncode",
                "widgets_values": ["low quality, blurry, watermark"]
            }
        }
        # Wrapped in a 'nodes' key for the extractor logic
        workflow = {"nodes": api_data}
        
        pos, neg = extract_prompts_from_workflow(workflow)
        self.assertEqual(pos, "vibrant sunset over ocean")
        self.assertEqual(neg, "low quality, blurry, watermark")

    def test_extract_heuristic_negative(self):
        """Should correctly identify negative prompt based on content keywords."""
        api_data = {
            "1": {
                "type": "CLIPTextEncode",
                "widgets_values": ["ugly, deformed, mutated, extra fingers"]
            },
            "2": {
                "type": "CLIPTextEncode",
                "widgets_values": ["a majestic eagle"]
            }
        }
        workflow = {"nodes": api_data}
        
        pos, neg = extract_prompts_from_workflow(workflow)
        self.assertEqual(pos, "a majestic eagle")
        self.assertEqual(neg, "ugly, deformed, mutated, extra fingers")

    def test_extract_single_prompt(self):
        """Should assume single CLIP node is positive."""
        api_data = {
            "1": {
                "type": "CLIPTextEncode",
                "widgets_values": ["solo traveler"]
            }
        }
        workflow = {"nodes": api_data}
        
        pos, neg = extract_prompts_from_workflow(workflow)
        self.assertEqual(pos, "solo traveler")
        self.assertEqual(neg, "")

if __name__ == "__main__":
    unittest.main()
