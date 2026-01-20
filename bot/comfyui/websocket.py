import aiohttp
import logging
import json
import asyncio
import random
from typing import Callable, Coroutine, Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Reconnection constants
INITIAL_BACKOFF = 1.0       # Initial delay in seconds
MAX_BACKOFF = 60.0          # Maximum delay cap
BACKOFF_MULTIPLIER = 2      # Exponential multiplier
JITTER_FACTOR = 0.1         # +/- 10% randomization

class ComfyUIWebSocket:
    """WebSocket Client for real-time ComfyUI events."""

    def __init__(self, base_url: str = "ws://127.0.0.1:8188", client_id: str = ""):
        # Convert http/https to ws/wss if needed
        if base_url.startswith("http://"):
            base_url = base_url.replace("http://", "ws://")
        elif base_url.startswith("https://"):
            base_url = base_url.replace("https://", "wss://")
            
        self.ws_url = f"{base_url.rstrip('/')}/ws"
        self.client_id = client_id
        if client_id:
            self.ws_url += f"?clientId={client_id}"
            
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]]] = {}
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None

        # Reconnection state
        self._reconnect_attempts = 0
        self._should_reconnect = True
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Lock to prevent race conditions between connect() and disconnect()
        self._state_lock = asyncio.Lock()

    async def connect(self):
        """Connect to the WebSocket."""
        async with self._state_lock:
            # Check if disconnect was called - don't proceed if so
            if not self._should_reconnect:
                logger.info("Connect aborted: disconnect was requested")
                return
                
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

            try:
                self.ws = await self.session.ws_connect(self.ws_url)
                # Re-check after await in case disconnect() was called during connection
                if not self._should_reconnect:
                    logger.info("Connect aborted after ws_connect: disconnect was requested")
                    if self.ws and not self.ws.closed:
                        await self.ws.close()
                    if self.session and not self.session.closed:
                        await self.session.close()
                    return
                self._running = True
                self._reconnect_attempts = 0  # Reset on successful connection
                self._listen_task = asyncio.create_task(self._listen())
                logger.info(f"Connected to ComfyUI WebSocket at {self.ws_url}")
            except Exception as e:
                logger.error(f"Failed to connect to WebSocket: {e}")
                if self.session and not self.session.closed:
                    await self.session.close()
                raise

    async def disconnect(self):
        """Disconnect from WebSocket."""
        async with self._state_lock:
            self._should_reconnect = False  # Prevent reconnection loop
            self._running = False

        # Cancel reconnection task if running (outside lock to avoid deadlock)
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

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
        finally:
            if self._running and self._should_reconnect:
                logger.warning("WebSocket connection lost. Starting reconnection...")
                self._reconnect_task = asyncio.create_task(self._handle_disconnect())

    def _calculate_backoff(self) -> float:
        """Calculate backoff delay with exponential growth and jitter."""
        delay = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** self._reconnect_attempts)
        delay = min(delay, MAX_BACKOFF)
        # Add jitter: +/- JITTER_FACTOR
        jitter = delay * JITTER_FACTOR * (2 * random.random() - 1)
        return delay + jitter

    async def _handle_disconnect(self) -> None:
        """Handle unexpected disconnection by attempting to reconnect."""
        self._running = False

        # Close existing connections
        if self.ws and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception:
                pass
        self.session = None
        self.ws = None

        await self._reconnect_loop()

    async def _reconnect_loop(self) -> None:
        """Background task that handles reconnection with exponential backoff."""
        while self._should_reconnect:
            self._reconnect_attempts += 1
            backoff = self._calculate_backoff()

            logger.info(
                f"Reconnection attempt {self._reconnect_attempts} "
                f"in {backoff:.1f}s..."
            )
            await asyncio.sleep(backoff)

            if not self._should_reconnect:
                logger.info("Reconnection cancelled.")
                return

            try:
                await self.connect()
                logger.info(
                    f"Successfully reconnected after "
                    f"{self._reconnect_attempts} attempt(s)."
                )
                return
            except Exception as e:
                logger.warning(f"Reconnection attempt failed: {e}")

        logger.info("Reconnection loop ended (should_reconnect=False).")
