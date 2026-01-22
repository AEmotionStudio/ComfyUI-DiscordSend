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
from io import BytesIO
from uuid import uuid4
from typing import Any, Union, List, Optional
from pathlib import Path
import sys
import datetime
import subprocess
import functools
import server

# Import shared utilities
from shared import (
    tensor_to_numpy_uint8,
    build_metadata_section
)
# Add BaseDiscordNode import
from .base_node import BaseDiscordNode

from shared.media import (
    validate_video_for_discord,
    normalize_video_extension,
    optimize_video_for_discord as shared_optimize_video,
    detect_ffmpeg
)
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

# Define constants
ENCODE_ARGS = ("utf-8", "ignore")
floatOrInt = ("FLOAT", "INT")
imageOrLatent = ("IMAGE", "LATENT")
BIGMAX = 1000000
has_vhs_formats = False

# Detect ffmpeg using shared utility
ffmpeg_path = detect_ffmpeg()

# Try to import ProgressBar from comfy.utils
try:
    from comfy.utils import ProgressBar
except ImportError:
    class ProgressBar:
        def __init__(self, total):
            self.total = total
            self.current = 0

        def update(self, advance=1):
            self.current += advance
            print(f"Progress: {self.current}/{self.total}", end="\r")

def process_batched_images(image_sequence, batch_size=20):
    """
    Generator that processes images in batches to optimize GPU-CPU transfer.

    Args:
        image_sequence: A torch.Tensor or list of tensors/images
        batch_size: Number of frames to process at once for Tensor inputs

    Yields:
        Numpy array for each batch or frame, contiguous and ready for ffmpeg
    """
    # Optimized path for Tensor input
    if isinstance(image_sequence, torch.Tensor):
        total = len(image_sequence)
        for i in range(0, total, batch_size):
            # Process a chunk of frames on GPU/CPU together
            # This amortizes the overhead of kernel launches and synchronization
            batch = image_sequence[i:i+batch_size]
            batch_np = tensor_to_numpy_uint8(batch)
            # Yield the whole batch at once to optimize pipe writes
            yield np.ascontiguousarray(batch_np)
    else:
        # Fallback for list input (e.g. pingpong or mixed sources)
        # We process individually as stacking might be expensive if they are not already contiguous tensors
        for img in image_sequence:
            yield np.ascontiguousarray(tensor_to_numpy_uint8(img))

