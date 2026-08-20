# ChronoLegal — Presentation Demo Questions

Five questions to ask live, plus one deliberately unrelated question to show
the insufficient-evidence fallback. Each maps cleanly to exactly one of the
six seeded landmark cases (`database/seeds/01_sample_cases.sql`), so the
retrieved source is unambiguous and easy for a judge/guide to verify.

---

### 1. "Can Parliament amend the Constitution to destroy its basic structure?"
- **Expected case:** *Kesavananda Bharati v. State of Kerala* (1973)
- **Demonstrates:** semantic retrieval matching a legal *doctrine name*
  ("basic structure") rather than a keyword the user typed literally.
- **What to point out:** the answer should name the doctrine, mention the
  7:6 majority, and cite this case specifically — not a generic
  constitutional-law answer.

### 2. "Did the Supreme Court decriminalize consensual same-sex relations under Section 377?"
- **Expected case:** *Navtej Singh Johar v. Union of India* (2018)
- **Demonstrates:** retrieval by a specific statutory section number
  (Section 377 IPC) combined with a legal outcome (decriminalization).
- **What to point out:** this is the most recent/well-known case in the set
  — a strong one to open or close with.

### 3. "What guidelines did the Court lay down to prevent sexual harassment at the workplace?"
- **Expected case:** *Vishaka v. State of Rajasthan* (1997)
- **Demonstrates:** retrieval matching a named legal framework ("Vishaka
  Guidelines") the user didn't have to know by name to ask about.

### 4. "Can the President impose President's Rule under Article 356 without a floor test?"
- **Expected case:** *S.R. Bommai v. Union of India* (1994)
- **Demonstrates:** retrieval on a specific constitutional article (356)
  plus a procedural concept ("floor test") — good for showing hybrid
  (semantic + BM25) retrieval handling an exact-term match well.

### 5. "What did the Court say about due process before impounding someone's passport?"
- **Expected case:** *Maneka Gandhi v. Union of India* (1978)
- **Demonstrates:** the "Golden Triangle" of Articles 14/19/21 — a good
  question for explaining grounded reasoning, since the answer should
  connect multiple articles the way the actual judgment does.

---

### 6. (Insufficient-evidence check) "What are the GDPR data protection requirements in the European Union?"
- **Expected result:** the system must return the existing fixed fallback —
  *"The uploaded legal corpus does not contain sufficient evidence to
  answer this question."* — not a fabricated answer from Groq's general
  knowledge.
- **Why this matters most:** this is the single most important thing to
  show a judge. It proves the system is actually grounded in the retrieved
  knowledge base rather than just being Groq with a legal-sounding system
  prompt. **If this question gets a confident, made-up legal answer
  instead of the fallback message, something is broken — flag it
  immediately rather than continuing the demo.**

---

## Bonus / backup case
*Olga Tellis v. Bombay Municipal Corporation* (1985) — right to livelihood
under Article 21 for pavement dwellers — is seeded but not used above; keep
it as a backup question ("Does the right to life include the right to a
livelihood?") if a judge asks for another live example.

## What each answer should visibly show
Case name, court, date, a retrieved excerpt (the actual quoted chunk text),
a relevance/similarity percentage, and a "View full case" link — all in the
expandable citation card under "Sources (N)" beneath the answer.
