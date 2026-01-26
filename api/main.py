# api/main.py — FastAPI application

from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
import asyncpg
import logging
import os
import sys

sys.path.insert(0, '/root/DwoodAmo/dialectic')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import (
    Room, User, Thread, Message, Memory, Event, EventType,
    SpeakerType, MessageType, MemoryScope
)
from memory.manager import MemoryManager
from llm.orchestrator import LLMOrchestrator
from transport.websocket import ConnectionManager, InboundMessage
from transport.handlers import MessageHandler
from api.auth.routes import router as auth_router, set_db_pool as set_auth_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://localhost/dialectic"
)

db_pool: Optional[asyncpg.Pool] = None


async def get_db():
    """Dependency for database connection."""
    async with db_pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setup and teardown."""
    global db_pool

    logger.info("Connecting to database...")
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database connected")

        # Set db_pool for auth module
        set_auth_db_pool(db_pool)

        async with db_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        logger.warning("Running in demo mode without database")

    yield

    if db_pool:
        await db_pool.close()
        logger.info("Database disconnected")


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Dialectic",
    description="A persistent, forkable, memory-bearing dialogue engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

connection_manager = ConnectionManager()


# ============================================================
# AUTH
# ============================================================

async def verify_room_token(
    room_id: UUID,
    token: str,
    db,
) -> Room:
    """Verify room token and return room if valid."""
    row = await db.fetchrow(
        "SELECT * FROM rooms WHERE id = $1 AND token = $2",
        room_id, token
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid room token")
    return Room(**dict(row))


# ============================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================

class CreateRoomRequest(BaseModel):
    name: Optional[str] = None
    global_ontology: Optional[str] = None
    global_rules: Optional[str] = None


class CreateRoomResponse(BaseModel):
    id: UUID
    token: str
    name: Optional[str]


class CreateUserRequest(BaseModel):
    display_name: str
    style_modifier: Optional[str] = None
    aggression_level: float = 0.5
    metaphysics_tolerance: float = 0.5
    custom_instructions: Optional[str] = None


class JoinRoomRequest(BaseModel):
    user_id: UUID


class SendMessageRequest(BaseModel):
    content: str
    message_type: str = "text"
    references_message_id: Optional[UUID] = None


class ForkThreadRequest(BaseModel):
    source_thread_id: UUID
    fork_after_message_id: UUID
    title: Optional[str] = None


class AddMemoryRequest(BaseModel):
    key: str
    content: str
    scope: str = "room"


class EditMemoryRequest(BaseModel):
    content: str
    reason: Optional[str] = None


class MemoryResponse(BaseModel):
    id: UUID
    key: str
    content: str
    scope: str
    version: int
    created_by_user_id: UUID
    status: str


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    sequence: int
    created_at: datetime
    speaker_type: str
    user_id: Optional[UUID]
    message_type: str
    content: str


class ThreadResponse(BaseModel):
    id: UUID
    room_id: UUID
    parent_thread_id: Optional[UUID]
    title: Optional[str]
    message_count: int


class SearchResultResponse(BaseModel):
    """Full-text search result with highlighted snippet."""
    id: UUID
    thread_id: UUID
    content: str
    snippet: str  # With highlighted matches
    sender_name: str
    speaker_type: str
    created_at: datetime
    rank: float


class PaginatedMessagesResponse(BaseModel):
    """Paginated messages with cursor information."""
    messages: List[MessageResponse]
    has_more_before: bool
    has_more_after: bool
    oldest_sequence: Optional[int]
    newest_sequence: Optional[int]


# ============================================================
# REST ENDPOINTS
# ============================================================

@app.post("/rooms", response_model=CreateRoomResponse)
async def create_room(
    request: CreateRoomRequest,
    db=Depends(get_db),
):
    """Create a new room."""
    room_id = uuid4()
    token = uuid4().hex
    now = datetime.utcnow()

    await db.execute(
        """INSERT INTO rooms (id, created_at, token, name, global_ontology, global_rules)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        room_id, now, token, request.name, request.global_ontology, request.global_rules
    )

    thread_id = uuid4()
    await db.execute(
        """INSERT INTO threads (id, room_id, created_at, title)
           VALUES ($1, $2, $3, $4)""",
        thread_id, room_id, now, "Main"
    )

    await db.execute(
        """INSERT INTO events (id, timestamp, event_type, room_id, payload)
           VALUES ($1, $2, $3, $4, $5)""",
        uuid4(), now, EventType.ROOM_CREATED.value, room_id,
        {"name": request.name}
    )
    await db.execute(
        """INSERT INTO events (id, timestamp, event_type, room_id, thread_id, payload)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        uuid4(), now, EventType.THREAD_CREATED.value, room_id, thread_id,
        {"title": "Main"}
    )

    return CreateRoomResponse(id=room_id, token=token, name=request.name)


@app.post("/users")
async def create_user(
    request: CreateUserRequest,
    db=Depends(get_db),
):
    """Create a new user."""
    user_id = uuid4()
    now = datetime.utcnow()

    await db.execute(
        """INSERT INTO users
           (id, created_at, display_name, style_modifier,
            aggression_level, metaphysics_tolerance, custom_instructions)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        user_id, now, request.display_name, request.style_modifier,
        request.aggression_level, request.metaphysics_tolerance,
        request.custom_instructions
    )

    return {"id": user_id, "display_name": request.display_name}


