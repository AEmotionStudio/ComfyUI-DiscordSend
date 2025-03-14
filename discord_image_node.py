import os
import datetime
import json
import time
import numpy as np
from PIL import Image
import torch
import folder_paths
from PIL.PngImagePlugin import PngInfo
from comfy.cli_args import args
import re
import cv2
import requests
from io import BytesIO
from uuid import uuid4
from typing import Any, Union, List, Optional
from pathlib import Path
import base64

class SaveImage:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI", "tooltip": "The prefix for the file to save."})
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = "image"
    DESCRIPTION = "Saves the input images to your ComfyUI output directory."

    def save_images(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    # Final sanitization check before embedding
                    sanitized_prompt = sanitize_json_for_export(prompt)
                    metadata.add_text("prompt", json.dumps(sanitized_prompt))
                if extra_pnginfo is not None:
                    # Final sanitization check before embedding
                    sanitized_extra_pnginfo = sanitize_json_for_export(extra_pnginfo)
                    for x in sanitized_extra_pnginfo:
                        if x == "workflow":
                            # Extra sanitization for workflow data
                            workflow_data = sanitize_json_for_export(sanitized_extra_pnginfo[x])
                            metadata.add_text(x, json.dumps(workflow_data))
                        else:
                            metadata.add_text(x, json.dumps(sanitized_extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        return { "ui": { "images": results } }

# Helper function to convert tensor to OpenCV format
def tensor_to_cv(tensor: torch.Tensor) -> np.ndarray:
    """Convert a PyTorch tensor to an OpenCV-compatible numpy array."""
    return np.clip(tensor.squeeze().cpu().numpy() * 255, 0, 255).astype(np.uint8)

# Helper function to sanitize JSON data by removing webhook information
def sanitize_json_for_export(json_data):
    """
    Remove sensitive webhook data and GitHub tokens from JSON data to protect user security.
    
    Parameters:
        json_data: The JSON data object (dict) or string to sanitize
        
    Returns:
        The sanitized JSON data with webhook information and GitHub tokens removed
    """
    if json_data is None:
        return None
        
    # Convert string to dict if necessary
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            # If not valid JSON, return as is
            return json_data
    else:
        data = json.loads(json.dumps(json_data))
    
    if not isinstance(data, dict):
        return json_data
    
    # Create a deep copy to avoid modifying the original
    sanitized_data = json.loads(json.dumps(data))
    
    # Sanitize the workflow data (remove webhook URLs and GitHub tokens)
    if "nodes" in sanitized_data:
        # Handle the case where nodes is a list (not a dictionary)
        if isinstance(sanitized_data["nodes"], list):
            for node in sanitized_data["nodes"]:
                if isinstance(node, dict):
                    # Check for webhook_url and github_token in inputs
                    if "inputs" in node and isinstance(node["inputs"], dict):
                        inputs = node["inputs"]
                        if "webhook_url" in inputs:
                            inputs["webhook_url"] = ""
                            print("Removed webhook URL from workflow JSON for security")
                        if "github_token" in inputs:
                            inputs["github_token"] = ""
                            print("Removed GitHub token from workflow JSON for security")
                        
                        # If inputs has any fields that are dictionaries, check them too
                        for input_name, input_value in inputs.items():
                            if isinstance(input_value, dict):
                                if "webhook_url" in input_value:
                                    input_value["webhook_url"] = ""
                                    print(f"Removed nested webhook URL from {input_name} in workflow JSON")
                                if "github_token" in input_value:
                                    input_value["github_token"] = ""
                                    print(f"Removed nested GitHub token from {input_name} in workflow JSON")
                    
                    # Check for webhook URL or GitHub token in widgets_values array
                    if "widgets_values" in node and isinstance(node["widgets_values"], list):
                        # First method: check for Discord/GitHub node by type
                        is_sensitive_node = False
                        if "type" in node and isinstance(node["type"], str):
                            # Check for any node that might contain Discord, webhook, or GitHub in its name
                            if ("Discord" in node["type"] or "discord" in node["type"] or 
                                "webhook" in node["type"].lower() or "github" in node["type"].lower()):
                                is_sensitive_node = True
                                
                        # Thoroughly scan all widget values for sensitive data regardless of node type
                        for i, value in enumerate(node["widgets_values"]):
                            # Check for sensitive data in any string value
                            if isinstance(value, str):
                                # Look for Discord webhook URLs
                                if "discord.com/api/webhooks" in value:
                                    node["widgets_values"][i] = ""
                                    print(f"Removed webhook URL from widgets_values[{i}] for security")
                                # Check for other webhook patterns
                                elif value.startswith("http") and ("webhook" in value.lower() or "discord" in value.lower()):
                                    node["widgets_values"][i] = ""
                                    print(f"Removed potential webhook URL from widgets_values[{i}] for security")
                                # Check for GitHub tokens
                                elif (value.startswith("ghp_") or  # GitHub personal access token
                                      value.startswith("github_pat_") or  # GitHub personal access token
                                      value.startswith("gho_") or  # GitHub OAuth token
                                      value.startswith("ghs_") or  # GitHub service token
                                      value.startswith("ghu_")):  # GitHub user-to-server token
                                    node["widgets_values"][i] = ""
                                    print(f"Removed GitHub token from widgets_values[{i}] for security")
                                # Check for generic tokens that could be GitHub tokens
                                elif len(value) >= 40 and "github" in node.get("type", "").lower() and any(c.isalnum() for c in value):
                                    node["widgets_values"][i] = ""
                                    print(f"Removed potential GitHub token from widgets_values[{i}] for security")
        
        # Handle the case where nodes is a dictionary (node_id -> node)
        elif isinstance(sanitized_data["nodes"], dict):
            for node_id, node in sanitized_data["nodes"].items():
                if isinstance(node, dict):
                    # Check for webhook_url and github_token in inputs
                    if "inputs" in node and isinstance(node["inputs"], dict):
                        inputs = node["inputs"]
                        if "webhook_url" in inputs:
                            inputs["webhook_url"] = ""
                            print("Removed webhook URL from workflow JSON for security")
                        if "github_token" in inputs:
                            inputs["github_token"] = ""
                            print("Removed GitHub token from workflow JSON for security")
                        
                        # If inputs has any fields that are dictionaries, check them too
                        for input_name, input_value in inputs.items():
                            if isinstance(input_value, dict):
                                if "webhook_url" in input_value:
                                    input_value["webhook_url"] = ""
                                    print(f"Removed nested webhook URL from {input_name} in workflow JSON")
                                if "github_token" in input_value:
                                    input_value["github_token"] = ""
                                    print(f"Removed nested GitHub token from {input_name} in workflow JSON")
                    
                    # Check for webhook URL or GitHub token in widgets_values array
                    if "widgets_values" in node and isinstance(node["widgets_values"], list):
                        # First method: check for Discord/GitHub node by type
                        is_sensitive_node = False
                        if "type" in node and isinstance(node["type"], str):
                            # Check for any node that might contain Discord, webhook, or GitHub in its name
                            if ("Discord" in node["type"] or "discord" in node["type"] or 
                                "webhook" in node["type"].lower() or "github" in node["type"].lower()):
                                is_sensitive_node = True
                                
                        # Thoroughly scan all widget values for sensitive data regardless of node type
                        for i, value in enumerate(node["widgets_values"]):
                            # Check for sensitive data in any string value
                            if isinstance(value, str):
                                # Look for Discord webhook URLs
                                if "discord.com/api/webhooks" in value:
                                    node["widgets_values"][i] = ""
                                    print(f"Removed webhook URL from widgets_values[{i}] for security")
                                # Check for other webhook patterns
                                elif value.startswith("http") and ("webhook" in value.lower() or "discord" in value.lower()):
                                    node["widgets_values"][i] = ""
                                    print(f"Removed potential webhook URL from widgets_values[{i}] for security")
                                # Check for GitHub tokens
                                elif (value.startswith("ghp_") or  # GitHub personal access token
                                      value.startswith("github_pat_") or  # GitHub personal access token
                                      value.startswith("gho_") or  # GitHub OAuth token
                                      value.startswith("ghs_") or  # GitHub service token
                                      value.startswith("ghu_")):  # GitHub user-to-server token
                                    node["widgets_values"][i] = ""
                                    print(f"Removed GitHub token from widgets_values[{i}] for security")
                                # Check for generic tokens that could be GitHub tokens
                                elif len(value) >= 40 and "github" in node.get("type", "").lower() and any(c.isalnum() for c in value):
                                    node["widgets_values"][i] = ""
                                    print(f"Removed potential GitHub token from widgets_values[{i}] for security")
    
    # Also handle extra_pnginfo format where there might be direct sensitive data
    if "webhook_url" in sanitized_data:
        sanitized_data["webhook_url"] = ""
        print("Removed top-level webhook URL from JSON data")
    
    if "github_token" in sanitized_data:
        sanitized_data["github_token"] = ""
        print("Removed top-level GitHub token from JSON data")
    
    # Recursively check for sensitive data in nested dictionaries
    def check_nested_dict(d):
        if isinstance(d, dict):
            # Check for direct sensitive keys
            if "webhook_url" in d:
                d["webhook_url"] = ""
                print("Removed nested webhook URL from JSON structure")
            if "github_token" in d:
                d["github_token"] = ""
                print("Removed nested GitHub token from JSON structure")
                
            # Recursively check all key-value pairs
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    check_nested_dict(v)
                # Check if any string value looks like a GitHub token
                elif isinstance(v, str):
                    if (v.startswith("ghp_") or v.startswith("github_pat_") or 
                        v.startswith("gho_") or v.startswith("ghs_") or v.startswith("ghu_")):
                        d[k] = ""
                        print(f"Removed a GitHub token from field '{k}' in JSON structure")
        elif isinstance(d, list):
            for i, item in enumerate(d):
                if isinstance(item, (dict, list)):
                    check_nested_dict(item)
                # Check for webhook URLs or GitHub tokens in string items of lists
                elif isinstance(item, str):
                    if "discord.com/api/webhooks" in item:
                        # Can't modify the string directly, but this will at least print a warning
                        print("Warning: Found webhook URL in a list item that cannot be directly sanitized")
                    elif (item.startswith("ghp_") or item.startswith("github_pat_") or 
                          item.startswith("gho_") or item.startswith("ghs_") or item.startswith("ghu_")):
                        print("Warning: Found GitHub token in a list item that cannot be directly sanitized")
    
    # Apply the recursive check
    check_nested_dict(sanitized_data)
    
    return sanitized_data

# Helper function to extract prompts from workflow data
def extract_prompts_from_workflow(workflow_data):
    """
    Extract positive and negative prompts from workflow data.
    
    Parameters:
        workflow_data: The workflow data dictionary or object
        
    Returns:
        A tuple of (positive_prompt, negative_prompt) or (None, None) if not found
    """
    print("extract_prompts_from_workflow called with workflow data")
    
    if workflow_data is None:
        print("extract_prompts_from_workflow: workflow_data is None")
        return None, None
    
    # Convert string to dict if necessary
    if isinstance(workflow_data, str):
        try:
            data = json.loads(workflow_data)
            print("extract_prompts_from_workflow: converted string to JSON")
        except json.JSONDecodeError:
            print("extract_prompts_from_workflow: failed to decode JSON string")
            return None, None
    else:
        data = workflow_data
    
    if not isinstance(data, dict):
        print(f"extract_prompts_from_workflow: data is not a dict, but {type(data)}")
        return None, None
    
    positive_prompt = None
    negative_prompt = None
    
    # Basic approach: find CLIPTextEncode nodes and extract their text
    if "nodes" in data:
        nodes = data["nodes"]
        print(f"extract_prompts_from_workflow: Found nodes key with {len(nodes)} items")
        
        # Handle list-based nodes structure
        if isinstance(nodes, list):
            clip_text_encode_nodes = []
            
            # Collect all CLIP nodes
            for node in nodes:
                if isinstance(node, dict) and "type" in node and node["type"] == "CLIPTextEncode":
                    if "widgets_values" in node and isinstance(node["widgets_values"], list) and len(node["widgets_values"]) > 0:
                        clip_text_encode_nodes.append(node)
            
            print(f"extract_prompts_from_workflow: Found {len(clip_text_encode_nodes)} CLIP nodes in list structure")
            
            # If we have exactly 2 CLIP nodes, determine which is which
            if len(clip_text_encode_nodes) == 2:
                # Try to determine by examining the text content first
                # Negative prompts often contain terms like "bad quality", "deformed", etc.
                negative_indicators = ["bad quality", "deformed", "blurry", "low quality", "worst quality",
                                      "ugly", "disfigured", "low res", "deformed", "poorly drawn", "mutation"]
                
                for node in clip_text_encode_nodes:
                    prompt_text = node["widgets_values"][0].lower()
                    # Check if this prompt contains negative indicators
                    matches = sum(1 for indicator in negative_indicators if indicator in prompt_text)
                    
                    if matches >= 3:  # If we have multiple matches, likely negative
                        negative_prompt = node["widgets_values"][0]
                    else:
                        # Assume it's positive if not strongly negative
                        positive_prompt = node["widgets_values"][0]
                
                # If we couldn't determine based on content, try with connections if links exist
                if (positive_prompt is None or negative_prompt is None) and "links" in data:
                    links = data["links"]
                    samplers = []
                    
                    # Find all KSampler nodes first
                    for node in nodes:
                        if isinstance(node, dict) and "type" in node and "KSampler" in node["type"]:
                            samplers.append(node)
                    
                    # If we found samplers, try to trace connections
                    if samplers and isinstance(links, list):
                        for link in links:
                            if len(link) >= 4:
                                from_node_id = link[0]
                                to_node_id = link[2]
                                to_slot = link[3]
                                
                                # Check if this link connects a CLIP node to a sampler
                                for clip_node in clip_text_encode_nodes:
                                    if clip_node.get("id") == from_node_id:
                                        for sampler in samplers:
                                            if sampler.get("id") == to_node_id:
                                                # Check which input slot this connects to
                                                if "inputs" in sampler and isinstance(sampler["inputs"], dict):
                                                    input_keys = list(sampler["inputs"].keys())
                                                    if to_slot < len(input_keys):
                                                        input_name = input_keys[to_slot]
                                                        
                                                        if "positive" in input_name.lower():
                                                            positive_prompt = clip_node["widgets_values"][0]
                                                        elif "negative" in input_name.lower():
                                                            negative_prompt = clip_node["widgets_values"][0]
                
                # If we still couldn't determine, go with our defaults
                if positive_prompt is None and negative_prompt is None:
                    # Simply swap them (assuming first is negative, second is positive)
                    negative_prompt = clip_text_encode_nodes[0]["widgets_values"][0]
                    positive_prompt = clip_text_encode_nodes[1]["widgets_values"][0]
                elif positive_prompt is None:  # Only negative was found
                    # Find the other one
                    for node in clip_text_encode_nodes:
                        if node["widgets_values"][0] != negative_prompt:
                            positive_prompt = node["widgets_values"][0]
                            break
                elif negative_prompt is None:  # Only positive was found
                    # Find the other one
                    for node in clip_text_encode_nodes:
                        if node["widgets_values"][0] != positive_prompt:
                            negative_prompt = node["widgets_values"][0]
                            break
            
            # If we have only one CLIP node, assume it's positive
            elif len(clip_text_encode_nodes) == 1:
                positive_prompt = clip_text_encode_nodes[0]["widgets_values"][0]
        
        # Handle dict-based nodes structure
        elif isinstance(nodes, dict):
            clip_text_encode_nodes = []
            
            # Find all CLIPTextEncode nodes
            for node_id, node in nodes.items():
                if isinstance(node, dict) and "type" in node and node["type"] == "CLIPTextEncode":
                    if "widgets_values" in node and isinstance(node["widgets_values"], list) and len(node["widgets_values"]) > 0:
                        # Store ID for reference
                        node_with_id = node.copy()
                        node_with_id["id"] = node_id
                        clip_text_encode_nodes.append(node_with_id)
            
            # Same process as above, but for dict-based structure
            if len(clip_text_encode_nodes) == 2:
                # Try to determine by examining the text content first
                negative_indicators = ["bad quality", "deformed", "blurry", "low quality", "worst quality",
                                      "ugly", "disfigured", "low res", "deformed", "poorly drawn", "mutation"]
                
                for node in clip_text_encode_nodes:
                    prompt_text = node["widgets_values"][0].lower()
                    # Check if this prompt contains negative indicators
                    matches = sum(1 for indicator in negative_indicators if indicator in prompt_text)
                    
                    if matches >= 3:  # If we have multiple matches, likely negative
                        negative_prompt = node["widgets_values"][0]
                    else:
                        # Assume it's positive if not strongly negative
                        positive_prompt = node["widgets_values"][0]
                
                # If we couldn't determine by content
                if positive_prompt is None and negative_prompt is None:
                    # Default if we can't determine
                    negative_prompt = clip_text_encode_nodes[0]["widgets_values"][0]
                    positive_prompt = clip_text_encode_nodes[1]["widgets_values"][0]
                elif positive_prompt is None:  # Only negative was found
                    # Find the other one
                    for node in clip_text_encode_nodes:
                        if node["widgets_values"][0] != negative_prompt:
                            positive_prompt = node["widgets_values"][0]
                            break
                elif negative_prompt is None:  # Only positive was found
                    # Find the other one
                    for node in clip_text_encode_nodes:
                        if node["widgets_values"][0] != positive_prompt:
                            negative_prompt = node["widgets_values"][0]
                            break
            
            # If we have only one CLIP node, assume it's positive
            elif len(clip_text_encode_nodes) == 1:
                positive_prompt = clip_text_encode_nodes[0]["widgets_values"][0]
    
    # If we've completed all our detection logic and still can't find a negative prompt
    # but we have a positive prompt, assume there's no negative prompt
    if positive_prompt is not None and negative_prompt is None:
        negative_prompt = ""
    
    print(f"extract_prompts_from_workflow returning: positive={positive_prompt is not None}, negative={negative_prompt is not None}")
    
    # Return the prompts in the correct order
    return positive_prompt, negative_prompt

class DiscordSendSaveImage:
    """
    A ComfyUI node that can send images to Discord and save them with advanced options.
    Images can be sent to Discord via webhook integration, while providing flexible
    saving options with customizable naming conventions and format options.
    """
    
    def __init__(self):
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        self.output_dir = None  # Will be set during saving to store the actual path used

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save and/or send to Discord."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI-Image", "tooltip": "The prefix for the saved files."}),
                "overwrite_last": (["enable", "disable"], {"default": "disable", "tooltip": "If enabled, will overwrite the last image instead of creating incrementing filenames."})
            },
            "optional": {
                "file_format": (["png", "jpeg", "webp"], {
                    "default": "png",
                    "tooltip": "The format to save images in. PNG is lossless but larger. JPEG and WebP are smaller but lossy."
                }),
                "quality": ("INT", {
                    "default": 95, 
                    "min": 1, 
                    "max": 100,
                    "step": 1,
                    "tooltip": "Quality for JPEG/WebP formats (1-100). Higher is better quality but larger file size."
                }),
                "lossless": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "If enabled, will use lossless compression for supported formats (PNG and WebP). JPEG will use maximum quality."
                }),
                "save_output": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to save images to disk. When disabled, images will only be previewed in the UI."
                }),
                "show_preview": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to show image previews in the UI. Disable to reduce UI clutter for large batches."
                }),
                "add_date": (["enable", "disable"], {
                    "default": "disable",
                    "tooltip": "Add the current date (YYYY-MM-DD) to filenames."
                }),
                "add_time": (["enable", "disable"], {
                    "default": "disable",
                    "tooltip": "Add the current time (HH-MM-SS) to filenames."
                }),
                "add_dimensions": (["enable", "disable"], {
                    "default": "disable",
                    "tooltip": "Add width and height dimensions to the filename (WxH format)."
                }),
                "resize_to_power_of_2": (["enable", "disable"], {
                    "default": "disable",
                    "tooltip": "Resize images to nearest power of 2 dimensions (useful for textures in game engines)."
                }),
                "resize_method": (["nearest-exact", "bilinear", "bicubic", "lanczos", "box"], {
                    "default": "lanczos", 
                    "tooltip": "The method to use when resizing images. Lanczos generally provides the best quality but may be slower."
                }),
                "send_to_discord": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to send the images to Discord via webhook."
                }),
                "webhook_url": ("STRING", {
                    "default": "", 
                    "multiline": False,
                    "tooltip": "Discord webhook URL to send images to. Leave empty to disable Discord integration."
                }),
                "discord_message": ("STRING", {
                    "default": "", 
                    "multiline": True,
                    "tooltip": "Optional message to send with the Discord images."
                }),
                "include_prompts_in_message": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to include the positive and negative prompts in the Discord message."
                }),
                "include_format_in_message": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to include the image format in the Discord message."
                }),
                "group_batched_images": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Group all images from a batch into a single Discord message with a gallery, rather than sending each one separately. Maximum is 9 images."
                }),
                "send_workflow_json": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to send the workflow JSON alongside the image to Discord, allowing dragging the JSON into ComfyUI to restore the workflow."
                }),
                "save_cdn_urls": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to save the Discord CDN URLs of the uploaded images as a text file and attach it to the Discord message."
                }),
                "github_cdn_update": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to update a GitHub repository with the Discord CDN URLs."
                }),
                "github_repo": ("STRING", {
                    "default": "", 
                    "multiline": False,
                    "tooltip": "GitHub repository to update with CDN URLs (format: username/repo)."
                }),
                "github_token": ("STRING", {
                    "default": "", 
                    "multiline": False,
                    "tooltip": "GitHub personal access token with repo permissions."
                }),
                "github_file_path": ("STRING", {
                    "default": "cdn_urls.md",
                    "multiline": False, 
                    "tooltip": "Path to the file within the GitHub repository to update with CDN URLs."
                }),
            },
            "hidden": {
                "prompt": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("image_path",)
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "image/output"
    DESCRIPTION = "Saves images with advanced options and can send them to Discord via webhook integration. Returns the path to the first saved image."

    @classmethod
    def CONTEXT_MENUS(s):
        return {
            "Show Preview": lambda self, **kwargs: {"show_preview": True},
            "Hide Preview": lambda self, **kwargs: {"show_preview": False},
        }

    def save_images(self, images, filename_prefix="ComfyUI-Image", overwrite_last="disable", 
                   file_format="png", quality=95, lossless=True, add_date="disable", add_time="disable", 
                   add_dimensions="disable", resize_to_power_of_2="disable", save_output=True, 
                   resize_method="lanczos", show_preview=True, send_to_discord=False, webhook_url="", discord_message="",
                   include_prompts_in_message=False, include_format_in_message=False, send_workflow_json=False, 
                   group_batched_images=True, save_cdn_urls=False, github_cdn_update=False, github_repo="", 
                   github_token="", github_file_path="cdn_urls.md", prompt=None, extra_pnginfo=None):
        """
        Save images for and optionally send to Discord.
        
        Parameters:
            images: The images to save/send
            filename_prefix: The prefix for the filename
            overwrite_last: Whether to overwrite the last image instead of incrementing
            file_format: Image format to save as (png, jpeg, webp)
            quality: Quality setting for lossy formats (1-100)
            lossless: Whether to use lossless compression for supported formats (PNG and WebP)
            add_date: Whether to add the date to the filename
            add_time: Whether to add the time to the filename
            add_dimensions: Whether to add the image dimensions to the filename
            resize_to_power_of_2: Whether to resize to power-of-2 dimensions for texture optimization
            resize_method: Method to use for resizing
            save_output: Whether to save to disk or just preview
            send_to_discord: Whether to send the images to Discord
            webhook_url: Discord webhook URL
            discord_message: Message to send with the images
            include_prompts_in_message: Whether to include prompts in Discord message
            include_format_in_message: Whether to include the image format in Discord messages
            send_workflow_json: Whether to send the workflow JSON to Discord
            group_batched_images: Whether to group all images from a batch into a single Discord message
            save_cdn_urls: Whether to save Discord CDN URLs as a text file and attach it to the Discord message
            github_cdn_update: Whether to update a GitHub repository with the Discord CDN URLs
            github_repo: GitHub repository (format: username/repo)
            github_token: GitHub personal access token
            github_file_path: Path to the file within the GitHub repository to update
            prompt: The generation prompt data
            extra_pnginfo: Extra PNG info for metadata
            
        Returns:
            UI information for ComfyUI and the path to the first saved image as a string.
            If no images were saved, an empty string is returned for the path.
        """
        results = []
        output_files = []
        discord_sent_files = []
        discord_send_success = True
        
        # For batch grouping
        batch_discord_files = []
        batch_discord_data = {}
        batch_workflow_json = None
        
        # For tracking Discord CDN URLs
        discord_cdn_urls = []
        batch_cdn_urls = []
        
        # Sanitize the workflow and extra_pnginfo data to remove webhook URLs
        # This protects user security when sharing images
        # (but keep a copy of the original data for prompt extraction)
        original_prompt = prompt
        original_extra_pnginfo = extra_pnginfo
        
        # Ensure webhook URL is sanitized from workflow data for all file formats
        if prompt is not None:
            prompt = sanitize_json_for_export(prompt)
        
        if extra_pnginfo is not None:
            extra_pnginfo = sanitize_json_for_export(extra_pnginfo)
            
        # Double-check webhook URL removal for Discord-specific data
        if send_to_discord:
            # Verify webhook is sanitized from workflow JSON data
            if send_workflow_json and extra_pnginfo is not None and "workflow" in extra_pnginfo:
                extra_pnginfo["workflow"] = sanitize_json_for_export(extra_pnginfo["workflow"])
        
        # Add date and/or time if enabled
        date_time_parts = []
        
        # Prepare info for Discord message
        image_info = {}
        
        if add_date == "enable":
            # Get ONLY the date in YYYY-MM-DD format
            current_date = time.strftime("%Y-%m-%d")
            date_time_parts.append(current_date)
            print(f"Adding date to filename: {current_date}")
            image_info["date"] = current_date
            
        if add_time == "enable":
            # Get ONLY the time in HH-MM-SS format
            current_time = time.strftime("%H-%M-%S")
            date_time_parts.append(current_time)
            print(f"Adding time to filename: {current_time}")
            image_info["time"] = current_time
        
        # Add date/time components to filename prefix if any were enabled
        if date_time_parts:
            date_time_suffix = "_" + "_".join(date_time_parts)
            filename_prefix += date_time_suffix
            print(f"Final timestamp suffix: {date_time_suffix}")
            
        # Add prefix append
        filename_prefix += self.prefix_append
        
        # Get ComfyUI output directory for safe path handling
        comfy_output_dir = folder_paths.get_output_directory()
        
        # Choose destination directory based on save_output flag
        if save_output:
            # Create a output subfolder in the ComfyUI output directory
            dest_folder = os.path.join(comfy_output_dir, "discord_output")
            os.makedirs(dest_folder, exist_ok=True)
        else:
            # Use ComfyUI's temporary directory for preview-only files
            dest_folder = folder_paths.get_temp_directory()
            os.makedirs(dest_folder, exist_ok=True)
            print(f"Using temporary directory for preview: {dest_folder}")
        
        # Setup paths using ComfyUI's path validation
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, dest_folder, images[0].shape[1], images[0].shape[0])
        
        # For overwrite functionality, we'll just always use the same counter instead of bypassing validation
        if overwrite_last == "enable":
            counter = 1  # Always use the same counter value for overwriting
        else:
            # When not overwriting, we need to find the highest existing counter and start from there
            # This ensures we're always creating new files
            try:
                # Get all existing files with this prefix
                base_filename = os.path.basename(filename).replace("%batch_num%", "")
                existing_files = [f for f in os.listdir(full_output_folder) 
                                if os.path.basename(f).startswith(base_filename)]
                
                if existing_files:
                    # Extract counters from filenames
                    existing_counters = []
                    for f in existing_files:
                        # Extract counter pattern (5 digits) from filename
                        counter_match = re.search(r'_(\d{5})\.', f)
                        if counter_match:
                            existing_counters.append(int(counter_match.group(1)))
                        
                        # Also try alternative pattern where the counter is followed by extension
                        counter_match = re.search(r'_(\d{5})_\.', f)
                        if counter_match:
                            existing_counters.append(int(counter_match.group(1)))
                    
                    # Set counter to one more than the highest existing counter
                    if existing_counters:
                        counter = max(existing_counters) + 1
            except Exception as e:
                print(f"Error determining next file counter: {e}")
                # Default to ComfyUI's counter if we can't determine the next one
        
        print(f"Using counter: {counter} for {'overwriting' if overwrite_last == 'enable' else 'new files'}")
        print(f"Output prefix: {filename_prefix}")
        
        # Map resize method strings to PIL resize methods
        resize_methods = {
            "nearest-exact": Image.NEAREST,
            "bilinear": Image.BILINEAR,
            "bicubic": Image.BICUBIC,
            "lanczos": Image.LANCZOS,
            "box": Image.BOX
        }
        
        # Handle different versions of PIL
        if hasattr(Image, 'Resampling'):
            resize_methods = {
                "nearest-exact": Image.Resampling.NEAREST,
                "bilinear": Image.Resampling.BILINEAR,
                "bicubic": Image.Resampling.BICUBIC,
                "lanczos": Image.Resampling.LANCZOS,
                "box": Image.Resampling.BOX
            }
        
        # Get the selected resize method, default to LANCZOS if not found
        selected_resize_method = resize_methods.get(resize_method, Image.LANCZOS)
        
        # Initialize Discord sender if enabled
        discord_success = False
        if send_to_discord and webhook_url:
            print(f"Discord integration enabled, preparing to send images to webhook")
            discord_success = True  # Will be set to False if any send fails
            
            # Initialize message_prefix for all Discord messages
            # This ensures prompts have a place to be attached regardless of other options
            image_info["message_prefix"] = ""
            
        elif send_to_discord and not webhook_url:
            print("Discord integration was enabled but no webhook URL was provided")
        
        # Add image info to Discord message if relevant options are enabled
        if send_to_discord and webhook_url and (add_date == "enable" or add_time == "enable" or add_dimensions == "enable" or resize_to_power_of_2 == "enable" or include_format_in_message):
            info_message = "\n\n**Image Information:**\n"
            
            if "date" in image_info:
                info_message += f"**Date:** {image_info['date']}\n"
                
            if "time" in image_info:
                info_message += f"**Time:** {image_info['time']}\n"
            
            # Add format to the message if the option is enabled
            if include_format_in_message:
                info_message += f"**Format:** {file_format.upper()}\n"
            
            # Update the message prefix with the information
            image_info["message_prefix"] = info_message
            
            # Note: We don't add to discord_message yet, as dimensions aren't known until processing
            print("Prepared image information section for Discord message")
        
        # Extract prompts if requested
        if send_to_discord and include_prompts_in_message:
            workflow_data = None
            
            # First try to get workflow from extra_pnginfo
            if original_extra_pnginfo is not None and isinstance(original_extra_pnginfo, dict) and "workflow" in original_extra_pnginfo:
                workflow_data = original_extra_pnginfo["workflow"]
            
            # If no workflow in extra_pnginfo, check if prompt is actually a workflow
            if workflow_data is None and original_prompt is not None:
                # Check if prompt is already a workflow
                if isinstance(original_prompt, dict) and "nodes" in original_prompt:
                    workflow_data = original_prompt
            
            # Extract prompts from workflow data
            if workflow_data is not None:
                positive_prompt, negative_prompt = extract_prompts_from_workflow(workflow_data)
                
                # Ensure the prompts are strings or None
                if positive_prompt is not False and positive_prompt is not None and not isinstance(positive_prompt, str):
                    positive_prompt = str(positive_prompt)
                    print(f"Converted positive prompt to string: {positive_prompt[:50]}...")
                
                if negative_prompt is not False and negative_prompt is not None and not isinstance(negative_prompt, str):
                    negative_prompt = str(negative_prompt)
                    print(f"Converted negative prompt to string: {negative_prompt[:50]}...")
                
                # Check if we have valid prompt data
                has_valid_prompt = (
                    (isinstance(positive_prompt, str) and positive_prompt) or 
                    (isinstance(negative_prompt, str) and negative_prompt)
                )
                
                # Add prompts to Discord message if found
                if has_valid_prompt:
                    prompt_message = "\n\n**Generation Prompts:**\n"
                    
                    if isinstance(positive_prompt, str) and positive_prompt:
                        prompt_message += f"**Positive:**\n```\n{positive_prompt}\n```\n"
                        
                    if isinstance(negative_prompt, str) and negative_prompt:
                        prompt_message += f"**Negative:**\n```\n{negative_prompt}\n```\n"
                    
                    # Store prompt message for adding after image info
                    image_info["prompt_message"] = prompt_message
                    print("Prepared prompts for Discord message")
        
        for batch_number, image in enumerate(images):
            # Convert the tensor to a PIL image
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            
            # Get original dimensions before any resizing
            orig_width, orig_height = img.size
            
            # Resize to power of 2 if enabled
            if resize_to_power_of_2 == "enable":
                # Calculate nearest power of 2 dimensions
                new_width = 2 ** int(np.log2(orig_width) + 0.5)  # Round to nearest power of 2
                new_height = 2 ** int(np.log2(orig_height) + 0.5)  # Round to nearest power of 2
                
                print(f"Resizing image from {orig_width}x{orig_height} to {new_width}x{new_height} (power of 2)")
                
                # Store original and resized dimensions for Discord message
                if send_to_discord and webhook_url and batch_number == 0:
                    image_info["original_dimensions"] = f"{orig_width}x{orig_height}"
                    image_info["resized_dimensions"] = f"{new_width}x{new_height}"
                
                # Only resize if dimensions changed
                if (new_width != orig_width or new_height != orig_height):
                    try:
                        img = img.resize((new_width, new_height), selected_resize_method)
                        print(f"Successfully resized using {resize_method} method")
                    except Exception as e:
                        print(f"Error during power of 2 resize: {e}")
                        # Fallback to BICUBIC if selected method fails
                        img = img.resize((new_width, new_height), Image.BICUBIC)
                        print("Fallback to BICUBIC resize method due to error")
            
            # Get dimensions - either original or resized
            width, height = img.size
            
            # Add dimensions to filename if enabled
            dimensions_suffix = ""
            if add_dimensions == "enable":
                dimensions_suffix = f"_{width}x{height}"
                filename_prefix += dimensions_suffix
                
                # Store dimensions for Discord message if needed
                if send_to_discord and webhook_url and batch_number == 0:
                    image_info["dimensions"] = f"{width}x{height}"
            
            # Add image information to Discord message if this is the first image
            if send_to_discord and webhook_url and batch_number == 0:
                # Add image info if available
                if "message_prefix" in image_info:
                    info_message = image_info["message_prefix"]
                    
                    # Add dimensions info if available
                    if "original_dimensions" in image_info and "resized_dimensions" in image_info:
                        info_message += f"**Original Dimensions:** {image_info['original_dimensions']}\n"
                        info_message += f"**Resized Dimensions:** {image_info['resized_dimensions']} (Power of 2)\n"
                    elif "dimensions" in image_info:
                        info_message += f"**Dimensions:** {image_info['dimensions']}\n"
                    
                    # Add the complete info message to the Discord message
                    discord_message += info_message
                    print("Added image information to Discord message")
                
                # Add prompts after image info if available (decoupled from image info presence)
                if "prompt_message" in image_info:
                    discord_message += image_info["prompt_message"]
                    print("Added prompts to Discord message after image information")
            
            # Create metadata for the image
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    # Final sanitization check before embedding
                    sanitized_prompt = sanitize_json_for_export(prompt)
                    metadata.add_text("prompt", json.dumps(sanitized_prompt))
                if extra_pnginfo is not None:
                    # Final sanitization check before embedding
                    sanitized_extra_pnginfo = sanitize_json_for_export(extra_pnginfo)
                    for x in sanitized_extra_pnginfo:
                        if x == "workflow":
                            # Extra sanitization for workflow data
                            workflow_data = sanitize_json_for_export(sanitized_extra_pnginfo[x])
                            metadata.add_text(x, json.dumps(workflow_data))
                        else:
                            metadata.add_text(x, json.dumps(sanitized_extra_pnginfo[x]))
            
            # For Discord output
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            
            # Add dimensions tag before the counter if enabled
            if add_dimensions == "enable" and dimensions_suffix not in filename_with_batch_num:
                # Insert dimensions before counter
                base_name = os.path.splitext(filename_with_batch_num)[0]
                filename_with_batch_num = f"{base_name}{dimensions_suffix}"
            
            # File extension based on format
            extension = f".{file_format}"
            file = f"{filename_with_batch_num}_{counter:05}_{extension}"
            
            # Remove the additional underscore before the extension
            if file.endswith(f"_{extension}"):
                file = file[:-len(f"_{extension}")] + extension
                
            filepath = os.path.join(full_output_folder, file)
            
            try:
                # Save the image based on format
                if file_format == "png":
                    # For PNG, make sure we have sanitized metadata
                    if metadata is not None and hasattr(metadata, "text"):
                        # Double check any JSON in the metadata
                        for key in list(metadata.text.keys()):
                            try:
                                value = metadata.text[key]
                                # Try to parse and sanitize any JSON values
                                json_value = json.loads(value)
                                sanitized_json = sanitize_json_for_export(json_value)
                                metadata.text[key] = json.dumps(sanitized_json)
                            except:
                                # Not JSON or error, leave as is
                                pass
                                
                    img.save(filepath, pnginfo=metadata, compress_level=self.compress_level)
                elif file_format == "jpeg":
                    # JPEG is always lossy, but we can set quality to maximum if lossless is requested
                    jpeg_quality = 100 if lossless else quality
                    img.save(filepath, format="JPEG", quality=jpeg_quality)
                elif file_format == "webp":
                    if lossless:
                        img.save(filepath, format="WEBP", lossless=True)
                    else:
                        img.save(filepath, format="WEBP", quality=quality)
                
                output_files.append(filepath)
                
                # Print dimensions for verification
                print(f"Saved image with dimensions: {img.size[0]}x{img.size[1]}")
                    
                # Add to results for UI display
                results.append({
                    "filename": file,
                    "subfolder": "discord_output/" + (subfolder if subfolder else "") if save_output else "",
                    "type": "output" if save_output else "temp",
                    "path": filepath
                })
                
                # Send to Discord if enabled
                if send_to_discord and webhook_url:
                    try:
                        # Prepare the image for Discord - use the resized PIL image (img) instead of original tensor
                        img_cv = np.array(img)
                        
                        # Convert RGB (PIL) to BGR (OpenCV) if needed
                        if len(img_cv.shape) == 3 and img_cv.shape[2] == 3:
                            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
                        
                        # Handle color conversion for special cases
                        if len(img_cv.shape) == 2:  # Grayscale
                            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2BGR)
                        elif len(img_cv.shape) == 3 and img_cv.shape[2] == 4:  # RGBA
                            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGBA2BGRA)
                        
                        # Generate unique filename for Discord using the selected format
                        discord_filename = f"{uuid4()}.{file_format}"
                        
                        # Encode image using the selected format
                        if file_format == "png":
                            _, buffer = cv2.imencode('.png', img_cv)
                        elif file_format == "jpeg":
                            # JPEG is always lossy, but we can set quality to maximum if lossless is requested
                            jpeg_quality = 100 if lossless else quality
                            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
                            _, buffer = cv2.imencode('.jpg', img_cv, encode_params)
                        elif file_format == "webp":
                            try:
                                if lossless:
                                    # For lossless WebP - using explicit parameter value as the constant may not be defined
                                    # cv2.IMWRITE_WEBP_LOSSLESS is 9 in OpenCV
                                    encode_params = [int(cv2.IMWRITE_WEBP_QUALITY), 100]  # First ensure high quality
                                    encode_params.extend([9, 1])  # 9 is the parameter ID for WEBP_LOSSLESS, 1 means true
                                    _, buffer = cv2.imencode('.webp', img_cv, encode_params)
                                    
                                    # If that fails, try alternative method
                                    if buffer is None or len(buffer) == 0:
                                        raise ValueError("WebP lossless encoding failed with direct method")
                                else:
                                    # For lossy WebP with quality parameter
                                    encode_params = [int(cv2.IMWRITE_WEBP_QUALITY), quality]
                                    _, buffer = cv2.imencode('.webp', img_cv, encode_params)
                            except Exception as e:
                                print(f"Error with WebP encoding for Discord: {e}, falling back to PNG")
                                # Fallback to PNG if WebP encoding fails
                                _, buffer = cv2.imencode('.png', img_cv)
                                # Update filename to reflect the format change
                                discord_filename = f"{os.path.splitext(discord_filename)[0]}.png"
                        
                        file_bytes = BytesIO(buffer)
                        
                        # If batch grouping is enabled, store the files for later
                        if group_batched_images:
                            # Store this image for batch sending
                            batch_discord_files.append((discord_filename, file_bytes.getvalue()))
                            
                            # Prepare workflow JSON only once for the whole batch
                            if batch_number == 0 and send_workflow_json and (prompt is not None or extra_pnginfo is not None):
                                try:
                                    workflow_json = None
                                    
                                    # First try to get workflow from extra_pnginfo
                                    if extra_pnginfo is not None and isinstance(extra_pnginfo, dict) and "workflow" in extra_pnginfo:
                                        workflow_json = extra_pnginfo["workflow"]
                                    
                                    # If no workflow in extra_pnginfo, check if prompt is actually a workflow
                                    if workflow_json is None and prompt is not None:
                                        # Check if prompt is already a workflow
                                        if isinstance(prompt, dict) and "nodes" in prompt and "links" in prompt:
                                            workflow_json = prompt
                                    
                                    # Ensure the workflow is sanitized
                                    if workflow_json:
                                        workflow_json = sanitize_json_for_export(workflow_json)
                                        batch_workflow_json = workflow_json
                                except Exception as e:
                                    print(f"Error preparing workflow JSON for batch: {e}")
                            
                            # Store discord message only once
                            if batch_number == 0 and discord_message:
                                batch_discord_data["content"] = discord_message
                            
                        else:
                            # Original non-batched behavior - send immediately
                            # Prepare the Discord request
                            files = {
                                "file": (discord_filename, file_bytes.getvalue())
                            }
                            
                            # If enabled, also send the workflow JSON
                            if send_workflow_json and (prompt is not None or extra_pnginfo is not None):
                                try:
                                    workflow_json = None
                                    
                                    # First check if extra_pnginfo contains the workflow data
                                    if extra_pnginfo is not None and "workflow" in extra_pnginfo:
                                        workflow_json = extra_pnginfo["workflow"]
                                    
                                    # If no workflow in extra_pnginfo, check if prompt is actually a workflow
                                    if workflow_json is None and prompt is not None:
                                        # Check if prompt is already a workflow
                                        if isinstance(prompt, dict) and "nodes" in prompt and "links" in prompt:
                                            workflow_json = prompt
                                    
                                    # Ensure the workflow is sanitized
                                    if workflow_json:
                                        workflow_json = sanitize_json_for_export(workflow_json)
                                        
                                        # Generate a JSON file with the same base name
                                        json_filename = f"{os.path.splitext(discord_filename)[0]}.json"
                                        
                                        # Convert workflow data to JSON string in the proper format
                                        json_data = json.dumps(workflow_json, indent=2)
                                        
                                        # Add JSON file to the request
                                        files["workflow"] = (json_filename, json_data.encode('utf-8'))
                                        
                                        print(f"ComfyUI workflow JSON file {json_filename} will be sent alongside the image")
                                    else:
                                        print("No workflow data found in the provided metadata")
                                except Exception as e:
                                    print(f"Error preparing workflow JSON: {e}")
                            
                            data = {}
                            if discord_message:
                                data["content"] = discord_message
                            
                            # Only send to Discord if not batching
                            if not group_batched_images:
                                # Send to Discord
                                response = requests.post(
                                    webhook_url,
                                    files=files,
                                    data=data
                                )
                                
                                # Discord can return either 204 (no content) or 200 (success with content) for successful requests
                                if response.status_code in [200, 204]:
                                    print(f"Successfully sent image {batch_number+1} to Discord")
                                    discord_sent_files.append(discord_filename)
                                    if send_workflow_json and "workflow" in files:
                                        print(f"Successfully sent workflow JSON for image {batch_number+1}")
                                    
                                    # Try to extract CDN URLs from batch response
                                    if save_cdn_urls and response.status_code == 200:
                                        try:
                                            response_data = response.json()
                                            print(f"Received JSON response from Discord with {len(response_data) if isinstance(response_data, dict) else 'invalid'} fields")
                                            
                                            if "attachments" in response_data and isinstance(response_data["attachments"], list):
                                                print(f"Found {len(response_data['attachments'])} attachments in Discord response")
                                                
                                                for idx, attachment in enumerate(response_data["attachments"]):
                                                    if "url" in attachment and "filename" in attachment:
                                                        # Filter out workflow JSON files from URLs list
                                                        if not attachment["filename"].endswith(".json"):
                                                            batch_cdn_urls.append((attachment["filename"], attachment["url"]))
                                                            print(f"Extracted CDN URL for batch image {idx+1}: {attachment['url']}")
                                                        else:
                                                            print(f"Skipping JSON file: {attachment['filename']}")
                                                    else:
                                                        print(f"Attachment {idx+1} missing URL or filename: {attachment.keys()}")
                                                
                                                print(f"Total batch CDN URLs collected: {len(batch_cdn_urls)}")
                                                
                                                # Create and send a text file with the CDN URLs if we have any
                                                if batch_cdn_urls:
                                                    try:
                                                        # Create the text file content
                                                        url_text_content = "# Discord CDN URLs\n\n"
                                                        for idx, (filename, url) in enumerate(batch_cdn_urls):
                                                            url_text_content += f"{idx+1}. {filename}: {url}\n"
                                                        
                                                        # Create a unique filename for the text file
                                                        urls_filename = f"cdn_urls-{uuid4()}.txt"
                                                        
                                                        # Prepare the request with just the URL file
                                                        url_files = {"file": (urls_filename, url_text_content.encode('utf-8'))}
                                                        url_data = {"content": "Discord CDN URLs for the uploaded images:"}
                                                        
                                                        # Send a follow-up message with just the URLs text file
                                                        url_response = requests.post(
                                                            webhook_url,
                                                            files=url_files,
                                                            data=url_data
                                                        )
                                                        
                                                        if url_response.status_code in [200, 204]:
                                                            print(f"Successfully sent CDN URLs text file to Discord")
                                                        else:
                                                            print(f"Error sending CDN URLs text file: Status code {url_response.status_code}")
                                                    except Exception as e:
                                                        print(f"Error creating or sending CDN URLs text file: {e}")
                                        except Exception as e:
                                            print(f"Error extracting CDN URLs from batch response: {e}")
                                else:
                                    print(f"Error: Discord returned status code {response.status_code}")
                                    discord_send_success = False
                            else:
                                # Just mark it as queued for batch sending
                                print(f"Image {batch_number+1} queued for batch sending to Discord")
                    except Exception as e:
                        print(f"Error processing image for Discord: {e}")
                        discord_send_success = False
                
                # Increment counter if not overwriting
                if overwrite_last != "enable":
                    counter += 1
            except Exception as e:
                print(f"Error saving image: {e}")
        
        if results:
            if save_output:
                print(f"DiscordSendSaveImage: Saved {len(results)} images to {full_output_folder}")
            else:
                print("DiscordSendSaveImage: Preview only mode - no images saved to disk")
                
            # Discord status
            if send_to_discord and discord_sent_files:
                print("DiscordSendSaveImage: Successfully sent all images to Discord")
                
                # If we have CDN URLs and we're not in batch mode, send them as a text file
                if save_cdn_urls and discord_cdn_urls and not (group_batched_images and len(images) > 1):
                    try:
                        # Create the text file content
                        url_text_content = "# Discord CDN URLs\n\n"
                        for idx, (filename, url) in enumerate(discord_cdn_urls):
                            url_text_content += f"{idx+1}. {filename}: {url}\n"
                        
                        # Create a unique filename for the text file
                        urls_filename = f"cdn_urls-{uuid4()}.txt"
                        
                        # Prepare the request with just the URL file
                        url_files = {"file": (urls_filename, url_text_content.encode('utf-8'))}
                        url_data = {"content": "Discord CDN URLs for the uploaded images:"}
                        
                        # Send a follow-up message with just the URLs text file
                        url_response = requests.post(
                            webhook_url,
                            files=url_files,
                            data=url_data
                        )
                        
                        if url_response.status_code in [200, 204]:
                            print(f"Successfully sent CDN URLs text file to Discord")
                        else:
                            print(f"Error sending CDN URLs text file: Status code {url_response.status_code}")
                    except Exception as e:
                        print(f"Error creating or sending CDN URLs text file: {e}")
            elif send_to_discord and not discord_send_success:
                print("DiscordSendSaveImage: There were errors sending some images to Discord")
        else:
            print("DiscordSendSaveImage: No images were processed")
        
        # Send batch to Discord if enabled and we have images
        if send_to_discord and webhook_url and group_batched_images and batch_discord_files:
            try:
                print(f"Sending {len(batch_discord_files)} images as a batch to Discord...")
                
                # Prepare files dictionary for the request
                files = {}
                for i, (filename, file_bytes) in enumerate(batch_discord_files):
                    files[f"file{i}"] = (filename, file_bytes)
                
                # Add workflow JSON if available
                if send_workflow_json and batch_workflow_json:
                    try:
                        # Generate a JSON file with a unique name
                        json_filename = f"workflow-{uuid4()}.json"
                        
                        # Convert workflow data to JSON string in the proper format
                        json_data = json.dumps(batch_workflow_json, indent=2)
                        
                        # Add JSON file to the request
                        files["workflow"] = (json_filename, json_data.encode('utf-8'))
                        
                        print(f"Adding workflow JSON file to batch Discord message")
                    except Exception as e:
                        print(f"Error preparing workflow JSON for batch: {e}")
                
                # Send the batch to Discord
                response = requests.post(
                    webhook_url,
                    files=files,
                    data=batch_discord_data
                )
                
                # Discord can return either 204 (no content) or 200 (success with content) for successful requests
                if response.status_code in [200, 204]:
                    print(f"Successfully sent batch of {len(batch_discord_files)} images to Discord as a gallery")
                    discord_send_success = True
                    discord_sent_files = ["batch_gallery"]  # Mark as successfully sent
                    
                    # Try to extract CDN URLs from batch response
                    if save_cdn_urls and response.status_code == 200:
                        try:
                            response_data = response.json()
                            print(f"Received JSON response from Discord with {len(response_data) if isinstance(response_data, dict) else 'invalid'} fields")
                            
                            if "attachments" in response_data and isinstance(response_data["attachments"], list):
                                print(f"Found {len(response_data['attachments'])} attachments in Discord response")
                                
                                for idx, attachment in enumerate(response_data["attachments"]):
                                    if "url" in attachment and "filename" in attachment:
                                        # Filter out workflow JSON files from URLs list
                                        if not attachment["filename"].endswith(".json"):
                                            batch_cdn_urls.append((attachment["filename"], attachment["url"]))
                                            print(f"Extracted CDN URL for batch image {idx+1}: {attachment['url']}")
                                        else:
                                            print(f"Skipping JSON file: {attachment['filename']}")
                                    else:
                                        print(f"Attachment {idx+1} missing URL or filename: {attachment.keys()}")
                                
                                print(f"Total batch CDN URLs collected: {len(batch_cdn_urls)}")
                                
                                # Create and send a text file with the CDN URLs if we have any
                                if batch_cdn_urls:
                                    try:
                                        # Create the text file content
                                        url_text_content = "# Discord CDN URLs\n\n"
                                        for idx, (filename, url) in enumerate(batch_cdn_urls):
                                            url_text_content += f"{idx+1}. {filename}: {url}\n"
                                        
                                        # Create a unique filename for the text file
                                        urls_filename = f"cdn_urls-{uuid4()}.txt"
                                        
                                        # Prepare the request with just the URL file
                                        url_files = {"file": (urls_filename, url_text_content.encode('utf-8'))}
                                        url_data = {"content": "Discord CDN URLs for the uploaded images:"}
                                        
                                        # Send a follow-up message with just the URLs text file
                                        url_response = requests.post(
                                            webhook_url,
                                            files=url_files,
                                            data=url_data
                                        )
                                        
                                        if url_response.status_code in [200, 204]:
                                            print(f"Successfully sent CDN URLs text file to Discord")
                                        else:
                                            print(f"Error sending CDN URLs text file: Status code {url_response.status_code}")
                                    except Exception as e:
                                        print(f"Error creating or sending CDN URLs text file: {e}")
                        except Exception as e:
                            print(f"Error extracting CDN URLs from batch response: {e}")
                    else:
                        print(f"Error sending batch to Discord: Status code {response.status_code} - {response.text}")
                    discord_send_success = False
            except Exception as e:
                print(f"Error sending batch to Discord: {e}")
                discord_send_success = False

        # Update GitHub repository with CDN URLs if enabled - MOVED HERE AFTER ALL DISCORD OPERATIONS
        if github_cdn_update and send_to_discord and (discord_cdn_urls or batch_cdn_urls):
            # Use whichever list of URLs we have
            urls_to_send = discord_cdn_urls if discord_cdn_urls else batch_cdn_urls
            
            print(f"GitHub update is enabled with: repo={github_repo}, token_provided={'Yes' if github_token else 'No'}, file_path={github_file_path}")
            print(f"Number of available CDN URLs to update GitHub: {len(urls_to_send)}")
            
            if urls_to_send:
                # Call the GitHub update function
                print(f"Updating GitHub repository {github_repo} with {len(urls_to_send)} Discord CDN URLs...")
                success, message = update_github_cdn_urls(
                    github_repo=github_repo,
                    github_token=github_token,
                    file_path=github_file_path,
                    cdn_urls=urls_to_send
                )
                if success:
                    print(f"GitHub update successful: {message}")
                else:
                    print(f"GitHub update failed: {message}")
            else:
                print("No CDN URLs available to update GitHub repository")
        elif github_cdn_update:
            # If GitHub update is enabled but not triggered, explain why
            reasons = []
            if not send_to_discord:
                reasons.append("send_to_discord is disabled")
            if not (discord_cdn_urls or batch_cdn_urls):
                reasons.append("no CDN URLs were collected (did Discord upload succeed?)")
            if not github_repo:
                reasons.append("github_repo is empty")
            if not github_token:
                reasons.append("github_token is empty")
            if not github_file_path:
                reasons.append("github_file_path is empty")
            
            print(f"GitHub update was enabled but not triggered because: {', '.join(reasons)}")
        
        # Control UI preview based on show_preview flag
        if show_preview:
            return {"ui": {"images": results}, "result": ((save_output, output_files, discord_send_success if send_to_discord else None),)}, output_files[0] if output_files else ""
        else:
            # Return a minimal UI object without images
            return {"ui": {}, "result": ((save_output, output_files, discord_send_success if send_to_discord else None),)}, output_files[0] if output_files else ""

    @classmethod
    def IS_CHANGED(s, images, filename_prefix="ComfyUI-Image", overwrite_last="disable", 
                  file_format="png", quality=95, lossless=True, add_date="disable", add_time="disable", 
                  add_dimensions="disable", resize_to_power_of_2="disable", save_output=True, 
                  resize_method="lanczos", show_preview=True, send_to_discord=False, webhook_url="", discord_message="",
                  include_prompts_in_message=False, include_format_in_message=False, group_batched_images=True, 
                  send_workflow_json=False, save_cdn_urls=False, github_cdn_update=False, github_repo="", 
                  github_token="", github_file_path="cdn_urls.md", prompt=None, extra_pnginfo=None):
        return True

