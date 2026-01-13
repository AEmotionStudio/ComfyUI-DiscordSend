"""
Data access layer for bot database operations.

Provides async CRUD operations for all database models.
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from .models import (
    Base,
    User,
    Server,
    ServerRole,
    Template,
    Job,
    Workflow,
    JobStatus,
    PermissionLevel,
)


class Repository:
    """Async repository for database operations."""

    def __init__(self, database_url: str):
        """
        Initialize the repository.

        Args:
            database_url: SQLAlchemy async database URL
        """
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Close the database connection."""
        await self.engine.dispose()

    # ==================== User Operations ====================

    async def get_or_create_user(
        self,
        discord_id: str,
        username: str,
    ) -> User:
        """Get existing user or create new one."""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.discord_id == discord_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(discord_id=discord_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            elif user.username != username:
                user.username = username
                await session.commit()

            return user

    async def get_user(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.discord_id == discord_id)
            )
            return result.scalar_one_or_none()

    async def update_user_delivery(
        self,
        discord_id: str,
        delivery_type: str,
    ) -> Optional[User]:
        """Update user's default delivery preference."""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.discord_id == discord_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.default_delivery = delivery_type
                await session.commit()
            return user

    # ==================== Server Operations ====================

    async def get_or_create_server(
        self,
        discord_id: str,
        name: str,
    ) -> Server:
        """Get existing server or create new one."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Server).where(Server.discord_id == discord_id)
            )
            server = result.scalar_one_or_none()

            if server is None:
                server = Server(discord_id=discord_id, name=name)
                session.add(server)
                await session.commit()
                await session.refresh(server)
            elif server.name != name:
                server.name = name
                await session.commit()

            return server

    async def get_server(self, discord_id: str) -> Optional[Server]:
        """Get server by Discord ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Server)
                .options(selectinload(Server.roles))
                .where(Server.discord_id == discord_id)
            )
            return result.scalar_one_or_none()

    async def update_server_channel(
        self,
        discord_id: str,
        channel_id: str,
    ) -> Optional[Server]:
        """Update server's default output channel."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Server).where(Server.discord_id == discord_id)
            )
            server = result.scalar_one_or_none()
            if server:
                server.default_channel_id = channel_id
                await session.commit()
            return server

    async def update_server_queue_limit(
        self,
        discord_id: str,
        limit: int,
    ) -> Optional[Server]:
        """Update server's per-user queue limit."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Server).where(Server.discord_id == discord_id)
            )
            server = result.scalar_one_or_none()
            if server:
                server.max_queue_per_user = limit
                await session.commit()
            return server

    # ==================== Role Operations ====================

    async def set_server_role(
        self,
        server_discord_id: str,
        role_discord_id: str,
        permission_level: str,
    ) -> ServerRole:
        """Set or update a role's permission level for a server."""
        async with self.async_session() as session:
            # Get server
            server_result = await session.execute(
                select(Server).where(Server.discord_id == server_discord_id)
            )
            server = server_result.scalar_one_or_none()
            if not server:
                raise ValueError(f"Server {server_discord_id} not found")

            # Check for existing role mapping
            role_result = await session.execute(
                select(ServerRole).where(
                    ServerRole.server_id == server.id,
                    ServerRole.role_discord_id == role_discord_id,
                )
            )
            role = role_result.scalar_one_or_none()

            if role:
                role.permission_level = permission_level
            else:
                role = ServerRole(
                    server_id=server.id,
                    role_discord_id=role_discord_id,
                    permission_level=permission_level,
                )
                session.add(role)

            await session.commit()
            await session.refresh(role)
            return role

    async def get_server_roles(self, server_discord_id: str) -> list[ServerRole]:
        """Get all role mappings for a server."""
        async with self.async_session() as session:
            server_result = await session.execute(
                select(Server).where(Server.discord_id == server_discord_id)
            )
            server = server_result.scalar_one_or_none()
            if not server:
                return []

            result = await session.execute(
                select(ServerRole).where(ServerRole.server_id == server.id)
            )
            return list(result.scalars().all())

    async def delete_server_role(
        self,
        server_discord_id: str,
        role_discord_id: str,
    ) -> bool:
        """Remove a role mapping."""
        async with self.async_session() as session:
            server_result = await session.execute(
                select(Server).where(Server.discord_id == server_discord_id)
            )
            server = server_result.scalar_one_or_none()
            if not server:
                return False

            result = await session.execute(
                delete(ServerRole).where(
                    ServerRole.server_id == server.id,
                    ServerRole.role_discord_id == role_discord_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== Template Operations ====================

    async def create_template(
        self,
        user_discord_id: str,
        name: str,
        positive_prompt: str,
        negative_prompt: str = "",
        parameters: Optional[dict] = None,
        server_discord_id: Optional[str] = None,
    ) -> Template:
        """Create a new prompt template."""
        async with self.async_session() as session:
            # Get user
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_discord_id} not found")

            # Get server if provided
            server_id = None
            if server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    server_id = server.id

            template = Template(
                user_id=user.id,
                server_id=server_id,
                name=name,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                parameters=json.dumps(parameters) if parameters else None,
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            return template

    async def get_template(
        self,
        user_discord_id: str,
        name: str,
        server_discord_id: Optional[str] = None,
    ) -> Optional[Template]:
        """Get a template by name."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return None

            # Build query
            query = select(Template).where(
                Template.user_id == user.id,
                Template.name == name,
            )

            if server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    query = query.where(Template.server_id == server.id)
            else:
                query = query.where(Template.server_id.is_(None))

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def list_templates(
        self,
        user_discord_id: str,
        server_discord_id: Optional[str] = None,
        include_shared: bool = True,
    ) -> list[Template]:
        """List templates for a user."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []

            # Private templates
            query = select(Template).where(
                Template.user_id == user.id,
                Template.server_id.is_(None),
            )
            result = await session.execute(query)
            templates = list(result.scalars().all())

            # Shared templates in server
            if include_shared and server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    shared_query = select(Template).where(
                        Template.server_id == server.id
                    )
                    shared_result = await session.execute(shared_query)
                    templates.extend(shared_result.scalars().all())

            return templates

    async def delete_template(
        self,
        user_discord_id: str,
        name: str,
        server_discord_id: Optional[str] = None,
    ) -> bool:
        """Delete a template."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return False

            query = delete(Template).where(
                Template.user_id == user.id,
                Template.name == name,
            )

            if server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    query = query.where(Template.server_id == server.id)
            else:
                query = query.where(Template.server_id.is_(None))

            result = await session.execute(query)
            await session.commit()
            return result.rowcount > 0

    # ==================== Job Operations ====================

    async def create_job(
        self,
        prompt_id: str,
        user_discord_id: str,
        positive_prompt: str,
        negative_prompt: str = "",
        parameters: Optional[dict] = None,
        workflow_json: Optional[str] = None,
        delivery_type: str = "channel",
        server_discord_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> Job:
        """Create a new generation job."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User {user_discord_id} not found")

            server_id = None
            if server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    server_id = server.id

            job = Job(
                prompt_id=prompt_id,
                user_id=user.id,
                server_id=server_id,
                channel_id=channel_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                parameters=json.dumps(parameters) if parameters else None,
                workflow_json=workflow_json,
                delivery_type=delivery_type,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def get_job(self, prompt_id: str) -> Optional[Job]:
        """Get a job by prompt ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.user))
                .where(Job.prompt_id == prompt_id)
            )
            return result.scalar_one_or_none()

    async def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """Get a job by internal ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.user))
                .where(Job.id == job_id)
            )
            return result.scalar_one_or_none()

    async def update_job_status(
        self,
        prompt_id: str,
        status: str,
        error_message: Optional[str] = None,
        output_images: Optional[list[str]] = None,
    ) -> Optional[Job]:
        """Update job status."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job).where(Job.prompt_id == prompt_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                return None

            job.status = status

            if status == JobStatus.RUNNING.value:
                job.started_at = datetime.utcnow()
            elif status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
                job.completed_at = datetime.utcnow()

            if error_message is not None:
                job.error_message = error_message

            if output_images is not None:
                job.output_images = json.dumps(output_images)

            await session.commit()
            return job

    async def update_job_progress(
        self,
        prompt_id: str,
        progress: int,
        progress_max: int,
    ) -> Optional[Job]:
        """Update job progress."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job).where(Job.prompt_id == prompt_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.progress = progress
                job.progress_max = progress_max
                await session.commit()
            return job

    async def update_job_message(
        self,
        prompt_id: str,
        message_id: str,
    ) -> Optional[Job]:
        """Update the Discord message ID for a job."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job).where(Job.prompt_id == prompt_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.message_id = message_id
                await session.commit()
            return job

    async def list_user_jobs(
        self,
        user_discord_id: str,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> list[Job]:
        """List jobs for a user."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []

            query = (
                select(Job)
                .where(Job.user_id == user.id)
                .order_by(Job.created_at.desc())
                .limit(limit)
            )

            if status:
                query = query.where(Job.status == status)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def count_user_pending_jobs(
        self,
        user_discord_id: str,
        server_discord_id: Optional[str] = None,
    ) -> int:
        """Count pending/running jobs for a user."""
        async with self.async_session() as session:
            user_result = await session.execute(
                select(User).where(User.discord_id == user_discord_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return 0

            query = (
                select(func.count(Job.id))
                .where(Job.user_id == user.id)
                .where(Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]))
            )

            if server_discord_id:
                server_result = await session.execute(
                    select(Server).where(Server.discord_id == server_discord_id)
                )
                server = server_result.scalar_one_or_none()
                if server:
                    query = query.where(Job.server_id == server.id)

            result = await session.execute(query)
            return result.scalar() or 0

    async def get_pending_jobs(self) -> list[Job]:
        """Get all pending jobs ordered by creation time."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.user))
                .where(Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]))
                .order_by(Job.created_at)
            )
            return list(result.scalars().all())

    # ==================== Workflow Operations ====================

    async def save_workflow(
        self,
        name: str,
        workflow_json: str,
        description: Optional[str] = None,
        is_default: bool = False,
    ) -> Workflow:
        """Save a workflow configuration."""
        async with self.async_session() as session:
            # If setting as default, unset other defaults
            if is_default:
                await session.execute(
                    update(Workflow).where(Workflow.is_default == True).values(is_default=False)
                )

            workflow = Workflow(
                name=name,
                workflow_json=workflow_json,
                description=description,
                is_default=is_default,
            )
            session.add(workflow)
            await session.commit()
            await session.refresh(workflow)
            return workflow

    async def get_default_workflow(self) -> Optional[Workflow]:
        """Get the default workflow."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.is_default == True)
            )
            return result.scalar_one_or_none()

    async def get_workflow(self, name: str) -> Optional[Workflow]:
        """Get a workflow by name."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.name == name)
            )
            return result.scalar_one_or_none()
