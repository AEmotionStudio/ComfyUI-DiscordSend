"""ComfyUI node for sending videos to Discord and saving them locally."""

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
from pathlib import Path
import sys
import datetime
import subprocess
import itertools
import functools
import server

# Import shared utilities
from discordsend_utils import sanitize_json_for_export, update_github_cdn_urls, send_to_discord_with_retry, tensor_to_numpy_uint8
# Define cached decorator for local use
def cached(max_size=None):
    """
    Simple cache decorator to avoid re-loading formats
    """
    def decorator(func):
        cache = {}
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key not in cache:
                cache[key] = func(*args, **kwargs)
            return cache[key]
        return wrapper
    
    # Handle when decorator is used without arguments
    if callable(max_size):
        func = max_size
        max_size = None
        return decorator(func)
    return decorator

# Try to import dependencies from nodes.py
try:
    from discordsend_utils import ffmpeg_path, get_audio, hash_path, validate_path, requeue_workflow, \
            gifski_path, calculate_file_hash, strip_path, try_download_video, is_url, \
            imageOrLatent, BIGMAX, merge_filter_args, ENCODE_ARGS, floatOrInt
    from comfy.utils import ProgressBar
    has_vhs_formats = False  # Set to False since we're not using VHS formats anymore
except ImportError:
    print("Warning: Some dependencies from Video Helper Suite might be missing")
    # Define minimal versions of required functions/classes
    ffmpeg_path = None
    ENCODE_ARGS = ("utf-8", "ignore")
    floatOrInt = ("FLOAT", "INT")
    imageOrLatent = ("IMAGE", "LATENT")
    BIGMAX = 1000000
    has_vhs_formats = False

    class ProgressBar:
        def __init__(self, total):
            self.total = total
            self.current = 0
        
        def update(self, advance=1):
            self.current += advance
            print(f"Progress: {self.current}/{self.total}", end="\r")

# Fallback if ffmpeg_path is None, try to detect it
if ffmpeg_path is None:
    # Try direct detection methods for ffmpeg
    try:
        # Try imageio-ffmpeg first (common in Python environments)
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            print(f"Found ffmpeg via imageio_ffmpeg: {ffmpeg_path}")
        except (ImportError, Exception):
            # Fall back to checking the system path
            from shutil import which
            ffmpeg_path = which("ffmpeg")
            if ffmpeg_path:
                print(f"Found ffmpeg in system path: {ffmpeg_path}")
    except Exception as e:
        print(f"Error during ffmpeg detection: {str(e)}")

# Function to validate video files for Discord compatibility
def validate_video_for_discord(file_path):
    """
    Validate that a video file is compatible with Discord.
    Returns a tuple of (is_valid, message)
    """
    if not os.path.exists(file_path):
        return False, f"File does not exist: {file_path}"
    
    # Check if file is empty or too small
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, "File is empty"
    if file_size < 1024:  # Less than 1KB
        return False, f"File is suspiciously small: {file_size} bytes"
    
    # Check if file is too large for Discord (Discord limit is 25MB for regular users, 50MB for Nitro)
    max_size = 25 * 1024 * 1024  # 25MB in bytes
    if file_size > max_size:
        return False, f"File exceeds Discord's size limit: {file_size} bytes (max {max_size} bytes)"
    
    # Get file extension
    ext = os.path.splitext(file_path)[1].lower().lstrip('.')
    
    # Return validation result based on file type
    if ext in ['mp4', 'webm', 'gif']:
        # These formats are well supported by Discord
        return True, "Valid video format for Discord"
    elif ext in ['mov']:
        # MOV files (ProRes) may need conversion for Discord
        return False, "MOV files may need conversion for Discord compatibility"
    elif ext in ['png']:
        # PNG sequences are not directly supported by Discord
        return False, "PNG sequences are not directly supported by Discord and require compilation into a video format"
    else:
        # For any other extension, warn but allow sending
        return False, f"Unknown format {ext}, may not be compatible with Discord"

