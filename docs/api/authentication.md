# Authentication Guide

ChronoLegal uses JWT (JSON Web Tokens) for stateless authentication.

## Flow

```
Client                          Server
  |                               |
  |  POST /auth/login             |
  |  {email, password}   -------> |
  |                               | verify bcrypt hash
  |  {access_token: "eyJ..."} <-- |
  |                               |
  |  GET /api/v1/chat/...         |
  |  Authorization: Bearer eyJ... |
  |                        -----> | decode + validate JWT
  |  200 OK               <------ |
```

## Token Details

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Expiry | 24 hours (configurable) |
| Payload claims | `sub` (user_id), `role`, `exp`, `iat` |

## Using Tokens

### curl
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | jq -r '.access_token')

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/auth/me
```

### Python
```python
import httpx

resp = httpx.post("http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@example.com", "password": "password"})
token = resp.json()["access_token"]

client = httpx.Client(headers={"Authorization": f"Bearer {token}"})
me = client.get("http://localhost:8000/api/v1/auth/me").json()
```

### JavaScript / fetch
```javascript
const { access_token } = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
}).then(r => r.json());

const me = await fetch('/api/v1/auth/me', {
  headers: { Authorization: `Bearer ${access_token}` },
}).then(r => r.json());
```

## Roles

| Role | Access |
|------|--------|
| `user` | All public endpoints |
| `admin` | All endpoints + `/admin/*` |

## Security Notes

- Tokens are signed with `JWT_SECRET_KEY` (set in `.env`)
- Never commit real secret keys
- Use HTTPS in production — Nginx config enforces this
- Refresh strategy: re-authenticate when token expires (no refresh tokens currently)
- Rate limiting: 30 auth attempts / minute per IP

## Error Codes

| Code | Reason |
|------|--------|
| 401 `Not authenticated` | No Authorization header |
| 401 `Could not validate credentials` | Token malformed or expired |
| 401 `Incorrect email or password` | Login failed |
| 403 `Not enough permissions` | User role insufficient |
