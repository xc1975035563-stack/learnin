"""Merge the phone library into the computer library and write one shared copy back."""

from __future__ import annotations

import json
import random
import socket
import sqlite3
from datetime import datetime
from pathlib import Path


MASTERY_COLORS = (
    "#c44536", "#d97706", "#0f766e", "#1d4e89", "#6d28d9", "#be185d",
    "#3f6212", "#b45309", "#0369a1", "#9f1239", "#0e7490", "#7c3aed",
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    def add(table: str, column: str, definition: str) -> None:
        names = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    add("domains", "uid", "TEXT")
    add("notes", "uid", "TEXT")
    add("cards", "uid", "TEXT")
    add("cards", "content_at", "TEXT")
    add("cards", "schedule_at", "TEXT")
    add("cards", "mastery_color", "TEXT")
    add("reviews", "uid", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tombstones (
            kind TEXT NOT NULL,
            uid TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            PRIMARY KEY (kind, uid)
        )
        """
    )
    for table in ("domains", "notes", "cards", "reviews"):
        conn.execute(
            f"UPDATE {table} SET uid = 'pc-' || id WHERE uid IS NULL OR uid = ''"
        )
    conn.execute(
        """
        UPDATE cards
        SET content_at = ?
        WHERE content_at IS NULL OR content_at = ''
        """,
        (now_iso(),),
    )
    conn.execute(
        """
        UPDATE cards
        SET schedule_at = COALESCE(
            (SELECT MAX(reviews.reviewed_at) FROM reviews WHERE reviews.card_id = cards.id),
            created_at
        )
        WHERE schedule_at IS NULL OR schedule_at = ''
        """
    )
    missing = conn.execute(
        "SELECT id FROM cards WHERE mastery_color IS NULL OR mastery_color = ''"
    ).fetchall()
    for row in missing:
        conn.execute(
            "UPDATE cards SET mastery_color = ? WHERE id = ?",
            (random.choice(MASTERY_COLORS), row["id"]),
        )


def _rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(row) for row in conn.execute(sql)]


def export_state(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    domains = _rows(conn, "SELECT id, uid, name, created_at FROM domains ORDER BY id")
    notes = _rows(
        conn,
        "SELECT id, uid, domain_id, title, body, created_at, updated_at FROM notes ORDER BY id",
    )
    cards = _rows(
        conn,
        """
        SELECT id, uid, domain_id, note_id, front, back, ease, interval_days, repetitions,
               due, created_at, mastery, mastery_color, content_at, schedule_at
        FROM cards ORDER BY id
        """,
    )
    studied: dict[int, list[str]] = {}
    for row in conn.execute("SELECT card_id, day FROM daily_reads ORDER BY day"):
        studied.setdefault(row["card_id"], []).append(row["day"])
    for card in cards:
        card["studied_days"] = studied.get(card["id"], [])
        card["mastery"] = card["mastery"] or "一般"
    reviews = _rows(
        conn,
        """
        SELECT id, uid, card_id, quality, reviewed_at, interval_after, ease_after
        FROM reviews ORDER BY id
        """,
    )
    tombstones = _rows(conn, "SELECT kind, uid, deleted_at FROM tombstones ORDER BY deleted_at")

    def nxt(items: list[dict]) -> int:
        return max((item["id"] for item in items), default=0) + 1

    return {
        "domains": domains,
        "notes": notes,
        "cards": cards,
        "reviews": reviews,
        "tombstones": tombstones,
        "next": {
            "domain": nxt(domains),
            "note": nxt(notes),
            "card": nxt(cards),
            "review": nxt(reviews),
        },
    }


def _index(items: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in items if item.get(key)}


def _alias_domains(server: list[dict], client: list[dict]) -> tuple[list[dict], dict[str, str]]:
    by_name: dict[str, dict] = {}
    alias: dict[str, str] = {}
    for item in server + client:
        name = str(item.get("name") or "").strip()
        uid = item.get("uid")
        if not name or not uid:
            continue
        kept = by_name.get(name)
        if kept is None:
            by_name[name] = {
                "uid": uid,
                "name": name,
                "created_at": item.get("created_at") or now_iso(),
                "id": item.get("id"),
            }
            alias[uid] = uid
        else:
            alias[uid] = kept["uid"]
    return list(by_name.values()), alias


def _newer(left: str | None, right: str | None) -> bool:
    return (left or "") >= (right or "")


def merge_state(server: dict, client: dict) -> dict:
    domains, alias = _alias_domains(server.get("domains") or [], client.get("domains") or [])

    def domain_uid_of(item: dict) -> str | None:
        if item.get("domain_uid"):
            return alias.get(item["domain_uid"], item["domain_uid"])
        domain_id = item.get("domain_id")
        for source in (server, client):
            for domain in source.get("domains") or []:
                if domain.get("id") == domain_id and domain.get("uid"):
                    return alias.get(domain["uid"], domain["uid"])
        return None

    notes: dict[str, dict] = {}
    for source in (server, client):
        for item in source.get("notes") or []:
            uid = item.get("uid")
            if not uid:
                continue
            domain_uid = domain_uid_of(item)
            note = {
                "uid": uid,
                "domain_uid": domain_uid,
                "title": item.get("title") or "",
                "body": item.get("body") or "",
                "created_at": item.get("created_at") or now_iso(),
                "updated_at": item.get("updated_at") or item.get("created_at") or "",
                "id": item.get("id"),
            }
            current = notes.get(uid)
            if current is None or _newer(note["updated_at"], current["updated_at"]):
                notes[uid] = note

    def card_note_uid(item: dict) -> str | None:
        if item.get("note_uid"):
            return item["note_uid"]
        note_id = item.get("note_id")
        if not note_id:
            return None
        for source in (server, client):
            for note in source.get("notes") or []:
                if note.get("id") == note_id and note.get("uid"):
                    return note["uid"]
        return None

    cards: dict[str, dict] = {}
    for source in (server, client):
        for item in source.get("cards") or []:
            uid = item.get("uid")
            if not uid:
                continue
            card = {
                "uid": uid,
                "domain_uid": domain_uid_of(item),
                "note_uid": card_note_uid(item),
                "front": item.get("front") or "",
                "back": item.get("back") or "",
                "ease": item.get("ease") if item.get("ease") is not None else 2.5,
                "interval_days": item.get("interval_days") or 0,
                "repetitions": item.get("repetitions") or 0,
                "due": item.get("due") or "",
                "created_at": item.get("created_at") or now_iso(),
                "mastery": item.get("mastery") or "一般",
                "mastery_color": item.get("mastery_color") or "",
                "studied_days": list(item.get("studied_days") or []),
                "content_at": item.get("content_at") or item.get("created_at") or "",
                "schedule_at": item.get("schedule_at") or item.get("created_at") or "",
                "id": item.get("id"),
            }
            current = cards.get(uid)
            if current is None:
                cards[uid] = card
                continue
            winner = card if _newer(card["content_at"], current["content_at"]) else current
            schedule = card if _newer(card["schedule_at"], current["schedule_at"]) else current
            merged = dict(winner)
            merged["ease"] = schedule["ease"]
            merged["interval_days"] = schedule["interval_days"]
            merged["repetitions"] = schedule["repetitions"]
            merged["due"] = schedule["due"]
            merged["schedule_at"] = schedule["schedule_at"]
            merged["studied_days"] = sorted(set(current["studied_days"]) | set(card["studied_days"]))
            cards[uid] = merged

    reviews: dict[str, dict] = {}
    for source in (server, client):
        id_to_uid = {card.get("id"): card.get("uid") for card in source.get("cards") or [] if card.get("uid")}
        for item in source.get("reviews") or []:
            uid = item.get("uid")
            if not uid:
                continue
            card_uid = item.get("card_uid") or id_to_uid.get(item.get("card_id"))
            reviews[uid] = {
                "uid": uid,
                "card_uid": card_uid,
                "quality": item.get("quality"),
                "reviewed_at": item.get("reviewed_at") or "",
                "interval_after": item.get("interval_after") or 0,
                "ease_after": item.get("ease_after") if item.get("ease_after") is not None else 2.5,
                "id": item.get("id"),
            }

    tombstones: dict[tuple[str, str], dict] = {}
    for item in (server.get("tombstones") or []) + (client.get("tombstones") or []):
        kind = item.get("kind")
        uid = item.get("uid")
        if kind not in {"note", "card"} or not uid:
            continue
        current = tombstones.get((kind, uid))
        if current is None or _newer(item.get("deleted_at"), current.get("deleted_at")):
            tombstones[(kind, uid)] = {"kind": kind, "uid": uid, "deleted_at": item.get("deleted_at") or ""}

    for (kind, uid), tomb in list(tombstones.items()):
        if kind == "note":
            note = notes.get(uid)
            if note and _newer(tomb["deleted_at"], note["updated_at"]):
                notes.pop(uid, None)
            elif note:
                tombstones.pop((kind, uid), None)
        if kind == "card":
            card = cards.get(uid)
            if card and _newer(tomb["deleted_at"], card["content_at"]) and _newer(tomb["deleted_at"], card["schedule_at"]):
                cards.pop(uid, None)
                reviews = {key: value for key, value in reviews.items() if value.get("card_uid") != uid}
            elif card:
                tombstones.pop((kind, uid), None)

    def assign(items: list[dict], existing_ids: dict[str, int]) -> None:
        used = set(existing_ids.values())
        nxt = max(used, default=0) + 1
        for item in items:
            found = existing_ids.get(item["uid"])
            if found:
                item["id"] = found
                continue
            while nxt in used:
                nxt += 1
            item["id"] = nxt
            used.add(nxt)
            nxt += 1

    assign(domains, {item["uid"]: item["id"] for item in server.get("domains") or [] if item.get("id")})
    domain_id_by_uid = {item["uid"]: item["id"] for item in domains}
    note_items = list(notes.values())
    assign(note_items, {item["uid"]: item["id"] for item in server.get("notes") or [] if item.get("id")})
    note_id_by_uid = {item["uid"]: item["id"] for item in note_items}
    for note in note_items:
        note["domain_id"] = domain_id_by_uid.get(note["domain_uid"])
        note.pop("domain_uid", None)
    note_items = [note for note in note_items if note.get("domain_id")]

    card_items = list(cards.values())
    assign(card_items, {item["uid"]: item["id"] for item in server.get("cards") or [] if item.get("id")})
    card_id_by_uid = {item["uid"]: item["id"] for item in card_items}
    for card in card_items:
        card["domain_id"] = domain_id_by_uid.get(card["domain_uid"])
        card["note_id"] = note_id_by_uid.get(card["note_uid"]) if card.get("note_uid") else None
        card.pop("domain_uid", None)
        card.pop("note_uid", None)
    card_items = [card for card in card_items if card.get("domain_id") and card.get("front") and card.get("back")]

    review_items = [item for item in reviews.values() if item.get("card_uid") in card_id_by_uid]
    assign(review_items, {item["uid"]: item["id"] for item in server.get("reviews") or [] if item.get("id")})
    for review in review_items:
        review["card_id"] = card_id_by_uid[review["card_uid"]]
        review.pop("card_uid", None)

    def ordered(items: list[dict]) -> list[dict]:
        return sorted(items, key=lambda item: item["id"])

    domains = ordered(domains)
    note_items = ordered(note_items)
    card_items = ordered(card_items)
    review_items = ordered(review_items)

    def nxt(items: list[dict]) -> int:
        return max((item["id"] for item in items), default=0) + 1

    return {
        "domains": domains,
        "notes": note_items,
        "cards": card_items,
        "reviews": review_items,
        "tombstones": sorted(tombstones.values(), key=lambda item: (item["kind"], item["uid"])),
        "next": {
            "domain": nxt(domains),
            "note": nxt(note_items),
            "card": nxt(card_items),
            "review": nxt(review_items),
        },
    }


def import_state(conn: sqlite3.Connection, state: dict) -> None:
    ensure_schema(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM reviews")
    conn.execute("DELETE FROM daily_reads")
    conn.execute("DELETE FROM cards")
    conn.execute("DELETE FROM notes")
    conn.execute("DELETE FROM domains")
    conn.execute("DELETE FROM tombstones")
    for domain in state["domains"]:
        conn.execute(
            "INSERT INTO domains (id, uid, name, created_at) VALUES (?, ?, ?, ?)",
            (domain["id"], domain["uid"], domain["name"], domain["created_at"]),
        )
    for note in state["notes"]:
        conn.execute(
            """
            INSERT INTO notes (id, uid, domain_id, title, body, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note["id"], note["uid"], note["domain_id"], note["title"], note["body"],
                note["created_at"], note["updated_at"],
            ),
        )
    for card in state["cards"]:
        conn.execute(
            """
            INSERT INTO cards (
                id, uid, domain_id, note_id, front, back, ease, interval_days, repetitions,
                due, created_at, mastery, mastery_color, content_at, schedule_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card["id"], card["uid"], card["domain_id"], card.get("note_id"), card["front"], card["back"],
                card["ease"], card["interval_days"], card["repetitions"], card["due"], card["created_at"],
                card.get("mastery") or "一般", card.get("mastery_color") or "", card["content_at"], card["schedule_at"],
            ),
        )
        for day in card.get("studied_days") or []:
            conn.execute(
                "INSERT OR IGNORE INTO daily_reads (card_id, day) VALUES (?, ?)",
                (card["id"], day),
            )
    for review in state["reviews"]:
        conn.execute(
            """
            INSERT INTO reviews (id, uid, card_id, quality, reviewed_at, interval_after, ease_after)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review["id"], review["uid"], review["card_id"], review["quality"], review["reviewed_at"],
                review["interval_after"], review["ease_after"],
            ),
        )
    for tomb in state["tombstones"]:
        conn.execute(
            "INSERT INTO tombstones (kind, uid, deleted_at) VALUES (?, ?, ?)",
            (tomb["kind"], tomb["uid"], tomb["deleted_at"]),
        )
    conn.execute("PRAGMA foreign_keys = ON")


