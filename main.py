"""Personal study desk: notes, Q&A cards, and SM-2 review in one library."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sm2 import schedule
from sync import client_payload, ensure_schema, export_state, import_state, lan_addresses, merge_state

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB_PATH = DATA / "learn.db"
STATIC = ROOT / "static"

app = FastAPI(title="自习室")


def connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY,
                domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
                note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                ease REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 0,
                repetitions INTEGER NOT NULL DEFAULT 0,
                due TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                quality INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                interval_after INTEGER NOT NULL,
                ease_after REAL NOT NULL
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(cards)")}
        if "mastery" not in columns:
            conn.execute("ALTER TABLE cards ADD COLUMN mastery TEXT NOT NULL DEFAULT '一般'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_reads (
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                PRIMARY KEY (card_id, day)
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) AS n FROM domains").fetchone()["n"]
        if count == 0:
            seed(conn)
        ensure_schema(conn)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> date:
    return date.today()


def seed(conn: sqlite3.Connection) -> None:
    stamp = now_iso()
    due = today().isoformat()
    domains = {}
    for name in ("AI", "英语"):
        cur = conn.execute(
            "INSERT INTO domains (name, created_at) VALUES (?, ?)",
            (name, stamp),
        )
        domains[name] = cur.lastrowid
        conn.execute("UPDATE domains SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))

    notes = [
        (
            domains["AI"],
            "过拟合和泛化",
            "过拟合：模型把训练集里的噪声也记住了，换一批数据就变差。\n"
            "泛化：模型在没见过的数据上仍然表现稳定。\n"
            "常见对策：更多数据、正则化、提前停止、交叉验证。",
        ),
        (
            domains["英语"],
            "读文档时先抓的句子",
            "遇到英文文档，先把定义句做成卡片，不要整段翻译。\n"
            "卡片正面用英文原句，背面用自己的中文解释加一个自己造的例句。",
        ),
    ]
    note_ids = []
    for domain_id, title, body in notes:
        cur = conn.execute(
            "INSERT INTO notes (domain_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (domain_id, title, body, stamp, stamp),
        )
        note_ids.append(cur.lastrowid)
        conn.execute("UPDATE notes SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))

    cards = [
        (domains["AI"], note_ids[0], "什么是过拟合？", "模型在训练集上很好，在新数据上变差。它记住了噪声，而不是规律。"),
        (domains["AI"], note_ids[0], "What does it mean when a model generalizes?", "模型能在没见过的数据上保持稳定表现，而不是只会做训练题。"),
        (domains["AI"], None, "梯度下降在做什么？", "沿损失下降最快的方向小步更新参数，让预测越来越接近目标。"),
        (domains["AI"], None, "What is a learning rate?", "更新参数时的步长。太大容易越过最优点，太小则学得很慢。"),
        (domains["AI"], None, "训练集、验证集、测试集分别用来做什么？", "训练集用来学习参数；验证集用来选模型和调参；测试集只在最后评估一次，避免被反复偷看。"),
        (domains["英语"], note_ids[1], "overfit the training set", "在训练集上过拟合。例句：The model overfit the training set and failed on new users."),
        (domains["英语"], note_ids[1], "The model generalizes well to unseen data.", "这个模型对没见过的数据也能泛化得不错。"),
        (domains["英语"], None, "hold out a test set", "留出一份测试集，训练过程中不使用它。"),
    ]
    for domain_id, note_id, front, back in cards:
        cur = conn.execute(
            """
            INSERT INTO cards
                (domain_id, note_id, front, back, ease, interval_days, repetitions, due, created_at)
            VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?)
            """,
            (domain_id, note_id, front, back, due, stamp),
        )
        conn.execute(
            "UPDATE cards SET uid = ?, content_at = ?, schedule_at = ? WHERE id = ?",
            (f"pc-{cur.lastrowid}", stamp, stamp, cur.lastrowid),
        )


class DomainIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class NoteIn(BaseModel):
    domain_id: int
    title: str = Field(min_length=1, max_length=120)
    body: str = ""


class CardIn(BaseModel):
    domain_id: int
    note_id: int | None = None
    front: str = Field(min_length=1, max_length=800)
    back: str = Field(min_length=1, max_length=20000)


class ReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5)


class ImportIn(BaseModel):
    domain_id: int
    text: str = Field(min_length=1)
    as_note_title: str = "导入的笔记"


def row_domain(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"]}


def row_note(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "domain_id": row["domain_id"],
        "domain": row["domain"],
        "title": row["title"],
        "body": row["body"],
        "updated_at": row["updated_at"],
    }


def row_card(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "domain_id": row["domain_id"],
        "domain": row["domain"],
        "note_id": row["note_id"],
        "front": row["front"],
        "back": row["back"],
        "ease": row["ease"],
        "interval_days": row["interval_days"],
        "repetitions": row["repetitions"],
        "due": row["due"],
        "mastery": row["mastery"] if "mastery" in row.keys() else "一般",
        "mastery_color": row["mastery_color"] if "mastery_color" in row.keys() else "",
        "studied_today": bool(row["studied_today"]) if "studied_today" in row.keys() else False,
    }


LEVELS = {"一般", "基本掌握", "熟练"}


class MasteryIn(BaseModel):
    level: str
    color: str = ""


def select_cards(conn: sqlite3.Connection, where: str, params: list) -> list[sqlite3.Row]:
    sql = f"""
        SELECT cards.*, domains.name AS domain,
          EXISTS(
            SELECT 1 FROM daily_reads
            WHERE daily_reads.card_id = cards.id AND daily_reads.day = ?
          ) AS studied_today
        FROM cards JOIN domains ON domains.id = cards.domain_id
        {where}
    """
    return conn.execute(sql, [today().isoformat(), *params]).fetchall()


def domain_progress(conn: sqlite3.Connection, domain_id: int) -> dict:
    day = today().isoformat()
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM cards WHERE domain_id = ?",
        (domain_id,),
    ).fetchone()["n"]
    reviewed = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM daily_reads JOIN cards ON cards.id = daily_reads.card_id
        WHERE cards.domain_id = ? AND daily_reads.day = ?
        """,
        (domain_id, day),
    ).fetchone()["n"]
    return {"reviewed": reviewed, "total": total}


