# models.py — Core data model + event sourcing foundation

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class MessageType(str, Enum):
    TEXT = "text"
    CLAIM = "claim"
    QUESTION = "question"
    DEFINITION = "definition"
    COUNTEREXAMPLE = "counterexample"
    MEMORY_WRITE = "memory_write"
    SYSTEM = "system"


class SpeakerType(str, Enum):
    HUMAN = "human"
    LLM_PRIMARY = "llm_primary"
    LLM_PROVOKER = "llm_provoker"
    SYSTEM = "system"


class EventType(str, Enum):
    ROOM_CREATED = "room_created"
    ROOM_SETTINGS_UPDATED = "room_settings_updated"
    THREAD_CREATED = "thread_created"
    THREAD_FORKED = "thread_forked"
    MESSAGE_CREATED = "message_created"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_DELETED = "message_deleted"
    MEMORY_ADDED = "memory_added"
    MEMORY_EDITED = "memory_edited"
    MEMORY_INVALIDATED = "memory_invalidated"
    USER_JOINED_ROOM = "user_joined"
    USER_MODIFIER_UPDATED = "user_modifier_updated"


class MemoryScope(str, Enum):
    ROOM = "room"
    USER = "user"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"


# ============================================================
# CORE ENTITIES
# ============================================================

class Room(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    token: str
    name: Optional[str] = None
    global_ontology: Optional[str] = None
    global_rules: Optional[str] = None
    primary_provider: str = "anthropic"
    fallback_provider: str = "openai"
    primary_model: str = "claude-sonnet-4-20250514"
    provoker_model: str = "claude-haiku-4-20250514"
    auto_interjection_enabled: bool = True
    interjection_turn_threshold: int = 4
    semantic_novelty_threshold: float = 0.7


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    display_name: str
    style_modifier: Optional[str] = None
    aggression_level: float = 0.5
    metaphysics_tolerance: float = 0.5
    custom_instructions: Optional[str] = None


class RoomMembership(BaseModel):
    room_id: UUID
    user_id: UUID
    joined_at: datetime


class Thread(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    room_id: UUID
    created_at: datetime
    parent_thread_id: Optional[UUID] = None
    fork_point_message_id: Optional[UUID] = None
    fork_memory_version: Optional[int] = None
    title: Optional[str] = None


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    thread_id: UUID
    sequence: int
    created_at: datetime
    speaker_type: SpeakerType
    user_id: Optional[UUID] = None
    message_type: MessageType
    content: str
    references_message_id: Optional[UUID] = None
    references_memory_id: Optional[UUID] = None
    model_used: Optional[str] = None
    prompt_hash: Optional[str] = None
    token_count: Optional[int] = None
    is_deleted: bool = False


class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    room_id: UUID
    created_at: datetime
    updated_at: datetime
    version: int = 1
    scope: MemoryScope
    owner_user_id: Optional[UUID] = None
    key: str
    content: str
    source_message_id: Optional[UUID] = None
    created_by_user_id: UUID
    status: MemoryStatus = MemoryStatus.ACTIVE
    invalidated_by_user_id: Optional[UUID] = None
    invalidated_at: Optional[datetime] = None
    invalidation_reason: Optional[str] = None
    embedding: Optional[list[float]] = None


class Event(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    sequence: Optional[int] = None
    timestamp: datetime
    event_type: EventType
    room_id: Optional[UUID] = None
    thread_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    payload: dict


# ============================================================
# PAYLOAD SCHEMAS
# ============================================================

class ThreadForkedPayload(BaseModel):
    new_thread_id: UUID
    parent_thread_id: UUID
    fork_point_message_id: UUID
    fork_memory_version: int
    title: Optional[str] = None


class MessageCreatedPayload(BaseModel):
    message_id: UUID
    sequence: int
    speaker_type: SpeakerType
    user_id: Optional[UUID]
    message_type: MessageType
    content: str
    references_message_id: Optional[UUID] = None
    model_used: Optional[str] = None
    prompt_hash: Optional[str] = None
    token_count: Optional[int] = None


class MemoryAddedPayload(BaseModel):
    memory_id: UUID
    scope: MemoryScope
    owner_user_id: Optional[UUID]
    key: str
    content: str
    source_message_id: Optional[UUID]


class MemoryEditedPayload(BaseModel):
    memory_id: UUID
    previous_version: int
    new_version: int
    previous_content: str
    new_content: str
    edit_reason: Optional[str] = None


class MemoryInvalidatedPayload(BaseModel):
    memory_id: UUID
    reason: Optional[str] = None
