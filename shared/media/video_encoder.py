"""
Video encoding utilities for ComfyUI-DiscordSend

Provides FFmpeg-based video encoding with fallback to PIL for GIF/WebP.
"""

import os
import subprocess
from typing import List, Tuple, Optional, Iterator, Any, Callable
from uuid import uuid4
import numpy as np


def detect_ffmpeg() -> Optional[str]:
    """
    Detect FFmpeg binary location.

    Returns:
        Path to FFmpeg executable, or None if not found
    """
    ffmpeg_path = None

    # Try imageio-ffmpeg first (common in Python environments)
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"Found ffmpeg via imageio_ffmpeg: {ffmpeg_path}")
        return ffmpeg_path
    except (ImportError, Exception):
        pass

    # Try system PATH
    try:
        from shutil import which
        ffmpeg_path = which("ffmpeg")
        if ffmpeg_path:
            print(f"Found ffmpeg in system path: {ffmpeg_path}")
            return ffmpeg_path
    except Exception:
        pass

    return None


class FFmpegEncoder:
    """
    FFmpeg-based video encoder supporting multiple formats.
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Initialize the encoder.

        Args:
            ffmpeg_path: Path to FFmpeg executable (auto-detected if None)
        """
        self.ffmpeg_path = ffmpeg_path or detect_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Install ffmpeg or imageio-ffmpeg.")

    def encode(
        self,
        images: List[np.ndarray],
        output_path: str,
        format_ext: str,
        frame_rate: float = 24.0,
        quality: int = 85,
        lossless: bool = False,
        loop_count: int = 0,
        codec: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Encode images to video using FFmpeg.

        Args:
            images: List of numpy arrays (H, W, C) in uint8 format
            output_path: Output file path
            format_ext: Output format extension (mp4, webm, gif)
            frame_rate: Frame rate in FPS
            quality: Quality level 1-100
            lossless: Use lossless encoding if supported
            loop_count: Number of loops (0 = infinite for GIF)
            codec: Specific codec to use (h264, h265, vp9, etc.)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Path to the encoded file
        """
        if not images:
            raise ValueError("No images provided for encoding")

        # Get dimensions from first image
        height, width = images[0].shape[:2]
        has_alpha = images[0].shape[2] == 4 if len(images[0].shape) > 2 else False

        # Determine input pixel format
        i_pix_fmt = "rgba" if has_alpha else "rgb24"
        dimensions = f"{width}x{height}"

        # Build FFmpeg arguments
        args = self._build_ffmpeg_args(
            format_ext=format_ext,
            dimensions=dimensions,
            frame_rate=frame_rate,
            quality=quality,
            lossless=lossless,
            loop_count=loop_count,
            i_pix_fmt=i_pix_fmt,
            has_alpha=has_alpha,
            codec=codec,
            output_path=output_path
        )

        # Execute encoding
        self._execute_encoding(args, images, i_pix_fmt, progress_callback)

        return output_path

    def _build_ffmpeg_args(
        self,
        format_ext: str,
        dimensions: str,
        frame_rate: float,
        quality: int,
        lossless: bool,
        loop_count: int,
        i_pix_fmt: str,
        has_alpha: bool,
        codec: Optional[str],
        output_path: str
    ) -> List[str]:
        """Build FFmpeg command arguments."""

        # Loop arguments
        loop_args = []
        if format_ext == "gif":
            loop_args = ["-loop", "0" if loop_count == 0 else str(loop_count)]

        # Base input arguments
        args = [
            self.ffmpeg_path, "-v", "error",
            "-f", "rawvideo",
            "-pix_fmt", i_pix_fmt,
            "-s", dimensions,
            "-r", str(frame_rate),
            "-i", "-"
        ] + loop_args

        # Format-specific encoding arguments
        if format_ext == "gif":
            args.extend(self._get_gif_args(quality))
        elif format_ext == "mp4":
            args.extend(self._get_mp4_args(quality, lossless, codec))
        elif format_ext == "webm":
            args.extend(self._get_webm_args(quality, lossless, has_alpha))
        else:
            # Default to MP4-like encoding
            args.extend(self._get_mp4_args(quality, lossless, codec))

        # Add output path
        args.extend(["-y", output_path])

        return args

    def _get_gif_args(self, quality: int) -> List[str]:
        """Get FFmpeg arguments for GIF encoding."""
        # Use palettegen for better quality
        if quality >= 80:
            return [
                "-vf", "split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2",
                "-f", "gif"
            ]
        else:
            return [
                "-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                "-f", "gif"
            ]

    def _get_mp4_args(self, quality: int, lossless: bool, codec: Optional[str]) -> List[str]:
        """Get FFmpeg arguments for MP4 encoding."""
        args = []

        # Determine codec
        use_h265 = codec == "h265" or codec == "hevc"

        if lossless:
            if use_h265:
                args.extend(["-c:v", "libx265", "-x265-params", "lossless=1"])
            else:
                args.extend(["-c:v", "libx264", "-crf", "0"])
        else:
            # Map quality (1-100) to CRF (51-0 for h264, lower is better)
            crf = int(51 - (quality / 100 * 33))  # Maps 1->51, 100->18

            if use_h265:
                args.extend(["-c:v", "libx265", "-crf", str(crf + 5)])  # H.265 uses different CRF scale
            else:
                args.extend(["-c:v", "libx264", "-crf", str(crf)])

        # Always use yuv420p for Discord compatibility
        args.extend(["-pix_fmt", "yuv420p", "-movflags", "faststart"])

        return args

    def _get_webm_args(self, quality: int, lossless: bool, has_alpha: bool) -> List[str]:
        """Get FFmpeg arguments for WebM encoding."""
        args = ["-c:v", "libvpx-vp9"]

        if lossless:
            args.extend(["-lossless", "1"])
        else:
            # Map quality to CRF (63-0 for VP9)
            crf = int(63 - (quality / 100 * 33))  # Maps 1->63, 100->30
            args.extend(["-crf", str(crf), "-b:v", "0"])

        # Pixel format - support alpha if present
        pix_fmt = "yuva420p" if has_alpha else "yuv420p"
        args.extend(["-pix_fmt", pix_fmt])

        # VP9 threading
        args.extend(["-row-mt", "1"])

        return args

    def _execute_encoding(
        self,
        args: List[str],
        images: List[np.ndarray],
        i_pix_fmt: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """Execute FFmpeg process and feed frames."""
        total_frames = len(images)

        # Create image chunk iterator for memory efficiency
        def image_chunks() -> Iterator[bytes]:
            for i, img in enumerate(images):
                # Ensure contiguous array for subprocess
                chunk = np.ascontiguousarray(img)
                if progress_callback:
                    progress_callback(i + 1, total_frames)
                yield chunk.tobytes()

        # Start FFmpeg process
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Feed frames
        try:
            for chunk in image_chunks():
                process.stdin.write(chunk)
            process.stdin.close()
            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                raise RuntimeError(f"FFmpeg encoding failed: {stderr}")
        finally:
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()


class PILEncoder:
    """
    PIL-based encoder for GIF and WebP formats.
    Fallback when FFmpeg is not available.
    """

    def encode(
        self,
        images: List[Any],  # PIL Images or numpy arrays
        output_path: str,
        format_ext: str,
        frame_rate: float = 24.0,
        quality: int = 85,
        lossless: bool = False,
        loop_count: int = 0,
        tensor_to_numpy_func: Optional[Callable] = None
    ) -> str:
        """
        Encode images using PIL.

        Args:
            images: List of PIL Images or numpy arrays
            output_path: Output file path
            format_ext: Output format (gif, webp)
            frame_rate: Frame rate in FPS
            quality: Quality level 1-100
            lossless: Use lossless encoding for WebP
            loop_count: Number of loops (0 = infinite)
            tensor_to_numpy_func: Optional function to convert tensors to numpy

        Returns:
            Path to the encoded file
        """
        from PIL import Image

        # Convert to PIL images if needed
        pil_images = []
        for img in images:
            if hasattr(img, 'shape'):  # numpy array or tensor
                if tensor_to_numpy_func and hasattr(img, 'cpu'):
                    img = tensor_to_numpy_func(img)
                elif hasattr(img, 'numpy'):
                    img = img.numpy()
                pil_images.append(Image.fromarray(img.astype(np.uint8)))
            else:
                pil_images.append(img)

        if not pil_images:
            raise ValueError("No images provided for encoding")

        # Calculate frame duration in milliseconds
        duration = int(1000 / frame_rate)

        if format_ext.lower() == "gif":
            self._encode_gif(pil_images, output_path, duration, loop_count)
        elif format_ext.lower() == "webp":
            self._encode_webp(pil_images, output_path, duration, loop_count, quality, lossless)
        else:
            # Single frame fallback
            pil_images[0].save(output_path, format=format_ext.upper())

        return output_path

    def _encode_gif(
        self,
        images: List[Any],
        output_path: str,
        duration: int,
        loop_count: int
    ) -> None:
        """Encode images as GIF."""
        durations = [duration] * len(images)
        images[0].save(
            output_path,
            format="GIF",
            append_images=images[1:] if len(images) > 1 else [],
            save_all=True,
            duration=durations,
            loop=0 if loop_count == 0 else loop_count,
            optimize=False
        )

    def _encode_webp(
        self,
        images: List[Any],
        output_path: str,
        duration: int,
        loop_count: int,
        quality: int,
        lossless: bool
    ) -> None:
        """Encode images as WebP."""
        save_kwargs = {
            "format": "WEBP",
            "append_images": images[1:] if len(images) > 1 else [],
            "save_all": True,
            "duration": duration,
            "loop": 0 if loop_count == 0 else loop_count,
        }

        if lossless:
            save_kwargs["lossless"] = True
        else:
            save_kwargs["quality"] = quality

        images[0].save(output_path, **save_kwargs)


def optimize_video_for_discord(
    input_file: str,
    ffmpeg_path: str,
    temp_dir: str
) -> Optional[str]:
    """
    Create a Discord-optimized version of a video file.

    Args:
        input_file: Path to the input video file
        ffmpeg_path: Path to FFmpeg executable
        temp_dir: Directory for temporary files

    Returns:
        Path to the optimized file, or None if optimization failed
    """
    format_ext = os.path.splitext(input_file)[1].lstrip('.').lower()
    discord_optimized_file = os.path.join(temp_dir, f"discord_optimized_{uuid4()}.{format_ext}")

    try:
        if format_ext == "mp4":
            optimize_args = [
                ffmpeg_path, "-i", input_file,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "faststart", "-preset", "fast",
                "-profile:v", "baseline", "-level", "3.0",
                "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-y", discord_optimized_file
            ]
        elif format_ext == "webm":
            optimize_args = [
                ffmpeg_path, "-i", input_file,
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuv420p",
                "-crf", "30", "-b:v", "0",
                "-deadline", "good",
                "-c:a", "libopus", "-b:a", "96k",
                "-y", discord_optimized_file
            ]
        elif format_ext == "gif":
            optimize_args = [
                ffmpeg_path, "-i", input_file,
                "-vf", "fps=15,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-y", discord_optimized_file
            ]
        else:
            print(f"No optimization rules for format: {format_ext}")
            return None

        print(f"Creating Discord-optimized version of {format_ext.upper()} file...")
        result = subprocess.run(
            optimize_args,
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and os.path.exists(discord_optimized_file):
            print(f"Discord-optimized file created: {discord_optimized_file}")
            return discord_optimized_file
        else:
            print(f"Optimization failed: {result.stderr}")
            return None

    except Exception as e:
        print(f"Error during Discord optimization: {e}")
        return None


def mux_audio_to_video(
    video_path: str,
    audio_waveform: np.ndarray,
    sample_rate: int,
    format_ext: str,
    ffmpeg_path: str,
    output_path: str,
    channels: int = 2
) -> bool:
    """
    Mux audio into a video file.

    Args:
        video_path: Path to the video file
        audio_waveform: Audio data as numpy array
        sample_rate: Audio sample rate
        format_ext: Video format extension
        ffmpeg_path: Path to FFmpeg executable
        output_path: Output path for the muxed file
        channels: Number of audio channels

    Returns:
        True if successful, False otherwise
    """
    try:
        # Determine audio codec based on format
        if format_ext == "mp4":
            audio_pass = ["-c:a", "aac", "-b:a", "192k"]
        elif format_ext == "webm":
            audio_pass = ["-c:a", "libopus", "-b:a", "128k"]
        else:
            audio_pass = ["-c:a", "libopus", "-b:a", "128k"]

        mux_args = [
            ffmpeg_path, "-v", "error", "-y",
            "-i", video_path,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-f", "f32le",
            "-i", "-",
            "-c:v", "copy"
        ] + audio_pass + ["-shortest", output_path]

        # Ensure contiguous array for subprocess
        audio_data = np.ascontiguousarray(audio_waveform)

        result = subprocess.run(
            mux_args,
            input=memoryview(audio_data),
            capture_output=True
        )

        if result.returncode == 0:
            print(f"Successfully muxed audio to video: {output_path}")
            return True
        else:
            print(f"Audio muxing failed: {result.stderr.decode('utf-8', errors='ignore')}")
            return False

    except Exception as e:
        print(f"Error muxing audio: {e}")
        return False
