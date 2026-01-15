import aiohttp
import logging
from typing import Optional, Dict, List, Any
import json
import uuid

logger = logging.getLogger(__name__)

class ComfyUIClient:
    """Async Client for interacting with ComfyUI REST API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def check_status(self) -> bool:
        """Check if ComfyUI server is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/system_stats") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"Failed to connect to ComfyUI: {e}")
            return False

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/system_stats") as response:
            response.raise_for_status()
            return await response.json()

    async def get_queue(self) -> Dict[str, Any]:
        """Get current queue status."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/queue") as response:
            response.raise_for_status()
            return await response.json()

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Get history for a specific prompt ID."""
        session = await self._get_session()
        async with session.get(f"{self.base_url}/history/{prompt_id}") as response:
            response.raise_for_status()
            return await response.json()

    async def queue_prompt(self, workflow: Dict[str, Any], client_id: str) -> Dict[str, Any]:
        """
        Queue a workflow for generation.
        
        Args:
            workflow: The workflow JSON object (API format)
            client_id: Unique client ID for WebSocket correlation
        """
        session = await self._get_session()
        payload = {
            "prompt": workflow,
            "client_id": client_id
        }
        async with session.post(f"{self.base_url}/prompt", json=payload) as response:
            response.raise_for_status()
            return await response.json()

    async def interrupt(self):
        """Interrupt currently executing prompt."""
        session = await self._get_session()
        async with session.post(f"{self.base_url}/interrupt") as response:
            try:
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to interrupt: {e}")

    async def delete_queue_item(self, prompt_id: str):
        """Remove an item from queue."""
        session = await self._get_session()
        payload = {"delete": [prompt_id]}
        async with session.post(f"{self.base_url}/queue", json=payload) as response:
            response.raise_for_status()

    async def get_image(self, filename: str, subfolder: str = "", type: str = "output") -> bytes:
        """Fetch a generated image."""
        session = await self._get_session()
        params = {"filename": filename, "subfolder": subfolder, "type": type}
        async with session.get(f"{self.base_url}/view", params=params) as response:
            response.raise_for_status()
            return await response.read()

    async def upload_image(self, image_data: bytes, filename: str, subfolder: str = ""):
        """Upload an image to ComfyUI (input folder)."""
        session = await self._get_session()
        data = aiohttp.FormData()
        data.add_field("image", image_data, filename=filename)
        if subfolder:
            data.add_field("subfolder", subfolder)
            
        async with session.post(f"{self.base_url}/upload/image", data=data) as response:
             response.raise_for_status()
             return await response.json()
