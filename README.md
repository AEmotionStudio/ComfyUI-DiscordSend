# ComfyUI-DiscordSend

![ComfyUI](https://img.shields.io/badge/ComfyUI-Extension-green?style=for-the-badge)
![Version](https://img.shields.io/badge/Version-1.1.0-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-GPLv3-red?style=for-the-badge)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen?style=for-the-badge&color=blue)
![Downloads](https://img.shields.io/badge/dynamic/json?color=blueviolet&label=Downloads&query=downloads.smart_count&url=https://raw.githubusercontent.com/AEmotionStudio/ComfyUI-DiscordSend/refs/heads/badges/traffic_stats.json&style=for-the-badge&logo=github)
![Visitors](https://img.shields.io/badge/dynamic/json?color=blue&label=Visitors&query=views.uniques&url=https://raw.githubusercontent.com/AEmotionStudio/ComfyUI-DiscordSend/refs/heads/badges/traffic_stats.json&style=for-the-badge&logo=github)
![Clones](https://img.shields.io/badge/dynamic/json?color=success&label=Clones&query=clones.uniques&url=https://raw.githubusercontent.com/AEmotionStudio/ComfyUI-DiscordSend/refs/heads/badges/traffic_stats.json&style=for-the-badge&logo=github)
![Last Commit](https://img.shields.io/github/last-commit/AEmotionStudio/ComfyUI-DiscordSend?style=for-the-badge&label=Last%20Update&color=orange)
![Activity](https://img.shields.io/github/commit-activity/m/AEmotionStudio/ComfyUI-DiscordSend?style=for-the-badge&label=Activity&color=yellow)

![Example workflow](/images/nodes_example_3.png)

**Send your AI-generated images and videos directly to Discord from ComfyUI!**

[Features](#-features) • [Installation](#-installation) • [Settings](#-settings) • [Technical Details](#-technical-details) • [Contributing](#-contributing) • [Changelog](#-changelog)

---

## What's New in v1.1.0 (January 10, 2026)

### 🚀 Core Updates
- **Structured Logging**: Implemented comprehensive logging for better debugging and stability.
- **Testing Suite**: Added initial test framework to ensure reliability.
- **Enhanced Stability**: Various improvements to image and video handling logic.

📄 See [CHANGELOG.md](CHANGELOG.md) for the complete version history.

---

## ✨ Features

<table>
  <tr>
    <td width="60%">
      <h3>🖼️ Image Node: DiscordSendSaveImage</h3>
      <ul>
        <li>Save images in various formats (PNG, JPEG, WebP)</li>
        <li>Send images directly to Discord via webhooks</li>
        <li>Include workflow JSON for easy reproduction</li>
        <li>Customizable Discord messages with prompt information</li>
        <li>Advanced file naming with date, time, and dimension options</li>
        <li>High-quality image export with configurable compression settings</li>
        <li>Built-in preview functionality within ComfyUI interface</li>
        <li>Batch grouping support (up to 9 images per Discord message)</li>
        <li>Unique identifier support to prevent conflicts between users</li>
      </ul>
    </td>
    <td width="40%">
       <img src="/images/nodes_example_3.png" alt="Image Node" width="100%">
    </td>
  </tr>
</table>

<table>
  <tr>
    <td width="40%">
       <img src="/images/discord_formatting.png" alt="Video Node" width="100%">
    </td>
    <td width="60%">
      <h3>🎬 Video Node: DiscordSendSaveVideo</h3>
      <ul>
        <li>Convert image sequences to videos in multiple formats</li>
        <li>Support for GIF, MP4, WebM, and professional formats like ProRes</li>
        <li>Configurable frame rates from 0.1 to 120 fps</li>
        <li>Extra-slow frame rates for photo slideshows</li>
        <li>Add audio to your videos</li>
        <li>Special effects like ping-pong looping</li>
        <li>Discord integration for sharing videos</li>
        <li>Include workflow data and video information in messages</li>
      </ul>
    </td>
  </tr>
</table>

<table>
  <tr>
    <td width="60%">
      <h3>🔄 GitHub Integration</h3>
      <ul>
        <li>Save Discord CDN URLs to a GitHub repository</li>
        <li>Automatically update existing URL collections with new uploads</li>
        <li>Formatted markdown files with timestamps and organized links</li>
        <li>Perfect for building media galleries or documentation</li>
        <li>Comprehensive security measures for GitHub tokens</li>
      </ul>
    </td>
    <td width="40%">
       <img src="/images/discord_webhook_step2.png" alt="GitHub Integration" width="100%">
    </td>
  </tr>
</table>

## 📥 Installation

### Option 1: Using ComfyUI Manager

1. Install [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager) if you don't have it already
2. Open ComfyUI, go to the Manager tab
3. Search for "ComfyUI-DiscordSend" and install

### Option 2: Manual Installation

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/AEmotionStudio/ComfyUI-DiscordSend
cd ComfyUI-DiscordSend
pip install -r requirements.txt  # Installs the minimal requirements (only the requests library)
```

> [!IMPORTANT]
> - For video functionality, ffmpeg must be installed on your system. The node will automatically detect its presence.
> - This extension has minimal dependencies, requiring only the 'requests' library which is included in the requirements.txt file.

## ⚙️ Settings

### Discord Webhook Setup

#### Step 1: Access Webhook Settings
1. In Discord, go to your server settings → Integrations → Webhooks

![Discord webhook settings](/images/discord_webhook_step1.png)

#### Step 2: Create and Copy Webhook
2. Create a New Webhook and copy the Webhook URL

![Create and copy webhook](/images/discord_webhook_step2.png)
![Create and copy webhook](/images/discord_webhook_step2_2.png)

#### Step 3: Configure the Node
3. Paste this URL into the "webhook_url" field in the DiscordSend nodes

![Configure webhook in node](/images/discord_webhook_step4.png)

<details>
<summary><strong>🖼️ Image Node Options (Click to Expand)</strong></summary>

| Option | Description |
|--------|-------------|
| **Required Parameters** ||
| `images` | The images to save and/or send to Discord |
| `filename_prefix` | Prefix for saved files (default: "ComfyUI-Image") |
| `overwrite_last` | Enable to overwrite last image instead of incrementing filenames |
| **File Options** ||
| `file_format` | PNG, JPEG, or WebP |
| `quality` | 1-100 for JPEG/WebP formats |
| `lossless` | Use lossless compression when available |
| `save_output` | Whether to save images to disk |
| `show_preview` | Show preview in ComfyUI interface |
| **Filename Options** ||
| `add_date` | Add current date to filenames |
| `add_time` | Add current time to filenames |
| `add_dimensions` | Add width and height to filenames |
| `resize_to_power_of_2` | Resize to nearest power of 2 dimensions |
| `resize_method` | Method for resizing (nearest, bilinear, etc.) |
| **Discord Options** ||
| `send_to_discord` | Enable Discord webhook integration |
| `webhook_url` | Discord webhook URL |
| `discord_message` | Text message to accompany images |
| `include_prompts_in_message` | Include generation prompts in Discord message |
| `include_format_in_message` | Include image format details in message |
| `group_batched_images` | Group batch images into one Discord message (max 9 images) |
| `send_workflow_json` | Send workflow JSON for reproducibility |
| **GitHub Options** ||
| `save_cdn_urls` | Save the Discord CDN URLs as a text file and attach to Discord message |
| `github_cdn_update` | Update a GitHub repository with Discord CDN URLs |
| `github_repo` | GitHub repository in format "username/repo" |
| `github_token` | GitHub personal access token (with repo permissions) |
| `github_file_path` | Path to file in repository to update (default: "cdn_urls.md") |

</details>

<details>
<summary><strong>🎬 Video Node Options (Click to Expand)</strong></summary>

| Option | Description |
|--------|-------------|
| **Required Parameters** ||
| `images` | Image sequence to convert to video |
| `filename_prefix` | Prefix for saved files (default: "ComfyUI-Video") |
| `overwrite_last` | Enable to overwrite last video instead of incrementing filenames |
| **Video Options** ||
| `format` | Various formats including GIF, MP4, WebM, ProRes |
| `frame_rate` | Frames per second (0.1-120), values below 1 make images stay longer |
| `quality` | Quality setting for compression (1-100) |
| `loop_count` | Number of loops for GIF (0=infinite) |
| `lossless` | Use lossless compression when available |
| `pingpong` | Create forward-backward looping effect |
| `save_output` | Whether to save video to disk |
| `audio` | Optional audio to embed in video |
| **Filename Options** ||
| `add_date` | Add current date to filenames |
| `add_time` | Add current time to filenames (DO NOT DISABLE for Discord uploads - see known issues) |
| `add_dimensions` | Add width and height to filenames |
| **Discord Options** ||
| `send_to_discord` | Enable Discord webhook integration |
| `webhook_url` | Discord webhook URL |
| `discord_message` | Text message to accompany videos |
| `include_prompts_in_message` | Include generation prompts in Discord message |
| `include_video_info` | Include video format details in message (disable if you don't want time/format info) |
| `send_workflow_json` | Send workflow JSON for reproducibility |
| **GitHub Options** ||
| `save_cdn_urls` | Save the Discord CDN URLs as a text file and attach to Discord message |
| `github_cdn_update` | Update a GitHub repository with Discord CDN URLs |
| `github_repo` | GitHub repository in format "username/repo" |
| `github_token` | GitHub personal access token (with repo permissions) |
| `github_file_path` | Path to file in repository to update (default: "cdn_urls.md") |

</details>

## 🔧 Technical Details

| Component | Description |
|-----------|-------------|
| **Video Processing** | Discord reprocesses all uploaded videos. Quality settings may be modified, and videos compressed. |
| **Max Resolution** | Typically limited to 1080p by Discord. |
| **Max Bitrate** | Reduced based on server boost level. |
| **Image Limit** | Max 9 images per message/gallery. Images >10MB may be refused. |

### Troubleshooting

1. **Videos not playing in Discord**: Try h264-MP4 format, reduce quality, enable `add_time`.
2. **"ffmpeg not found"**: Install system ffmpeg and restart ComfyUI.
3. **Webhook errors**: Verify URL validity and channel existence.
4. **UUID Conflicts**: Ensure unique output directories for multiple users.
5. **GitHub Issues**: Check token permissions (`public_repo`) and repo access.

> [!WARNING]
> **Critical Issue**: Do NOT disable `add_time` for videos sent to Discord. They may appear as a single frame due to Discord's processing. Disable `include_video_info` instead if you want to hide details.

## 🤝 Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started. Whether it's bug reports, feature suggestions, or pull requests, your help is appreciated.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the [GPL-3.0 License](LICENSE.md) - see the LICENSE file for details.

---

<div align="center">
  <br/>
  <h3>Developed by <a href="https://aemotionstudio.org/">Æmotion Studio</a></h3>

  <a href="https://www.youtube.com/@aemotionstudio/videos">
    <img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube" />
  </a>
  <a href="https://discord.gg/UzC9353mfp">
    <img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://ko-fi.com/aemotionstudio">
    <img src="https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi" />
  </a>

  <br/>
  <br/>

  <p>Happy Creating! 🎨</p>
</div>
