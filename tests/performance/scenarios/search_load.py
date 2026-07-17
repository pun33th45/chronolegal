"""
Search-focused load scenario.

Simulates a burst of concurrent search queries — the most common operation
in ChronoLegal. Run this standalone:

    locust -f scenarios/search_load.py --host http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 120s --headless
"""

import random

from locust import HttpUser, between, task

QUERIES = [
    "fundamental rights india",
    "right to privacy",
    "article 21 personal liberty",
    "basic structure doctrine",
    "natural justice audi alteram partem",
    "preventive detention safeguards",
    "freedom of speech reasonable restrictions",
    "equal protection law article 14",
    "right to education 86th amendment",
    "judicial review powers supreme court",
]

COURTS = [
    None,
    "Supreme Court of India",
    "Delhi High Court",
    "Bombay High Court",
]


class SearchUser(HttpUser):
    wait_time = between(0.5, 3)

    def on_start(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "loadtest@chronolegal.test", "password": "LoadTest123!"},
        )
        self.token = resp.json().get("access_token", "") if resp.status_code == 200 else ""

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def semantic_search(self):
        payload = {
            "query": random.choice(QUERIES),
            "page": 1,
            "page_size": 10,
        }
        court = random.choice(COURTS)
        if court:
            payload["filters"] = {"court": court}

        self.client.post("/api/v1/search/", json=payload, headers=self._auth(), name="/search")

    @task(2)
    def suggestions(self):
        prefix = random.choice(["fund", "priva", "artic", "basic", "right"])
        self.client.get(
            f"/api/v1/search/suggestions?q={prefix}&limit=5",
            headers=self._auth(),
            name="/search/suggestions",
        )

    @task(1)
    def health_check(self):
        self.client.get("/api/health", name="/health")
