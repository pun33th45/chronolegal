# ChronoLegal API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/api/docs` (Swagger UI)

---

## Authentication

All protected endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are obtained via the login endpoint and expire after 24 hours (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## Endpoints

### Auth

#### `POST /auth/register`
Register a new user.

**Body**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Advocate Sharma"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Advocate Sharma",
  "role": "user",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

#### `POST /auth/login`
Authenticate and get access token.

**Body**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response `200`**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

#### `GET /auth/me`
Get current user profile. Requires auth.

**Response `200`**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Advocate Sharma",
  "role": "user"
}
```

---

### Chat (RAG Q&A)

#### `POST /chat/`
Non-streaming legal Q&A. Requires auth.

**Body**
```json
{
  "question": "What did the Supreme Court hold in Kesavananda Bharati?",
  "conversation_id": "uuid-optional"
}
```

**Response `200`**
```json
{
  "answer": "The Supreme Court held...",
  "citations": [
    {
      "case_name": "Kesavananda Bharati v. State of Kerala",
      "citation": "(1973) 4 SCC 225",
      "court": "Supreme Court of India",
      "year": 1973,
      "relevance_score": 0.94,
      "chunk_text": "...the basic structure of the Constitution..."
    }
  ],
  "conversation_id": "uuid",
  "message_id": "uuid"
}
```

---

#### `POST /chat/stream`
SSE streaming legal Q&A. Requires auth.

Returns `text/event-stream`. Events:

| Event type | Data |
|-----------|------|
| `token` | Next token string |
| `citations` | JSON array of citation objects |
| `done` | `{"conversation_id": "...", "message_id": "..."}` |
| `error` | Error message string |

**Example**
```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is basic structure doctrine?"}' \
  http://localhost:8000/api/v1/chat/stream
```

---

#### `GET /chat/conversations`
List user's conversations. Requires auth.

**Query params**: `page=1&page_size=20`

**Response `200`**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Basic structure doctrine",
      "created_at": "...",
      "message_count": 5
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

#### `GET /chat/conversations/{conversation_id}`
Get a single conversation with messages. Requires auth.

#### `DELETE /chat/conversations/{conversation_id}`
Delete a conversation. Requires auth.

---

### Search

#### `POST /search/`
Hybrid semantic + keyword search. Requires auth.

**Body**
```json
{
  "query": "fundamental rights privacy",
  "filters": {
    "court": "Supreme Court of India",
    "year_from": 2000,
    "year_to": 2023,
    "acts": ["Constitution of India"]
  },
  "page": 1,
  "page_size": 10
}
```

**Response `200`**
```json
{
  "results": [
    {
      "case_id": "uuid",
      "case_name": "Justice K.S. Puttaswamy v. Union of India",
      "citation": "(2017) 10 SCC 1",
      "court": "Supreme Court of India",
      "year": 2017,
      "snippet": "...right to privacy is a fundamental right...",
      "relevance_score": 0.97
    }
  ],
  "total": 127,
  "page": 1,
  "page_size": 10,
  "query_time_ms": 48
}
```

---

#### `GET /search/suggestions`
Autocomplete suggestions. Requires auth.

**Query params**: `q=kesavan&limit=5`

**Response `200`**
```json
["Kesavananda Bharati", "Kesavananda Bharati v. State of Kerala"]
```

---

### Cases

#### `GET /cases/{case_id}`
Get full case details. Requires auth.

**Response `200`**
```json
{
  "id": "uuid",
  "case_name": "Maneka Gandhi v. Union of India",
  "citation": "(1978) 1 SCC 248",
  "court": "Supreme Court of India",
  "bench": ["Y.V. Chandrachud CJ", "V.R. Krishna Iyer J"],
  "year": 1978,
  "date_decided": "1978-01-25",
  "judgment_text": "...",
  "acts_cited": ["Constitution of India"],
  "sections_cited": ["Article 14", "Article 19", "Article 21"],
  "outcome": "Allowed"
}
```

#### `GET /cases/{case_id}/similar`
Get semantically similar cases. Requires auth.

**Query params**: `limit=5`

---

### Summary

#### `POST /summary/`
Generate AI summary of a case. Requires auth.

**Body**
```json
{
  "case_id": "uuid",
  "style": "concise"
}
```

`style` options: `concise` | `detailed` | `bullet_points`

**Response `200`**
```json
{
  "case_id": "uuid",
  "summary": "...",
  "style": "concise",
  "word_count": 150
}
```

---

### NER (Named Entity Recognition)

#### `POST /ner/`
Extract legal entities from a case. Requires auth.

**Body**
```json
{ "case_id": "uuid" }
```

**Response `200`**
```json
{
  "case_id": "uuid",
  "entities": {
    "judges": ["Y.V. Chandrachud CJ", "V.R. Krishna Iyer J"],
    "advocates": ["Soli J. Sorabjee"],
    "courts": ["Supreme Court of India", "Delhi High Court"],
    "acts": ["Constitution of India", "Passport Entry into India Act"],
    "sections": ["Article 21", "Article 19(1)(a)"],
    "organizations": ["Union of India", "Ministry of External Affairs"],
    "dates": ["25 January 1978"]
  }
}
```

---

### Timeline

#### `GET /timeline/{case_id}`
Get chronological event timeline for a case. Requires auth.

**Response `200`**
```json
{
  "case_id": "uuid",
  "events": [
    {
      "date": "1977-07-02",
      "event": "Passport impounded by MEA without reasons",
      "type": "procedural"
    },
    {
      "date": "1978-01-25",
      "event": "Supreme Court expands Article 21 — procedure must be fair, just, reasonable",
      "type": "judgment"
    }
  ]
}
```

---

### Analytics

#### `GET /analytics/dashboard`
Aggregated analytics data. Requires auth.

**Response `200`**
```json
{
  "total_cases": 12481,
  "total_searches": 3420,
  "top_courts": [{"court": "Supreme Court of India", "count": 8450}],
  "top_acts": [{"act": "Constitution of India", "count": 6230}],
  "case_trends": [{"year": 2020, "count": 1204}],
  "decision_types": [{"type": "Allowed", "count": 5421}],
  "top_keywords": [{"word": "fundamental rights", "count": 820}]
}
```

---

### Feedback

#### `POST /feedback/`
Submit search/answer feedback. Requires auth.

**Body**
```json
{
  "message_id": "uuid",
  "rating": 4,
  "comment": "Good answer but missing a key case"
}
```

---

### Admin (admin role only)

#### `GET /admin/stats`
System health and embedding stats.

**Response `200`**
```json
{
  "total_cases": 12481,
  "embedded_cases": 12481,
  "embedding_progress": 1.0,
  "chroma_documents": 124810,
  "active_users_24h": 42,
  "searches_24h": 380,
  "avg_response_ms": 1240
}
```

#### `POST /admin/reindex`
Trigger full re-embedding (async). Admin only.

---

## Error Responses

All errors follow this shape:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request / validation error |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 422 | Unprocessable entity (schema validation) |
| 429 | Rate limit exceeded (60 req/min per IP) |
| 500 | Internal server error |

---

## Rate Limiting

- **General**: 60 requests / minute per IP
- **Chat/Search**: 30 requests / minute per user
- **Admin**: 10 requests / minute

Headers returned on rate limit:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1704067260
```

---

## WebSocket

`WS /ws/chat?token=<access_token>`

Bidirectional streaming alternative to SSE.

**Send**
```json
{ "question": "...", "conversation_id": "uuid-optional" }
```

**Receive** — same event stream as SSE (`token`, `citations`, `done`, `error`).
