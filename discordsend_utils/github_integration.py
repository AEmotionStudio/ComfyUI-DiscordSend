"""
GitHub Integration Utilities for ComfyUI-DiscordSend

Handles updating GitHub repositories with Discord CDN URLs.
"""

import base64
import time
from typing import List, Optional, Tuple

import requests


def update_github_cdn_urls(
    github_repo: str,
    github_token: str,
    file_path: str,
    cdn_urls: List[Tuple[str, str]],
    commit_message: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Update a file in a GitHub repository with Discord CDN URLs.
    
    Args:
        github_repo: The GitHub repository (format: username/repo)
        github_token: The GitHub personal access token for authentication
        file_path: The path to the file within the repository to update
        cdn_urls: List of (filename, url) tuples containing Discord CDN URLs
        commit_message: Optional commit message, defaults to a standard message
        
    Returns:
        Tuple of (success, message) where success is a boolean and message is a status message
    """
    # Validate required parameters
    if not github_repo:
        return False, "Missing GitHub repository name"
    
    if not github_token:
        return False, "Missing GitHub personal access token"
    
    if not file_path:
        return False, "Missing file path in repository"
    
    if not cdn_urls:
        return False, "No CDN URLs to update"
    
    # Ensure repository format is valid
    if "/" not in github_repo:
        return False, f"Invalid GitHub repository format: {github_repo}. Expected format: username/repo"
    
    # Setup API endpoint
    api_url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Check if file exists and get its SHA
        file_sha = None
        current_content = ""
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            file_data = response.json()
            file_sha = file_data.get("sha")
            
            # Get current content
            if file_data.get("content"):
                current_content = base64.b64decode(file_data["content"]).decode("utf-8")
                
        elif response.status_code == 404:
            pass  # File doesn't exist, will create new
        else:
            # Sanitize response text
            error_details = response.text
            if github_token and github_token in error_details:
                error_details = error_details.replace(github_token, "[REDACTED_TOKEN]")
            return False, f"Error checking GitHub file: {response.status_code} - {error_details}"
        
        # Prepare file content
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Merge with existing content if present
        existing_urls = {}
        if current_content:
            for line in current_content.splitlines():
                if ": https://" in line and "cdn.discordapp.com" in line:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        name_part = parts[0]
                        # Remove numbering if present
                        if ". " in name_part:
                            name_part = name_part.split(". ", 1)[1]
                        existing_urls[name_part] = parts[1]
        
        # Add new URLs (overwrites duplicates)
        for filename, url in cdn_urls:
            existing_urls[filename] = url
        
        # Format content
        new_content = f"# Discord CDN URLs\nLast updated: {timestamp}\n\n"
        for i, (filename, url) in enumerate(existing_urls.items(), 1):
            new_content += f"{i}. {filename}: {url}\n"
        
        # Set commit message
        if not commit_message:
            commit_message = f"Update Discord CDN URLs - {timestamp}"
        
        # Prepare request data
        data = {
            "message": commit_message,
            "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
        }
        
        if file_sha:
            data["sha"] = file_sha
        
        # Create/update file
        response = requests.put(api_url, headers=headers, json=data, timeout=30)
        
        if response.status_code in [200, 201]:
            return True, f"Successfully updated GitHub file with {len(cdn_urls)} Discord CDN URLs"
        else:
            # Sanitize response text to ensure no token leakage
            error_details = response.text
            if github_token and github_token in error_details:
                error_details = error_details.replace(github_token, "[REDACTED_TOKEN]")
            return False, f"Error updating GitHub file: {response.status_code} - {error_details}"
    
    except requests.exceptions.Timeout:
        return False, "GitHub API request timed out"
    except requests.exceptions.RequestException as e:
        # Scrub token from error messages
        error_message = str(e)
        if github_token and github_token in error_message:
            error_message = error_message.replace(github_token, "[REDACTED_TOKEN]")
        return False, f"GitHub API request failed: {error_message}"
    except Exception as e:
        error_message = str(e)
        if github_token and github_token in error_message:
            error_message = error_message.replace(github_token, "[REDACTED_TOKEN]")
        return False, f"Exception during GitHub update: {error_message}"
