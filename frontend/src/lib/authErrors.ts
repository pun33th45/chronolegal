// Shared error-message handling for the login/register forms.
//
// FastAPI returns `detail` as a plain string for most errors (e.g. "Email
// already registered"), but as an array of Pydantic error objects for request
// validation failures (422, e.g. a weak password) — rendering that array
// directly fails silently/unreadably, so both shapes are normalized to one
// string here. A request that never got a response at all (backend
// unreachable, CORS block, timeout) is reported distinctly, since "the
// backend is down" and "the backend rejected your input" need different copy.

const FRIENDLY_MESSAGES: Record<string, string> = {
  'Email already registered': 'An account with this email already exists. Try signing in instead.',
  'Username already taken': 'That username is already taken — please choose another.',
}

export function getAuthErrorMessage(err: unknown, fallback: string): string {
  const response = (err as { response?: { data?: { detail?: unknown } } })?.response
  if (!response) {
    return 'Unable to reach ChronoLegal right now. Please try again in a moment.'
  }

  const detail = response.data?.detail
  if (typeof detail === 'string') {
    return FRIENDLY_MESSAGES[detail] ?? detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    if (typeof first?.msg === 'string') return first.msg
  }
  return fallback
}
