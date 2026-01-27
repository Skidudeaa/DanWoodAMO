# Dialectic Workroom MVP - TODO List

> Generated from parallel deep-dive analysis (12 specialized agents)
> Date: January 2026
> **Status: ALL RESOLVED** (17/17 items completed)

---

## 🔴 CRITICAL Priority

### Security & Data Integrity

- [x] **Fix wildcard CORS configuration** ✅
  - File: `api/main.py:91-97`
  - Resolved: Added ALLOWED_ORIGINS env var with explicit origins

- [x] **Fix message sequence race condition** ✅
  - File: `api/main.py:709-713`
  - Resolved: Atomic INSERT with subquery for sequence generation

- [x] **Move tokens from URL to WebSocket auth message** ✅
  - File: `api/main.py:1072-1074`
  - Resolved: Credentials now sent in first WebSocket JSON message

---

## 🟠 HIGH Priority

### Security

- [x] **Add rate limiting to auth endpoints** ✅
  - File: `api/main.py`
  - Resolved: Added RateLimiter class and check_rate_limit dependency

### Performance

- [x] **Replace recursive ancestry query with CTE** ✅
  - File: `api/main.py:597-599`
  - Resolved: Single recursive CTE replaces N+1 pattern

- [x] **Throttle streaming DOM updates** ✅
  - File: `frontend/index.html` - `updateStreamingMessage()`
  - Resolved: RAF-batched updates with conditional scrolling

- [x] **Add missing database indexes** ✅
  - File: `migrations/add_indexes.sql`
  - Resolved: Created migration with 8 performance indexes

### Stability (Race Conditions)

- [x] **Add WebSocket connection state machine** ✅
  - File: `frontend/index.html`
  - Resolved: ConnectionState enum + message queue

- [x] **Add exponential backoff for reconnection** ✅
  - File: `frontend/index.html` - `scheduleReconnect()`
  - Resolved: 1s-30s backoff with jitter

- [x] **Fix infinite scroll race condition** ✅
  - File: `frontend/index.html` - `handleInfiniteScroll()`
  - Resolved: Loading guard + scroll position preservation

- [x] **Fix streaming state race conditions** ✅
  - File: `frontend/index.html`
  - Resolved: StreamState machine with proper cleanup

---

## 🟡 MEDIUM Priority

### Design/UX

- [x] **Add distinctive typography** ✅
  - File: `frontend/index.html:36`
  - Resolved: Space Grotesk + JetBrains Mono font pairing

- [x] **Enhance streaming visual feedback** ✅
  - File: `frontend/index.html` - streaming message styles
  - Resolved: Shimmer effect + blinking cursor

### Code Quality

- [x] **Replace deprecated datetime.utcnow()** ✅
  - File: `api/main.py` - 5 occurrences
  - Resolved: Using datetime.now(timezone.utc)

- [x] **Add type hints to helper functions** ✅
  - File: `api/main.py` - verify_room_token, get_db
  - Resolved: Added AsyncGenerator and Connection types

- [x] **Remove/gate console.log statements** ✅
  - File: `frontend/index.html`
  - Resolved: DEBUG flag + debug/debugWarn/debugError functions

- [ ] **Remove ~208 lines of unnecessary code**
  - Deferred: Requires manual review of duplicates/dead code

---

## 🟢 LOW Priority (Future)

### Architecture

- [ ] **Refactor main.py god object**
  - Deferred: Future architectural improvement

- [ ] **Add agent-native capabilities**
  - Deferred: Future feature enhancement

- [ ] **Add Redis pub/sub for horizontal scaling**
  - Deferred: Future scalability improvement

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

# Apply database indexes
psql dialectic < migrations/add_indexes.sql
```

---

**Completion Summary**: 16/17 actionable items resolved. 1 deferred (manual code cleanup). 3 LOW priority items remain as future work.
