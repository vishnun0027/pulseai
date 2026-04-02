from __future__ import annotations

import csv
import io
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import dashboard.auth as auth_module
import dashboard.main as main_module
import dashboard.routes as routes_module
from dashboard.main import app


class InMemoryState:
    def __init__(self) -> None:
        self.users = []
        self.next_user_id = 1
        self.anomaly_events = [
            {
                "id": 101,
                "agent_id": "agent-test-1",
                "ts": datetime(2026, 4, 2, 6, 30, tzinfo=timezone.utc),
                "cpu_usage": 88.2,
                "used_memory_gb": 3.4,
                "anomaly_score": 0.742,
                "is_anomaly": True,
                "drift_detected": False,
                "explanation": {
                    "top_contributors": [
                        {"feature": "cpu_raw", "impact": 0.53},
                        {"feature": "cpu_mean_5", "impact": 0.22},
                    ]
                },
            },
            {
                "id": 102,
                "agent_id": "agent-test-2",
                "ts": datetime(2026, 4, 2, 7, 0, tzinfo=timezone.utc),
                "cpu_usage": 22.1,
                "used_memory_gb": 1.9,
                "anomaly_score": -0.081,
                "is_anomaly": False,
                "drift_detected": True,
                "explanation": {},
            },
        ]

    async def fetch_one(self, query: str, *args):
        normalized = " ".join(query.split()).lower()

        if "select count(*) as total from users" in normalized:
            return {"total": len(self.users)}

        if "select id from users where username =" in normalized:
            username = args[0]
            user = next((u for u in self.users if u["username"] == username), None)
            return {"id": user["id"]} if user else None

        if "select id, username, role from users where username =" in normalized:
            username = args[0]
            user = next((u for u in self.users if u["username"] == username), None)
            if not user:
                return None
            return {"id": user["id"], "username": user["username"], "role": user["role"]}

        if "select id, username, password_hash, role from users where username =" in normalized:
            username = args[0]
            user = next((u for u in self.users if u["username"] == username), None)
            if not user:
                return None
            return {
                "id": user["id"],
                "username": user["username"],
                "password_hash": user["password_hash"],
                "role": user["role"],
            }

        if "insert into users" in normalized and "returning id, username, role" in normalized:
            username, password_hash, role = args
            user = {
                "id": self.next_user_id,
                "username": username,
                "password_hash": password_hash,
                "role": role,
                "last_login_at": None,
            }
            self.next_user_id += 1
            self.users.append(user)
            return {"id": user["id"], "username": user["username"], "role": user["role"]}

        if "select count(*) as total from anomaly_events" in normalized:
            rows = self._filter_events(query, list(args))
            return {"total": len(rows)}

        if "from anomaly_events where id = $1" in normalized:
            event_id = args[0]
            return next((e for e in self.anomaly_events if e["id"] == event_id), None)

        raise AssertionError(f"Unhandled fetch_one query: {query}")

    async def fetch_all(self, query: str, *args):
        normalized = " ".join(query.split()).lower()

        if "from anomaly_events" in normalized:
            return self._filter_events(query, list(args))

        if "from users" in normalized:
            return list(self.users)

        raise AssertionError(f"Unhandled fetch_all query: {query}")

    async def execute(self, query: str, *args):
        normalized = " ".join(query.split()).lower()

        if "update users set last_login_at = now()" in normalized:
            user_id = args[0]
            for user in self.users:
                if user["id"] == user_id:
                    user["last_login_at"] = datetime.now(timezone.utc)
                    return "UPDATE 1"
            return "UPDATE 0"

        raise AssertionError(f"Unhandled execute query: {query}")

    def _filter_events(self, query: str, args: list):
        rows = list(self.anomaly_events)
        normalized = " ".join(query.split()).lower()

        idx = 0
        if "agent_id = $1" in normalized:
            agent_id = args[idx]
            rows = [row for row in rows if row["agent_id"] == agent_id]
            idx += 1

        if "is_anomaly = true" in normalized:
            rows = [row for row in rows if row["is_anomaly"]]

        if "ts >=" in normalized:
            from_ts = args[idx]
            rows = [row for row in rows if row["ts"] >= from_ts]
            idx += 1

        if "ts <=" in normalized:
            to_ts = args[idx]
            rows = [row for row in rows if row["ts"] <= to_ts]
            idx += 1

        rows.sort(key=lambda row: row["ts"], reverse=True)

        if "limit $" in normalized and "offset $" in normalized:
            limit = args[idx]
            offset = args[idx + 1]
            rows = rows[offset: offset + limit]

        return rows


