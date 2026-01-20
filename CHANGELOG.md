# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-01-20

### Major Refactoring Release

Complete architectural refactoring to improve code organization, reduce duplication, and add bot features.

### Added
- **Directory Structure**: New `nodes/`, `shared/`, `bot/` organization
- **BaseDiscordNode**: Shared base class for image and video nodes (343 lines of reusable code)
- **Shared Utilities**: 17 modular utility files in `shared/` package
  - `shared/discord/` - webhook client, message builder, CDN extractor
  - `shared/media/` - video encoder, format utils, image processing
  - `shared/workflow/` - sanitizer, prompt extractor, workflow builder
- **Bot Features**:
  - WebSocket reconnection with exponential backoff
  - Error delivery to Discord users
  - `/template` commands (save, load, list, delete)
  - `/history` and `/rerun` commands
  - Config templates: `config.yaml.example`, `.env.example`

### Changed
- **Code Reduction**: Total node code reduced by 620 lines (24%)
  - Image node: 986 → 836 lines
  - Video node: 1562 → 1092 lines
- **Imports**: All imports now use `shared/` package instead of `discordsend_utils/`
- **Video Encoding**: Extracted to `FFmpegEncoder` and `PILEncoder` classes

### Fixed
- Bot startup bugs (BotConfig import, missing json import, permission imports)
- SDXL workflow prompt extraction support
- CDN URL redundant sends on 204 responses
- Message builder metadata section formatting

### Removed
- `discordsend_utils/` directory (replaced by `shared/`)
- Obsolete documentation files

## [Unreleased]

### Changed
- **Performance**: Optimized image processing in `DiscordSendSaveImage` node.
  - Replaced redundant PIL-to-Numpy conversions with optimized Torch operations (~70% faster tensor processing).
  - Optimized JPEG encoding to use PIL directly, bypassing OpenCV conversion (~30% faster).

## [1.1.0] - 2026-01-10

### Added
- **Image Node**: `DiscordSendSaveImage` for saving and sending images with advanced formatting.
- **Video Node**: `DiscordSendSaveVideo` for converting image sequences to video (GIF, MP4, WebM, ProRes).
- **GitHub Integration**: Automatically archive Discord CDN URLs to a GitHub repository.
- **Testing**: Added initial test suite.
- **Logging**: Implemented structured logging for better debugging.