def require_domain(conn: sqlite3.Connection, domain_id: int) -> None:
    found = conn.execute("SELECT id FROM domains WHERE id = ?", (domain_id,)).fetchone()
    if not found:
        raise HTTPException(404, "领域不存在")


def parse_cards(text: str) -> list[tuple[str, str]]:
    cards: list[tuple[str, str]] = []
    blocks = [block.strip() for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
    for block in blocks:
        front = ""
        back_lines: list[str] = []
        mode = ""
        for line in block.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if stripped.startswith("问：") or stripped.startswith("问:"):
                front = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                mode = "front"
            elif lower.startswith("q:") or lower.startswith("q："):
                front = stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
                mode = "front"
            elif stripped.startswith("答：") or stripped.startswith("答:"):
                back_lines = [stripped.split("：", 1)[-1].split(":", 1)[-1].strip()]
                mode = "back"
            elif lower.startswith("a:") or lower.startswith("a："):
                back_lines = [stripped.split(":", 1)[-1].split("：", 1)[-1].strip()]
                mode = "back"
            elif mode == "back":
                back_lines.append(stripped)
            elif mode == "front" and not front:
                front = stripped
        back = "\n".join(line for line in back_lines if line).strip()
        if front and back:
            cards.append((front, back))
    return cards


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/domains")
def list_domains() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, name FROM domains ORDER BY id").fetchall()
    return [row_domain(row) for row in rows]


@app.post("/api/domains")
def create_domain(payload: DomainIn) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO domains (name, created_at, uid) VALUES (?, ?, ?)",
                (name, now_iso(), ""),
            )
            conn.execute("UPDATE domains SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "这个领域已经有了") from None
        row = conn.execute("SELECT id, name FROM domains WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_domain(row)


@app.delete("/api/domains/{domain_id}")
def delete_domain(domain_id: int) -> dict:
    with connect() as conn:
        cur = conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "领域不存在")
    return {"ok": True}


@app.get("/api/notes")
def list_notes(domain_id: int | None = None) -> list[dict]:
    sql = """
        SELECT notes.*, domains.name AS domain
        FROM notes JOIN domains ON domains.id = notes.domain_id
    """
    params: tuple = ()
    if domain_id is not None:
        sql += " WHERE notes.domain_id = ?"
        params = (domain_id,)
    sql += " ORDER BY notes.updated_at DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_note(row) for row in rows]


@app.post("/api/notes")
def create_note(payload: NoteIn) -> dict:
    stamp = now_iso()
    with connect() as conn:
        require_domain(conn, payload.domain_id)
        cur = conn.execute(
            "INSERT INTO notes (domain_id, title, body, created_at, updated_at, uid) VALUES (?, ?, ?, ?, ?, ?)",
            (payload.domain_id, payload.title.strip(), payload.body.strip(), stamp, stamp, ""),
        )
        conn.execute("UPDATE notes SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))
        row = conn.execute(
            """
            SELECT notes.*, domains.name AS domain
            FROM notes JOIN domains ON domains.id = notes.domain_id
            WHERE notes.id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    return row_note(row)


@app.put("/api/notes/{note_id}")
def update_note(note_id: int, payload: NoteIn) -> dict:
    with connect() as conn:
        require_domain(conn, payload.domain_id)
        cur = conn.execute(
            "UPDATE notes SET domain_id = ?, title = ?, body = ?, updated_at = ? WHERE id = ?",
            (payload.domain_id, payload.title.strip(), payload.body.strip(), now_iso(), note_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "笔记不存在")
        row = conn.execute(
            """
            SELECT notes.*, domains.name AS domain
            FROM notes JOIN domains ON domains.id = notes.domain_id
            WHERE notes.id = ?
            """,
            (note_id,),
        ).fetchone()
    return row_note(row)


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT uid FROM notes WHERE id = ?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(404, "笔记不存在")
        conn.execute(
            "INSERT OR REPLACE INTO tombstones (kind, uid, deleted_at) VALUES ('note', ?, ?)",
            (row["uid"], now_iso()),
        )
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return {"ok": True}


@app.get("/api/cards")
def list_cards(domain_id: int | None = None) -> list[dict]:
    where = "ORDER BY cards.due, cards.id"
    params: list = []
    if domain_id is not None:
        where = "WHERE cards.domain_id = ? ORDER BY cards.due, cards.id"
        params = [domain_id]
    with connect() as conn:
        rows = select_cards(conn, where, params)
    return [row_card(row) for row in rows]


@app.post("/api/cards")
def create_card(payload: CardIn) -> dict:
    with connect() as conn:
        require_domain(conn, payload.domain_id)
        stamp = now_iso()
        cur = conn.execute(
            """
            INSERT INTO cards
                (domain_id, note_id, front, back, ease, interval_days, repetitions, due, created_at, mastery, uid, content_at, schedule_at)
            VALUES (?, ?, ?, ?, 2.5, 0, 0, ?, ?, '一般', '', ?, ?)
            """,
            (
                payload.domain_id,
                payload.note_id,
                payload.front.strip(),
                payload.back.strip(),
                today().isoformat(),
                stamp,
                stamp,
                stamp,
            ),
        )
        conn.execute("UPDATE cards SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))
        row = select_cards(conn, "WHERE cards.id = ?", [cur.lastrowid])[0]
    return row_card(row)


@app.put("/api/cards/{card_id}")
def update_card(card_id: int, payload: CardIn) -> dict:
    with connect() as conn:
        require_domain(conn, payload.domain_id)
        cur = conn.execute(
            "UPDATE cards SET domain_id = ?, note_id = ?, front = ?, back = ?, content_at = ? WHERE id = ?",
            (payload.domain_id, payload.note_id, payload.front.strip(), payload.back.strip(), now_iso(), card_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "卡片不存在")
        rows = select_cards(conn, "WHERE cards.id = ?", [card_id])
    return row_card(rows[0])


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT uid FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not row:
            raise HTTPException(404, "卡片不存在")
        conn.execute(
            "INSERT OR REPLACE INTO tombstones (kind, uid, deleted_at) VALUES ('card', ?, ?)",
            (row["uid"], now_iso()),
        )
        conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    return {"ok": True}


@app.get("/api/review")
def review_queue(domain_id: int | None = None) -> dict:
    where = "WHERE cards.due <= ?"
    params: list = [today().isoformat()]
    if domain_id is not None:
        where += " AND cards.domain_id = ?"
        params.append(domain_id)
    where += " ORDER BY cards.due, cards.id"
    with connect() as conn:
        rows = select_cards(conn, where, params)
        nxt = conn.execute(
            "SELECT MIN(due) AS due FROM cards WHERE due > ?",
            (today().isoformat(),),
        ).fetchone()
    return {
        "due_on": today().isoformat(),
        "cards": [row_card(row) for row in rows],
        "next_due": nxt["due"] if nxt else None,
    }


@app.post("/api/cards/{card_id}/review")
def review_card(card_id: int, payload: ReviewIn) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not row:
            raise HTTPException(404, "卡片不存在")
        repetitions, ease, interval = schedule(
            payload.quality,
            row["repetitions"],
            row["ease"],
            row["interval_days"],
        )
        due = (today() + timedelta(days=interval)).isoformat()
        conn.execute(
            """
            UPDATE cards
            SET repetitions = ?, ease = ?, interval_days = ?, due = ?, schedule_at = ?
            WHERE id = ?
            """,
            (repetitions, ease, interval, due, now_iso(), card_id),
        )
        review = conn.execute(
            """
            INSERT INTO reviews (card_id, quality, reviewed_at, interval_after, ease_after)
            VALUES (?, ?, ?, ?, ?)
            """,
            (card_id, payload.quality, now_iso(), interval, ease),
        )
        conn.execute(
            "UPDATE reviews SET uid = ? WHERE id = ?",
            (f"pc-{review.lastrowid}", review.lastrowid),
        )
    return {"due": due, "interval_days": interval, "ease": ease, "repetitions": repetitions}


@app.post("/api/cards/{card_id}/mastery")
def set_mastery(card_id: int, payload: MasteryIn) -> dict:
    if payload.level not in LEVELS:
        raise HTTPException(400, "掌握程度只能是一般、基本掌握或熟练")
    with connect() as conn:
        color = payload.color if payload.color.startswith("#") and len(payload.color) == 7 else ""
        cur = conn.execute(
            "UPDATE cards SET mastery = ?, mastery_color = ?, content_at = ? WHERE id = ?",
            (payload.level, color, now_iso(), card_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "卡片不存在")
    return {"id": card_id, "mastery": payload.level, "mastery_color": color}


@app.post("/api/cards/{card_id}/studied")
def mark_studied(card_id: int) -> dict:
    day = today().isoformat()
    with connect() as conn:
        row = conn.execute("SELECT domain_id FROM cards WHERE id = ?", (card_id,)).fetchone()
        if not row:
            raise HTTPException(404, "卡片不存在")
        cur = conn.execute(
            "INSERT OR IGNORE INTO daily_reads (card_id, day) VALUES (?, ?)",
            (card_id, day),
        )
        progress = domain_progress(conn, row["domain_id"])
    return {"studied_today": True, "counted": cur.rowcount == 1, **progress}


@app.get("/api/progress")
def progress(domain_id: int) -> dict:
    with connect() as conn:
        require_domain(conn, domain_id)
        return domain_progress(conn, domain_id)


@app.post("/api/import")
def import_text(payload: ImportIn) -> dict:
    cards = parse_cards(payload.text)
    stamp = now_iso()
    due = today().isoformat()
    with connect() as conn:
        require_domain(conn, payload.domain_id)
        if cards:
            for front, back in cards:
                cur = conn.execute(
                    """
                    INSERT INTO cards
                        (domain_id, note_id, front, back, ease, interval_days, repetitions, due, created_at, content_at, schedule_at)
                    VALUES (?, NULL, ?, ?, 2.5, 0, 0, ?, ?, ?, ?)
                    """,
                    (payload.domain_id, front, back, due, stamp, stamp, stamp),
                )
                conn.execute("UPDATE cards SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))
            return {"cards": len(cards), "notes": 0}
        title = payload.as_note_title.strip() or "导入的笔记"
        cur = conn.execute(
            "INSERT INTO notes (domain_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (payload.domain_id, title, payload.text.strip(), stamp, stamp),
        )
        conn.execute("UPDATE notes SET uid = ? WHERE id = ?", (f"pc-{cur.lastrowid}", cur.lastrowid))
    return {"cards": 0, "notes": 1}


def streak_from(dates: list[str]) -> int:
    if not dates:
        return 0
    seen = {date.fromisoformat(item) for item in dates}
    cursor = today()
    if cursor not in seen:
        cursor -= timedelta(days=1)
        if cursor not in seen:
            return 0
    count = 0
    while cursor in seen:
        count += 1
        cursor -= timedelta(days=1)
    return count


@app.get("/api/stats")
def stats() -> dict:
    start = today() - timedelta(days=6)
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM cards").fetchone()["n"]
        due = conn.execute(
            "SELECT COUNT(*) AS n FROM cards WHERE due <= ?",
            (today().isoformat(),),
        ).fetchone()["n"]
        reviewed_today = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE reviewed_at >= ?",
            (today().isoformat(),),
        ).fetchone()["n"]
        remembered = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE reviewed_at >= ? AND quality >= 3",
            (today().isoformat(),),
        ).fetchone()["n"]
        by_domain = conn.execute(
            """
            SELECT domains.name AS name, COUNT(cards.id) AS cards
            FROM domains LEFT JOIN cards ON cards.domain_id = domains.id
            GROUP BY domains.id
            ORDER BY domains.id
            """
        ).fetchall()
        recent = conn.execute(
            """
            SELECT substr(reviewed_at, 1, 10) AS day, COUNT(*) AS n
            FROM reviews
            WHERE reviewed_at >= ?
            GROUP BY day
            """,
            (start.isoformat(),),
        ).fetchall()
        all_days = conn.execute(
            "SELECT DISTINCT substr(reviewed_at, 1, 10) AS day FROM reviews"
        ).fetchall()
    counts = {row["day"]: row["n"] for row in recent}
    days = []
    for offset in range(6, -1, -1):
        day = (today() - timedelta(days=offset)).isoformat()
        days.append({"day": day[5:], "count": counts.get(day, 0)})
    return {
        "total_cards": total,
        "due": due,
        "reviewed_today": reviewed_today,
        "remembered_today": remembered,
        "streak": streak_from([row["day"] for row in all_days]),
        "domains": [{"name": row["name"], "cards": row["cards"]} for row in by_domain],
        "days": days,
    }


@app.get("/api/info")
def info() -> dict:
    return {"addresses": lan_addresses()}


@app.post("/api/sync")
def sync_library(payload: dict) -> dict:
    try:
        client = client_payload(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    with connect() as conn:
        server = export_state(conn)
        merged = merge_state(server, client)
        import_state(conn, merged)
        return export_state(conn)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
