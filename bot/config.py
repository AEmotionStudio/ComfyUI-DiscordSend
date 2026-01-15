"""
Configuration management for the Discord bot.

Configuration is loaded from (in priority order):
1. Environment variables (highest priority)
2. Config file (bot/config.yaml)
3. Defaults (lowest priority)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DiscordConfig:
    """Discord-related configuration."""
    token: str = ""
    application_id: Optional[str] = None


@dataclass
class ComfyUIConfig:
    """ComfyUI connection configuration."""
    url: str = "http://127.0.0.1:8188"
    ws_url: str = "ws://127.0.0.1:8188/ws"
    timeout: int = 30


@dataclass
class DefaultsConfig:
    """Default values for bot operations."""
    max_queue_per_user: int = 3
    progress_update_interval: float = 2.0
    workflow_path: Optional[str] = None
    default_steps: int = 20
    default_cfg: float = 7.0
    default_width: int = 512
    default_height: int = 512


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = ""

    def __post_init__(self):
        if not self.url:
            # Default to SQLite in bot/data directory
            bot_dir = Path(__file__).parent
            data_dir = bot_dir / "data"
            data_dir.mkdir(exist_ok=True)
            self.url = f"sqlite+aiosqlite:///{data_dir}/bot.db"


@dataclass
class SecurityConfig:
    """Security configuration."""
    allowed_guilds: list[int] = field(default_factory=list)


@dataclass
class BotConfig:
    """Main bot configuration container."""
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    comfyui: ComfyUIConfig = field(default_factory=ComfyUIConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "BotConfig":
        """
        Load configuration from file and environment variables.

        Args:
            config_path: Optional path to config.yaml file

        Returns:
            Loaded BotConfig instance
        """
        config = cls()

        # Load from config file if exists
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        if config_path.exists():
            config._load_from_file(config_path)

        # Override with environment variables
        config._load_from_env()

        return config

    def _load_from_file(self, path: Path) -> None:
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Discord config
        if "discord" in data:
            discord_data = data["discord"]
            if "token" in discord_data:
                self.discord.token = discord_data["token"]
            if "application_id" in discord_data:
                self.discord.application_id = discord_data["application_id"]

        # ComfyUI config
        if "comfyui" in data:
            comfyui_data = data["comfyui"]
            if "url" in comfyui_data:
                self.comfyui.url = comfyui_data["url"]
            if "ws_url" in comfyui_data:
                self.comfyui.ws_url = comfyui_data["ws_url"]
            if "timeout" in comfyui_data:
                self.comfyui.timeout = comfyui_data["timeout"]

        # Defaults config
        if "defaults" in data:
            defaults_data = data["defaults"]
            if "max_queue_per_user" in defaults_data:
                self.defaults.max_queue_per_user = defaults_data["max_queue_per_user"]
            if "progress_update_interval" in defaults_data:
                self.defaults.progress_update_interval = defaults_data["progress_update_interval"]
            if "workflow_path" in defaults_data:
                self.defaults.workflow_path = defaults_data["workflow_path"]
            if "default_steps" in defaults_data:
                self.defaults.default_steps = defaults_data["default_steps"]
            if "default_cfg" in defaults_data:
                self.defaults.default_cfg = defaults_data["default_cfg"]
            if "default_width" in defaults_data:
                self.defaults.default_width = defaults_data["default_width"]
            if "default_height" in defaults_data:
                self.defaults.default_height = defaults_data["default_height"]

        # Database config
        if "database" in data:
            db_data = data["database"]
            if "url" in db_data:
                self.database.url = db_data["url"]

        # Security config
        if "security" in data:
            security_data = data["security"]
            if "allowed_guilds" in security_data:
                self.security.allowed_guilds = security_data["allowed_guilds"] or []

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Discord
        if token := os.getenv("DISCORDBOT_DISCORD_TOKEN"):
            self.discord.token = token
        if app_id := os.getenv("DISCORDBOT_APPLICATION_ID"):
            self.discord.application_id = app_id

        # ComfyUI
        if url := os.getenv("DISCORDBOT_COMFYUI_URL"):
            self.comfyui.url = url
        if ws_url := os.getenv("DISCORDBOT_COMFYUI_WS_URL"):
            self.comfyui.ws_url = ws_url
        if timeout := os.getenv("DISCORDBOT_COMFYUI_TIMEOUT"):
            self.comfyui.timeout = int(timeout)

        # Database
        if db_url := os.getenv("DISCORDBOT_DATABASE_URL"):
            self.database.url = db_url

        # Defaults
        if max_queue := os.getenv("DISCORDBOT_MAX_QUEUE_PER_USER"):
            self.defaults.max_queue_per_user = int(max_queue)
        if workflow := os.getenv("DISCORDBOT_WORKFLOW_PATH"):
            self.defaults.workflow_path = workflow

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.discord.token:
            errors.append("Discord token is required (set DISCORDBOT_DISCORD_TOKEN)")

        if not self.comfyui.url:
            errors.append("ComfyUI URL is required")

        return errors


# Global config instance (lazy loaded)
_config: Optional[BotConfig] = None


def get_config() -> BotConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = BotConfig.load()
    return _config


def reload_config(config_path: Optional[Path] = None) -> BotConfig:
    """Reload configuration from disk."""
    global _config
    _config = BotConfig.load(config_path)
    return _config
