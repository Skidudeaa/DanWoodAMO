# transport/handlers.py — WebSocket message handlers

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
import logging
import sys
sys.path.insert(0, '/root/DwoodAmo/dialectic')

from models import (
    Room, User, Thread, Message, Memory, Event, EventType,
    SpeakerType, MessageType, MessageCreatedPayload
)
from memory.manager import MemoryManager
from llm.orchestrator import LLMOrchestrator
from .websocket import (
    ConnectionManager, Connection, InboundMessage, OutboundMessage, MessageTypes
)

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    ARCHITECTURE: Dispatches inbound WebSocket messages to appropriate handlers.
    WHY: Clean separation between transport and business logic.
    """

    def __init__(
        self,
        db,
        connection_manager: ConnectionManager,
        memory_manager: MemoryManager,
        llm_orchestrator: LLMOrchestrator,
    ):
        self.db = db
        self.connections = connection_manager
        self.memory = memory_manager
        self.llm = llm_orchestrator

    async def handle(self, conn: Connection, message: InboundMessage) -> None:
        """Route message to appropriate handler."""

        handlers = {
            MessageTypes.SEND_MESSAGE: self._handle_send_message,
            MessageTypes.TYPING_START: self._handle_typing,
            MessageTypes.TYPING_STOP: self._handle_typing,
            MessageTypes.FORK_THREAD: self._handle_fork_thread,
            MessageTypes.SWITCH_THREAD: self._handle_switch_thread,
            MessageTypes.ADD_MEMORY: self._handle_add_memory,
            MessageTypes.EDIT_MEMORY: self._handle_edit_memory,
            MessageTypes.INVALIDATE_MEMORY: self._handle_invalidate_memory,
            MessageTypes.PING: self._handle_ping,
        }

        handler = handlers.get(message.type)
        if handler:
            try:
                await handler(conn, message.payload)
            except Exception as e:
                logger.exception(f"Handler error for {message.type}")
                await self._send_error(conn, str(e))
        else:
            logger.warning(f"Unknown message type: {message.type}")
            await self._send_error(conn, f"Unknown message type: {message.type}")

    async def _handle_send_message(self, conn: Connection, payload: dict) -> None:
        """Handle new message from user."""

        content = payload.get("content", "").strip()
        if not content:
            return

        message_type = MessageType(payload.get("type", "text"))
        references_message_id = payload.get("references_message_id")

        thread_id = conn.thread_id
        if not thread_id:
            row = await self.db.fetchrow(
                """SELECT id FROM threads
                   WHERE room_id = $1 AND parent_thread_id IS NULL
                   ORDER BY created_at LIMIT 1""",
                conn.room_id
            )
            thread_id = row['id'] if row else None

        if not thread_id:
            await self._send_error(conn, "No active thread")
            return

        max_seq = await self.db.fetchval(
            "SELECT COALESCE(MAX(sequence), 0) FROM messages WHERE thread_id = $1",
            thread_id
        )
        sequence = max_seq + 1
        now = datetime.utcnow()
        message_id = uuid4()

        message = Message(
            id=message_id,
            thread_id=thread_id,
            sequence=sequence,
            created_at=now,
            speaker_type=SpeakerType.HUMAN,
            user_id=conn.user_id,
            message_type=message_type,
            content=content,
            references_message_id=UUID(references_message_id) if references_message_id else None,
        )

        event = Event(
            id=uuid4(),
            timestamp=now,
            event_type=EventType.MESSAGE_CREATED,
            room_id=conn.room_id,
            thread_id=thread_id,
            user_id=conn.user_id,
            payload=MessageCreatedPayload(
                message_id=message_id,
                sequence=sequence,
                speaker_type=SpeakerType.HUMAN,
                user_id=conn.user_id,
                message_type=message_type,
                content=content,
                references_message_id=message.references_message_id,
            ).model_dump()
        )

        await self.db.execute(
            """INSERT INTO events (id, timestamp, event_type, room_id, thread_id, user_id, payload)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            event.id, event.timestamp, event.event_type.value,
            event.room_id, event.thread_id, event.user_id, event.payload
        )

        await self.db.execute(
            """INSERT INTO messages
               (id, thread_id, sequence, created_at, speaker_type, user_id,
                message_type, content, references_message_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            message.id, message.thread_id, message.sequence, message.created_at,
            message.speaker_type.value, message.user_id, message.message_type.value,
            message.content, message.references_message_id
        )

        user_row = await self.db.fetchrow(
            "SELECT display_name FROM users WHERE id = $1", conn.user_id
        )

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.MESSAGE_CREATED,
            payload={
                "id": str(message.id),
                "thread_id": str(message.thread_id),
                "sequence": message.sequence,
                "created_at": message.created_at.isoformat(),
                "speaker_type": message.speaker_type.value,
                "user_id": str(message.user_id),
                "user_name": user_row['display_name'] if user_row else "Unknown",
                "message_type": message.message_type.value,
                "content": message.content,
            }
        ))

        mentioned = "@llm" in content.lower()

        try:
            novelty = await self.memory.compute_message_novelty(conn.room_id, content)
        except Exception:
            novelty = 0.5

        await self._trigger_llm(conn.room_id, thread_id, mentioned, novelty)

    async def _trigger_llm(
        self,
        room_id: UUID,
        thread_id: UUID,
        mentioned: bool,
        semantic_novelty: float,
    ) -> None:
        """Invoke LLM orchestrator and broadcast response."""

        await self.connections.broadcast(room_id, OutboundMessage(
            type=MessageTypes.LLM_THINKING,
            payload={"thread_id": str(thread_id)},
        ))

        room_row = await self.db.fetchrow("SELECT * FROM rooms WHERE id = $1", room_id)
        room = Room(**dict(room_row))

        thread_row = await self.db.fetchrow("SELECT * FROM threads WHERE id = $1", thread_id)
        thread = Thread(**dict(thread_row))

        user_rows = await self.db.fetch(
            """SELECT u.* FROM users u
               JOIN room_memberships rm ON u.id = rm.user_id
               WHERE rm.room_id = $1""",
            room_id
        )
        users = [User(**dict(row)) for row in user_rows]

        from operations import get_thread_messages
        messages = await get_thread_messages(self.db, thread_id, include_ancestry=True)

        memories = await self.memory.get_context_for_prompt(room_id)

        result = await self.llm.on_message(
            room=room,
            thread=thread,
            users=users,
            messages=messages,
            memories=memories,
            mentioned=mentioned,
            semantic_novelty=semantic_novelty,
        )

        if result.triggered and result.response:
            await self.connections.broadcast(room_id, OutboundMessage(
                type=MessageTypes.MESSAGE_CREATED,
                payload={
                    "id": str(result.response.id),
                    "thread_id": str(result.response.thread_id),
                    "sequence": result.response.sequence,
                    "created_at": result.response.created_at.isoformat(),
                    "speaker_type": result.response.speaker_type.value,
                    "user_id": None,
                    "user_name": "Claude" if "primary" in result.response.speaker_type.value else "Provoker",
                    "message_type": result.response.message_type.value,
                    "content": result.response.content,
                    "model_used": result.response.model_used,
                },
            ))

    async def _handle_typing(self, conn: Connection, payload: dict) -> None:
        """Broadcast typing indicator."""
        is_typing = payload.get("typing", False)

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.USER_TYPING,
            payload={
                "user_id": str(conn.user_id),
                "typing": is_typing,
            },
        ), exclude_user=conn.user_id)

    async def _handle_fork_thread(self, conn: Connection, payload: dict) -> None:
        """Create a new thread forking from current."""

        source_thread_id = UUID(payload["source_thread_id"])
        fork_after_message_id = UUID(payload["fork_after_message_id"])
        title = payload.get("title")

        from operations import fork_thread
        new_thread = await fork_thread(
            self.db,
            room_id=conn.room_id,
            source_thread_id=source_thread_id,
            fork_after_message_id=fork_after_message_id,
            forking_user_id=conn.user_id,
            title=title,
        )

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.THREAD_CREATED,
            payload={
                "id": str(new_thread.id),
                "parent_thread_id": str(new_thread.parent_thread_id),
                "fork_point_message_id": str(new_thread.fork_point_message_id),
                "title": new_thread.title,
            },
        ))

    async def _handle_switch_thread(self, conn: Connection, payload: dict) -> None:
        """Switch user's active thread."""
        thread_id = UUID(payload["thread_id"])
        conn.thread_id = thread_id
        logger.info(f"User {conn.user_id} switched to thread {thread_id}")

    async def _handle_add_memory(self, conn: Connection, payload: dict) -> None:
        """Add a new memory."""
        memory = await self.memory.add_memory(
            room_id=conn.room_id,
            key=payload["key"],
            content=payload["content"],
            created_by_user_id=conn.user_id,
        )

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.MEMORY_UPDATED,
            payload={
                "action": "added",
                "memory_id": str(memory.id),
                "key": memory.key,
                "content": memory.content,
            },
        ))

    async def _handle_edit_memory(self, conn: Connection, payload: dict) -> None:
        """Edit existing memory."""
        memory = await self.memory.edit_memory(
            memory_id=UUID(payload["memory_id"]),
            new_content=payload["content"],
            edited_by_user_id=conn.user_id,
        )

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.MEMORY_UPDATED,
            payload={
                "action": "edited",
                "memory_id": str(memory.id),
                "key": memory.key,
                "content": memory.content,
                "version": memory.version,
            },
        ))

    async def _handle_invalidate_memory(self, conn: Connection, payload: dict) -> None:
        """Invalidate a memory."""
        memory = await self.memory.invalidate_memory(
            memory_id=UUID(payload["memory_id"]),
            invalidated_by_user_id=conn.user_id,
            reason=payload.get("reason"),
        )

        await self.connections.broadcast(conn.room_id, OutboundMessage(
            type=MessageTypes.MEMORY_UPDATED,
            payload={
                "action": "invalidated",
                "memory_id": str(memory.id),
            },
        ))

    async def _handle_ping(self, conn: Connection, payload: dict) -> None:
        """Respond to ping."""
        await self.connections.send_to_user(conn.user_id, conn.room_id, OutboundMessage(
            type=MessageTypes.PONG,
            payload={"timestamp": datetime.utcnow().isoformat()},
        ))

    async def _send_error(self, conn: Connection, error: str) -> None:
        """Send error to client."""
        await self.connections.send_to_user(conn.user_id, conn.room_id, OutboundMessage(
            type=MessageTypes.ERROR,
            payload={"error": error},
        ))
