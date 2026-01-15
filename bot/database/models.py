"""
SQLAlchemy ORM models for bot persistence.

Tables:
- users: Discord user preferences
- servers: Guild configuration
- server_roles: Permission role mappings
- templates: Saved prompt presets
- jobs: Generation history and queue
- workflows: Default workflow storage
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class DeliveryType(str, Enum):
    """Delivery method for generated images."""
    CHANNEL = "channel"
    DM = "dm"


class JobStatus(str, Enum):
    """Status of a generation job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionLevel(str, Enum):
    """Permission levels for role-based access."""
    USER = "user"
    GENERATOR = "generator"
    ADMIN = "admin"


class User(Base):
    """Discord user preferences and data."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(String(20), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    default_delivery = Column(String(10), default=DeliveryType.CHANNEL.value)
    default_workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    templates = relationship("Template", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    default_workflow = relationship("Workflow", foreign_keys=[default_workflow_id])

    def __repr__(self) -> str:
        return f"<User(id={self.id}, discord_id={self.discord_id}, username={self.username})>"


class Server(Base):
    """Discord server (guild) configuration."""
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    default_channel_id = Column(String(20), nullable=True)
    enabled = Column(Boolean, default=True)
    max_queue_per_user = Column(Integer, default=3)
    default_workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    roles = relationship("ServerRole", back_populates="server", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="server", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="server")
    default_workflow = relationship("Workflow", foreign_keys=[default_workflow_id])

    def __repr__(self) -> str:
        return f"<Server(id={self.id}, discord_id={self.discord_id}, name={self.name})>"


class ServerRole(Base):
    """Role-based permission mapping for servers."""
    __tablename__ = "server_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    role_discord_id = Column(String(20), nullable=False)
    permission_level = Column(String(20), nullable=False)

    # Relationships
    server = relationship("Server", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("server_id", "role_discord_id", name="uq_server_role"),
        Index("idx_server_roles_server", "server_id"),
    )

    def __repr__(self) -> str:
        return f"<ServerRole(server_id={self.server_id}, role={self.role_discord_id}, level={self.permission_level})>"


class Workflow(Base):
    """Stored workflow configurations."""
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    workflow_json = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, name={self.name}, is_default={self.is_default})>"


class Template(Base):
    """User-saved prompt templates."""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)  # NULL = private
    name = Column(String(100), nullable=False)
    positive_prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, default="")
    parameters = Column(Text, nullable=True)  # JSON: {steps, cfg, seed, etc.}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="templates")
    server = relationship("Server", back_populates="templates")

    __table_args__ = (
        Index("idx_templates_user", "user_id"),
        Index("idx_templates_server", "server_id"),
        UniqueConstraint("user_id", "server_id", "name", name="uq_template_name"),
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name={self.name}, user_id={self.user_id})>"


class Job(Base):
    """Generation job tracking and history."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)
    channel_id = Column(String(20), nullable=True)

    # Status tracking
    status = Column(String(20), default=JobStatus.PENDING.value, index=True)
    queue_position = Column(Integer, nullable=True)
    progress = Column(Integer, default=0)
    progress_max = Column(Integer, default=0)

    # Generation parameters
    positive_prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    parameters = Column(Text, nullable=True)  # JSON
    workflow_json = Column(Text, nullable=True)

    # Results
    output_images = Column(Text, nullable=True)  # JSON array
    error_message = Column(Text, nullable=True)

    # Delivery
    delivery_type = Column(String(10), default=DeliveryType.CHANNEL.value)
    message_id = Column(String(20), nullable=True)  # Discord message for updates

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")
    server = relationship("Server", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_user", "user_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created", "created_at"),
    )

    @property
    def duration(self) -> Optional[float]:
        """Get job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, prompt_id={self.prompt_id}, status={self.status})>"
