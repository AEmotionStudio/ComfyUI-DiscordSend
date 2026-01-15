import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any

from ..database.repository import Repository
from ..database.models import JobStatus, Job
from ..comfyui.client import ComfyUIClient
from ..comfyui.websocket import ComfyUIWebSocket
from .delivery import DeliveryService

logger = logging.getLogger(__name__)

class JobManager:
    """Manages the lifecycle of generation jobs."""

    def __init__(self, repository: Repository, comfy_client: ComfyUIClient, comfy_ws: ComfyUIWebSocket, delivery_service: DeliveryService):
        self.repo = repository
        self.client = comfy_client
        self.ws = comfy_ws
        self.delivery = delivery_service
        self.client_id = str(uuid.uuid4())
        
        # In-memory mapping of prompt_id -> current status buffer
        self._active_jobs = {} 
        self._delivery_tasks = {} # prompt_id -> asyncio.Task 

    async def start(self):
        """Start listening to WebSocket events."""
        self.ws.add_listener("status", self._on_status)
        self.ws.add_listener("execution_start", self._on_execution_start)
        self.ws.add_listener("executing", self._on_executing)
        self.ws.add_listener("executed", self._on_executed)
        self.ws.add_listener("execution_error", self._on_execution_error)
        self.ws.add_listener("progress", self._on_progress)
        logger.info(f"JobManager started with client_id: {self.client_id}")

    async def create_job(self, 
                         user_discord_id: str, 
                         workflow: Dict[str, Any],
                         positive_prompt: str,
                         negative_prompt: str = "",
                         parameters: Optional[Dict] = None,
                         server_discord_id: Optional[str] = None, 
                         channel_id: Optional[str] = None,
                         delivery_type: str = "channel") -> Job:
        """Submit a job to ComfyUI and database."""
        
        # 0. Validate and ensure entities exist
        user = await self.repo.get_or_create_user(user_discord_id, "Unknown")
        
        # Check queue limit
        current_queue_count = await self.repo.count_user_pending_jobs(user_discord_id, server_discord_id)
        
        # Get server specific limit or default
        max_queue = 3
        if server_discord_id:
            server = await self.repo.get_server(server_discord_id)
            if server:
                max_queue = server.max_queue_per_user
                
        if current_queue_count >= max_queue:
            raise ValueError(f"Queue limit reached ({max_queue} jobs). Please wait for your current jobs to finish.")

        # 1. Submit to ComfyUI
        response = await self.client.queue_prompt(workflow, self.client_id)
        prompt_id = response.get("prompt_id")
        
        if not prompt_id:
            raise ValueError("Failed to get prompt_id from ComfyUI")

        # 2. Create DB entry
        job = await self.repo.create_job(
            prompt_id=prompt_id,
            user_discord_id=user_discord_id,
            server_discord_id=server_discord_id,
            channel_id=channel_id,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            parameters=parameters,
            workflow_json=json.dumps(workflow),
            delivery_type=delivery_type
        )
        
        logger.info(f"Created job {job.id} (prompt_id: {prompt_id}) for user {user_discord_id}")
        return job

    async def cancel_job(self, job_id: int) -> bool:
        """Cancel a job."""
        job = await self.repo.get_job_by_id(job_id)
        if not job:
            return False
            
        if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
            return False

        if job.status == JobStatus.RUNNING.value:
            await self.client.interrupt()
        
        # Remove from queue if pending
        try:
             await self.client.delete_queue_item(job.prompt_id)
        except:
             pass 

        await self.repo.update_job_status(job.prompt_id, JobStatus.CANCELLED.value)
        return True

    async def _schedule_delivery(self, job: Job):
        """Schedule a debounced delivery for a job."""
        prompt_id = job.prompt_id
        
        # Cancel existing timer if any
        if prompt_id in self._delivery_tasks:
            self._delivery_tasks[prompt_id].cancel()
            
        # Create new timer
        task = asyncio.create_task(self._deliver_delayed(job))
        self._delivery_tasks[prompt_id] = task
        
        # Cleanup callback
        def cleanup(t):
            if prompt_id in self._delivery_tasks and self._delivery_tasks[prompt_id] == t:
                self._delivery_tasks.pop(prompt_id, None)
                
        task.add_done_callback(cleanup)

    async def _deliver_delayed(self, job: Job):
        """Wait briefly then deliver the job."""
        try:
            await asyncio.sleep(1.0) # Debounce window
            logger.info(f"Job {job.id} delivery timer expired. Delivering results...")
            await self.delivery.deliver_job(job)
        except asyncio.CancelledError:
            logger.debug(f"Job {job.id} delivery debounced/cancelled.")
        except Exception as e:
            logger.error(f"Error in delayed delivery for job {job.id}: {e}")

    # -- WebSocket Event Handlers --

    async def _on_status(self, data: Dict[str, Any]):
        pass

    async def _on_execution_start(self, data: Dict[str, Any]):
        prompt_id = data.get("data", {}).get("prompt_id")
        if prompt_id:
            await self.repo.update_job_status(prompt_id, JobStatus.RUNNING.value)

    async def _on_executing(self, data: Dict[str, Any]):
        pass

    async def _on_progress(self, data: Dict[str, Any]):
        msg = data.get("data", {})
        prompt_id = msg.get("prompt_id")
        value = msg.get("value")
        max_val = msg.get("max")
        
        if prompt_id and value is not None and max_val is not None:
            await self.repo.update_job_progress(prompt_id, value, max_val)

    async def _on_executed(self, data: Dict[str, Any]):
        """
        Handle execution completion of a node.
        If it contains images, we assume it's a relevant output.
        We accumulate images and update job status.
        """
        msg = data.get("data", {})
        prompt_id = msg.get("prompt_id")
        output = msg.get("output", {})
        
        if prompt_id and "images" in output:
            # Found images
            images = output["images"]
            
            # Update DB with images and mark as completed
            # NOTE: In complex workflows, there might be multiple outputs.
            # Ideally we check if this is the last one or something.
            # But normally 'executed' with images means we got something.
            # We'll mark as completed for now. If multiple exist, latest wins.
            
            job = await self.repo.update_job_status(
                prompt_id, 
                JobStatus.COMPLETED.value, 
                output_images=images
            )
            
            if job:
                logger.info(f"Job {job.id} update received. Scheduling delivery...")
                await self._schedule_delivery(job)

    async def _on_execution_error(self, data: Dict[str, Any]):
        msg = data.get("data", {})
        prompt_id = msg.get("prompt_id")
        exception_type = msg.get("exception_type", "Unknown Error")
        exception_message = msg.get("exception_message", "")
        
        if prompt_id:
            error_msg = f"{exception_type}: {exception_message}"
            job = await self.repo.update_job_status(prompt_id, JobStatus.FAILED.value, error_message=error_msg)
            # Notify user of failure via delivery service? 
            # Ideally yes, but DeliveryService currently only sends images.
            # We might want to expand DeliveryService to handle errors too, or reuse the channel_id to post the failure embed.
            pass