# Add function to send CDN URLs to GitHub repository
def update_github_cdn_urls(github_repo, github_token, file_path, cdn_urls, commit_message=None):
    """
    Update a file in a GitHub repository with Discord CDN URLs.
    
    Parameters:
        github_repo: The GitHub repository (format: username/repo)
        github_token: The GitHub personal access token for authentication
        file_path: The path to the file within the repository to update
        cdn_urls: List of (filename, url) tuples containing Discord CDN URLs
        commit_message: Optional commit message, defaults to a standard message
        
    Returns:
        Tuple of (success, message) where success is a boolean and message is a status message
    """
    print(f"update_github_cdn_urls called with repo: {github_repo}, file_path: {file_path}, URLs count: {len(cdn_urls)}")
    
    # Check required parameters
    if not github_repo:
        print("Error: GitHub repository name is empty")
        return False, "Missing GitHub repository name"
    
    if not github_token:
        print("Error: GitHub token is empty")
        return False, "Missing GitHub personal access token"
    
    if not file_path:
        print("Error: GitHub file path is empty")
        return False, "Missing file path in repository"
    
    if not cdn_urls:
        print("Error: No CDN URLs provided to update")
        return False, "No CDN URLs to update"
    
    # Ensure repository format is valid
    if "/" not in github_repo:
        print(f"Error: Invalid GitHub repository format: {github_repo}. Expected format: username/repo")
        return False, f"Invalid GitHub repository format: {github_repo}. Expected format: username/repo"
    
    # Setup API endpoint for the file
    api_url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"
    
    # Create headers with token but don't log the actual token
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Log attempt without exposing the token
    print(f"Attempting to access GitHub API at: {api_url} with authentication")
    
    try:
        # Check if file exists and get its SHA if it does
        file_sha = None
        try:
            print("Checking if file exists on GitHub...")
            response = requests.get(api_url, headers=headers)
            print(f"GitHub API check response: Status {response.status_code}")
            
            if response.status_code == 200:
                file_data = response.json()
                file_sha = file_data.get("sha")
                print(f"File exists, got SHA: {file_sha[:7]}...")
                
                # Get current content if file exists
                current_content = ""
                if file_data.get("content"):
                    current_content = base64.b64decode(file_data["content"]).decode("utf-8")
                    print(f"Retrieved existing file content ({len(current_content)} bytes)")
            elif response.status_code == 404:
                print("File doesn't exist yet, will create a new file")
            else:
                print(f"Unexpected response checking GitHub file: {response.status_code}")
                print(f"Response body: {response.text[:200]}...")
                return False, f"Error checking GitHub file: {response.status_code} - {response.text}"
        except Exception as e:
            # Continue with file creation if checking failed
            print(f"Warning: Failed to check file existence: {str(e)}")
        
        # Prepare the file content with the CDN URLs
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Start with new content template
        new_content = f"# Discord CDN URLs\nLast updated: {timestamp}\n\n"
        
        # If we have existing content, try to merge it
        if file_sha and 'current_content' in locals() and current_content:
            print("Merging with existing content...")
            # Extract existing URLs
            existing_urls = {}
            for line in current_content.splitlines():
                if ": https://" in line and "cdn.discordapp.com" in line:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        name_part = parts[0]
                        if ". " in name_part:  # Remove numbering if present
                            name_part = name_part.split(". ", 1)[1]
                        existing_urls[name_part] = parts[1]
            
            print(f"Found {len(existing_urls)} existing URLs in the file")
            
            # Add new URLs (don't duplicate filenames)
            for filename, url in cdn_urls:
                existing_urls[filename] = url
            
            # Format all URLs
            new_content = f"# Discord CDN URLs\nLast updated: {timestamp}\n\n"
            for i, (filename, url) in enumerate(existing_urls.items(), 1):
                new_content += f"{i}. {filename}: {url}\n"
                
            print(f"Final content has {len(existing_urls)} URLs")
        else:
            # Just add the new URLs
            print("Creating new content with just the new URLs")
            for i, (filename, url) in enumerate(cdn_urls, 1):
                new_content += f"{i}. {filename}: {url}\n"
                
            print(f"New content has {len(cdn_urls)} URLs")
        
        # Set default commit message if not provided
        if not commit_message:
            commit_message = f"Update Discord CDN URLs - {timestamp}"
        
        # Prepare the request data
        data = {
            "message": commit_message,
            "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
        }
        
        # Add SHA if file exists (for updating instead of creating)
        if file_sha:
            data["sha"] = file_sha
            print(f"Adding SHA to request for updating existing file")
        else:
            print("Creating new file (no SHA included)")
        
        # Make the request to create/update the file
        print(f"Sending PUT request to GitHub API...")
        response = requests.put(api_url, headers=headers, json=data)
        
        print(f"GitHub API response: Status {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"GitHub API success response: {response.text[:200]}...")
            return True, f"Successfully updated GitHub file with {len(cdn_urls)} Discord CDN URLs"
        else:
            print(f"GitHub API error response: {response.text[:200]}...")
            return False, f"Error updating GitHub file: {response.status_code} - {response.text}"
    
    except Exception as e:
        import traceback
        print(f"Exception during GitHub update: {str(e)}")
        
        # Scrub any potential token from error messages before logging
        error_message = str(e)
        if github_token and github_token in error_message:
            error_message = error_message.replace(github_token, "[REDACTED_TOKEN]")
            
        # Get traceback but ensure it doesn't contain the token
        tb = traceback.format_exc()
        if github_token and github_token in tb:
            tb = tb.replace(github_token, "[REDACTED_TOKEN]")
            
        print(f"Traceback: {tb}")
        return False, f"Exception during GitHub update: {error_message}"