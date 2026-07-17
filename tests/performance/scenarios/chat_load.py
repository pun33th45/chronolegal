"""
Chat / RAG pipeline load scenario.

Tests the most expensive path — non-streaming RAG inference.
Lower concurrency than search because LLM is the bottleneck.

    locust -f scenarios/chat_load.py --host http://localhost:8000 \
        --users 10 --spawn-rate 1 --run-time 120s --headless
"""

import random

from locust import HttpUser, between, task

QUESTIONS = [
    "What is the basic structure doctrine of the Indian Constitution?",
    "Explain the right to privacy as held in Puttaswamy case",
    "What were the main holdings of Maneka Gandhi v. Union of India?",
    "How does Article 21 protect personal liberty?",
    "What is the doctrine of prospective overruling?",
    "Explain the principles of natural justice",
    "What is the difference between Article 14 and Article 15?",
    "How has the Supreme Court interpreted right to life?",
]


class ChatUser(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "loadtest@chronolegal.test", "password": "LoadTest123!"},
        )
        self.token = resp.json().get("access_token", "") if resp.status_code == 200 else ""
        self.conversation_id = None

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def ask_question(self):
        payload = {"question": random.choice(QUESTIONS)}
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        with self.client.post(
            "/api/v1/chat/",
            json=payload,
            headers=self._auth(),
            name="/chat (non-streaming)",
            timeout=120,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.conversation_id = data.get("conversation_id")
                if not data.get("answer"):
                    resp.failure("Empty answer in response")
            else:
                resp.failure(f"Chat failed: {resp.status_code}")

    @task(1)
    def list_conversations(self):
        self.client.get(
            "/api/v1/chat/conversations",
            headers=self._auth(),
            name="/chat/conversations",
        )
