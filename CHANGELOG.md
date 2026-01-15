# Changelog

All notable changes to this project will be documented in this file.

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
