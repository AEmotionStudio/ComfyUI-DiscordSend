"""ComfyUI node for sending images to Discord and saving them locally."""

import os
import json
import numpy as np
from PIL import Image
import folder_paths
from PIL.PngImagePlugin import PngInfo
from comfy.cli_args import args
import re
import cv2
from io import BytesIO
from uuid import uuid4
from typing import Any, Union, List, Optional

# Import shared utilities
from shared import (
    sanitize_token_from_text,
    tensor_to_numpy_uint8,
    validate_path_is_safe
)


from .base_node import BaseDiscordNode


class DiscordSendSaveImage(BaseDiscordNode):
    """
    A ComfyUI node that can send images to Discord and save them with advanced options.
    Images can be sent to Discord via webhook integration, while providing flexible
    saving options with customizable naming conventions and format options.
    """
    
    def __init__(self):
        super().__init__()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        self.output_dir = None

    @classmethod
    def INPUT_TYPES(s):
        # Get base inputs from BaseDiscordNode
        base_inputs = BaseDiscordNode.get_discord_input_types()
        cdn_inputs = BaseDiscordNode.get_cdn_input_types()
        filename_inputs = BaseDiscordNode.get_filename_input_types(add_date_default=False)
        
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save and/or send to Discord."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI-Image", "tooltip": "The prefix for the saved files. Supports %batch_num% placeholder for batch indexing."}),
                "overwrite_last": ("BOOLEAN", {"default": False, "tooltip": "⚠️ CAUTION: If enabled, new saves will REPLACE the previous file with the same name. Useful for iterative testing, dangerous for batch production. Note: You must also disable 'add_time' and 'add_date' to ensure filenames are identical."})
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
                    "tooltip": "Use lossless compression for WebP (PNG is always lossless). For JPEG, forces maximum quality (100)."
                }),
                "save_output": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to save images to disk. When disabled, images will only be previewed in the UI."
                }),
                "show_preview": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to show image previews in the UI. Disable to reduce UI clutter for large batches."
                }),
                "resize_to_power_of_2": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Resize images to nearest power of 2 dimensions (useful for game textures). Uses the algorithm selected in 'resize_method'."
                }),
                "resize_method": (["nearest-exact", "bilinear", "bicubic", "lanczos", "box"], {
                    "default": "lanczos", 
                    "tooltip": "Resampling algorithm used ONLY when 'resize_to_power_of_2' is enabled. Ignored otherwise. \n• lanczos: Best for photos\n• nearest-exact: Best for pixel art\n• bilinear/bicubic: Faster"
                }),
                "include_format_in_message": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to include the image format in the Discord message."
                }),
                "group_batched_images": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Group all images from a batch into a single Discord message with a gallery, rather than sending each one separately. Maximum is 9 images."
                }),
                # Mix in shared options
                **filename_inputs,
                **base_inputs,
                **cdn_inputs,
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
        
        # 1. Sanitize workflow data using base class method
        prompt, extra_pnginfo, original_prompt, original_extra_pnginfo = self.sanitize_workflow_data(
            prompt, extra_pnginfo
        )
        
        # 2. Build filename prefix with metadata using base class method
        filename_prefix, image_info = self.build_filename_prefix(
            filename_prefix, add_date, add_time, False, None, None
        )
        
        # Add prefix append
        filename_prefix += self.prefix_append
        
        # 3. Get output directory using base class method
        dest_folder = self.get_dest_folder(save_output)
        
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
        
        # Build image info message using shared utility
        if send_to_discord and webhook_url and (add_date or add_time or add_dimensions or resize_to_power_of_2 or include_format_in_message):
            info_message = build_metadata_section(
                info_dict=image_info,
                include_date=add_date,
                include_time=add_time,
                include_dimensions=False,  # Dimensions added later after processing
                include_format=include_format_in_message,
                file_format=file_format,
                section_title="Image Information"
            )
            image_info["message_prefix"] = info_message
            print("Prepared image information section for Discord message")

        # 4. Extract and build prompts section
        if send_to_discord and include_prompts_in_message:
            workflow_data = self.extract_workflow_from_metadata(original_prompt, original_extra_pnginfo)
            if workflow_data:
                prompt_message = self.build_prompt_message(workflow_data)
                if prompt_message:
                    image_info["prompt_message"] = prompt_message
                    print("Prepared prompts for Discord message")
        
        # Optimization: Create metadata once for the entire batch
        # This prevents redundant sanitization and JSON serialization for every image
        metadata = None
        if not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                # Prompt is already sanitized at start of function
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                # extra_pnginfo is already sanitized at start of function
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))

        for batch_number, image in enumerate(images):
            # Convert the tensor to a PIL image
            i = tensor_to_numpy_uint8(image)
            img = Image.fromarray(i)
            
            # Track if resizing happened to optimize Discord encoding later
            was_resized = False
            orig_width, orig_height = img.size
            
            # Resize to power of 2 if enabled
            if resize_to_power_of_2:
                new_width = 2 ** int(np.log2(orig_width) + 0.5)
                new_height = 2 ** int(np.log2(orig_height) + 0.5)
                
                print(f"Resizing image from {orig_width}x{orig_height} to {new_width}x{new_height} (power of 2)")
                
                if send_to_discord and webhook_url and batch_number == 0:
                    image_info["original_dimensions"] = f"{orig_width}x{orig_height}"
                    image_info["resized_dimensions"] = f"{new_width}x{new_height}"
                
                if (new_width != orig_width or new_height != orig_height):
                    try:
                        img = img.resize((new_width, new_height), selected_resize_method)
                        was_resized = True
                        print(f"Successfully resized using {resize_method} method")
                    except Exception as e:
                        print(f"Error during power of 2 resize: {e}")
                        img = img.resize((new_width, new_height), Image.BICUBIC)
                        was_resized = True
                        print("Fallback to BICUBIC resize method due to error")
            
            # Get dimensions
            width, height = img.size
            
            # Add dimensions to filename if enabled
            dimensions_suffix = ""
            if add_dimensions:
                dimensions_suffix = f"_{width}x{height}"
                filename_prefix += dimensions_suffix
                
                if send_to_discord and webhook_url and batch_number == 0:
                    image_info["dimensions"] = f"{width}x{height}"
            
            # Add image information to Discord message if this is the first image
            if send_to_discord and webhook_url and batch_number == 0:
                if "message_prefix" in image_info:
                    info_message = image_info["message_prefix"]
                    has_resize_dimensions = "original_dimensions" in image_info and "resized_dimensions" in image_info
                    has_dimensions = "dimensions" in image_info

                    if (has_resize_dimensions or has_dimensions) and not info_message:
                        info_message = "\n\n**Image Information:**\n"

                    if has_resize_dimensions:
                        info_message += f"**Original Dimensions:** {image_info['original_dimensions']}\n"
                        info_message += f"**Resized Dimensions:** {image_info['resized_dimensions']} (Power of 2)\n"
                    elif has_dimensions:
                        info_message += f"**Dimensions:** {image_info['dimensions']}\n"

                    if info_message:
                        discord_message += info_message
                        print("Added image information to Discord message")
                
                if "prompt_message" in image_info:
                    discord_message += image_info["prompt_message"]
                    print("Added prompts to Discord message after image information")
            
            # For Discord output
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            
            # Add dimensions tag before the counter if enabled
            if add_dimensions and dimensions_suffix not in filename_with_batch_num:
                base_name = os.path.splitext(filename_with_batch_num)[0]
                filename_with_batch_num = f"{base_name}{dimensions_suffix}"
            
            # File extension based on format
            extension = f".{file_format}"
            file = f"{filename_with_batch_num}_{counter:05}_{extension}"
            
            if file.endswith(f"_{extension}"):
                file = file[:-len(f"_{extension}")] + extension
                
            filepath = os.path.join(full_output_folder, file)
            
            # Security: Validate output path to prevent symlink overwrites
            validate_path_is_safe(filepath)

            try:
                # Save the image based on format
                if file_format == "png":
                    img.save(filepath, pnginfo=metadata, compress_level=self.compress_level)
                elif file_format == "jpeg":
                    jpeg_quality = 100 if lossless else quality
                    img.save(filepath, format="JPEG", quality=jpeg_quality)
                elif file_format == "webp":
                    if lossless:
                        img.save(filepath, format="WEBP", lossless=True)
                    else:
                        img.save(filepath, format="WEBP", quality=quality)
                
                output_files.append(filepath)
                
                print(f"Saved image with dimensions: {img.size[0]}x{img.size[1]}")
                    
                results.append({
                    "filename": file,
                    "subfolder": "discord_output/" + (subfolder if subfolder else "") if save_output else "",
                    "type": "output" if save_output else "temp",
                    "path": filepath
                })
                
                # Send to Discord if enabled
                if send_to_discord and webhook_url:
                    try:
                        discord_filename = f"{uuid4()}.{file_format}"
                        file_bytes = BytesIO()

                        if file_format == "jpeg":
                            save_img = img
                            if save_img.mode == 'RGBA':
                                save_img = save_img.convert('RGB')
                            jpeg_quality = 100 if lossless else quality
                            save_img.save(file_bytes, format="JPEG", quality=jpeg_quality)
                            file_bytes.seek(0)

                        elif file_format == "png":
                            if not was_resized:
                                img_cv = i
                            else:
                                img_cv = np.array(img)

                            if len(img_cv.shape) == 3 and img_cv.shape[2] == 3:
                                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
                            if len(img_cv.shape) == 2:
                                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2BGR)
                            elif len(img_cv.shape) == 3 and img_cv.shape[2] == 4:
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
                                discord_filename = f"{os.path.splitext(discord_filename)[0]}.png"
                                file_bytes = BytesIO() # Reset buffer
                                img.save(file_bytes, format="PNG", compress_level=self.compress_level)
                                file_bytes.seek(0)
                        
                        if group_batched_images:
                            batch_discord_files.append((discord_filename, file_bytes.getvalue()))
                            
                            # Prepare workflow JSON only once for the whole batch
                            if batch_number == 0 and send_workflow_json and (prompt is not None or extra_pnginfo is not None):
                                wflow = self.extract_workflow_from_metadata(original_prompt, original_extra_pnginfo)
                                if wflow:
                                    batch_workflow_json = wflow
                            
                            if batch_number == 0 and discord_message:
                                batch_discord_data["content"] = discord_message
                            
                        else:
                            # Immediate send
                            files = {
                                "file": (discord_filename, file_bytes.getvalue())
                            }
                            
                            if send_workflow_json and (prompt is not None or extra_pnginfo is not None):
                                wflow = self.extract_workflow_from_metadata(original_prompt, original_extra_pnginfo)
                                if wflow:
                                    json_filename = f"{os.path.splitext(discord_filename)[0]}.json"
                                    files["workflow"] = (json_filename, json.dumps(wflow, indent=2).encode('utf-8'))
                            
                            data = {}
                            if discord_message:
                                data["content"] = discord_message
                            
                            success, response, new_urls = self.send_discord_files(webhook_url, files, data, save_cdn_urls)
                            
                            if success:
                                print(f"Successfully sent image {batch_number+1} to Discord")
                                discord_sent_files.append(discord_filename)
                                if new_urls:
                                    batch_cdn_urls.extend(new_urls)
                                    self.send_cdn_urls_to_discord(webhook_url, new_urls, "Discord CDN URLs for the uploaded images:")
                            else:
                                print(f"Error: Discord returned status code {response.status_code}")
                                discord_send_success = False

                    except Exception as e:
                        print(f"Error processing image for Discord: {e}")
                        discord_send_success = False
                
                if not overwrite_last:
                    counter += 1
            except Exception as e:
                print(f"Error saving image: {e}")
        
        if results:
            if save_output:
                print(f"DiscordSendSaveImage: Saved {len(results)} images to {full_output_folder}")
            else:
                print("DiscordSendSaveImage: Preview only mode - no images saved to disk")
                
            if send_to_discord and discord_sent_files:
                print("DiscordSendSaveImage: Successfully sent all images to Discord")
            elif send_to_discord and not discord_send_success:
                print("DiscordSendSaveImage: There were errors sending some images to Discord")
        else:
            print("DiscordSendSaveImage: No images were processed")
        
        # Send batch to Discord
        if send_to_discord and webhook_url and group_batched_images and batch_discord_files:
            try:
                print(f"Sending {len(batch_discord_files)} images as a batch to Discord...")
                
                files = {}
                for i, (filename, file_bytes) in enumerate(batch_discord_files):
                    files[f"file{i}"] = (filename, file_bytes)
                
                if send_workflow_json and batch_workflow_json:
                     json_filename = f"workflow-{uuid4()}.json"
                     json_data = json.dumps(batch_workflow_json, indent=2)
                     files["workflow"] = (json_filename, json_data.encode('utf-8'))
                
                success, response, new_urls = self.send_discord_files(webhook_url, files, batch_discord_data, save_cdn_urls)
                
                if success:
                    print(f"Successfully sent batch of {len(batch_discord_files)} images to Discord as a gallery")
                    discord_sent_files = ["batch_gallery"]
                    if save_cdn_urls and new_urls:
                        batch_cdn_urls.extend(new_urls)
                        self.send_cdn_urls_to_discord(webhook_url, new_urls, "Discord CDN URLs for the uploaded images:")
                else:
                    error_msg = sanitize_token_from_text(response.text, webhook_url)
                    print(f"Error sending batch to Discord: Status code {response.status_code} - {error_msg}")
                    discord_send_success = False
            except Exception as e:
                print(f"Error sending batch to Discord: {e}")
                discord_send_success = False

        # Update GitHub repository
        if github_cdn_update and send_to_discord and (discord_cdn_urls or batch_cdn_urls):
            urls_to_send = discord_cdn_urls if discord_cdn_urls else batch_cdn_urls
            self.update_github_cdn(urls_to_send, github_repo, github_token, github_file_path)
            
        elif github_cdn_update:
            reasons = []
            if not send_to_discord: reasons.append("send_to_discord is disabled")
            if not (discord_cdn_urls or batch_cdn_urls): reasons.append("no CDN URLs were collected")
            if not github_repo: reasons.append("github_repo is empty")
            if not github_token: reasons.append("github_token is empty")
            if not github_file_path: reasons.append("github_file_path is empty")
            print(f"GitHub update was enabled but not triggered because: {', '.join(reasons)}")
        
        # Return results
        if show_preview:
            return {"ui": {"images": results}, "result": ((save_output, output_files, discord_send_success if send_to_discord else None),)}, output_files[0] if output_files else ""
        else:
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