class DiscordSendSaveVideo(BaseDiscordNode):
    """
    A ComfyUI node that can send videos to Discord and save them with advanced options.
    Videos can be sent to Discord via webhook integration, while providing flexible
    saving options with customizable format options.
    """
    
    def __init__(self):
        super().__init__()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        self.output_dir = None  # Will be set during saving to store the actual path used

    @classmethod
    def INPUT_TYPES(s):
        """
        Define the input types for the DiscordSendSaveVideo node.
        """
        # Get base inputs from BaseDiscordNode
        base_inputs = BaseDiscordNode.get_discord_input_types()
        cdn_inputs = BaseDiscordNode.get_cdn_input_types()
        filename_inputs = BaseDiscordNode.get_filename_input_types(add_date_default=True)

        # Override tooltip for add_time to warn about Discord single-frame bug
        filename_inputs["add_time"][1]["tooltip"] = "Add time (HH-MM-SS) to the filename. ⚠️ CRITICAL: Keep enabled for Discord videos to prevent single-frame playback issues!"

        # Determine format options and defaults based on ffmpeg availability
        if ffmpeg_path is None:
            print("ffmpeg not found. Video output will be limited or unavailable.")
            # Always make GIF available even without ffmpeg (we'll use PIL as fallback)
            video_formats = ["video/gif"]
            format_default = "video/gif"
            format_tooltip = "⚠️ FFmpeg not found! Only GIF format is available (using PIL fallback).\n\nPlease install FFmpeg to unlock MP4, WebM, and other video formats."
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
            format_default = "video/h264-mp4"
            format_tooltip = ("The video format to save in. Options include:\n"
                              "# Image formats:\n"
                              "- image/gif: Standard GIF format (NO AUDIO support)\n"
                              "- image/webp: WebP format (better quality than GIF, NO AUDIO support)\n"
                              "- video/gif: Video format GIF (higher frame rate support, NO AUDIO support)\n\n"
                              "# Standard video formats:\n"
                              "- video/mp4: Standard MP4 format with good compatibility (supports audio)\n"
                              "- video/h264-mp4: High-quality MP4 with H264 codec (supports audio)\n"
                              "- video/h265-mp4: MP4 with H265/HEVC codec (better compression, supports audio)\n"
                              "- video/webm: Standard WebM format (supports audio)\n"
                              "- video/vp9-webm: WebM with VP9 codec (higher quality, supports audio)\n\n"
                              "# Professional formats:\n"
                              "- video/prores: Apple ProRes (professional quality, supports audio when saving locally but NO AUDIO when sending to Discord, requires QuickTime or specialized player to view on Windows)")
        
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The image sequence to save as video and/or send to Discord."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI-Video", "tooltip": "The prefix for the saved files."}),
                "overwrite_last": ("BOOLEAN", {"default": False, "tooltip": "If enabled, will overwrite the last video instead of creating incrementing filenames."})
            },
            "optional": {
                # Video format settings
                "format": (video_formats, {
                    'default': format_default,
                    "tooltip": format_tooltip
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
                
                # Video Info Option
                "include_video_info": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Whether to include the video information (frame rate, format) in the Discord message."
                }),
                
                # Mix in shared options
                **filename_inputs,
                **base_inputs,
                **cdn_inputs,
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
        
        # 1. Sanitize workflow data using base class method
        prompt, extra_pnginfo, original_prompt, original_extra_pnginfo = self.sanitize_workflow_data(
            prompt, extra_pnginfo
        )
        
        # Get number of frames and set up progress bar
        num_frames = len(images)
        if num_frames == 0:
            print("DiscordSendSaveVideo: No frames to process")
            raise ValueError("DiscordSendSaveVideo: No frames to process. Please check your input images.")
        
        pbar = ProgressBar(num_frames)
        
        # Get first image for metadata
        first_image = images[0]
        
        # 2. Build filename prefix with metadata using base class method
        height, width = images[0].shape[0], images[0].shape[1]
        video_info = {}
        filename_prefix, video_info = self.build_filename_prefix(
            filename_prefix, add_date, add_time, add_dimensions, width, height
        )

        # Add prefix append
        filename_prefix += self.prefix_append
        
        # 3. Get output directory using base class method
        dest_folder = self.get_dest_folder(save_output)
            
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
        
        # Sanitize format_ext to prevent path traversal
        # Allow only alphanumeric characters and hyphens
        format_ext = re.sub(r'[^a-zA-Z0-9-]', '', format_ext)

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
                error_msg = f"Error creating {format} with PIL: {str(e)}"
                print(error_msg)
                raise RuntimeError(error_msg)
            
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
                    # Optimization: Use process_batched_images to optimize GPU-CPU transfer
                    # Ensure contiguity to avoid ValueError in subprocess.stdin.write
                    image_chunks = process_batched_images(image_sequence)
                    
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
                        for chunk in image_chunks:
                            # Update pbar based on chunk size (it might be a batch)
                            if len(chunk.shape) == 4: # (Batch, H, W, C)
                                pbar.update(chunk.shape[0])
                            else: # (H, W, C)
                                pbar.update(1)
                            process.stdin.write(chunk)
                        
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

                # Optimization: Use process_batched_images to optimize GPU-CPU transfer
                # Ensure contiguity to avoid ValueError in subprocess.stdin.write
                image_chunks = process_batched_images(image_sequence)
                
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
                    for chunk in image_chunks:
                        # Update pbar based on chunk size (it might be a batch)
                        if len(chunk.shape) == 4: # (Batch, H, W, C)
                            pbar.update(chunk.shape[0])
                        else: # (H, W, C)
                            pbar.update(1)
                        process.stdin.write(chunk)
                    
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
                        
                        # Use ascontiguousarray to ensure the transposed array is C-contiguous.
                        # This avoids BufferError in subprocess.run when using memoryview on non-contiguous arrays.
                        audio_data = np.ascontiguousarray(a_waveform.squeeze(0).transpose(0,1).numpy())
                        
                        try:
                            # Use memoryview to avoid copy while satisfying subprocess.run input check
                            res = subprocess.run(mux_args, input=memoryview(audio_data), env=env, capture_output=True, check=True)
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
            discord_optimized_file = None
            try:
                # For Discord compatibility, create a special Discord-optimized copy of the video
                input_file = output_files[-1]  # Get input file (the last output file)
                temp_dir = folder_paths.get_temp_directory()

                # Use shared utility for Discord optimization
                discord_optimized_file = shared_optimize_video(input_file, ffmpeg_path, temp_dir)
                if discord_optimized_file is None:
                    print(f"Using original file for Discord: {input_file}")
                
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
                
                # Initialize message content with user message
                message_content = discord_message if discord_message else ""
                
                # Add video metadata to Discord message using shared utility
                if include_video_info:
                    metadata_section = build_metadata_section(
                        info_dict=video_info,
                        include_date=add_date,
                        include_time=add_time,
                        include_dimensions=add_dimensions,
                        include_format=True,
                        file_format=format,
                        frame_rate=frame_rate,
                        section_title="Video Info"
                    )
                    if metadata_section:
                        if message_content:
                            message_content += "\n\n"
                        message_content += metadata_section
                        print(f"Added video metadata to Discord message: {len(metadata_section)} chars")
                
                # Include the generation prompts if requested
                if include_prompts_in_message:
                    # Use helper to extract workflow data
                    wflow = self.extract_workflow_from_metadata(original_prompt, original_extra_pnginfo)
                    
                    if wflow:
                        # Use helper to build prompt message
                        prompt_msg = self.build_prompt_message(wflow)
                        if prompt_msg:
                            if message_content:
                                message_content += "\n\n"
                            message_content += prompt_msg
                            print("Successfully added prompts to Discord message")
                
                # Prepare files for upload
                files = {}
                
                # Use our optimized file for Discord instead of the original
                # If discord_optimized_file is None, it means we use the original file
                file_path_to_send = discord_optimized_file if discord_optimized_file else input_file
                
                # Validate video before sending
                is_valid, validation_message = validate_video_for_discord(file_path_to_send)
                if not is_valid:
                    print(f"WARNING: {validation_message}")
                    print("Will attempt to send file to Discord anyway.")
                else:
                    print(f"Video validation for Discord: {validation_message}")
                
                try:
                    with open(file_path_to_send, 'rb') as f:
                        file_content = f.read()
                        
                        # Generate unique filename for Discord
                        # Use UUID to prevent filename collisions
                        original_extension = os.path.splitext(file_path_to_send)[1].lstrip('.')
                        discord_filename = f"{uuid4()}.{original_extension}"
                        
                        files["file"] = (discord_filename, file_content)
                        
                        # Add workflow JSON if requested
                        if send_workflow_json:
                             wflow = self.extract_workflow_from_metadata(original_prompt, original_extra_pnginfo)
                             if wflow:
                                 json_filename = f"{uuid4()}.json"
                                 json_data = json.dumps(wflow, indent=2).encode('utf-8')
                                 files["workflow"] = (json_filename, json_data)
                        
                        data = {}
                        if message_content:
                            data["content"] = message_content
                        
                        # Send to Discord using base class helper
                        success, response, new_urls = self.send_discord_files(webhook_url, files, data, save_cdn_urls)
                        
                        if success:
                            discord_sent_files.append(discord_filename)
                            print(f"Successfully sent video to Discord with filename: {discord_filename}")
                            if new_urls:
                                discord_cdn_urls.extend(new_urls)
                                self.send_cdn_urls_to_discord(webhook_url, new_urls, "Discord CDN URLs for the uploaded video:")
                        else:
                            print(f"Error sending video to Discord: Status code {response.status_code}")
                            discord_send_success = False

                except Exception as e:
                    print(f"Error preparing/sending video to Discord: {e}")
                    discord_send_success = False

                finally:
                    # Clean up temp file
                    if discord_optimized_file and os.path.exists(discord_optimized_file):
                        try:
                            os.remove(discord_optimized_file)
                            print(f"Cleaned up temporary file: {discord_optimized_file}")
                        except Exception as e:
                            print(f"Error cleaning up temporary file: {e}")

            except Exception as e:
                print(f"Error in Discord processing (outer): {e}")
                discord_send_success = False
                
            finally:
                # Security: Ensure temporary optimized file is deleted
                if discord_optimized_file and os.path.exists(discord_optimized_file):
                    try:
                        os.remove(discord_optimized_file)
                    except Exception:
                        pass
                        
        # Update GitHub repository
        if github_cdn_update and send_to_discord and discord_cdn_urls:
             self.update_github_cdn(discord_cdn_urls, github_repo, github_token, github_file_path)
             
        elif github_cdn_update:
            reasons = []
            if not send_to_discord: reasons.append("send_to_discord is disabled")
            if not discord_cdn_urls: reasons.append("no CDN URLs were collected")
            if not github_repo: reasons.append("github_repo is empty")
            if not github_token: reasons.append("github_token is empty")
            if not github_file_path: reasons.append("github_file_path is empty")
            print(f"GitHub update was enabled but not triggered because: {', '.join(reasons)}")
        
        # Check if any output files were created
        if len(output_files) == 0:
            print("DiscordSendSaveVideo: No output files were created")
            raise RuntimeError("DiscordSendSaveVideo: No output files were created. Check console for details.")
        
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