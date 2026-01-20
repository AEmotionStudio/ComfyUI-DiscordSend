"""
Base class for Discord-enabled ComfyUI nodes.

Provides common functionality for sending media to Discord,
including INPUT_TYPES definitions, sanitization, and Discord integration.
"""

import os
import folder_paths

from shared import (
    sanitize_json_for_export,
    update_github_cdn_urls,
    send_to_discord_with_retry,
    build_filename_with_metadata,
    get_output_directory,
    build_metadata_section,
    build_prompt_section,
    extract_cdn_urls_from_response,
    send_cdn_urls_file,
    extract_prompts_from_workflow
)


class BaseDiscordNode:
    """
    Base class for Discord-enabled ComfyUI nodes.

    Provides common functionality for:
    - Filename generation with metadata
    - Output directory management
    - Discord webhook integration
    - GitHub CDN URL updates
    - Workflow data sanitization
    """

    def __init__(self):
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4
        self.output_dir = None

    @staticmethod
    def get_discord_input_types():
        """
        Returns Discord-related INPUT_TYPES fields.

        These can be merged into a node's INPUT_TYPES definition.
        """
        return {
            "send_to_discord": ("BOOLEAN", {
                "default": False,
                "tooltip": "If enabled, will send the media to Discord via webhook."
            }),
            "webhook_url": ("STRING", {
                "default": "",
                "multiline": False,
                "tooltip": "Discord webhook URL. Get this from Discord server settings > Integrations > Webhooks."
            }),
            "discord_message": ("STRING", {
                "default": "",
                "multiline": True,
                "tooltip": "Message to include with the media when sending to Discord."
            }),
            "include_prompts_in_message": ("BOOLEAN", {
                "default": False,
                "tooltip": "If enabled, will include the generation prompts in the Discord message."
            }),
            "send_workflow_json": ("BOOLEAN", {
                "default": False,
                "tooltip": "If enabled, will send the workflow JSON alongside the media."
            }),
        }

    @staticmethod
    def get_cdn_input_types():
        """
        Returns CDN and GitHub-related INPUT_TYPES fields.
        """
        return {
            "save_cdn_urls": ("BOOLEAN", {
                "default": False,
                "tooltip": "If enabled, will extract and save Discord CDN URLs."
            }),
            "github_cdn_update": ("BOOLEAN", {
                "default": False,
                "tooltip": "If enabled, will update a GitHub repository with the CDN URLs."
            }),
            "github_repo": ("STRING", {
                "default": "",
                "multiline": False,
                "tooltip": "GitHub repository in format 'username/repo'."
            }),
            "github_token": ("STRING", {
                "default": "",
                "multiline": False,
                "tooltip": "GitHub personal access token with repo write permissions."
            }),
            "github_file_path": ("STRING", {
                "default": "cdn_urls.md",
                "multiline": False,
                "tooltip": "Path to the file in the GitHub repository to update."
            }),
        }

    @staticmethod
    def get_filename_input_types(
        add_date_default: bool = False,
        add_time_default: bool = True,
        add_dimensions_default: bool = False
    ):
        """
        Returns filename metadata INPUT_TYPES fields.

        Args:
            add_date_default: Default value for add_date
            add_time_default: Default value for add_time
            add_dimensions_default: Default value for add_dimensions
        """
        return {
            "add_date": ("BOOLEAN", {
                "default": add_date_default,
                "tooltip": "Add date (YYYY-MM-DD) to the filename."
            }),
            "add_time": ("BOOLEAN", {
                "default": add_time_default,
                "tooltip": "Add time (HH-MM-SS) to the filename."
            }),
            "add_dimensions": ("BOOLEAN", {
                "default": add_dimensions_default,
                "tooltip": "Add dimensions (WxH) to the filename."
            }),
        }

    def sanitize_workflow_data(self, prompt, extra_pnginfo):
        """
        Sanitize workflow data by removing sensitive information.

        Args:
            prompt: The prompt data
            extra_pnginfo: Extra PNG info including workflow

        Returns:
            Tuple of (sanitized_prompt, sanitized_extra_pnginfo,
                     original_prompt, original_extra_pnginfo)
        """
        # Store original references for prompt extraction
        original_prompt = prompt
        original_extra_pnginfo = extra_pnginfo

        # Sanitize workflow data
        if prompt is not None:
            prompt = sanitize_json_for_export(prompt)

        if extra_pnginfo is not None:
            extra_pnginfo = sanitize_json_for_export(extra_pnginfo)

        return prompt, extra_pnginfo, original_prompt, original_extra_pnginfo

    def build_filename_prefix(
        self,
        filename_prefix: str,
        add_date: bool,
        add_time: bool,
        add_dimensions: bool = False,
        width: int = None,
        height: int = None
    ):
        """
        Build filename prefix with metadata.

        Returns:
            Tuple of (modified_prefix, info_dict)
        """
        info_dict = {}
        filename_prefix, info_dict = build_filename_with_metadata(
            prefix=filename_prefix,
            add_date=add_date,
            add_time=add_time,
            add_dimensions=add_dimensions,
            width=width,
            height=height,
            info_dict=info_dict
        )
        filename_prefix += self.prefix_append
        return filename_prefix, info_dict

    def get_dest_folder(self, save_output: bool):
        """
        Get the destination folder for output files.

        Args:
            save_output: Whether to save to output directory (True) or temp (False)

        Returns:
            Path to the destination folder
        """
        return get_output_directory(
            save_output=save_output,
            comfy_output_dir=folder_paths.get_output_directory(),
            temp_dir=folder_paths.get_temp_directory()
        )

    def extract_workflow_from_metadata(self, original_prompt, original_extra_pnginfo):
        """
        Extract workflow data from metadata.

        Args:
            original_prompt: Original prompt data
            original_extra_pnginfo: Original extra PNG info

        Returns:
            Workflow data dict, or None if not found
        """
        workflow_data = None

        # First try to get workflow from extra_pnginfo
        if (original_extra_pnginfo is not None and
            isinstance(original_extra_pnginfo, dict) and
            "workflow" in original_extra_pnginfo):
            workflow_data = original_extra_pnginfo["workflow"]

        # If no workflow in extra_pnginfo, check if prompt is actually a workflow
        if workflow_data is None and original_prompt is not None:
            if isinstance(original_prompt, dict) and "nodes" in original_prompt:
                workflow_data = original_prompt

        return workflow_data

    def build_prompt_message(self, workflow_data):
        """
        Extract and build prompt message from workflow data.

        Args:
            workflow_data: Workflow data dict

        Returns:
            Formatted prompt section string, or empty string
        """
        if workflow_data is None:
            return ""

        positive_prompt, negative_prompt = extract_prompts_from_workflow(workflow_data)
        return build_prompt_section(positive_prompt, negative_prompt)

    def send_discord_files(
        self,
        webhook_url: str,
        files: dict,
        data: dict,
        save_cdn_urls: bool = False
    ):
        """
        Send files to Discord via webhook.

        Args:
            webhook_url: Discord webhook URL
            files: Files dict for the request
            data: Data dict for the request
            save_cdn_urls: Whether to extract CDN URLs from response

        Returns:
            Tuple of (success, response, cdn_urls)
        """
        cdn_urls = []

        response = send_to_discord_with_retry(
            webhook_url,
            files=files,
            data=data
        )

        success = response.status_code in [200, 204]

        if success and save_cdn_urls:
            cdn_urls = extract_cdn_urls_from_response(response)

        return success, response, cdn_urls

    def send_cdn_urls_to_discord(
        self,
        webhook_url: str,
        cdn_urls: list,
        message: str = "Discord CDN URLs:"
    ):
        """
        Send CDN URLs as a text file to Discord.

        Args:
            webhook_url: Discord webhook URL
            cdn_urls: List of (filename, url) tuples
            message: Message to accompany the file

        Returns:
            True if successful
        """
        if not cdn_urls:
            return False

        return send_cdn_urls_file(
            webhook_url=webhook_url,
            urls=cdn_urls,
            send_func=send_to_discord_with_retry,
            message=message
        )

    def update_github_cdn(
        self,
        cdn_urls: list,
        github_repo: str,
        github_token: str,
        github_file_path: str
    ):
        """
        Update GitHub repository with CDN URLs.

        Args:
            cdn_urls: List of (filename, url) tuples
            github_repo: GitHub repository in 'owner/repo' format
            github_token: GitHub personal access token
            github_file_path: Path to file in repository

        Returns:
            Tuple of (success, message)
        """
        if not cdn_urls:
            return False, "No CDN URLs to update"

        print(f"Updating GitHub repository {github_repo} with {len(cdn_urls)} CDN URLs...")

        success, message = update_github_cdn_urls(
            github_repo=github_repo,
            github_token=github_token,
            file_path=github_file_path,
            cdn_urls=cdn_urls
        )

        if success:
            print(f"GitHub update successful: {message}")
        else:
            print(f"GitHub update failed: {message}")

        return success, message
