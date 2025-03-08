# ComfyUI-DiscordSend

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![ComfyUI](https://img.shields.io/badge/ComfyUI-compatible-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)

**Send your amazing AI-generated images and videos directly to Discord from ComfyUI!**

ComfyUI-DiscordSend provides custom nodes for ComfyUI that allow you to seamlessly:
- Save images and videos locally with advanced formatting options
- Send images, videos, and workflows directly to Discord via webhooks
- Include prompt information and metadata with your creations
- Maintain unique identifiers between different users and uploads

> [!TIP]
> Perfect for sharing your creations with communities, friends, or your own archive channels!

![Example workflow](/images/nodes_example_2.png)

## ✨ Features

### 🖼️ Image Node: `DiscordSendSaveImage`

- Save images in various formats (PNG, JPEG, WebP)
- Send images directly to Discord via webhooks
- Include workflow JSON for easy reproduction
- Customizable Discord messages with prompt information
- Advanced file naming with date, time, and dimension options
- High-quality image export with configurable compression settings
- Built-in preview functionality within ComfyUI interface
- Batch grouping support (up to 9 images per Discord message)
- Unique identifier support to prevent conflicts between users

### 🎬 Video Node: `DiscordSendSaveVideo`

- Convert image sequences to videos in multiple formats
- Support for GIF, MP4, WebM, and professional formats like ProRes
- Configurable frame rates and quality settings
- Add audio to your videos (when supported by format)
- Special effects like ping-pong looping
- Discord integration for sharing videos
- Include workflow data and video information in messages
- UUID support for distinguishing between multiple user uploads

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

## 🚀 Usage

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

#### Webhook Auto-Sanitization

ComfyUI-DiscordSend includes an automatic webhook sanitization feature that:
- Strips out sensitive parts of the webhook URL when displaying in logs
- Automatically converts various Discord webhook URL formats to the standard format
- Supports Discord webhook URLs from different domains (discord.com, discordapp.com)
- Validates webhook URLs before sending to help prevent errors
- Preserves the webhook token internally for actual API calls while hiding it from exposure
- Removes webhook URLs from workflow JSON files before they're sent to Discord
- Sanitizes image metadata to prevent webhook URLs from being embedded in saved images
- Filters webhook URLs from Discord messages to prevent accidental token sharing
- Ensures that webhook URLs are never exposed through any generated content, so long as you are using these nodes to save and not other save nodes in combination (as other save nodes will not sanitize the webhook url when saving alongside this one).

This comprehensive sanitization helps protect your Discord server's webhook tokens from accidental exposure in logs, screenshots, saved files, or shared content while making it easier to use any webhook URL format.

> [!WARNING]
> **Security Recommendation**: It is strongly recommended to only share access to your server webhook with trusted users. Creating individual webhook integrations per user makes it easier to identify which user is sending content to your Discord server. Using a single webhook for multiple users makes content moderation difficult as all uploads will appear under the same webhook identity.

### Image Node

1. Add the `DiscordSendSaveImage` node to your workflow
2. Connect your image output to this node
3. Configure saving and Discord options
4. Run your workflow!

#### Batch Image Handling

When sending multiple images in a batch:
- Up to 9 images can be grouped in a single Discord message
- Enable `group_batched_images` to combine images from a batch
- Batches larger than 9 images will be split into multiple messages
- Each batch maintains the same workflow JSON if enabled

### Video Node

1. Add the `DiscordSendSaveVideo` node to your workflow
2. Connect your image sequence to this node
3. Set frame rate, format, and other video options
4. Optionally connect audio
5. Run your workflow to create and send videos!

> [!NOTE]
> - The video node does not display a preview in the ComfyUI interface, unlike the image node
> - For best Discord compatibility, keep videos under 8MB (or 50MB for servers with boosts)

### 📱 Discord Message Preview

Here's how your images and videos will appear in Discord when sent using ComfyUI-DiscordSend:

![Discord message formatting](/images/discord_formatting.png)

The node formats messages with:
- Optional custom message text
- Generation prompts when enabled
- Technical details about the media
- Professional presentation with markdown formatting
- Attached workflow JSON file when enabled
- Image galleries for batch uploads (up to 9 images per message)

## 📝 Configuration Options

### DiscordSendSaveImage Options

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

### DiscordSendSaveVideo Options

| Option | Description |
|--------|-------------|
| **Required Parameters** ||
| `images` | Image sequence to convert to video |
| `filename_prefix` | Prefix for saved files (default: "ComfyUI-Video") |
| `overwrite_last` | Enable to overwrite last video instead of incrementing filenames |
| **Video Options** ||
| `format` | Various formats including GIF, MP4, WebM, ProRes |
| `frame_rate` | Frames per second (1-120) |
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

## 📋 Requirements

- ComfyUI (latest version recommended)
- Python 3.8+
- Python dependencies: Only the 'requests' library (automatically installed via requirements.txt)
- For video functionality: ffmpeg (system-level dependency)

## ❓ Troubleshooting

> [!WARNING]
> If Discord fails to receive your media, check:

- **File Size**: Discord has upload limits (8MB for regular servers, 50MB for boosted servers)
- **Webhook URL**: Ensure your webhook URL is valid and has not been regenerated

### Discord Limitations

- **Video Processing**: Discord reprocesses all uploaded videos to optimize for their platform. This means:
  - Original quality settings may be modified regardless of what you set
  - Videos may be compressed further even with high-quality settings
  - Some formats may be converted to different formats by Discord
  - Previews may not be available immediately after upload
  - Maximum resolution is limited (typically 1080p)
  - Maximum bitrate may be reduced based on server boost level

- **Image Limitations**:
  - Maximum of 9 images per message/gallery
  - Images over 10MB may be refused

### Troubleshooting

1. **Videos not playing in Discord**
   - Try using more compatible formats like h264-MP4
   - Reduce quality settings to decrease file size
   - Make sure add_time is enabled

2. **"ffmpeg not found" warning**
   - Install ffmpeg on your system and ensure it's in your PATH
   - Restart ComfyUI after installation

3. **Webhook errors**
   - Verify webhook URL is correct and the channel still exists
   - Check Discord's status if all webhooks are failing

4. **UUID Support and Conflicts**
   - Each upload includes a UUID to prevent conflicts between users
   - If you experience files overwriting each other, ensure multiple users aren't sharing the same output directory

### Known Issues

1. **Critical: Do NOT disable `add_time` for videos sent to Discord**
   - When the `add_time` option is disabled for videos being sent to Discord, they may appear as a single frame or static image
   - If you want to omit time information in Discord messages, disable `include_video_info` instead
   - This is a limitation of how Discord identifies and processes video files

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

Please follow the standard GitHub flow for contributions.

## 🙏 Acknowledgements

- ComfyUI team for the amazing platform
- All contributors and users who provide feedback

## 🔗 Connect with me

- YouTube: [AEmotionStudio](https://www.youtube.com/@aemotionstudio/videos)
- GitHub: [AEmotionStudio](https://github.com/AEmotionStudio)
- Discord: [Join our community](https://discord.gg/UzC9353mfp)
- Website: [aemotionstudio.org](https://aemotionstudio.org/)

## ☕ Support

If you find ComfyUI-DiscordSend useful, consider supporting its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/aemotionstudio)

Your support helps me dedicate more time to maintaining and improving this project and others with new features, bug fixes, and better documentation.

### 💖 Additional Ways to Support

- ⭐ Star the repository
- 📢 Share it with others
- 🛠️ Contribute to its development

For business inquiries or professional support, please contact me through my [website](https://aemotionstudio.org/) or join my [Discord server](https://discord.gg/UzC9353mfp).

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.
