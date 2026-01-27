# Dialectic Workroom MVP - TODO List

> Generated from parallel deep-dive analysis (12 specialized agents)
> Date: January 2026

---

## 🔴 CRITICAL Priority

### Security & Data Integrity

- [ ] **Fix wildcard CORS configuration**
  - File: `api/main.py:91-97`
  - Risk: Any site can make authenticated requests (CSRF)
  - Fix: Replace `allow_origins=["*"]` with explicit origins from env var

- [ ] **Fix message sequence race condition**
  - File: `api/main.py:709-713`
  - Risk: Concurrent messages get duplicate sequence numbers
  - Fix: Use atomic INSERT with subquery for sequence generation

- [ ] **Move tokens from URL to WebSocket auth message**
  - File: `api/main.py:1072-1074`
  - Risk: Tokens logged in server logs, browser history, referrer headers
  - Fix: Accept connection first, then validate credentials in first message

---

## 🟠 HIGH Priority

### Security

- [ ] **Add rate limiting to auth endpoints**
  - File: `api/main.py`
  - Endpoints: `/auth/login`, `/auth/signup`, `/rooms`
  - Fix: Add slowapi or custom limiter (5/min for login)

### Performance

- [ ] **Replace recursive ancestry query with CTE**
  - File: `api/main.py:597-599`
  - Issue: `get_thread_messages()` recursively fetches parent threads one by one
  - Fix: Single recursive CTE query

- [ ] **Throttle streaming DOM updates**
  - File: `frontend/index.html` - `updateStreamingMessage()`
  - Issue: Every token triggers immediate DOM manipulation
  - Fix: Use requestAnimationFrame batching

- [ ] **Add missing database indexes**
  - Tables: messages, events, room_memberships, user_presence, message_receipts
  - Indexes needed:
    - `idx_messages_thread_sequence ON messages(thread_id, sequence)`
    - `idx_messages_search ON messages USING gin(search_vector)`
    - `idx_events_room_sequence ON events(room_id, sequence)`
    - `idx_room_memberships_user ON room_memberships(user_id)`
    - `idx_user_presence_room ON user_presence(room_id, user_id)`
    - `idx_message_receipts_user ON message_receipts(user_id, receipt_type)`

### Stability (Race Conditions)

- [ ] **Add WebSocket connection state machine**
  - File: `frontend/index.html`
  - Issue: Messages lost during reconnection, duplicate connections possible
  - Fix: Add ConnectionState enum and message queue

- [ ] **Add exponential backoff for reconnection**
  - File: `frontend/index.html` - `scheduleReconnect()`
  - Issue: Fixed 3-second interval can overwhelm server
  - Fix: Exponential backoff (1s base, 30s max) with jitter

- [ ] **Fix infinite scroll race condition**
  - File: `frontend/index.html` - `handleInfiniteScroll()`
  - Issue: Rapid scrolling triggers multiple concurrent API calls
  - Fix: Add loading guard with `isLoadingMore` state

- [ ] **Fix streaming state race conditions**
  - File: `frontend/index.html`
  - Issues: Cancel during done, multiple streams, disconnect during stream
  - Fix: Add stream state machine with proper cleanup

---

## 🟡 MEDIUM Priority

### Design/UX

- [ ] **Add distinctive typography**
  - File: `frontend/index.html:36`
  - Issue: Generic system fonts are forgettable
  - Fix: Add Space Grotesk + JetBrains Mono font pairing

- [ ] **Enhance streaming visual feedback**
  - File: `frontend/index.html` - streaming message styles
  - Issue: Lacks "thinking" quality of modern LLM UIs
  - Fix: Add shimmer effect and blinking cursor

### Code Quality

- [ ] **Replace deprecated datetime.utcnow()**
  - File: `api/main.py` - lines 275, 313, 350, 554, 714
  - Issue: Deprecated in Python 3.12+
  - Fix: Use `datetime.now(timezone.utc)`

- [ ] **Add type hints to helper functions**
  - File: `api/main.py` - `verify_room_token()` and others
  - Fix: Add return type annotations

- [ ] **Remove/gate console.log statements**
  - File: `frontend/index.html` - multiple locations
  - Fix: Add DEBUG flag, replace with gated debug() function

- [ ] **Remove ~208 lines of unnecessary code**
  - Duplicate event handlers (~40 lines)
  - Dead code paths (~25 lines)
  - Inline styles duplicating CSS (~30 lines)
  - Verbose logging (~15 lines)
  - Repeated try/except patterns (~20 lines)
  - Comments restating obvious code (~78 lines)

---

## 🟢 LOW Priority (Future)

### Architecture

- [ ] **Refactor main.py god object**
  - Issue: 1300 lines handling routes, schemas, business logic
  - Target structure:
    ```
    api/
    ├── main.py           # App setup only
    ├── routes/
    ├── schemas/
    └── services/
    ```

- [ ] **Add agent-native capabilities**
  - Issue: LLM cannot write memories, fork threads, switch threads
  - Fix: Expose tool-calling to LLM for contextual actions

- [ ] **Add Redis pub/sub for horizontal scaling**
  - Issue: In-memory ConnectionManager limits to single server
  - Fix: Replace with Redis pub/sub (already noted in code)

---

## Implementation Sprints

### Sprint 1: Security (Day 1)
- [ ] Fix CORS wildcard
- [ ] Add rate limiting
- [ ] Move tokens from URL
- [ ] Add database indexes

### Sprint 2: Stability (Day 2)
- [ ] Fix message sequence race
- [ ] Add exponential backoff
- [ ] Add message queue
- [ ] Fix infinite scroll race

### Sprint 3: Performance (Day 3)
- [ ] Replace recursive ancestry with CTE
- [ ] Throttle streaming DOM updates
- [ ] Add requestAnimationFrame batching

### Sprint 4: Polish (Day 4)
- [ ] Replace deprecated datetime
- [ ] Add distinctive typography
- [ ] Enhance streaming visuals
- [ ] Remove console.log
- [ ] Add type hints

---

## Verification

```bash
# Start backend
python dialectic/run.py

# Start frontend
python -m http.server 3000 --directory dialectic/frontend

# Test CORS (should fail with proper config)
curl -H "Origin: http://evil.com" -X OPTIONS http://localhost:8000/rooms

# Test rate limiting (should get 429 after 5 attempts)
for i in {1..10}; do curl -X POST http://localhost:8000/auth/login; done
```

---

**Total Estimated Effort**: ~16 hours for CRITICAL + HIGH priority items
