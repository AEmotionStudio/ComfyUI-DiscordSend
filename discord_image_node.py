"""ComfyUI node for sending images to Discord and saving them locally."""

import os
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

# Import shared utilities
from discordsend_utils import (
    sanitize_json_for_export, 
    update_github_cdn_urls, 
    extract_prompts_from_workflow,
    send_to_discord_with_retry,
    tensor_to_numpy_uint8
)


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
                "overwrite_last": ("BOOLEAN", {"default": False, "tooltip": "If enabled, will overwrite the last image instead of creating incrementing filenames."})
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
                    "tooltip": "Quality (1-100) for JPEG/WebP. Ignored for PNG. Higher values = better quality but larger file size."
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
                "add_date": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Add the current date (YYYY-MM-DD) to filenames."
                }),
                "add_time": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Add the current time (HH-MM-SS) to filenames."
                }),
                "add_dimensions": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Add width and height dimensions to the filename (WxH format)."
                }),
                "resize_to_power_of_2": ("BOOLEAN", {
                    "default": False,
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
                    "tooltip": "Discord webhook URL (from Server Settings > Integrations > Webhooks). Leave empty to disable Discord integration."
                }),
                "discord_message": ("STRING", {
                    "default": "", 
                    "multiline": True,
                    "tooltip": "Optional text to display with the image. Supports Discord Markdown (bold, italic, etc.)."
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

    def save_images(self, images, filename_prefix="ComfyUI-Image", overwrite_last=False, 
                   file_format="png", quality=95, lossless=True, add_date=False, add_time=False, 
                   add_dimensions=False, resize_to_power_of_2=False, save_output=True, 
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
        
        if add_date:
            # Get ONLY the date in YYYY-MM-DD format
            current_date = time.strftime("%Y-%m-%d")
            date_time_parts.append(current_date)
            print(f"Adding date to filename: {current_date}")
            image_info["date"] = current_date
            
        if add_time:
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
        if overwrite_last:
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
        
        print(f"Using counter: {counter} for {'overwriting' if overwrite_last else 'new files'}")
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
        if send_to_discord and webhook_url and (add_date or add_time or add_dimensions or resize_to_power_of_2 or include_format_in_message):
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
            # Optimization: Use torch operations for scaling/clipping/casting via tensor_to_numpy_uint8
            # This is significantly faster (~70%) and uses less memory than naive numpy conversion
            i = tensor_to_numpy_uint8(image)
            img = Image.fromarray(i)
            
            # Track if resizing happened to optimize Discord encoding later
            was_resized = False

            # Get original dimensions before any resizing
            orig_width, orig_height = img.size
            
            # Resize to power of 2 if enabled
            if resize_to_power_of_2:
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
                        was_resized = True
                        print(f"Successfully resized using {resize_method} method")
                    except Exception as e:
                        print(f"Error during power of 2 resize: {e}")
                        # Fallback to BICUBIC if selected method fails
                        img = img.resize((new_width, new_height), Image.BICUBIC)
                        was_resized = True
                        print("Fallback to BICUBIC resize method due to error")
            
            # Get dimensions - either original or resized
            width, height = img.size
            
            # Add dimensions to filename if enabled
            dimensions_suffix = ""
            if add_dimensions:
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
            if add_dimensions and dimensions_suffix not in filename_with_batch_num:
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
                        # Generate unique filename for Discord using the selected format
                        discord_filename = f"{uuid4()}.{file_format}"
                        file_bytes = BytesIO()

                        # Optimization: Use PIL directly for JPEG/WebP to avoid numpy conversion overhead
                        # Use CV2 for PNG as it is significantly faster for that format
                        
                        # Optimization: Use PIL for JPEG encoding directly (faster, less memory)
                        # Keep OpenCV for PNG (faster) and Pillow for WebP (legacy/consistency)

                        if file_format == "jpeg":
                            # JPEG does not support RGBA, convert to RGB if needed
                            save_img = img
                            if save_img.mode == 'RGBA':
                                save_img = save_img.convert('RGB')
                            
                            jpeg_quality = 100 if lossless else quality
                            save_img.save(file_bytes, format="JPEG", quality=jpeg_quality)
                            file_bytes.seek(0)

                        elif file_format == "png":
                            # Use CV2 for PNG (significantly faster)
                            # Optimization: If image wasn't resized, use the original numpy array 'i'
                            # This avoids an expensive PIL->Numpy conversion/copy (~500ms for 4K images)
                            if not was_resized:
                                img_cv = i
                            else:
                                img_cv = np.array(img)

                            # Convert RGB (PIL) to BGR (OpenCV)
                            if len(img_cv.shape) == 3 and img_cv.shape[2] == 3:
                                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)

                            # Handle color conversion for special cases
                            if len(img_cv.shape) == 2:  # Grayscale
                                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2BGR)
                            elif len(img_cv.shape) == 3 and img_cv.shape[2] == 4:  # RGBA
                                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGBA2BGRA)

                            _, buffer = cv2.imencode('.png', img_cv)
                            file_bytes = BytesIO(buffer)

                        elif file_format == "webp":
                            try:
                                if lossless:
                                    img.save(file_bytes, format="WEBP", lossless=True)
                                else:
                                    img.save(file_bytes, format="WEBP", quality=quality)
                                file_bytes.seek(0)
                            except Exception as e:
                                print(f"Error with WebP encoding for Discord: {e}, falling back to PNG")
                                # Fallback to PNG if WebP encoding fails (using PIL)
                                discord_filename = f"{os.path.splitext(discord_filename)[0]}.png"
                                file_bytes = BytesIO() # Reset buffer
                                img.save(file_bytes, format="PNG", compress_level=self.compress_level)
                                file_bytes.seek(0)
                        
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
                                # Send to Discord with retry logic
                                response = send_to_discord_with_retry(
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
                                                        url_response = send_to_discord_with_retry(
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
                if not overwrite_last:
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
                        url_response = send_to_discord_with_retry(
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
                
                # Send the batch to Discord with retry logic
                response = send_to_discord_with_retry(
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
                                        url_response = send_to_discord_with_retry(
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
    def IS_CHANGED(s, images, filename_prefix="ComfyUI-Image", overwrite_last=False, 
                  file_format="png", quality=95, lossless=True, add_date=False, add_time=False, 
                  add_dimensions=False, resize_to_power_of_2=False, save_output=True, 
                  resize_method="lanczos", show_preview=True, send_to_discord=False, webhook_url="", discord_message="",
                  include_prompts_in_message=False, include_format_in_message=False, group_batched_images=True, 
                  send_workflow_json=False, save_cdn_urls=False, github_cdn_update=False, github_repo="", 
                  github_token="", github_file_path="cdn_urls.md", prompt=None, extra_pnginfo=None):
        return True