@app.post("/rooms/{room_id}/join")
async def join_room(
    room_id: UUID,
    request: JoinRoomRequest,
    token: str = Query(...),
    db=Depends(get_db),
):
    """Join a room."""
    room_row = await db.fetchrow(
        "SELECT * FROM rooms WHERE id = $1 AND token = $2",
        room_id, token
    )
    if not room_row:
        raise HTTPException(status_code=401, detail="Invalid room token")

    existing = await db.fetchrow(
        "SELECT * FROM room_memberships WHERE room_id = $1 AND user_id = $2",
        room_id, request.user_id
    )
    if existing:
        return {"status": "already_member"}

    now = datetime.utcnow()

    await db.execute(
        """INSERT INTO room_memberships (room_id, user_id, joined_at)
           VALUES ($1, $2, $3)""",
        room_id, request.user_id, now
    )

    await db.execute(
        """INSERT INTO events (id, timestamp, event_type, room_id, user_id, payload)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        uuid4(), now, EventType.USER_JOINED_ROOM.value, room_id, request.user_id, {}
    )

    return {"status": "joined"}


@app.get("/rooms/{room_id}/threads")
async def list_threads(
    room_id: UUID,
    token: str = Query(...),
    db=Depends(get_db),
):
    """List all threads in a room."""
    await verify_room_token(room_id, token, db)

    rows = await db.fetch(
        """SELECT t.*,
                  (SELECT COUNT(*) FROM messages m WHERE m.thread_id = t.id) as message_count
           FROM threads t
           WHERE t.room_id = $1
           ORDER BY t.created_at""",
        room_id
    )

    return [ThreadResponse(
        id=row['id'],
        room_id=row['room_id'],
        parent_thread_id=row['parent_thread_id'],
        title=row['title'],
        message_count=row['message_count'],
    ) for row in rows]


@app.get("/threads/{thread_id}/messages", response_model=PaginatedMessagesResponse)
async def get_messages(
    thread_id: UUID,
    token: str = Query(...),
    include_ancestry: bool = True,
    limit: int = Query(50, ge=1, le=200, description="Max messages to return"),
    before_sequence: Optional[int] = Query(None, description="Return messages before this sequence"),
    after_sequence: Optional[int] = Query(None, description="Return messages after this sequence"),
    db=Depends(get_db),
):
    """
    Get messages in a thread with cursor-based pagination.

    ARCHITECTURE: Bidirectional cursor pagination using sequence numbers.
    WHY: Enables infinite scroll in both directions and precise positioning.
    TRADEOFF: Slightly more complex than offset pagination, but stable under mutations.
    """
    thread_row = await db.fetchrow(
        "SELECT * FROM threads WHERE id = $1", thread_id
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    await verify_room_token(thread_row['room_id'], token, db)

    if include_ancestry:
        from operations import get_thread_messages
        all_messages = await get_thread_messages(db, thread_id, include_ancestry=True)

        # Apply cursor filters
        if before_sequence is not None:
            all_messages = [m for m in all_messages if m.sequence < before_sequence]
            # Get most recent N (from end)
            messages = all_messages[-limit:]
        elif after_sequence is not None:
            all_messages = [m for m in all_messages if m.sequence > after_sequence]
            # Get oldest N (from start)
            messages = all_messages[:limit]
        else:
            # Default: most recent messages
            messages = all_messages[-limit:]

        # Calculate has_more flags
        if messages:
            oldest_seq = min(m.sequence for m in messages)
            newest_seq = max(m.sequence for m in messages)
            has_more_before = any(m.sequence < oldest_seq for m in all_messages)
            has_more_after = any(m.sequence > newest_seq for m in all_messages)
        else:
            oldest_seq = None
            newest_seq = None
            has_more_before = False
            has_more_after = False
    else:
        # Build query based on cursor direction
        if after_sequence is not None:
            query = """
                SELECT * FROM messages
                WHERE thread_id = $1 AND NOT is_deleted AND sequence > $2
                ORDER BY sequence ASC LIMIT $3
            """
            rows = await db.fetch(query, thread_id, after_sequence, limit)
            messages = [Message(**dict(row)) for row in rows]
        elif before_sequence is not None:
            query = """
                SELECT * FROM messages
                WHERE thread_id = $1 AND NOT is_deleted AND sequence < $2
                ORDER BY sequence DESC LIMIT $3
            """
            rows = await db.fetch(query, thread_id, before_sequence, limit)
            messages = [Message(**dict(row)) for row in reversed(rows)]
        else:
            # Default: most recent messages
            query = """
                SELECT * FROM messages
                WHERE thread_id = $1 AND NOT is_deleted
                ORDER BY sequence DESC LIMIT $2
            """
            rows = await db.fetch(query, thread_id, limit)
            messages = [Message(**dict(row)) for row in reversed(rows)]

        # Calculate has_more flags
        if messages:
            oldest_seq = min(m.sequence for m in messages)
            newest_seq = max(m.sequence for m in messages)

            has_more_before = await db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM messages WHERE thread_id = $1 AND NOT is_deleted AND sequence < $2)",
                thread_id, oldest_seq
            )
            has_more_after = await db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM messages WHERE thread_id = $1 AND NOT is_deleted AND sequence > $2)",
                thread_id, newest_seq
            )
        else:
            oldest_seq = None
            newest_seq = None
            has_more_before = False
            has_more_after = False

    message_responses = [MessageResponse(
        id=m.id,
        thread_id=m.thread_id,
        sequence=m.sequence,
        created_at=m.created_at,
        speaker_type=m.speaker_type.value if hasattr(m.speaker_type, 'value') else m.speaker_type,
        user_id=m.user_id,
        message_type=m.message_type.value if hasattr(m.message_type, 'value') else m.message_type,
        content=m.content,
    ) for m in messages]

    return PaginatedMessagesResponse(
        messages=message_responses,
        has_more_before=has_more_before,
        has_more_after=has_more_after,
        oldest_sequence=oldest_seq,
        newest_sequence=newest_seq,
    )


@app.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: UUID,
    request: SendMessageRequest,
    token: str = Query(...),
    user_id: UUID = Query(...),
    db=Depends(get_db),
):
    """Send a message (REST fallback for WebSocket)."""
    thread_row = await db.fetchrow(
        "SELECT * FROM threads WHERE id = $1", thread_id
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    room = await verify_room_token(thread_row['room_id'], token, db)

    max_seq = await db.fetchval(
        "SELECT COALESCE(MAX(sequence), 0) FROM messages WHERE thread_id = $1",
        thread_id
    )
    sequence = max_seq + 1
    now = datetime.utcnow()
    message_id = uuid4()

    await db.execute(
        """INSERT INTO messages
           (id, thread_id, sequence, created_at, speaker_type, user_id,
            message_type, content, references_message_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
        message_id, thread_id, sequence, now,
        SpeakerType.HUMAN.value, user_id, request.message_type,
        request.content, request.references_message_id
    )

    await db.execute(
        """INSERT INTO events (id, timestamp, event_type, room_id, thread_id, user_id, payload)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        uuid4(), now, EventType.MESSAGE_CREATED.value,
        room.id, thread_id, user_id,
        {"message_id": str(message_id), "content": request.content}
    )

    return MessageResponse(
        id=message_id,
        thread_id=thread_id,
        sequence=sequence,
        created_at=now,
        speaker_type=SpeakerType.HUMAN.value,
        user_id=user_id,
        message_type=request.message_type,
        content=request.content,
    )


@app.post("/threads/{thread_id}/fork")
async def fork_thread_endpoint(
    thread_id: UUID,
    request: ForkThreadRequest,
    token: str = Query(...),
    user_id: UUID = Query(...),
    db=Depends(get_db),
):
    """Fork a thread."""
    thread_row = await db.fetchrow(
        "SELECT * FROM threads WHERE id = $1", thread_id
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    room = await verify_room_token(thread_row['room_id'], token, db)

    from operations import fork_thread
    new_thread = await fork_thread(
        db,
        room_id=room.id,
        source_thread_id=request.source_thread_id,
        fork_after_message_id=request.fork_after_message_id,
        forking_user_id=user_id,
        title=request.title,
    )

    return ThreadResponse(
        id=new_thread.id,
        room_id=new_thread.room_id,
        parent_thread_id=new_thread.parent_thread_id,
        title=new_thread.title,
        message_count=0,
    )


@app.get("/rooms/{room_id}/memories")
async def list_memories(
    room_id: UUID,
    token: str = Query(...),
    include_invalidated: bool = False,
    db=Depends(get_db),
):
    """List all memories in a room."""
    await verify_room_token(room_id, token, db)

    memory_manager = MemoryManager(db)
    memories = await memory_manager.get_room_memories(room_id, include_invalidated)

    return [MemoryResponse(
        id=m.id,
        key=m.key,
        content=m.content,
        scope=m.scope.value if hasattr(m.scope, 'value') else m.scope,
        version=m.version,
        created_by_user_id=m.created_by_user_id,
        status=m.status.value if hasattr(m.status, 'value') else m.status,
    ) for m in memories]


@app.post("/rooms/{room_id}/memories")
async def add_memory(
    room_id: UUID,
    request: AddMemoryRequest,
    token: str = Query(...),
    user_id: UUID = Query(...),
    db=Depends(get_db),
):
    """Add a new memory."""
    await verify_room_token(room_id, token, db)

    memory_manager = MemoryManager(db)
    memory = await memory_manager.add_memory(
        room_id=room_id,
        key=request.key,
        content=request.content,
        created_by_user_id=user_id,
        scope=MemoryScope(request.scope),
    )

    return MemoryResponse(
        id=memory.id,
        key=memory.key,
        content=memory.content,
        scope=memory.scope.value,
        version=memory.version,
        created_by_user_id=memory.created_by_user_id,
        status=memory.status.value,
    )


@app.put("/memories/{memory_id}")
async def edit_memory(
    memory_id: UUID,
    request: EditMemoryRequest,
    token: str = Query(...),
    user_id: UUID = Query(...),
    db=Depends(get_db),
):
    """Edit a memory."""
    row = await db.fetchrow("SELECT room_id FROM memories WHERE id = $1", memory_id)
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    await verify_room_token(row['room_id'], token, db)

    memory_manager = MemoryManager(db)
    memory = await memory_manager.edit_memory(
        memory_id=memory_id,
        new_content=request.content,
        edited_by_user_id=user_id,
        edit_reason=request.reason,
    )

    return MemoryResponse(
        id=memory.id,
        key=memory.key,
        content=memory.content,
        scope=memory.scope.value if hasattr(memory.scope, 'value') else memory.scope,
        version=memory.version,
        created_by_user_id=memory.created_by_user_id,
        status=memory.status.value if hasattr(memory.status, 'value') else memory.status,
    )


@app.delete("/memories/{memory_id}")
async def invalidate_memory(
    memory_id: UUID,
    token: str = Query(...),
    user_id: UUID = Query(...),
    reason: Optional[str] = None,
    db=Depends(get_db),
):
    """Invalidate a memory."""
    row = await db.fetchrow("SELECT room_id FROM memories WHERE id = $1", memory_id)
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    await verify_room_token(row['room_id'], token, db)

    memory_manager = MemoryManager(db)
    await memory_manager.invalidate_memory(
        memory_id=memory_id,
        invalidated_by_user_id=user_id,
        reason=reason,
    )

    return {"status": "invalidated"}


@app.get("/rooms/{room_id}/memories/search")
async def search_memories(
    room_id: UUID,
    query: str,
    token: str = Query(...),
    limit: int = 10,
    db=Depends(get_db),
):
    """Semantic search over memories."""
    await verify_room_token(room_id, token, db)

    memory_manager = MemoryManager(db)
    matches = await memory_manager.search_memories(room_id, query, limit)

    return [{
        "memory_id": str(m.memory_id),
        "key": m.key,
        "content": m.content,
        "score": m.score,
    } for m in matches]


# ============================================================
# FULL-TEXT SEARCH ENDPOINTS
# ============================================================

@app.get("/messages/search", response_model=List[SearchResultResponse])
async def search_messages(
    q: str = Query(..., min_length=1, description="Search query"),
    thread_id: Optional[UUID] = Query(None, description="Filter by thread"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    speaker_type: Optional[str] = Query(None, description="Filter by speaker type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    token: str = Query(...),
    user_id: UUID = Query(...),
    db=Depends(get_db),
):
    """
    Full-text search over messages.

    ARCHITECTURE: Uses PostgreSQL tsvector with plainto_tsquery for search.
    WHY: Native FTS is fast, ranked, and supports stemming/normalization.
    TRADEOFF: Less flexible than Elasticsearch, but zero infrastructure overhead.
    """
    # Build query with room membership check
    query = """
        SELECT
            m.id,
            m.thread_id,
            m.content,
            ts_headline('english', m.content, plainto_tsquery('english', $1),
                'StartSel=<mark>, StopSel=</mark>, MaxWords=50, MinWords=20'
            ) as snippet,
            COALESCE(u.display_name, m.speaker_type) as sender_name,
            m.speaker_type,
            m.created_at,
            ts_rank(m.search_vector, plainto_tsquery('english', $1)) as rank
        FROM messages m
        JOIN threads t ON m.thread_id = t.id
        JOIN room_memberships rm ON t.room_id = rm.room_id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE rm.user_id = $2
          AND m.search_vector @@ plainto_tsquery('english', $1)
          AND NOT m.is_deleted
    """
    params = [q, user_id]
    param_idx = 3

    if thread_id:
        query += f" AND m.thread_id = ${param_idx}"
        params.append(thread_id)
        param_idx += 1

    if date_from:
        query += f" AND m.created_at >= ${param_idx}"
        params.append(date_from)
        param_idx += 1

    if date_to:
        query += f" AND m.created_at <= ${param_idx}"
        params.append(date_to)
        param_idx += 1

    if speaker_type:
        query += f" AND m.speaker_type = ${param_idx}"
        params.append(speaker_type)
        param_idx += 1

    query += f" ORDER BY rank DESC, m.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    rows = await db.fetch(query, *params)

    return [SearchResultResponse(
        id=row['id'],
        thread_id=row['thread_id'],
        content=row['content'],
        snippet=row['snippet'],
        sender_name=row['sender_name'],
        speaker_type=row['speaker_type'],
        created_at=row['created_at'],
        rank=float(row['rank']),
    ) for row in rows]


@app.get("/threads/{thread_id}/messages/context")
async def get_message_context(
    thread_id: UUID,
    message_id: UUID = Query(..., description="Target message ID"),
    context: int = Query(25, ge=1, le=100, description="Messages before/after"),
    token: str = Query(...),
    db=Depends(get_db),
):
    """
    Get messages around a target message for jump-to navigation.

    ARCHITECTURE: Uses sequence numbers for efficient range queries.
    WHY: Enables precise cursor positioning when jumping to search results.
    """
    # Verify thread exists and user has access
    thread_row = await db.fetchrow(
        "SELECT * FROM threads WHERE id = $1", thread_id
    )
    if not thread_row:
        raise HTTPException(status_code=404, detail="Thread not found")

    await verify_room_token(thread_row['room_id'], token, db)

    # Get target message sequence
    target = await db.fetchrow(
        "SELECT sequence FROM messages WHERE id = $1 AND thread_id = $2",
        message_id, thread_id
    )
    if not target:
        raise HTTPException(status_code=404, detail="Message not found in thread")

    target_sequence = target['sequence']

    # Get surrounding messages
    rows = await db.fetch(
        """
        SELECT * FROM messages
        WHERE thread_id = $1
          AND NOT is_deleted
          AND sequence BETWEEN $2 AND $3
        ORDER BY sequence ASC
        """,
        thread_id,
        max(1, target_sequence - context),
        target_sequence + context,
    )

    messages = [Message(**dict(row)) for row in rows]

    return [MessageResponse(
        id=m.id,
        thread_id=m.thread_id,
        sequence=m.sequence,
        created_at=m.created_at,
        speaker_type=m.speaker_type.value if hasattr(m.speaker_type, 'value') else m.speaker_type,
        user_id=m.user_id,
        message_type=m.message_type.value if hasattr(m.message_type, 'value') else m.message_type,
        content=m.content,
    ) for m in messages]


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: UUID,
    token: str = Query(...),
    user_id: UUID = Query(...),
    thread_id: Optional[UUID] = Query(None),
):
    """WebSocket connection for real-time messaging."""

    async with db_pool.acquire() as db:
        room_row = await db.fetchrow(
            "SELECT * FROM rooms WHERE id = $1 AND token = $2",
            room_id, token
        )
        if not room_row:
            await websocket.close(code=4001, reason="Invalid room token")
            return

        membership = await db.fetchrow(
            "SELECT * FROM room_memberships WHERE room_id = $1 AND user_id = $2",
            room_id, user_id
        )
        if not membership:
            await websocket.close(code=4002, reason="Not a room member")
            return

    conn = await connection_manager.connect(
        websocket=websocket,
        user_id=user_id,
        room_id=room_id,
        thread_id=thread_id,
    )

    try:
        while True:
            data = await websocket.receive_text()
            message = InboundMessage.from_json(data)

            async with db_pool.acquire() as db:
                memory_manager = MemoryManager(db)
                llm_orchestrator = LLMOrchestrator(db)
                handler = MessageHandler(
                    db=db,
                    connection_manager=connection_manager,
                    memory_manager=memory_manager,
                    llm_orchestrator=llm_orchestrator,
                )
                await handler.handle(conn, message)

    except WebSocketDisconnect:
        await connection_manager.disconnect(conn)
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        await connection_manager.disconnect(conn)


# ============================================================
# OBSERVABILITY
# ============================================================

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/rooms/{room_id}/events")
async def get_events(
    room_id: UUID,
    token: str = Query(...),
    limit: int = 100,
    after_sequence: Optional[int] = None,
    event_types: Optional[str] = None,
    db=Depends(get_db),
):
    """Get event log for a room."""
    await verify_room_token(room_id, token, db)

    query = "SELECT * FROM events WHERE room_id = $1"
    params = [room_id]

    if after_sequence:
        query += f" AND sequence > ${len(params) + 1}"
        params.append(after_sequence)

    if event_types:
        types = event_types.split(",")
        query += f" AND event_type = ANY(${len(params) + 1})"
        params.append(types)

    query += f" ORDER BY sequence LIMIT ${len(params) + 1}"
    params.append(limit)

    rows = await db.fetch(query, *params)

    return [{
        "id": str(row['id']),
        "sequence": row['sequence'],
        "timestamp": row['timestamp'].isoformat(),
        "event_type": row['event_type'],
        "user_id": str(row['user_id']) if row['user_id'] else None,
        "payload": row['payload'],
    } for row in rows]
