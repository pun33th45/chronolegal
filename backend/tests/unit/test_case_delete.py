"""Judgment deletion — the real DELETE /api/v1/cases/{case_id} endpoint with a
real in-memory Chroma collection and a fake transactional DB session (changes
apply only on commit), so atomicity is tested without any real database."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import chromadb
import pytest
from fastapi.testclient import TestClient

OWNER = SimpleNamespace(id=uuid.uuid4(), is_admin=False, is_active=True)
OTHER = SimpleNamespace(id=uuid.uuid4(), is_admin=False, is_active=True)
ADMIN = SimpleNamespace(id=uuid.uuid4(), is_admin=True, is_active=True)


class FakeDB:
    """Records deletions and applies them to the store only on commit."""

    def __init__(self, store):
        self.store, self.pending, self.committed, self.rolled_back = store, [], 0, 0

    async def flush(self):
        pass

    async def commit(self):
        for case_id in self.pending:
            self.store.pop(case_id, None)  # case row; its chunks go with it (ON DELETE CASCADE)
        self.pending.clear()
        self.committed += 1

    async def rollback(self):
        self.pending.clear()
        self.rolled_back += 1


def _case(case_id, name):
    return SimpleNamespace(
        id=uuid.uuid4(), case_id=case_id, case_name=name, court="Supreme Court of India",
        judges=None, judgment_date=None, acts=None, decision_type=None, summary=None,
        citation_count=0, chunk_count=0, is_embedded=True, source_file=None,
        created_at="2026-10-06T00:00:00Z",
    )


@pytest.fixture
def env():
    owned = f"upload_{OWNER.id}_abc12345"
    store = {
        owned: {"case": _case(owned, "Owned judgment"), "chunks": ["c0", "c1"]},
        f"upload_{OWNER.id}_nochunks": {"case": _case(f"upload_{OWNER.id}_nochunks", "No chunks"), "chunks": []},
        f"upload_{OWNER.id}_novectors": {"case": _case(f"upload_{OWNER.id}_novectors", "No vectors"), "chunks": ["c0"]},
        "seeded-case-1973": {"case": _case("seeded-case-1973", "Seeded case"), "chunks": []},
    }
    collection = chromadb.EphemeralClient().get_or_create_collection(f"t_{uuid.uuid4().hex}")
    for case_id, n in ((owned, 2), ("seeded-case-1973", 3)):
        collection.add(
            ids=[f"{case_id}__chunk_{i}" for i in range(n)],
            embeddings=[[0.1, 0.2, 0.3]] * n,
            documents=["text"] * n,
            metadatas=[{"case_id": case_id, "chunk_index": i} for i in range(n)],
        )

    class FakeCaseService:
        def __init__(self, db):
            self.db = db

        async def get_by_case_id(self, case_id):
            entry = store.get(case_id)
            return entry["case"] if entry else None

        async def delete_case(self, case):
            self.db.pending.append(case.case_id)

        async def list_cases(self, **_):
            return [e["case"] for e in store.values()]

    from app.api.v1.endpoints.auth import get_current_user
    from app.core.database import get_db
    from app.main import app

    state = {"user": OWNER, "db": None}

    async def _db():
        state["db"] = FakeDB(store)
        yield state["db"]

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    with (
        patch("app.api.v1.endpoints.cases.CaseService", FakeCaseService),
        patch("app.services.ai.embedding_service.get_collection", lambda: collection),
    ):
        yield SimpleNamespace(client=TestClient(app), store=store, collection=collection, state=state, owned=owned)
    app.dependency_overrides.clear()


def _vectors(collection, case_id):
    return len(collection.get(where={"case_id": case_id})["ids"])


def test_owner_deletes_case_chunks_and_only_its_vectors(env):
    r = env.client.delete(f"/api/v1/cases/{env.owned}")
    assert r.status_code == 204
    assert env.owned not in env.store  # case row and (cascaded) chunks gone
    assert _vectors(env.collection, env.owned) == 0
    assert _vectors(env.collection, "seeded-case-1973") == 3  # other judgments untouched
    assert env.state["db"].committed == 1


@pytest.mark.parametrize("suffix", ["nochunks", "novectors"])
def test_case_without_chunks_or_vectors_is_still_deletable(env, suffix):
    case_id = f"upload_{OWNER.id}_{suffix}"
    assert _vectors(env.collection, case_id) == 0
    assert env.client.delete(f"/api/v1/cases/{case_id}").status_code == 204
    assert case_id not in env.store


def test_nonexistent_case_returns_404(env):
    assert env.client.delete("/api/v1/cases/does-not-exist").status_code == 404


def test_other_users_upload_is_forbidden_and_untouched(env):
    env.state["user"] = OTHER
    r = env.client.delete(f"/api/v1/cases/{env.owned}")
    assert r.status_code == 403
    assert "permission" in r.json()["detail"]
    assert env.owned in env.store and _vectors(env.collection, env.owned) == 2


def test_seeded_case_needs_admin(env):
    assert env.client.delete("/api/v1/cases/seeded-case-1973").status_code == 403
    env.state["user"] = ADMIN
    assert env.client.delete("/api/v1/cases/seeded-case-1973").status_code == 204
    assert _vectors(env.collection, "seeded-case-1973") == 0


def test_vector_delete_failure_rolls_back_everything(env):
    class Broken:
        def delete(self, **_):
            raise RuntimeError("chroma unavailable")

    with patch("app.services.ai.embedding_service.get_collection", lambda: Broken()):
        r = env.client.delete(f"/api/v1/cases/{env.owned}")
    assert r.status_code == 500
    assert "chroma" not in r.text.lower()  # no internal error text leaks
    assert env.owned in env.store  # nothing half-deleted
    assert env.state["db"].rolled_back == 1 and env.state["db"].committed == 0
    assert _vectors(env.collection, env.owned) == 2


def test_list_reports_who_may_delete(env):
    flags = {c["case_id"]: c["can_delete"] for c in env.client.get("/api/v1/cases/").json()}
    assert flags[env.owned] is True and flags["seeded-case-1973"] is False
    env.state["user"] = OTHER
    flags = {c["case_id"]: c["can_delete"] for c in env.client.get("/api/v1/cases/").json()}
    assert not any(flags.values())


def test_unauthenticated_delete_is_rejected(env):
    from app.api.v1.endpoints.auth import get_current_user
    from app.main import app

    del app.dependency_overrides[get_current_user]
    r = env.client.delete(f"/api/v1/cases/{env.owned}")
    assert r.status_code == 401
    assert env.owned in env.store