class DiscordSendSaveVideo:
    """
    A ComfyUI node that can send videos to Discord and save them with advanced options.
    Videos can be sent to Discord via webhook integration, while providing flexible
    saving options with customizable format options.
    """
    
    def __init__(self):
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        self.output_dir = None  # Will be set during saving to store the actual path used

    @classmethod
    def INPUT_TYPES(s):
        """
        Define the input types for the DiscordSendSaveVideo node.
        """
        # Check if ffmpeg is available
        if ffmpeg_path is None:
            print("ffmpeg not found. Video output will be limited or unavailable.")
            # Always make GIF available even without ffmpeg (we'll use PIL as fallback)
            video_formats = ["video/gif"]
        else:
            # Enhanced video formats for high-quality output
            video_formats = [
                # Image/Animation formats
                "image/gif",       # Standard GIF format
                "image/webp",      # WebP format (better quality than GIF)
                "video/gif",       # Video format GIF (higher frame rate support)
                
                # Standard video formats
                "video/mp4",       # Standard MP4 format with good compatibility
                "video/h264-mp4",  # High-quality MP4 with H264 codec
                "video/h265-mp4",  # MP4 with H265/HEVC codec (better compression)
                "video/webm",      # Standard WebM format
                "video/vp9-webm",  # WebM with VP9 codec (higher quality than VP8)
                
                # Professional formats
                "video/prores",    # Apple ProRes (high quality, low compression)
            ]
        
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The image sequence to save as video and/or send to Discord."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI-Video", "tooltip": "The prefix for the saved files."}),
                "overwrite_last": ("BOOLEAN", {"default": False, "tooltip": "If enabled, will overwrite the last video instead of creating incrementing filenames."})
            },
            "optional": {
                # Video format settings
                "format": (video_formats, {
                    'default': "video/h264-mp4", 
                    "tooltip": "The video format to save in. Options include:\n" +
                               "# Image formats:\n" +
                               "- image/gif: Standard GIF format (NO AUDIO support)\n" +
                               "- image/webp: WebP format (better quality than GIF, NO AUDIO support)\n" +
                               "- video/gif: Video format GIF (higher frame rate support, NO AUDIO support)\n\n" +
                               "# Standard video formats:\n" +
                               "- video/mp4: Standard MP4 format with good compatibility (supports audio)\n" +
                               "- video/h264-mp4: High-quality MP4 with H264 codec (supports audio)\n" +
                               "- video/h265-mp4: MP4 with H265/HEVC codec (better compression, supports audio)\n" +
                               "- video/webm: Standard WebM format (supports audio)\n" +
                               "- video/vp9-webm: WebM with VP9 codec (higher quality, supports audio)\n\n" +
                               "# Professional formats:\n" +
                               "- video/prores: Apple ProRes (professional quality, supports audio when saving locally but NO AUDIO when sending to Discord, requires QuickTime or specialized player to view on Windows)"
                }),
                "frame_rate": (
                    "FLOAT", 
                    {"default": 8.0, "min": 0.1, "max": 120.0, "step": 0.1, "tooltip": "Frames per second for the output video. Values below 1 will make each image stay on screen longer (e.g., 0.5 = 2 seconds per frame)."}
                ),
                "quality": ("INT", {
                    "default": 85,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Quality setting for video compression (1-100). Higher is better quality but larger file size."
                }),
                "loop_count": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "display": "loop (0=infinite)",
                    "tooltip": "Number of times to loop the video (0 = infinite loop, only applies to GIF format)."
                }),
                "lossless": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "If enabled, will use lossless compression for supported formats. This option may be ignored for formats that don't support lossless encoding."
                }),
                
                # Video effect options
                "pingpong": ("BOOLEAN", {"default": False, "tooltip": "If enabled, video will play forward then backward (ping-pong effect)."}),
                "save_output": ("BOOLEAN", {
                    "default": True, 
                    "tooltip": "Whether to save videos to disk. When disabled, videos will only be previewed in the UI."
                }),
                "audio": ("AUDIO", {
                    "tooltip": "Optional audio to embed in the video."
                }),
                
                # Filename options
                "add_date": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Add the current date (YYYY-MM-DD) to filenames."
                }),
                "add_time": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Add the current time (HH-MM-SS) to filenames. ⚠️ Recommended for Discord to avoid caching issues."
                }),
                "add_dimensions": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Add width and height dimensions to the filename (WxH format)."
                }),
                
                # Discord options
                "send_to_discord": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to send the videos to Discord via webhook."
                }),
                "webhook_url": ("STRING", {
                    "default": "", 
                    "multiline": False,
                    "tooltip": "Discord webhook URL (from Server Settings > Integrations > Webhooks). Leave empty to disable Discord integration."
                }),
                "discord_message": ("STRING", {
                    "default": "", 
                    "multiline": True,
                    "tooltip": "Optional text to display with the video. Supports Discord Markdown (bold, italic, etc.)."
                }),
                "include_prompts_in_message": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to include the positive and negative prompts in the Discord message."
                }),
                "include_video_info": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to include the video information (frame rate, format) in the Discord message."
                }),
                "send_workflow_json": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to send the workflow JSON alongside the video to Discord, allowing dragging the JSON into ComfyUI to restore the workflow."
                }),
                "save_cdn_urls": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Whether to save the Discord CDN URLs of the uploaded videos as a text file and attach it to the Discord message."
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
                })
            },
            "hidden": {
                "prompt": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID"
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    RETURN_TYPE_TOOLTIPS = ("Path to the saved video file, can be used in other nodes to reference the generated video.",)
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    CATEGORY = "video/output"
    DESCRIPTION = "Saves image sequences as videos with advanced options and can send them to Discord via webhook integration."
    OUTPUT_IS_LIST = (False,)

    @classmethod
    def CONTEXT_MENUS(s):
        return {
        }

    def save_video(self, images, filename_prefix="ComfyUI-Video", overwrite_last=False,
                   format="video/h264-mp4", frame_rate=8.0, quality=85, loop_count=0, lossless=False, 
                   pingpong=False, save_output=True, audio=None,
                   add_date=True, add_time=True, add_dimensions=True,
                   send_to_discord=False, webhook_url="", discord_message="",
                   include_prompts_in_message=False, include_video_info=True, send_workflow_json=False, 
                   save_cdn_urls=False, github_cdn_update=False, github_repo="", github_token="", 
                   github_file_path="cdn_urls.md", prompt=None, extra_pnginfo=None, unique_id=None, **format_properties):
        """
        Save image sequences as videos and optionally send to Discord.
        """
        results = []
        output_files = []
        discord_sent_files = []
        discord_send_success = True
        
        # For tracking Discord CDN URLs
        discord_cdn_urls = []
        
        # Store original prompt for later processing but sanitize it for security
        original_prompt = prompt
        original_extra_pnginfo = extra_pnginfo
        
        # Sanitize the workflow and extra_pnginfo data to remove webhook URLs
        # This protects user security when sharing workflows
        if prompt is not None:
            prompt = sanitize_json_for_export(prompt)
        
        if extra_pnginfo is not None:
            extra_pnginfo = sanitize_json_for_export(extra_pnginfo)
            
        # Ensure workflow JSON is sanitized if sending to Discord
        if send_to_discord and send_workflow_json and original_prompt is not None:
            # Double sanitization for Discord export to ensure all webhook URLs are removed
            workflow_export = sanitize_json_for_export(original_prompt)
        
        # Get number of frames and set up progress bar
        num_frames = len(images)
        if num_frames == 0:
            print("DiscordSendSaveVideo: No frames to process")
            return {"ui": {}, "result": (None,)}
        
        pbar = ProgressBar(num_frames)
        
        # Get first image for metadata
        first_image = images[0]
        
        # Add date and/or time if enabled
        date_time_parts = []
        
        # Video info for Discord message
        video_info = {}
        
        if add_date:
            # Get ONLY the date in YYYY-MM-DD format
            current_date = time.strftime("%Y-%m-%d")
            date_time_parts.append(current_date)
            print(f"Adding date to filename: {current_date}")
            video_info["date"] = current_date
            
        if add_time:
            # Get ONLY the time in HH-MM-SS format
            current_time = time.strftime("%H-%M-%S")
            date_time_parts.append(current_time)
            print(f"Adding time to filename: {current_time}")
            video_info["time"] = current_time
            
        # Add dimensions if enabled
        if add_dimensions:
            # Get dimensions from first frame
            height, width = images[0].shape[0], images[0].shape[1]
            dim_text = f"{width}x{height}"
            date_time_parts.append(dim_text)
            print(f"Adding dimensions to filename: {dim_text}")
            video_info["dimensions"] = dim_text
        
        # Add date/time/dimensions components to filename prefix if any were enabled
        if date_time_parts:
            date_time_suffix = "_" + "_".join(date_time_parts)
            filename_prefix += date_time_suffix
            print(f"Final metadata suffix: {date_time_suffix}")
            
        # Add prefix append
        filename_prefix += self.prefix_append
        
        # Get ComfyUI output directory for safe path handling
        comfy_output_dir = folder_paths.get_output_directory()
        
        # Choose destination directory based on save_output flag
        if save_output:
            # Create a video output subfolder in the ComfyUI output directory
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
            
        # For overwrite functionality
        if overwrite_last:
            counter = 1  # Always use the same counter value for overwriting
            print("Overwrite mode enabled: will overwrite last video with same name")
        
        # Set metadata
        metadata = PngInfo()
        video_metadata = {}
        if prompt is not None:
            metadata.add_text("prompt", json.dumps(prompt))
            video_metadata["prompt"] = json.dumps(prompt)
        if extra_pnginfo is not None:
            for x in extra_pnginfo:
                metadata.add_text(x, json.dumps(extra_pnginfo[x]))
                video_metadata[x] = extra_pnginfo[x]
        metadata.add_text("CreationTime", datetime.datetime.now().isoformat(" ")[:19])
        
        # Save first frame as PNG to keep metadata
        first_image_file = f"{filename}_{counter:05}.png"
        first_image_path = os.path.join(full_output_folder, first_image_file)
        Image.fromarray(tensor_to_numpy_uint8(first_image)).save(
            first_image_path,
            pnginfo=metadata,
            compress_level=4,
        )
        output_files.append(first_image_path)
        
        # Process format string
        format_type, format_ext = format.split("/")
        
        # Handle special format extensions
        if format == "video/h264-mp4" or format == "video/h265-mp4":
            format_ext = "mp4"
        elif format == "video/vp9-webm":
            format_ext = "webm"
        elif format == "video/prores":
            format_ext = "mov"
        
        # Prepare images for ffmpeg or PIL
        if pingpong:
            # Create ping-pong effect
            def to_pingpong(inp):
                if not hasattr(inp, "__getitem__"):
                    inp = list(inp)
                yield from inp
                for i in range(len(inp)-2, 0, -1):
                    yield inp[i]
            image_sequence = list(to_pingpong(images))
        else:
            image_sequence = images
        
        # Set up file naming and path
        file = f"{filename}_{counter:05}.{format_ext}"
        file_path = os.path.join(full_output_folder, file)
        
        # Check if we need ffmpeg (for video formats) or can use PIL (for image formats)
        use_pil = format_type == "image" or ffmpeg_path is None
        
        # For PIL-based formats (image/xxx) or when ffmpeg is not available
        if use_pil:
            try:
                print(f"Using PIL for {format} creation")
                # Convert tensor images to PIL images
                pil_images = []
                for img in image_sequence:
                    img_np = tensor_to_numpy_uint8(img)
                    pil_images.append(Image.fromarray(img_np))
                
                if len(pil_images) > 0:
                    if format_ext == "gif":
                        # Calculate durations
                        duration = int(1000 / frame_rate)  # Convert fps to ms per frame
                        durations = [duration] * len(pil_images)
                        
                        # Save GIF using PIL
                        pil_images[0].save(
                            file_path,
                            format="GIF",
                            append_images=pil_images[1:],
                            save_all=True,
                            duration=durations,
                            loop=0 if loop_count == 0 else loop_count,
                            optimize=False
                        )
                        output_files.append(file_path)
                    elif format_ext == "webp":
                        # WebP supports animation too
                        duration = int(1000 / frame_rate)
                        
                        # WebP supports lossless mode
                        if lossless:
                            pil_images[0].save(
                                file_path,
                                format="WEBP",
                                append_images=pil_images[1:],
                                save_all=True,
                                duration=duration,
                                loop=0 if loop_count == 0 else loop_count,
                                lossless=True
                            )
                        else:
                            pil_images[0].save(
                                file_path,
                                format="WEBP",
                                append_images=pil_images[1:],
                                save_all=True,
                                duration=duration,
                                loop=0 if loop_count == 0 else loop_count,
                                quality=quality,
                            )
                        output_files.append(file_path)
                    else:
                        # For non-animated formats, just save the first frame
                        print(f"Format {format} doesn't support animation with PIL. Saving first frame only.")
                        pil_images[0].save(file_path, format=format_ext.upper())
                        output_files.append(file_path)
                else:
                    print("No images to save")
            except Exception as e:
                print(f"Error creating {format} with PIL: {str(e)}")
                return {"ui": {}, "result": (None,)}
            
            if ffmpeg_path is None and format_type == "video" and format_ext not in ["gif", "webp"]:
                print(f"Warning: ffmpeg is required for video format {format} and could not be found.")
                print(f"The file was saved as an image sequence instead.")
        else:
            # Handle VHS formats if this is an advanced format
            is_vhs_format = has_vhs_formats and format not in ["video/mp4", "video/webm", "video/gif"]
            
            # If using VHS format, apply format widgets and get custom parameters
            if is_vhs_format:
                try:
                    # Extract the format name without the prefix
                    vhs_format_name = format.split("/")[-1]
                    
                    # Define basic formats directly without loading from JSON files
                    basic_formats = {
                        "mp4": {
                            "extension": "mp4",
                            "main_pass": ["-c:v", "libx264", "-crf", str(100-quality), "-pix_fmt", "yuv420p"],
                        },
                        "webm": {
                            "extension": "webm",
                            "main_pass": ["-c:v", "libvpx-vp9", "-crf", str(100-quality), "-b:v", "0"],
                        },
                        "gif": {
                            "extension": "gif",
                            "main_pass": ["-vf", f"fps={frame_rate}", "-loop", "0" if loop_count == 0 else str(loop_count)],
                        }
                    }
                    
                    # Use basic format if defined, otherwise default
                    video_format = basic_formats.get(vhs_format_name, {"extension": vhs_format_name, "main_pass": []})
                    
                    # Debug output to help diagnose format issues
                    print(f"Using format: {vhs_format_name}")
                    print(f"Format options: {str(video_format)}")
                    
                    # Handle special format settings like dimension alignment
                    has_alpha = first_image.shape[-1] == 4
                    dim_alignment = video_format.get("dim_alignment", 2)
                    
                    # Check if dimensions need to be adjusted
                    if (first_image.shape[1] % dim_alignment) or (first_image.shape[0] % dim_alignment):
                        # Output frames must be padded
                        print(f"Adjusting dimensions to match format requirements (alignment: {dim_alignment})")
                        to_pad = (-first_image.shape[1] % dim_alignment,
                                -first_image.shape[0] % dim_alignment)
                        # Use simple resizing since we don't have the padding function
                        new_dims = (
                            -first_image.shape[1] % dim_alignment + first_image.shape[1],
                            -first_image.shape[0] % dim_alignment + first_image.shape[0]
                        )
                        dimensions = f"{new_dims[0]}x{new_dims[1]}"
                    else:
                        dimensions = f"{first_image.shape[1]}x{first_image.shape[0]}"
                    
                    # Set color depth
                    if video_format.get('input_color_depth', '8bit') == '16bit':
                        # Handle 16-bit if needed - for now we just fall back to 8-bit
                        print("16-bit color depth requested but not supported in this node, using 8-bit")
                        if has_alpha:
                            i_pix_fmt = 'rgba'
                        else:
                            i_pix_fmt = 'rgb24'
                    else:
                        if has_alpha:
                            i_pix_fmt = 'rgba'
                        else:
                            i_pix_fmt = 'rgb24'
                    
                    # Get bitrate settings
                    bitrate_arg = []
                    bitrate = video_format.get('bitrate')
                    if bitrate is not None:
                        if video_format.get('megabit') == 'True':
                            bitrate_arg = ["-b:v", f"{bitrate}M"]
                        else:
                            bitrate_arg = ["-b:v", f"{bitrate}K"]
                    
                    # Handle loop arguments
                    if loop_count > 0:
                        loop_args = ["-vf", f"loop={loop_count}:size={num_frames}"]
                    else:
                        loop_args = []
                    
                    # Set up file path with correct extension
                    file = f"{filename}_{counter:05}.{video_format['extension']}"
                    file_path = os.path.join(full_output_folder, file)
                    
                    # Set up environment
                    env = os.environ.copy()
                    if "environment" in video_format:
                        env.update(video_format["environment"])
                    
                    # Convert tensor images to bytes
                    # Optimization: Use tensor_to_numpy_uint8 for faster conversion
                    images_bytes = map(lambda x: tensor_to_numpy_uint8(x).tobytes(), image_sequence)
                    
                    # Base ffmpeg arguments
                    args = [
                        ffmpeg_path, "-v", "error", 
                        "-f", "rawvideo", 
                        "-pix_fmt", i_pix_fmt,
                        "-s", dimensions, 
                        "-r", str(frame_rate), 
                        "-i", "-"
                    ] + loop_args
                    
                    # Apply main pass arguments from format
                    args += video_format['main_pass'] + bitrate_arg + [file_path]
                    
                    # Execute ffmpeg process
                    try:
                        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                        
                        # Feed frames to ffmpeg
                        for image_bytes in images_bytes:
                            pbar.update(1)
                            process.stdin.write(image_bytes)
                        
                        # Close stdin and get output
                        process.stdin.close()
                        process.wait()
                        
                        if process.returncode != 0:
                            stderr = process.stderr.read().decode(*ENCODE_ARGS)
                            raise Exception(f"ffmpeg encoding error: {stderr}")
                        
                        output_files.append(file_path)
                    except Exception as e:
                        print(f"Error with VHS format encoding: {str(e)}")
                        # Fall back to basic encoding if VHS format fails
                        is_vhs_format = False
                
                except Exception as e:
                    print(f"Error applying VHS format {format}: {str(e)}")
                    # Fall back to basic encoding if VHS format fails
                    is_vhs_format = False
            
            # Use standard ffmpeg for basic formats or if VHS format failed
            if not is_vhs_format:
                # Use ffmpeg for video processing
                # Set video parameters
                dimensions = f"{first_image.shape[1]}x{first_image.shape[0]}"
                has_alpha = first_image.shape[-1] == 4
                
                # Convert tensor images to bytes 
                if has_alpha:
                    i_pix_fmt = 'rgba'
                else:
                    i_pix_fmt = 'rgb24'

                # Optimization: Use tensor_to_numpy_uint8 for faster conversion
                images_bytes = map(lambda x: tensor_to_numpy_uint8(x).tobytes(), image_sequence)
                
                # Set up ffmpeg arguments based on format
                loop_args = []
                if format_ext == "gif" and loop_count > 0:
                    loop_args = ["-vf", f"loop={loop_count}:size={num_frames}"]
                
                bitrate_arg = []
                # Higher quality = higher bitrate (up to 20M for 100 quality)
                bitrate = int((quality / 100.0) * 20)
                if bitrate > 0 and not lossless:  # Only use bitrate for non-lossless
                    bitrate_arg = ["-b:v", f"{bitrate}M"]
                
                # Base ffmpeg arguments
                args = [
                    ffmpeg_path, "-v", "error", 
                    "-f", "rawvideo", 
                    "-pix_fmt", i_pix_fmt,
                    "-s", dimensions, 
                    "-r", str(frame_rate), 
                    "-i", "-"
                ] + loop_args
                
                # Format-specific arguments
                main_pass = []
                if format_ext == "gif":
                    # Different GIF encoders
                    if format == "video/gif":
                        # Standard GIF settings
                        if lossless:
                            # For "lossless" GIF, use highest quality settings possible
                            main_pass = ["-vf", "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=full[p];[s1][p]paletteuse=dither=sierra2_4a", "-loop", "0"]
                        else:
                            main_pass = ["-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", "-loop", "0"]
                    
                    # Add flags to improve Discord compatibility
                    if loop_count <= 0:
                        loop_count = 0  # Ensure infinite loop for Discord
                elif format_ext == "mp4":
                    # Determine MP4 codec based on the format
                    if format == "video/h264-mp4":
                        # High-quality H.264 settings
                        if lossless:
                            main_pass = ["-c:v", "libx264", "-preset", "slow", "-qp", "0"]
                        else:
                            main_pass = ["-c:v", "libx264", "-preset", "slow", "-crf", str(int(18 - (quality/10)))]
                    elif format == "video/h265-mp4":
                        # H.265/HEVC settings (better compression)
                        if lossless:
                            main_pass = ["-c:v", "libx265", "-preset", "medium", "-x265-params", "lossless=1"]
                        else:
                            main_pass = ["-c:v", "libx265", "-preset", "medium", "-crf", str(int(23 - (quality/5)))]
                    else:
                        # Standard MP4 settings
                        if lossless:
                            main_pass = ["-c:v", "libx264", "-preset", "medium", "-qp", "0"]
                        else:
                            main_pass = ["-c:v", "libx264", "-preset", "medium", "-crf", str(int(28 - (quality/5)))]
                    
                    # Ensure Discord compatibility by always using yuv420p
                    main_pass.extend(["-pix_fmt", "yuv420p"])
                    
                    # Add extra parameters for Discord compatibility
                    main_pass.extend(["-movflags", "faststart"])
                elif format_ext == "webm":
                    # Determine WebM codec based on the format
                    if format == "video/vp9-webm":
                        # VP9 settings (higher quality than VP8)
                        if lossless:
                            main_pass = ["-c:v", "libvpx-vp9", "-lossless", "1", "-row-mt", "1"]
                        else:
                            main_pass = ["-c:v", "libvpx-vp9", "-crf", str(int(30 - (quality/3))), "-b:v", "0", "-row-mt", "1"]
                    else:
                        # Standard WebM settings
                        if lossless:
                            main_pass = ["-c:v", "libvpx-vp9", "-lossless", "1"]
                        else:
                            main_pass = ["-c:v", "libvpx-vp9", "-crf", str(int(63 - (quality * 0.63)))]
                    
                    # Set pixel format based on alpha
                    if has_alpha:
                        main_pass.extend(["-pix_fmt", "yuva420p"])
                    else:
                        main_pass.extend(["-pix_fmt", "yuv420p"])
                    
                    # Additional flags for Discord compatibility
                    main_pass.extend(["-auto-alt-ref", "0"])
                
                args += main_pass + bitrate_arg + [file_path]
                
                # Execute ffmpeg process
                env = os.environ.copy()
                try:
                    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                    
                    # Feed frames to ffmpeg
                    for image_bytes in images_bytes:
                        pbar.update(1)
                        process.stdin.write(image_bytes)
                    
                    # Close stdin and get output
                    process.stdin.close()
                    process.wait()
                    
                    if process.returncode != 0:
                        stderr = process.stderr.read().decode(*ENCODE_ARGS)
                        raise Exception(f"ffmpeg encoding error: {stderr}")
                    
                    output_files.append(file_path)
                except Exception as e:
                    print(f"DiscordSendSaveVideo error: {str(e)}")
                    discord_send_success = False
            
            # Add audio if provided (applies to both VHS and standard formats)
            if audio is not None and discord_send_success:
                try:
                    a_waveform = audio.get('waveform', None)
                    if a_waveform is not None:
                        # Create audio file if input was provided
                        if is_vhs_format:
                            extension = video_format['extension']
                        else:
                            extension = format_ext
                        
                        output_file_with_audio = f"{filename}_{counter:05}-audio.{extension}"
                        output_file_with_audio_path = os.path.join(full_output_folder, output_file_with_audio)
                        
                        # Set up audio encoding parameters
                        channels = a_waveform.size(1)
                        sample_rate = audio.get('sample_rate', 44100)
                        
                        # Determine audio codec based on format
                        if is_vhs_format and "audio_pass" in video_format:
                            # Use format-specific audio settings if available
                            audio_pass = video_format["audio_pass"]
                        else:
                            # Default audio codecs based on format
                            if format_ext == "mp4":
                                audio_pass = ["-c:a", "aac", "-b:a", "192k"]
                            elif format_ext == "webm":
                                audio_pass = ["-c:a", "libopus", "-b:a", "128k"]
                            else:
                                audio_pass = ["-c:a", "libopus", "-b:a", "128k"]
                        
                        # FFmpeg command with audio re-encoding
                        mux_args = [
                            ffmpeg_path, "-v", "error", "-n", 
                            "-i", file_path,
                            "-ar", str(sample_rate), 
                            "-ac", str(channels),
                            "-f", "f32le", 
                            "-i", "-", 
                            "-c:v", "copy"
                        ] + audio_pass + [
                            "-shortest", 
                            output_file_with_audio_path
                        ]
                        
                        audio_data = a_waveform.squeeze(0).transpose(0,1).numpy().tobytes()
                        
                        try:
                            res = subprocess.run(mux_args, input=audio_data, env=env, capture_output=True, check=True)
                            if res.stderr:
                                print(res.stderr.decode(*ENCODE_ARGS), end="", file=sys.stderr)
                            
                            output_files.append(output_file_with_audio_path)
                            file = output_file_with_audio  # Use this file for preview
                        except subprocess.CalledProcessError as e:
                            print(f"Error adding audio to video: {e.stderr.decode(*ENCODE_ARGS)}")
                except Exception as e:
                    print(f"Error processing audio: {str(e)}")
        
        # Send to Discord if requested
        if send_to_discord and webhook_url:
            try:
                # For Discord compatibility, create a special Discord-optimized copy of the video
                # This is particularly important when add_time is disabled
                discord_optimized_file = None
                try:
                    # Get input file (the last output file)
                    input_file = output_files[-1]
                    
                    # Create optimized output file in a temp location
                    temp_dir = folder_paths.get_temp_directory()
                    discord_optimized_file = os.path.join(temp_dir, f"discord_optimized_{uuid4()}{os.path.splitext(input_file)[1]}")
                    
                    # Set up ffmpeg arguments for optimized Discord conversion
                    # This creates a new file specifically optimized for Discord playback
                    format_ext = os.path.splitext(input_file)[1].lstrip('.').lower()
                    optimize_args = []
                    
                    if format_ext == "mp4":
                        # MP4 optimization for Discord
                        optimize_args = [
                            ffmpeg_path, "-i", input_file,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-movflags", "faststart", "-preset", "fast",
                            "-profile:v", "baseline", "-level", "3.0",
                            "-crf", "23"
                        ]
                        
                        # Add audio if present in original file
                        optimize_args.extend(["-c:a", "aac", "-b:a", "128k"])
                        
                        # Add output file
                        optimize_args.append(discord_optimized_file)
                    elif format_ext == "webm":
                        # WebM optimization for Discord
                        optimize_args = [
                            ffmpeg_path, "-i", input_file,
                            "-c:v", "libvpx-vp9", 
                            "-pix_fmt", "yuv420p",
                            "-crf", "30", "-b:v", "0",
                            "-deadline", "good"
                        ]
                        
                        # Add audio if present in original file
                        optimize_args.extend(["-c:a", "libopus", "-b:a", "96k"])
                        
                        # Add output file
                        optimize_args.append(discord_optimized_file)
                    elif format_ext == "gif":
                        # GIF optimization for Discord
                        optimize_args = [
                            ffmpeg_path, "-i", input_file,
                            "-vf", "fps=15,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        ]
                        
                        # Add output file
                        optimize_args.append(discord_optimized_file)
                    
                    if optimize_args:
                        print(f"Creating Discord-optimized version of {format_ext.upper()} file...")
                        subprocess.run(optimize_args, check=True, capture_output=True)
                        print(f"Discord-optimized file created: {discord_optimized_file}")
                    else:
                        # If no optimization needed, just use the original file
                        discord_optimized_file = input_file
                        print(f"Using original file for Discord: {discord_optimized_file}")
                        
                except Exception as e:
                    print(f"Warning: Failed to create Discord-optimized file: {str(e)}")
                    print("Falling back to original file")
                    discord_optimized_file = output_files[-1]
                
                # Prepare Discord files and message
                discord_files = []
                
                # Include the workflow JSON if requested
                workflow_file = None
                if send_workflow_json and (original_prompt is not None or original_extra_pnginfo is not None):
                    try:
                        # Extract workflow data
                        workflow_json = None
                        
                        # First check if extra_pnginfo contains the workflow data
                        if original_extra_pnginfo is not None and "workflow" in original_extra_pnginfo:
                            workflow_json = original_extra_pnginfo["workflow"]
                            # Ensure the workflow is sanitized
                            workflow_json = sanitize_json_for_export(workflow_json)
                        
                        # If no workflow in extra_pnginfo, check if prompt is actually a workflow
                        if workflow_json is None and original_prompt is not None:
                            # Check if prompt is already a workflow
                            if isinstance(original_prompt, dict) and "nodes" in original_prompt and "links" in original_prompt:
                                workflow_json = original_prompt
                                # Ensure the workflow is sanitized
                                workflow_json = sanitize_json_for_export(workflow_json)
                        
                        # Only proceed if we have workflow data
                        if workflow_json:
                            # Generate a JSON filename with UUID
                            json_filename = f"{uuid4()}.json"
                            
                            # Convert workflow data to JSON string in the proper format
                            workflow_json_str = json.dumps(workflow_json, indent=2)
                            workflow_file = BytesIO(workflow_json_str.encode('utf-8'))
                            print(f"ComfyUI workflow JSON file will be sent alongside the video")
                        else:
                            print("No workflow data found in the provided metadata")
                    except Exception as e:
                        print(f"Error preparing workflow for Discord: {str(e)}")
                
                # Prepare message content
                message_content = discord_message
                
                # Add video metadata information to Discord message when enabled
                video_metadata_text = ""
                
                # Only build video metadata text if the option is enabled
                if include_video_info:
                    # Add date if enabled
                    if add_date and "date" in video_info:
                        video_metadata_text += f"**Date**: {video_info['date']}\n"
                    
                    # Add time if enabled
                    if add_time and "time" in video_info:
                        video_metadata_text += f"**Time**: {video_info['time']}\n"
                    
                    # Add dimensions if enabled
                    if add_dimensions and "dimensions" in video_info:
                        video_metadata_text += f"**Dimensions**: {video_info['dimensions']}\n"
                    
                    # Add frame rate information
                    video_metadata_text += f"**Frame Rate**: {frame_rate} fps\n"
                    
                    # Add format information
                    video_metadata_text += f"**Format**: {format}\n"
                    
                    # Add video metadata to message if any was collected
                    if video_metadata_text and message_content:
                        message_content += "\n\n**Video Info**:\n" + video_metadata_text
                        print(f"Added video metadata to Discord message: {len(video_metadata_text)} chars")
                    elif video_metadata_text:
                        message_content = "**Video Info**:\n" + video_metadata_text
                        print(f"Added video metadata to Discord message: {len(video_metadata_text)} chars")
                else:
                    print("Video info was not included in Discord message (disabled by user)")
                
                # Include the generation prompts if requested
                if include_prompts_in_message:
                    print(f"Prompt inclusion requested! Starting prompt extraction process...")
                    print(f"original_prompt type: {type(original_prompt) if original_prompt is not None else 'None'}")
                    print(f"original_extra_pnginfo type: {type(original_extra_pnginfo) if original_extra_pnginfo is not None else 'None'}")
                    
                    if original_prompt is not None:
                        print(f"original_prompt keys: {original_prompt.keys() if isinstance(original_prompt, dict) else 'Not a dict'}")
                    
                    if original_extra_pnginfo is not None:
                        print(f"original_extra_pnginfo keys: {original_extra_pnginfo.keys() if isinstance(original_extra_pnginfo, dict) else 'Not a dict'}")
                        if isinstance(original_extra_pnginfo, dict) and "workflow" in original_extra_pnginfo:
                            print(f"workflow keys: {original_extra_pnginfo['workflow'].keys() if isinstance(original_extra_pnginfo['workflow'], dict) else 'Workflow not a dict'}")
                    
                    # First identify the workflow data to extract prompts from
                    workflow_data = None
                    
                    # First try to get workflow from extra_pnginfo
                    if original_extra_pnginfo is not None and isinstance(original_extra_pnginfo, dict) and "workflow" in original_extra_pnginfo:
                        workflow_data = original_extra_pnginfo["workflow"]
                        print("Found workflow data in extra_pnginfo")
                    
                    # If no workflow in extra_pnginfo, check if prompt is actually a workflow
                    if workflow_data is None and original_prompt is not None:
                        # Check if prompt is already a workflow
                        if isinstance(original_prompt, dict) and "nodes" in original_prompt:
                            workflow_data = original_prompt
                            print("Found workflow data in original_prompt")
                    
                    # Extract prompts if we found workflow data
                    if workflow_data is not None:
                        print("Workflow data found, attempting to extract prompts...")
                        
                        # Extract prompts and add to message
                        try:
                            # Try to use discord_image_node's function first
                            try:
                                from discord_image_node import extract_prompts_from_workflow
                                positive_prompt, negative_prompt = extract_prompts_from_workflow(workflow_data)
                                
                                print(f"extract_prompts_from_workflow returned: positive_type={type(positive_prompt)}, negative_type={type(negative_prompt)}")
                                
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
                                
                                if has_valid_prompt:
                                    print(f"Successfully extracted prompts via discord_image_node")
                                    
                                    # Add to message
                                    prompt_text = "\n\n**Generation Prompts:**\n"
                                    
                                    if isinstance(positive_prompt, str) and positive_prompt:
                                        prompt_text += f"**Positive:**\n```\n{positive_prompt}\n```\n"
                                    
                                    if isinstance(negative_prompt, str) and negative_prompt:
                                        prompt_text += f"**Negative:**\n```\n{negative_prompt}\n```\n"
                                    
                                    # Add to message content
                                    message_content += prompt_text
                                    print("Successfully added prompts to Discord message")
                                else:
                                    print("No valid prompts extracted from discord_image_node function")
                                    # Raise an exception to trigger the fallback extraction method
                                    raise ValueError("No valid prompts extracted")
                            
                            except Exception as e:
                                print(f"Could not use discord_image_node extraction: {str(e)}")
                                print("Falling back to built-in prompt extraction")
                                
                                # Local extraction logic
                                positive_prompt = None
                                negative_prompt = None
                                
                                # Find CLIP text nodes
                                clip_nodes = []
                                
                                # Define node types that can contain prompts
                                prompt_node_types = [
                                    "CLIPTextEncode",      # Standard SD 1.5 prompt node
                                    "SDXLPromptEncoder",   # SDXL prompt encoder 
                                    "SDXLTextEncode",      # Another SDXL text node
                                ]
                                
                                if "nodes" in workflow_data:
                                    nodes = workflow_data["nodes"]
                                    node_list = []
                                    
                                    # Debug print full node data for the first few nodes
                                    print("\nExamining raw node data:")
                                    if isinstance(nodes, dict):
                                        for i, (node_id, node) in enumerate(list(nodes.items())[:3]):
                                            print(f"Node {i} (ID: {node_id}): {node.get('type', 'unknown')} - Active status: bypassed={node.get('bypassed', 'Not set')}, muted={node.get('muted', 'Not set')}, disabled={node.get('disabled', 'Not set')}")
                                    elif isinstance(nodes, list) and len(nodes) > 0:
                                        for i, node in enumerate(nodes[:3]):
                                            print(f"Node {i}: {node.get('type', 'unknown')} - Active status: bypassed={node.get('bypassed', 'Not set')}, muted={node.get('muted', 'Not set')}, disabled={node.get('disabled', 'Not set')}")
                                    
                                    # Convert to list for processing
                                    if isinstance(nodes, dict):
                                        print("Nodes is a dictionary, converting to list...")
                                        for node_id, node in nodes.items():
                                            if isinstance(node, dict):
                                                # Store the ID in the node dict for reference
                                                node_with_id = node.copy()  # Copy to avoid modifying original
                                                node_with_id["id"] = node_id
                                                node_list.append(node_with_id)
                                    elif isinstance(nodes, list):
                                        print("Nodes is already a list")
                                        node_list = nodes
                                    else:
                                        print(f"Unexpected type for nodes: {type(nodes)}")
                                    
                                    print(f"Processed {len(node_list)} nodes from workflow data")
                                    
                                    # Let's specifically search for all CLIP text nodes to analyze
                                    print("\nSearching for all possible prompt nodes (active or disabled):")
                                    all_prompt_nodes = []
                                    for node in node_list:
                                        if isinstance(node, dict) and "type" in node:
                                            node_type = node.get("type", "")
                                            if node_type in prompt_node_types or ("Text" in node_type and ("Encode" in node_type or "Prompt" in node_type)):
                                                # Found a potential prompt node
                                                title = node.get("title", "Untitled")
                                                is_active = not (node.get("bypassed", False) or node.get("muted", False) or 
                                                                node.get("disabled", False) or node.get("active", True) == False or 
                                                                node.get("enabled", True) == False)
                                                
                                                # Print detailed info
                                                print(f"Prompt node found: {title} (Type: {node_type})")
                                                print(f"  - Status: {'ACTIVE' if is_active else 'DISABLED'}")
                                                print(f"  - Properties: bypassed={node.get('bypassed', 'Not set')}, muted={node.get('muted', 'Not set')}, disabled={node.get('disabled', 'Not set')}")
                                                if "widgets_values" in node and node["widgets_values"]:
                                                    text_preview = node["widgets_values"][0][:50] + "..." if len(node["widgets_values"][0]) > 50 else node["widgets_values"][0]
                                                    print(f"  - Content preview: {text_preview}")
                                                
                                                all_prompt_nodes.append(node)
                                    
                                    print(f"Found {len(all_prompt_nodes)} total potential prompt nodes ({len([n for n in all_prompt_nodes if not (n.get('bypassed', False) or n.get('muted', False) or n.get('disabled', False) or n.get('active', True) == False or n.get('enabled', True) == False)])} active, {len([n for n in all_prompt_nodes if n.get('bypassed', False) or n.get('muted', False) or n.get('disabled', False) or n.get('active', True) == False or n.get('enabled', True) == False])} disabled)")
                                    
                                    # Check for active prompt nodes (not muted/bypassed)
                                    for node in node_list:
                                        if isinstance(node, dict) and "type" in node:
                                            # Check for various ways a node might be disabled
                                            is_disabled = (
                                                node.get("bypassed", False) or 
                                                node.get("muted", False) or 
                                                node.get("disabled", False) or
                                                node.get("active", True) == False or 
                                                node.get("enabled", True) == False
                                            )
                                            
                                            # If no clear status property, let's check outputs to see if they're connected
                                            if not is_disabled and ("outputs" in node or "Output" in node):
                                                # No outputs might mean disconnected
                                                has_outputs = False
                                                if "outputs" in node and node["outputs"]:
                                                    has_outputs = True
                                                elif "Output" in node and node["Output"]:
                                                    has_outputs = True
                                                
                                                # Check if we should include nodes with no connections (sometimes these are valid sources)
                                                # For prompt nodes, we'll consider them even if disconnected, but log it
                                                if not has_outputs and node["type"] in prompt_node_types:
                                                    print(f"Note: Including prompt node that appears disconnected: {node.get('title', node['type'])}")
                                            
                                            if is_disabled:
                                                print(f"Skipping disabled node: {node.get('title', node.get('type', 'unknown'))}")
                                                continue
                                            
                                            # If we reach here, the node is active
                                            # Check standard prompt node types
                                            if node["type"] in prompt_node_types:
                                                if "widgets_values" in node and node["widgets_values"]:
                                                    clip_nodes.append(node)
                                                    print(f"Found active prompt node: {node.get('title', node['type'])}")
                                            # Also look for other common prompt nodes
                                            elif "Text" in node["type"] and ("Encode" in node["type"] or "Prompt" in node["type"]):
                                                print(f"Found potential prompt node of type: {node['type']}")
                                                if "widgets_values" in node and node["widgets_values"]:
                                                    print(f"Values: {node['widgets_values']}")
                                                    clip_nodes.append(node)
                                
                                print(f"Found {len(clip_nodes)} active prompt nodes")
                                
                                # Dump the first 5 nodes to debug
                                print("Sampling first few nodes for debugging:")
                                if isinstance(workflow_data["nodes"], dict):
                                    sample_nodes = list(workflow_data["nodes"].values())[:5]
                                    for i, node in enumerate(sample_nodes):
                                        if isinstance(node, dict):
                                            print(f"Node {i}: type={node.get('type', 'unknown')}, title={node.get('title', 'untitled')}")
                                elif isinstance(workflow_data["nodes"], list):
                                    for i, node in enumerate(workflow_data["nodes"][:5]):
                                        if isinstance(node, dict):
                                            print(f"Node {i}: type={node.get('type', 'unknown')}, title={node.get('title', 'untitled')}")
                                
                                # Process CLIP nodes
                                if len(clip_nodes) == 2:
                                    # Identify which is positive/negative
                                    indicators = ["worst quality", "low quality", "bad quality", "nude", "nsfw"]
                                    scores = [0, 0]
                                    
                                    for i, node in enumerate(clip_nodes):
                                        text = node["widgets_values"][0].lower()
                                        for indicator in indicators:
                                            if indicator in text:
                                                scores[i] += 1
                                    
                                    # The one with more negative indicators is the negative prompt
                                    if scores[0] > scores[1]:
                                        negative_prompt = clip_nodes[0]["widgets_values"][0]
                                        positive_prompt = clip_nodes[1]["widgets_values"][0]
                                    else:
                                        negative_prompt = clip_nodes[1]["widgets_values"][0]
                                        positive_prompt = clip_nodes[0]["widgets_values"][0]
                                    
                                    print(f"Identified prompts with scores: {scores}")
                                    
                                    # Add to message
                                    prompt_text = "\n\n**Generation Prompts:**\n"
                                    prompt_text += f"**Positive:**\n```\n{positive_prompt}\n```\n"
                                    prompt_text += f"**Negative:**\n```\n{negative_prompt}\n```\n"
                                    
                                    # Add to message content
                                    message_content += prompt_text
                                    print("Added prompts to Discord message via built-in extraction")
                                elif len(clip_nodes) == 1:
                                    # Just one prompt, assume it's positive
                                    positive_prompt = clip_nodes[0]["widgets_values"][0]
                                    
                                    # Add to message
                                    prompt_text = "\n\n**Generation Prompts:**\n"
                                    prompt_text += f"**Positive:**\n```\n{positive_prompt}\n```\n"
                                    
                                    # Add to message content
                                    message_content += prompt_text
                                    print("Added single prompt to Discord message")
                                else:
                                    # Handle multiple CLIP nodes (more than 2)
                                    print(f"Found {len(clip_nodes)} CLIP nodes, will analyze each to determine positive/negative")
                                    
                                    # Collect potential positive and negative prompts
                                    positive_candidates = []
                                    negative_candidates = []
                                    
                                    # Common negative prompt indicators
                                    negative_indicators = ["worst quality", "low quality", "bad quality", "nude", "nsfw", 
                                                         "negative", "bad", "worse", "poor", "deformed"]
                                    
                                    for node in clip_nodes:
                                        # Get the node's text content
                                        if "widgets_values" in node and node["widgets_values"]:
                                            text = node["widgets_values"][0]
                                            title = node.get("title", "").lower()
                                            node_type = node.get("type", "").lower()
                                            
                                            # Check if title explicitly indicates a negative prompt
                                            is_negative = False
                                            if "negative" in title:
                                                is_negative = True
                                                print(f"Found explicit negative prompt node by title: {title}")
                                            else:
                                                # Check content for negative indicators
                                                text_lower = text.lower()
                                                negative_score = 0
                                                for indicator in negative_indicators:
                                                    if indicator in text_lower:
                                                        negative_score += 1
                                                
                                                if negative_score >= 2:  # Threshold for considering as negative
                                                    is_negative = True
                                                    print(f"Identified negative prompt by content with score {negative_score}")
                                            
                                            # Categorize the prompt
                                            if is_negative:
                                                negative_candidates.append(text)
                                            else:
                                                positive_candidates.append(text)
                                    
                                    # Get the final prompts
                                    positive_prompt = None
                                    negative_prompt = None
                                    
                                    if positive_candidates:
                                        # Use the longest positive prompt as it likely has more information
                                        positive_prompt = max(positive_candidates, key=len)
                                        print(f"Selected positive prompt ({len(positive_prompt)} chars)")
                                    
                                    if negative_candidates:
                                        # Use the longest negative prompt
                                        negative_prompt = max(negative_candidates, key=len)
                                        print(f"Selected negative prompt ({len(negative_prompt)} chars)")
                                    
                                    # Add to message if any prompts were found
                                    if positive_prompt or negative_prompt:
                                        prompt_text = "\n\n**Generation Prompts:**\n"
                                        
                                        if positive_prompt:
                                            prompt_text += f"**Positive:**\n```\n{positive_prompt}\n```\n"
                                        
                                        if negative_prompt:
                                            prompt_text += f"**Negative:**\n```\n{negative_prompt}\n```\n"
                                        
                                        # Add to message content
                                        message_content += prompt_text
                                        print(f"Added prompts to Discord message from {len(positive_candidates)} positive and {len(negative_candidates)} negative candidates")
                                    else:
                                        print("Could not identify any positive or negative prompts from the CLIP nodes")
                        except Exception as e:
                            print(f"Error extracting prompts: {str(e)}")
                            print(f"Error type: {type(e).__name__}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("No workflow data found for prompt extraction")
                
                # Send videos to Discord
                # Use requests to send files to Discord webhook
                discord_data = {"content": message_content} if message_content else {}
                
                # Debug the message content to make sure prompts are included
                print(f"Final Discord message content length: {len(message_content) if message_content else 0} characters")
                if message_content:
                    lines = message_content.split('\n')
                    print(f"Message has {len(lines)} lines")
                    if "Generation Prompts" in message_content:
                        print("Message contains 'Generation Prompts' section")
                    else:
                        print("WARNING: Message does NOT contain 'Generation Prompts' section")
                
                # Prepare files for upload
                files = []
                
                # Use our optimized file for Discord instead of the original
                file_path = discord_optimized_file
                
                try:
                    # Validate the video file before sending to Discord
                    is_valid, validation_message = validate_video_for_discord(file_path)
                    if not is_valid:
                        print(f"WARNING: {validation_message}")
                        print("Will attempt to send file to Discord anyway.")
                    else:
                        print(f"Video validation for Discord: {validation_message}")
                    
                    # Add main video file
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                        # Use UUID to generate a unique filename for Discord
                        # This is better than using the original filename to prevent issues with duplicate filenames
                        original_extension = os.path.splitext(file_path)[1].lstrip('.')
                        discord_filename = f"{uuid4()}.{original_extension}"
                        
                        # Determine MIME type for Discord
                        mime_type = ""
                        if original_extension == "mp4":
                            mime_type = "video/mp4"
                        elif original_extension == "webm":
                            mime_type = "video/webm"
                        elif original_extension == "gif":
                            mime_type = "image/gif"
                        elif original_extension == "webp":
                            mime_type = "image/webp"
                        elif original_extension == "mov":
                            mime_type = "video/quicktime"
                        else:
                            # Default to video/extension
                            mime_type = f"video/{original_extension}"
                        
                        # Log the file details for debugging
                        print(f"Sending file to Discord: {file_path}")
                        print(f"File size: {len(file_content)} bytes")
                        print(f"Using MIME type: {mime_type}")
                        print(f"Discord filename: {discord_filename}")
                        
                        files.append(('file', (discord_filename, file_content, mime_type)))
                except Exception as e:
                    print(f"Error preparing video file for Discord: {str(e)}")
                    discord_send_success = False
                
                # Add workflow JSON if requested
                if workflow_file:
                    # Also use UUID for the JSON file to ensure uniqueness
                    json_filename = f"{uuid4()}.json"
                    files.append(('workflow', (json_filename, workflow_file.getvalue(), 'application/json')))
                
                # Send to Discord with retry logic
                response = send_to_discord_with_retry(
                    webhook_url,
                    data=discord_data,
                    files=files
                )
                
                # Discord can return either 204 (no content) or 200 (success with content) for successful requests
                if response.status_code in [200, 204]:
                    discord_sent_files.append(discord_filename)  # Store the Discord UUID filename instead of local path
                    print(f"Successfully sent video to Discord with filename: {discord_filename}")
                    
                    # Try to extract CDN URL if available
                    if save_cdn_urls and response.status_code == 200:
                        try:
                            response_data = response.json()
                            # Discord webhook responses include attachments with URLs
                            if "attachments" in response_data and isinstance(response_data["attachments"], list):
                                for attachment in response_data["attachments"]:
                                    if "url" in attachment and "filename" in attachment:
                                        # Filter out workflow JSON files
                                        if not attachment["filename"].endswith(".json"):
                                            discord_cdn_urls.append((attachment["filename"], attachment["url"]))
                                            print(f"Extracted CDN URL for video: {attachment['url']}")
                        except Exception as e:
                            print(f"Error extracting CDN URL from response: {e}")
                else:
                    print(f"Discord API error: {response.status_code} - {response.text}")
                    discord_send_success = False
            
            except Exception as e:
                print(f"Error sending to Discord: {str(e)}")
                discord_send_success = False
                
            # If we have CDN URLs and the option is enabled, send them as a text file
            if save_cdn_urls and discord_cdn_urls:
                try:
                    # Create the text file content
                    url_text_content = "# Discord CDN URLs\n\n"
                    for idx, (filename, url) in enumerate(discord_cdn_urls):
                        url_text_content += f"{idx+1}. {filename}: {url}\n"
                    
                    # Create a unique filename for the text file
                    urls_filename = f"cdn_urls-{uuid4()}.txt"
                    
                    # Prepare the request with just the URL file
                    url_files = {"file": (urls_filename, url_text_content.encode('utf-8'))}
                    url_data = {"content": "Discord CDN URLs for the uploaded videos:"}
                    
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
        
        # Update GitHub repository with CDN URLs if enabled
        if github_cdn_update and send_to_discord and discord_cdn_urls:
            # Use the collected CDN URLs for GitHub update
            print(f"GitHub update is enabled with: repo={github_repo}, token_provided={'Yes' if github_token else 'No'}, file_path={github_file_path}")
            print(f"Number of available CDN URLs to update GitHub: {len(discord_cdn_urls)}")
            
            if discord_cdn_urls:
                # Call the GitHub update function
                print(f"Updating GitHub repository {github_repo} with {len(discord_cdn_urls)} Discord CDN URLs...")
                success, message = update_github_cdn_urls(
                    github_repo=github_repo,
                    github_token=github_token,
                    file_path=github_file_path,
                    cdn_urls=discord_cdn_urls
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
            if not discord_cdn_urls:
                reasons.append("no CDN URLs were collected (did Discord upload succeed?)")
            if not github_repo:
                reasons.append("github_repo is empty")
            if not github_token:
                reasons.append("github_token is empty")
            if not github_file_path:
                reasons.append("github_file_path is empty")
            
            print(f"GitHub update was enabled but not triggered because: {', '.join(reasons)}")
        
        # Check if any output files were created
        if len(output_files) == 0:
            print("DiscordSendSaveVideo: No output files were created")
            return {"ui": {}, "result": (None,)}
        
        # Status messages
        if save_output:
            print(f"DiscordSendSaveVideo: Saved video to {full_output_folder}")
        else:
            print("DiscordSendSaveVideo: Preview only mode - no video saved to disk")
            
        # Discord status
        if send_to_discord and discord_sent_files:
            print("DiscordSendSaveVideo: Successfully sent video to Discord")
        elif send_to_discord and not discord_send_success:
            print("DiscordSendSaveVideo: There were errors sending video to Discord")
        
        # Get the final output file path - the last one in the list
        final_output_path = output_files[-1]
        
        # Return UI info with basic video preview for ComfyUI
        preview = {
            "filename": os.path.basename(final_output_path),
            "subfolder": subfolder,
            "type": "output" if save_output else "temp",
            "format": format,
            "frame_rate": frame_rate,
            "fullpath": final_output_path,
        }
        
        return {"ui": {"videos": [preview]}, "result": (final_output_path,)}

    @classmethod
    def IS_CHANGED(s, images, filename_prefix="ComfyUI-Video", overwrite_last=False,
                  format="video/h264-mp4", frame_rate=8.0, quality=85, loop_count=0, lossless=False, 
                  pingpong=False, save_output=True, audio=None,
                  add_date=True, add_time=True, add_dimensions=True,
                  send_to_discord=False, webhook_url="", discord_message="",
                  include_prompts_in_message=False, include_video_info=True, send_workflow_json=False, 
                  save_cdn_urls=False, github_cdn_update=False, github_repo="", github_token="", 
                  github_file_path="cdn_urls.md", prompt=None, extra_pnginfo=None, unique_id=None, **format_properties):
        # Always return True to ensure execution and proper handling of dynamic format properties
        return True 