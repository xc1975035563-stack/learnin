const { schedule } = require("./sm2");

const LEVELS = ["一般", "基本掌握", "熟练"];
const KEY = "study-room-v1";

function pad(number) {
  return String(number).padStart(2, "0");
}

function today() {
  const date = new Date();
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function nowIso() {
  const date = new Date();
  return `${today()}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function addDays(iso, days) {
  const parts = iso.split("-").map(Number);
  const date = new Date(parts[0], parts[1] - 1, parts[2]);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function parseCards(text) {
  const cards = [];
  const blocks = String(text).replace(/\r\n/g, "\n").split("\n\n").map((block) => block.trim()).filter(Boolean);
  blocks.forEach((block) => {
    let front = "";
    let backLines = [];
    let mode = "";
    block.split("\n").forEach((line) => {
      const stripped = line.trim();
      const lower = stripped.toLowerCase();
      const tail = (value) => {
        const full = value.includes("：") ? value.split("：").slice(1).join("：") : value;
        return (full.includes(":") ? full.split(":").slice(1).join(":") : full).trim();
      };
      if (stripped.startsWith("问：") || stripped.startsWith("问:")) {
        front = tail(stripped);
        mode = "front";
      } else if (lower.startsWith("q:") || lower.startsWith("q：")) {
        front = tail(stripped);
        mode = "front";
      } else if (stripped.startsWith("答：") || stripped.startsWith("答:")) {
        backLines = [tail(stripped)];
        mode = "back";
      } else if (lower.startsWith("a:") || lower.startsWith("a：")) {
        backLines = [tail(stripped)];
        mode = "back";
      } else if (mode === "back") {
        backLines.push(stripped);
      } else if (mode === "front" && !front) {
        front = stripped;
      }
    });
    const back = backLines.filter(Boolean).join("\n").trim();
    if (front && back) cards.push([front, back]);
  });
  return cards;
}

function streakFrom(dates) {
  if (!dates.length) return 0;
  const seen = {};
  dates.forEach((item) => { seen[item] = true; });
  let cursor = today();
  if (!seen[cursor]) {
    cursor = addDays(cursor, -1);
    if (!seen[cursor]) return 0;
  }
  let count = 0;
  while (seen[cursor]) {
    count += 1;
    cursor = addDays(cursor, -1);
  }
  return count;
}

function createStore(storage, seed) {
  function ensure(db) {
    let changed = false;
    if (!db.device_id) {
      db.device_id = `wx-${Math.random().toString(36).slice(2, 10)}`;
      changed = true;
    }
    if (!db.tombstones) {
      db.tombstones = [];
      changed = true;
    }
    const seeded = {
      domain: new Set(seed.domains.map((item) => item.id)),
      note: new Set(seed.notes.map((item) => item.id)),
      card: new Set(seed.cards.map((item) => item.id)),
      review: new Set((seed.reviews || []).map((item) => item.id)),
    };
    const assign = (row, kind) => {
      if (row.uid) return;
      row.uid = seeded[kind].has(row.id) ? `pc-${row.id}` : `${db.device_id}-${row.id}`;
      changed = true;
    };
    db.domains.forEach((row) => assign(row, "domain"));
    db.notes.forEach((row) => assign(row, "note"));
    db.cards.forEach((row) => {
      assign(row, "card");
      if (!row.content_at) {
        row.content_at = row.created_at;
        changed = true;
      }
      if (!row.schedule_at) {
        row.schedule_at = row.created_at;
        changed = true;
      }
      if (!row.studied_days) {
        row.studied_days = [];
        changed = true;
      }
    });
    (db.reviews || []).forEach((row) => assign(row, "review"));
    return changed;
  }

  function load() {
    let saved = storage.get();
    if (!saved || !saved.domains || !saved.cards) saved = clone(seed);
    if (ensure(saved)) storage.set(saved);
    return saved;
  }

  function save(db) {
    storage.set(db);
    return db;
  }

  function domainName(db, id) {
    const found = db.domains.find((item) => item.id === id);
    return found ? found.name : "";
  }

  function presentCard(db, card) {
    return Object.assign({}, card, {
      domain: domainName(db, card.domain_id),
      studied_today: (card.studied_days || []).indexOf(today()) >= 0,
    });
  }

  function requireDomain(db, domainId) {
    if (!db.domains.some((item) => item.id === domainId)) {
      throw new Error("领域不存在");
    }
  }

  return {
    today,
    listDomains() {
      return load().domains.slice();
    },
    listNotes(domainId) {
      const db = load();
      return db.notes
        .filter((note) => domainId == null || note.domain_id === domainId)
        .map((note) => Object.assign({}, note, { domain: domainName(db, note.domain_id) }))
        .sort((left, right) => (left.updated_at < right.updated_at ? 1 : -1));
    },
    listCards(domainId) {
      const db = load();
      return db.cards
        .filter((card) => domainId == null || card.domain_id === domainId)
        .map((card) => presentCard(db, card))
        .sort((left, right) => (left.due === right.due ? left.id - right.id : left.due < right.due ? -1 : 1));
    },
    reviewQueue(domainId) {
      const db = load();
      const day = today();
      const cards = db.cards
        .filter((card) => card.due <= day && (domainId == null || card.domain_id === domainId))
        .map((card) => presentCard(db, card))
        .sort((left, right) => (left.due === right.due ? left.id - right.id : left.due < right.due ? -1 : 1));
      const later = db.cards.map((card) => card.due).filter((due) => due > day).sort();
      return { due_on: day, cards, next_due: later[0] || null };
    },
    progress(domainId) {
      const db = load();
      const day = today();
      const cards = db.cards.filter((card) => card.domain_id === domainId);
      const reviewed = cards.filter((card) => (card.studied_days || []).indexOf(day) >= 0).length;
      return { reviewed, total: cards.length };
    },
    createDomain(name) {
      const cleaned = String(name || "").trim();
      if (!cleaned) throw new Error("名称不能为空");
      const db = load();
      if (db.domains.some((item) => item.name === cleaned)) throw new Error("这个领域已经有了");
      const domain = { id: db.next.domain, uid: `${db.device_id}-domain-${db.next.domain}`, name: cleaned, created_at: nowIso() };
      db.next.domain += 1;
      db.domains.push(domain);
      save(db);
      return domain;
    },
    saveNote(payload) {
      const db = load();
      requireDomain(db, payload.domain_id);
      const stamp = nowIso();
      const title = String(payload.title || "").trim();
      const body = String(payload.body || "").trim();
      if (!title) throw new Error("标题不能为空");
      if (payload.id) {
        const note = db.notes.find((item) => item.id === payload.id);
        if (!note) throw new Error("笔记不存在");
        note.domain_id = payload.domain_id;
        note.title = title;
        note.body = body;
        note.updated_at = stamp;
      } else {
        db.notes.push({
          id: db.next.note,
          uid: `${db.device_id}-note-${db.next.note}`,
          domain_id: payload.domain_id,
          title,
          body,
          created_at: stamp,
          updated_at: stamp,
        });
        db.next.note += 1;
      }
      save(db);
    },
    deleteNote(id) {
      const db = load();
      const before = db.notes.length;
      const note = db.notes.find((item) => item.id === id);
      if (!note) throw new Error("笔记不存在");
      db.tombstones.push({ kind: "note", uid: note.uid, deleted_at: nowIso() });
      db.notes = db.notes.filter((item) => item.id !== id);
      if (db.notes.length === before) throw new Error("笔记不存在");
      db.cards.forEach((card) => {
        if (card.note_id === id) card.note_id = null;
      });
      save(db);
    },
    saveCard(payload) {
      const db = load();
      requireDomain(db, payload.domain_id);
      const front = String(payload.front || "").trim();
      const back = String(payload.back || "").trim();
      if (!front || !back) throw new Error("问题和答案都不能为空");
      if (payload.id) {
        const card = db.cards.find((item) => item.id === payload.id);
        if (!card) throw new Error("卡片不存在");
        card.domain_id = payload.domain_id;
        card.note_id = payload.note_id || null;
        card.front = front;
        card.back = back;
        card.content_at = nowIso();
      } else {
        const stamp = nowIso();
        db.cards.push({
          id: db.next.card,
          uid: `${db.device_id}-card-${db.next.card}`,
          domain_id: payload.domain_id,
          note_id: payload.note_id || null,
          front,
          back,
          ease: 2.5,
          interval_days: 0,
          repetitions: 0,
          due: today(),
          created_at: stamp,
          content_at: stamp,
          schedule_at: stamp,
          mastery: "一般",
          studied_days: [],
        });
        db.next.card += 1;
      }
      save(db);
    },
    deleteCard(id) {
      const db = load();
      const card = db.cards.find((item) => item.id === id);
      if (!card) throw new Error("卡片不存在");
      db.tombstones.push({ kind: "card", uid: card.uid, deleted_at: nowIso() });
      const before = db.cards.length;
      db.cards = db.cards.filter((item) => item.id !== id);
      if (db.cards.length === before) throw new Error("卡片不存在");
      db.reviews = db.reviews.filter((review) => review.card_id !== id);
      save(db);
    },
    rate(cardId, quality) {
      const db = load();
      const card = db.cards.find((item) => item.id === cardId);
      if (!card) throw new Error("卡片不存在");
      const result = schedule(Number(quality), card.repetitions, card.ease, card.interval_days);
      const stamp = nowIso();
      card.repetitions = result[0];
      card.ease = result[1];
      card.interval_days = result[2];
      card.due = addDays(today(), result[2]);
      card.schedule_at = stamp;
      db.reviews.push({
        id: db.next.review,
        uid: `${db.device_id}-review-${db.next.review}`,
        card_id: cardId,
        quality: Number(quality),
        reviewed_at: stamp,
        interval_after: result[2],
        ease_after: result[1],
      });
      db.next.review += 1;
      save(db);
      return { due: card.due, interval_days: card.interval_days, ease: card.ease, repetitions: card.repetitions };
    },
    setMastery(cardId, level, color) {
      if (LEVELS.indexOf(level) < 0) throw new Error("掌握程度只能是一般、基本掌握或熟练");
      const db = load();
      const card = db.cards.find((item) => item.id === cardId);
      if (!card) throw new Error("卡片不存在");
      card.mastery = level;
      card.mastery_color = color || "";
      card.content_at = nowIso();
      save(db);
    },
    markStudied(cardId) {
      const db = load();
      const card = db.cards.find((item) => item.id === cardId);
      if (!card) throw new Error("卡片不存在");
      card.studied_days = card.studied_days || [];
      const day = today();
      const counted = card.studied_days.indexOf(day) < 0;
      if (counted) card.studied_days.push(day);
      save(db);
      const progress = this.progress(card.domain_id);
      return Object.assign({ studied_today: true, counted }, progress);
    },
    importText(domainId, text) {
      const db = load();
      requireDomain(db, domainId);
      const cards = parseCards(text);
      const stamp = nowIso();
      if (cards.length) {
        cards.forEach((pair) => {
          db.cards.push({
            id: db.next.card,
            uid: `${db.device_id}-card-${db.next.card}`,
            domain_id: domainId,
            note_id: null,
            front: pair[0],
            back: pair[1],
            ease: 2.5,
            interval_days: 0,
            repetitions: 0,
            due: today(),
            created_at: stamp,
            content_at: stamp,
            schedule_at: stamp,
            mastery: "一般",
            studied_days: [],
          });
          db.next.card += 1;
        });
        save(db);
        return { cards: cards.length, notes: 0 };
      }
      db.notes.push({
        id: db.next.note,
        uid: `${db.device_id}-note-${db.next.note}`,
        domain_id: domainId,
        title: "导入的笔记",
        body: String(text || "").trim(),
        created_at: stamp,
        updated_at: stamp,
      });
      db.next.note += 1;
      save(db);
      return { cards: 0, notes: 1 };
    },
    stats() {
      const db = load();
      const day = today();
      const start = addDays(day, -6);
      const total = db.cards.length;
      const due = db.cards.filter((card) => card.due <= day).length;
      const todayReviews = db.reviews.filter((review) => review.reviewed_at.slice(0, 10) === day);
      const counts = {};
      db.reviews.forEach((review) => {
        const reviewDay = review.reviewed_at.slice(0, 10);
        if (reviewDay >= start) counts[reviewDay] = (counts[reviewDay] || 0) + 1;
      });
      const days = [];
      for (let offset = 6; offset >= 0; offset -= 1) {
        const key = addDays(day, -offset);
        days.push({ day: key.slice(5), count: counts[key] || 0 });
      }
      const allDays = db.reviews.map((review) => review.reviewed_at.slice(0, 10));
      return {
        total_cards: total,
        due,
        reviewed_today: todayReviews.length,
        remembered_today: todayReviews.filter((review) => review.quality >= 3).length,
        streak: streakFrom(allDays),
        domains: db.domains.map((domain) => ({
          name: domain.name,
          cards: db.cards.filter((card) => card.domain_id === domain.id).length,
        })),
        days,
      };
    },
    snapshot() {
      const db = load();
      const domainUid = (id) => {
        const found = db.domains.find((item) => item.id === id);
        return found ? found.uid : null;
      };
      const noteUid = (id) => {
        const found = db.notes.find((item) => item.id === id);
        return found ? found.uid : null;
      };
      const cardUid = (id) => {
        const found = db.cards.find((item) => item.id === id);
        return found ? found.uid : null;
      };
      return {
        device_id: db.device_id,
        domains: db.domains.map((item) => ({ uid: item.uid, name: item.name, created_at: item.created_at })),
        notes: db.notes.map((item) => ({
          uid: item.uid,
          domain_uid: domainUid(item.domain_id),
          title: item.title,
          body: item.body,
          created_at: item.created_at,
          updated_at: item.updated_at,
        })),
        cards: db.cards.map((item) => ({
          uid: item.uid,
          domain_uid: domainUid(item.domain_id),
          note_uid: item.note_id ? noteUid(item.note_id) : null,
          front: item.front,
          back: item.back,
          ease: item.ease,
          interval_days: item.interval_days,
          repetitions: item.repetitions,
          due: item.due,
          created_at: item.created_at,
          mastery: item.mastery,
          mastery_color: item.mastery_color || "",
          studied_days: item.studied_days || [],
          content_at: item.content_at,
          schedule_at: item.schedule_at,
        })),
        reviews: db.reviews.map((item) => ({
          uid: item.uid,
          card_uid: cardUid(item.card_id),
          quality: item.quality,
          reviewed_at: item.reviewed_at,
          interval_after: item.interval_after,
          ease_after: item.ease_after,
        })),
        tombstones: db.tombstones || [],
      };
    },
    applySnapshot(state) {
      const current = load();
      save({
        device_id: current.device_id,
        domains: state.domains,
        notes: state.notes,
        cards: state.cards,
        reviews: state.reviews,
        tombstones: state.tombstones || [],
        next: state.next,
      });
    },
  };
}

function wechatStore(seed) {
  return createStore({
    get: () => wx.getStorageSync(KEY),
    set: (value) => wx.setStorageSync(KEY, value),
  }, seed);
}

module.exports = { createStore, wechatStore, parseCards, LEVELS };
