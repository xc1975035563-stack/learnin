"""Login isolation and the sync conflict rules."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sync import merge_state


def card(uid: str, front: str, content_at: str, schedule_at: str, due: str, studied: list[str]) -> dict:
    return {
        "id": 1,
        "uid": uid,
        "domain_id": 1,
        "note_id": None,
        "front": front,
        "back": "答案",
        "ease": 2.5,
        "interval_days": 1,
        "repetitions": 1,
        "due": due,
        "created_at": "2026-11-01T00:00:00",
        "mastery": "一般",
        "mastery_color": "",
        "studied_days": studied,
        "content_at": content_at,
        "schedule_at": schedule_at,
    }


def library(cards: list[dict], tombstones: list[dict] | None = None) -> dict:
    return {
        "domains": [{"id": 1, "uid": "domain-1", "name": "AI", "created_at": "2026-11-01T00:00:00"}],
        "notes": [],
        "cards": cards,
        "reviews": [],
        "tombstones": tombstones or [],
    }


class MergeTests(unittest.TestCase):
    def test_content_and_schedule_come_from_different_sides(self) -> None:
        server = library([card("card-1", "电脑上的新问题", "2026-11-20T10:00:00", "2026-11-18T10:00:00", "2026-11-19", ["2026-11-18"])])
        client = library([card("card-1", "手机上的旧问题", "2026-11-19T10:00:00", "2026-11-21T10:00:00", "2026-11-28", ["2026-11-21"])])
        merged = merge_state(server, client)
        saved = merged["cards"][0]
        self.assertEqual(saved["front"], "电脑上的新问题")
        self.assertEqual(saved["due"], "2026-11-28")
        self.assertEqual(saved["studied_days"], ["2026-11-18", "2026-11-21"])

    def test_newer_delete_removes_the_card(self) -> None:
        server = library([card("card-1", "还在", "2026-11-18T10:00:00", "2026-11-18T10:00:00", "2026-11-19", [])])
        client = library([], [{"kind": "card", "uid": "card-1", "deleted_at": "2026-11-20T10:00:00"}])
        merged = merge_state(server, client)
        self.assertEqual(merged["cards"], [])

    def test_edit_after_delete_keeps_the_card(self) -> None:
        server = library([card("card-1", "删后又改了", "2026-11-21T10:00:00", "2026-11-21T10:00:00", "2026-11-22", [])])
        client = library([], [{"kind": "card", "uid": "card-1", "deleted_at": "2026-11-20T10:00:00"}])
        merged = merge_state(server, client)
        self.assertEqual(merged["cards"][0]["front"], "删后又改了")
        self.assertEqual(merged["tombstones"], [])


class AccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LEARN_DB"] = str(Path(self.tmp.name) / "learn.db")
        from main import app, init_db

        init_db()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()
        os.environ.pop("LEARN_DB", None)

    def auth(self, username: str) -> dict[str, str]:
        response = self.client.post("/api/register", json={"username": username, "password": "secret1"})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def test_two_users_do_not_see_each_other(self) -> None:
        first = self.auth("yan")
        second = self.auth("other")
        self.assertGreater(len(self.client.get("/api/domains", headers=first).json()), 0)
        self.assertEqual(self.client.get("/api/domains", headers=second).json(), [])
        created = self.client.post("/api/domains", headers=second, json={"name": "AI"})
        self.assertEqual(created.status_code, 200, created.text)
        names = [item["name"] for item in self.client.get("/api/domains", headers=first).json()]
        self.assertEqual(names.count("AI"), 1)

    def test_sync_of_one_user_leaves_the_other_library(self) -> None:
        first = self.auth("yan")
        second = self.auth("other")
        before = self.client.get("/api/cards", headers=first).json()
        self.assertGreater(len(before), 0)
        synced = self.client.post(
            "/api/sync",
            headers=second,
            json={"domains": [], "notes": [], "cards": [], "reviews": [], "tombstones": []},
        )
        self.assertEqual(synced.status_code, 200, synced.text)
        self.assertEqual(synced.json()["cards"], [])
        self.assertEqual(len(self.client.get("/api/cards", headers=first).json()), len(before))

    def test_library_requires_login(self) -> None:
        response = self.client.get("/api/domains")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