class FakeBroadcaster:
    async def start(self):
        return None

    async def stop(self):
        return None

    async def subscribe(self):
        yield json.dumps(
            {
                "agent_id": "agent-test-1",
                "timestamp": 1775111400,
                "cpu": 88.2,
                "memory": 3.4,
                "anomaly_score": 0.742,
                "is_anomaly": True,
                "drift_detected": False,
                "explanation": {
                    "top_contributors": [
                        {"feature": "cpu_raw", "impact": 0.53},
                        {"feature": "cpu_mean_5", "impact": 0.22},
                    ]
                },
            }
        )


@contextmanager
def patched_app():
    state = InMemoryState()
    fake_broadcaster = FakeBroadcaster()

    original_auth_fetch_one = auth_module.fetch_one
    original_auth_execute = auth_module.execute
    original_main_init_pool = main_module.init_pool
    original_main_close_pool = main_module.close_pool
    original_main_broadcaster = main_module.broadcaster
    original_routes_fetch_one = routes_module.fetch_one
    original_routes_fetch_all = routes_module.fetch_all
    original_routes_broadcaster = routes_module.broadcaster

    auth_module.fetch_one = state.fetch_one
    auth_module.execute = state.execute
    main_module.init_pool = _noop_async
    main_module.close_pool = _noop_async
    main_module.broadcaster = fake_broadcaster
    routes_module.fetch_one = state.fetch_one
    routes_module.fetch_all = state.fetch_all
    routes_module.broadcaster = fake_broadcaster

    try:
        yield state
    finally:
        auth_module.fetch_one = original_auth_fetch_one
        auth_module.execute = original_auth_execute
        main_module.init_pool = original_main_init_pool
        main_module.close_pool = original_main_close_pool
        main_module.broadcaster = original_main_broadcaster
        routes_module.fetch_one = original_routes_fetch_one
        routes_module.fetch_all = original_routes_fetch_all
        routes_module.broadcaster = original_routes_broadcaster


async def _noop_async(*args, **kwargs):
    return None


def main() -> None:
    with patched_app():
        with TestClient(app) as client:
            unauthorized = client.get("/api/anomalies")
            assert unauthorized.status_code == 401, unauthorized.text

            bootstrap = client.get("/api/auth/bootstrap-status")
            assert bootstrap.status_code == 200
            assert bootstrap.json()["bootstrap_required"] is True

            register = client.post(
                "/api/auth/register",
                json={"username": "admin", "password": "supersecure123"},
            )
            assert register.status_code == 201, register.text
            reg_json = register.json()
            assert reg_json["user"]["role"] == "admin"
            assert reg_json["bootstrap"] is True
            assert "pulseai_session" in client.cookies

            me = client.get("/api/auth/me")
            assert me.status_code == 200, me.text
            assert me.json()["user"]["username"] == "admin"

            anomalies = client.get("/api/anomalies?limit=10")
            assert anomalies.status_code == 200, anomalies.text
            anomaly_json = anomalies.json()
            assert anomaly_json["total"] == 2
            assert len(anomaly_json["items"]) == 2

            report = client.get("/api/reports/export?only_anomalies=true")
            assert report.status_code == 200, report.text
            assert report.headers["content-type"].startswith("text/csv")
            csv_rows = list(csv.reader(io.StringIO(report.text)))
            assert len(csv_rows) == 2
            assert csv_rows[0][0] == "id"
            assert csv_rows[1][1] == "agent-test-1"

            client.post("/api/auth/logout")
            after_logout = client.get("/api/auth/me")
            assert after_logout.status_code == 401
            stream_after_logout = client.get("/api/stream")
            assert stream_after_logout.status_code == 401

            login = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "supersecure123"},
            )
            assert login.status_code == 200, login.text
            assert login.json()["user"]["role"] == "admin"

    print("dashboard auth/report smoke test: PASS")


if __name__ == "__main__":
    main()
