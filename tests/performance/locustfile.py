"""
ChronoLegal — Locust Load Test Suite

Usage:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

    # Headless CI run (100 users, spawn 10/s, run 60s)
    locust -f locustfile.py --host http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 60s --headless \
        --html reports/load_report.html
"""

import json
import random

from locust import HttpUser, TaskSet, between, task

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

QUESTIONS = [
    "What is the basic structure doctrine?",
    "Explain Article 21 rights as per Maneka Gandhi case",
    "What did Supreme Court hold in Kesavananda Bharati?",
    "Rights of accused under Article 22",
    "Directive principles vs fundamental rights",
    "What is habeas corpus in Indian law?",
    "Explain the right to privacy ruling of 2017",
    "What is the doctrine of proportionality?",
]

SEARCH_QUERIES = [
    "fundamental rights",
    "right to privacy surveillance",
    "article 21 personal liberty",
    "basic structure constitution",
    "natural justice principles",
    "preventive detention",
]


# ---------------------------------------------------------------------------
# Task sets
# ---------------------------------------------------------------------------

class AuthTasks(TaskSet):
    """Authenticate and store token for subsequent requests."""

    token: str = ""

    def on_start(self):
        self._login()

    def _login(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "loadtest@chronolegal.test", "password": "LoadTest123!"},
            name="/auth/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def search(self):
        query = random.choice(SEARCH_QUERIES)
        self.client.post(
            "/api/v1/search/",
            json={"query": query, "page": 1, "page_size": 10},
            headers=self._headers(),
            name="/search",
        )

    @task(2)
    def chat_non_streaming(self):
        question = random.choice(QUESTIONS)
        self.client.post(
            "/api/v1/chat/",
            json={"question": question},
            headers=self._headers(),
            name="/chat (non-streaming)",
            timeout=60,
        )

    @task(2)
    def list_conversations(self):
        self.client.get(
            "/api/v1/chat/conversations",
            headers=self._headers(),
            name="/chat/conversations",
        )

    @task(1)
    def analytics_dashboard(self):
        self.client.get(
            "/api/v1/analytics/dashboard",
            headers=self._headers(),
            name="/analytics/dashboard",
        )

    @task(1)
    def search_suggestions(self):
        q = random.choice(["fund", "priva", "artic", "basic"])
        self.client.get(
            f"/api/v1/search/suggestions?q={q}&limit=5",
            headers=self._headers(),
            name="/search/suggestions",
        )


# ---------------------------------------------------------------------------
# User classes
# ---------------------------------------------------------------------------

class RegularUser(HttpUser):
    """Simulates a typical legal researcher."""

    tasks = [AuthTasks]
    wait_time = between(1, 5)
    weight = 3


class HeavyUser(HttpUser):
    """Power user — shorter waits, more requests."""

    tasks = [AuthTasks]
    wait_time = between(0.5, 2)
    weight = 1
