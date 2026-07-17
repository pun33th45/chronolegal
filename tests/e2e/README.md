# ChronoLegal — End-to-End Tests

Playwright E2E tests that verify the full user journey against a running stack.

## Prerequisites

1. ChronoLegal stack running: `make dev`
2. Node.js 18+

## Setup

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

## Running

```bash
# All tests (headless)
npm test

# Headed (see the browser)
npm run test:headed

# Debug mode (step through)
npm run test:debug

# Show HTML report
npm run report
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:5173` | Frontend URL |

## Test Files

| File | Coverage |
|------|---------|
| `specs/auth.spec.ts` | Register, login, logout, protected routes |
| `specs/chat.spec.ts` | Q&A streaming, citations, conversations |
| `specs/search.spec.ts` | Search, filters, case viewer navigation |
| `specs/analytics.spec.ts` | Dashboard charts and stats |

## Notes

- Tests run sequentially (`workers: 1`) to avoid auth conflicts
- Screenshots saved on failure to `playwright-report/`
- Add `data-testid` attributes to frontend components when adding new specs
