import aiohttp
import logging
import json
import asyncio
from typing import Callable, Coroutine, Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ComfyUIWebSocket:
    """WebSocket Client for real-time ComfyUI events."""

    def __init__(self, base_url: str = "ws://127.0.0.1:8188", client_id: str = ""):
        # Convert http/https to ws/wss if needed
        if base_url.startswith("http://"):
            base_url = base_url.replace("http://", "ws://")
        elif base_url.startswith("https://"):
            base_url = base_url.replace("https://", "wss://")
            
        self.ws_url = f"{base_url.rstrip('/')}/ws"
        if client_id:
            self.ws_url += f"?clientId={client_id}"
            
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]]] = {}
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Connect to the WebSocket."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        
        try:
            self.ws = await self.session.ws_connect(self.ws_url)
            self._running = True
            self._listen_task = asyncio.create_task(self._listen())
            logger.info(f"Connected to ComfyUI WebSocket at {self.ws_url}")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            if self.session and not self.session.closed:
                await self.session.close()
            raise

    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        if self._listen_task:
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

    def add_listener(self, event_type: str, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        """Register a callback for an event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    async def _listen(self):
        """Listen loop for incoming messages."""
        if not self.ws:
            return

        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        event_type = data.get("type", "unknown")
                        # Some messages pack content in 'data', others at top level
                        # ComfyUI typically sends {type: "event_name", data: {...}, sid: "..."}
                        
                        handlers = self._callbacks.get(event_type, [])
                        for handler in handlers:
                            try:
                                await handler(data)
                            except Exception as e:
                                logger.error(f"Error in WebSocket handler for {event_type}: {e}")
                                
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket connection closed with error")
                    break
        except Exception as e:
             if self._running:
                 logger.error(f"WebSocket listener error: {e}")
                 # Verify reconnection logic would handle this or let job manager handle it
        finally:
             if self._running:
                 logger.info("WebSocket listener stopped unexpectedly.")