def client_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("同步内容不是对象")
    for key in ("domains", "notes", "cards", "reviews", "tombstones"):
        if payload.get(key) is None:
            payload[key] = []
        if not isinstance(payload[key], list):
            raise ValueError("同步内容不完整")
    return payload


def _usable(ip: str, name: str = "") -> bool:
    if not ip or ip.startswith("127.") or ip.startswith("169.254.") or ip.startswith("198.18."):
        return False
    lowered = name.lower()
    blocked = ("vmware", "virtual", "vpn", "bluetooth", "loopback", "vethernet", "蓝牙", "本地连接")
    return not any(word in lowered for word in blocked)


def _local_ips() -> list[str]:
    ips: list[str] = []

    def add(ip: str, name: str = "") -> None:
        if _usable(ip, name) and ip not in ips:
            ips.append(ip)

    try:
        import subprocess

        raw = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress, InterfaceAlias | ConvertTo-Json"],
            text=True,
            timeout=8,
        )
        parsed = json.loads(raw)
        rows = parsed if isinstance(parsed, list) else [parsed]
        for row in rows:
            add(row.get("IPAddress", ""), row.get("InterfaceAlias", ""))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        pass
    if ips:
        return ips
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    return ips


def lan_addresses(port: int = 8765) -> list[str]:
    addresses = [f"http://127.0.0.1:{port}", *[f"http://{ip}:{port}" for ip in _local_ips()]]
    tunnel = Path(__file__).resolve().parent / "data" / "tunnel_url.txt"
    if tunnel.exists():
        public = tunnel.read_text(encoding="utf-8").strip()
        if public.startswith("https://") and public not in addresses:
            addresses.append(public)
    return addresses
