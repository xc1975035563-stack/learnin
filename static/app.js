const state = {
  view: "review",
  domainId: null,
  domains: [],
  queue: [],
  index: 0,
  revealed: false,
  editingNote: null,
  editingCard: null,
  editingReview: false,
};

const viewEl = document.querySelector("#view");
const toastEl = document.querySelector("#toast");
let toastTimer = 0;

fetch("/api/info")
  .then((response) => response.json())
  .then((data) => {
    const phones = (data.addresses || []).filter((item) => !item.includes("127.0.0.1"));
    const address = document.querySelector("#sync-address");
    if (!address || !phones.length) return;
    const https = phones.filter((item) => item.startsWith("https://"));
    address.textContent = https.length
      ? `手机用系统浏览器打开：${https.join(" 或 ")} 。不要在微信里打开，微信会拦截这个地址。电脑不用和手机连同一个 Wi-Fi。`
      : `手机和电脑不在同一网络时，这里还没有公网地址。`;
  })
  .catch(() => {});

document.querySelector("#today").textContent = new Date().toLocaleDateString("zh-CN", {
  month: "long",
  day: "numeric",
  weekday: "short",
});

document.querySelector(".tabs").addEventListener("click", (event) => {
  const button = event.target.closest(".tab");
  if (!button) return;
  state.view = button.dataset.view;
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab === button));
  render();
});

document.addEventListener("keydown", (event) => {
  if (state.view !== "review" || event.target.matches("input, textarea")) return;
  if (event.key === " " || event.key === "Enter") {
    event.preventDefault();
    if (!state.revealed) reveal();
  }
  const quality = { "1": 1, "2": 3, "3": 4, "4": 5 }[event.key];
  if (quality && state.revealed) rate(quality);
});

function token() {
  return localStorage.getItem("study-token") || "";
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    localStorage.removeItem("study-token");
    showGate();
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "请求失败");
  }
  return response.json();
}

let registering = false;

function showGate() {
  document.querySelector("#gate").hidden = false;
  document.querySelector("#desk").hidden = true;
  document.querySelector("#logout").hidden = true;
}

function showDesk(username) {
  document.querySelector("#gate").hidden = true;
  document.querySelector("#desk").hidden = false;
  const logout = document.querySelector("#logout");
  logout.hidden = false;
  logout.textContent = `${username} · 退出`;
}

document.querySelector("#auth-switch").addEventListener("click", () => {
  registering = !registering;
  document.querySelector("#auth-submit").textContent = registering ? "注册" : "登录";
  document.querySelector("#auth-switch").textContent = registering ? "已有账号，去登录" : "没有账号，去注册";
  document.querySelector("#gate-title").textContent = registering ? "注册一个自己的题库" : "登录后才能看到自己的题库";
});

document.querySelector("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    const result = await api(registering ? "/api/register" : "/api/login", {
      method: "POST",
      body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
    });
    localStorage.setItem("study-token", result.token);
    showDesk(result.username);
    await loadDomains();
    render();
  } catch (error) {
    toast(error.message);
  }
});

document.querySelector("#logout").addEventListener("click", async () => {
  try {
    await api("/api/logout", { method: "POST", body: "{}" });
  } catch {
    /* 本地直接退出 */
  }
  localStorage.removeItem("study-token");
  showGate();
});

function toast(message) {
  toastEl.hidden = false;
  toastEl.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.hidden = true;
  }, 2200);
}

function domainOptions(selected) {
  return state.domains
    .map((domain) => `<option value="${domain.id}" ${domain.id === selected ? "selected" : ""}>${escapeHtml(domain.name)}</option>`)
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderRich(value, highlight = false) {
  const html = escapeHtml(value)
    .replaceAll("[[red]]", '<span class="bad">')
    .replaceAll("[[/red]]", "</span>");
  return highlight ? emphasize(html) : html;
}

const KEY_TERMS = [
  "Retrieval-Augmented Generation",
  "Reciprocal Rank Fusion",
  "Function Calling",
  "Text2SQL",
  "Cross-Encoder",
  "Embedding Model",
  "Graph RAG",
  "GraphRAG",
  "LangChain",
  "LangGraph",
  "Langchain",
  "FastAPI",
  "Elasticsearch",
  "Transformer",
  "向量数据库",
  "嵌入模型",
  "检索增强生成",
  "稀疏向量召回",
  "密集向量召回",
  "关键词召回",
  "混合召回",
  "倒数排名融合",
  "近似最近邻",
  "上下文管理器",
  "列表推导式",
  "多头注意力",
  "自注意力",
  "知识图谱",
  "图数据库",
  "查询改写",
  "查询路由",
  "重排序",
  "深拷贝",
  "浅拷贝",
  "装饰器",
  "生成器",
  "迭代器",
  "召回率",
  "准确率",
  "忠实度",
  "元数据",
  "相似度",
  "分块",
  "幻觉",
  "pgvector",
  "Milvus",
  "Qdrant",
  "Chroma",
  "FAISS",
  "Neo4j",
  "Redis",
  "BM25",
  "TF-IDF",
  "HNSW",
  "HyDE",
  "RAGAS",
  "Top-K",
  "IVF",
  "ANN",
  "RRF",
  "LLM",
  "RAG",
  "GPT",
  "BERT",
  "SQL",
  "JSON",
].sort((left, right) => right.length - left.length);

function emphasize(html) {
  const pattern = new RegExp(KEY_TERMS.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g");
  return html.split(/(<[^>]+>)/).map((part) => (
    part.startsWith("<") ? part : part.replace(pattern, "<strong>$&</strong>")
  )).join("");
}

function isInterview(card) {
  return card.domain === "面试题库";
}

const MASTERY_COLORS = ["#c44536", "#d97706", "#0f766e", "#1d4e89", "#6d28d9", "#be185d", "#3f6212", "#b45309", "#0369a1", "#9f1239", "#0e7490", "#7c3aed"];

function randomMasteryColor(previous) {
  const choices = MASTERY_COLORS.filter((color) => color !== previous);
  return choices[Math.floor(Math.random() * choices.length)];
}

function masteryBar(card) {
  if (!isInterview(card)) return "";
  return `
    <div class="mastery">
      <span>掌握程度</span>
      ${["一般", "基本掌握", "熟练"].map((level) => {
        const selected = card.mastery === level && card.mastery_color;
        const style = selected ? ` style="background:${card.mastery_color};border-color:${card.mastery_color}"` : "";
        return `<button type="button" class="level ${selected ? "on" : ""}"${style} data-mastery="${card.id}" data-level="${level}" data-color="${selected ? card.mastery_color : ""}">${level}</button>`;
      }).join("")}
      <button type="button" class="btn studied ${card.studied_today ? "done" : ""}" data-studied="${card.id}">今日已复习</button>
    </div>`;
}

function progressLine(progress) {
  if (!progress) return "";
  return `<p class="progress">今日复习进度 ${progress.reviewed}/${progress.total}</p>`;
}

async function interviewProgress() {
  const domain = state.domains.find((item) => item.name === "面试题库");
  if (!domain) return null;
  return api(`/api/progress?domain_id=${domain.id}`);
}

function bindStudyActions() {
  viewEl.querySelectorAll("[data-mastery]").forEach((button) => {
    button.addEventListener("click", () => setMastery(Number(button.dataset.mastery), button.dataset.level));
  });
  viewEl.querySelectorAll("[data-studied]").forEach((button) => {
    button.addEventListener("click", () => markStudied(Number(button.dataset.studied)));
  });
}

async function setMastery(id, level) {
  const current = [...document.querySelectorAll(`[data-mastery="${id}"]`)]
    .find((button) => button.classList.contains("on"));
  const color = randomMasteryColor(current ? current.dataset.color : "");
  await api(`/api/cards/${id}/mastery`, {
    method: "POST",
    body: JSON.stringify({ level, color }),
  });
  toast(`掌握程度：${level}`);
  render();
}

async function markStudied(id) {
  const result = await api(`/api/cards/${id}/studied`, { method: "POST", body: "{}" });
  toast(result.counted ? `今日复习进度 ${result.reviewed}/${result.total}` : "这题今天已经计入进度");
  render();
}

async function loadDomains() {
  state.domains = await api("/api/domains");
  const box = document.querySelector("#domains");
  box.innerHTML = `
    <button class="chip ${state.domainId === null ? "active" : ""}" data-id="">全部</button>
    ${state.domains.map((domain) => `
      <button class="chip ${state.domainId === domain.id ? "active" : ""}" data-id="${domain.id}">${escapeHtml(domain.name)}</button>
    `).join("")}
    <button class="chip" data-id="add">＋ 领域</button>
  `;
}

document.querySelector("#domains").addEventListener("click", async (event) => {
  const button = event.target.closest(".chip");
  if (!button) return;
  if (button.dataset.id === "add") {
    const name = prompt("新领域名称，例如：面试、阅读");
    if (!name) return;
    try {
      await api("/api/domains", { method: "POST", body: JSON.stringify({ name }) });
      await loadDomains();
      render();
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  state.domainId = button.dataset.id ? Number(button.dataset.id) : null;
  state.index = 0;
  state.revealed = false;
  await loadDomains();
  render();
});

async function render() {
  if (state.view === "review") await renderReview();
  if (state.view === "notes") await renderNotes();
  if (state.view === "cards") await renderCards();
  if (state.view === "stats") await renderStats();
}

async function renderReview() {
  const query = state.domainId ? `?domain_id=${state.domainId}` : "";
  const data = await api(`/api/review${query}`);
  const progress = await interviewProgress();
  state.queue = data.cards;
  if (state.index >= state.queue.length) state.index = 0;
  if (!state.queue.length) {
    viewEl.innerHTML = `
      <section class="study">
        ${state.domains.find((item) => item.id === state.domainId)?.name === "面试题库" ? progressLine(progress) : ""}
        <p class="kicker">今天的清单已经清空</p>
        <h2 class="prompt">没有到期的卡片</h2>
        <p class="empty">${data.next_due ? `下一张在 ${data.next_due}。可以去笔记里再做几张，或切换领域看看。` : "库里还没有排期中的卡片。先写一张问答卡。"}</p>
      </section>`;
    return;
  }
  const card = state.queue[state.index];
  const highlight = isInterview(card);
  viewEl.innerHTML = `
    <section class="study">
      ${highlight ? progressLine(progress) : ""}
      <p class="kicker">${escapeHtml(card.domain)} · ${state.index + 1} / ${state.queue.length}</p>
      ${state.editingReview ? `
        <textarea class="inline" name="front">${escapeHtml(card.front)}</textarea>
        <textarea class="inline tall" name="back">${escapeHtml(card.back)}</textarea>
        <div class="actions">
          <button class="btn primary" type="button" id="save-review">保存</button>
          <button class="btn" type="button" id="cancel-review">取消</button>
        </div>
      ` : `
        <h2 class="prompt">${renderRich(card.front, highlight)}</h2>
        ${masteryBar(card)}
        ${state.revealed ? `<p class="answer">${renderRich(card.back, highlight)}</p>` : ""}
        <div class="actions">
          ${state.revealed ? `
            <button class="rate again" data-quality="1">重来</button>
            <button class="rate hard" data-quality="3">困难</button>
            <button class="rate good" data-quality="4">记得</button>
            <button class="rate easy" data-quality="5">简单</button>
          ` : `<button class="btn primary" id="reveal">看答案</button>`}
          <button class="btn" type="button" id="edit-review">编辑</button>
        </div>
        <p class="hint">空格翻开答案。记得之后按 1 重来，2 困难，3 记得，4 简单。</p>
      `}
    </section>`;
  viewEl.querySelector("#reveal")?.addEventListener("click", reveal);
  viewEl.querySelector("#edit-review")?.addEventListener("click", async () => {
    state.editingReview = true;
    await renderReview();
    viewEl.querySelector("[name=front]")?.focus();
  });
  viewEl.querySelector("#cancel-review")?.addEventListener("click", () => {
    state.editingReview = false;
    renderReview();
  });
  viewEl.querySelector("#save-review")?.addEventListener("click", () => saveReviewCard(card));
  viewEl.querySelectorAll(".rate").forEach((button) => {
    button.addEventListener("click", () => rate(Number(button.dataset.quality)));
  });
  bindStudyActions();
}

async function saveReviewCard(card) {
  const front = viewEl.querySelector("[name=front]").value.trim();
  const back = viewEl.querySelector("[name=back]").value.trim();
  if (!front || !back) {
    toast("问题和答案都不能为空");
    return;
  }
  await api(`/api/cards/${card.id}`, {
    method: "PUT",
    body: JSON.stringify({
      domain_id: card.domain_id,
      note_id: card.note_id,
      front,
      back,
    }),
  });
  state.editingReview = false;
  toast("已改在这道题上");
  renderReview();
}

function reveal() {
  state.revealed = true;
  renderReview();
}

async function rate(quality) {
  state.editingReview = false;
  const card = state.queue[state.index];
  if (!card) return;
  const result = await api(`/api/cards/${card.id}/review`, {
    method: "POST",
    body: JSON.stringify({ quality }),
  });
  state.queue.splice(state.index, 1);
  if (state.index >= state.queue.length) state.index = 0;
  state.revealed = false;
  const when = result.interval_days === 1 ? "明天" : `${result.interval_days} 天后`;
  toast(quality < 3 ? "这张明天再来" : `下次在${when}`);
  renderReview();
}

async function renderNotes() {
  const query = state.domainId ? `?domain_id=${state.domainId}` : "";
  const notes = await api(`/api/notes${query}`);
  const editing = state.editingNote;
  const domainId = editing?.domain_id || state.domainId || state.domains[0]?.id;
  viewEl.innerHTML = `
    <section class="panel">
      <form class="form" id="note-form">
        <label>领域<select name="domain_id">${domainOptions(domainId)}</select></label>
        <label>标题<input name="title" required value="${escapeHtml(editing?.title || "")}" /></label>
        <label>正文<textarea name="body">${escapeHtml(editing?.body || "")}</textarea></label>
        <div class="row">
          <button class="btn primary" type="submit">${editing ? "保存笔记" : "写下笔记"}</button>
          ${editing ? `<button class="btn" type="button" id="cancel-note">取消</button>` : ""}
        </div>
      </form>
      <form class="form" id="import-form">
        <label>把问答直接做成卡片
          <textarea name="text" placeholder="问：什么是过拟合？&#10;答：模型记住了训练集里的噪声。&#10;&#10;Q: learning rate&#10;A: 更新参数时的步长。"></textarea>
        </label>
        <button class="btn" type="submit">导入卡片</button>
        <p class="hint">用空行分开多张卡。问/答 或 Q/A 都会识别。没有问答格式时，会存成一篇笔记。</p>
      </form>
    </section>
    <section class="list">
      ${notes.length ? notes.map(noteCard).join("") : `<p class="empty">这个领域还没有笔记。</p>`}
    </section>`;

  viewEl.querySelector("#note-form").addEventListener("submit", saveNote);
  viewEl.querySelector("#cancel-note")?.addEventListener("click", () => {
    state.editingNote = null;
    renderNotes();
  });
  viewEl.querySelector("#import-form").addEventListener("submit", importCards);
  bindNoteActions();
}

function noteCard(note) {
  return `
    <article class="item">
      <p class="meta">${escapeHtml(note.domain)}</p>
      <h3>${escapeHtml(note.title)}</h3>
      <p>${renderRich(note.body)}</p>
      <div class="row" style="margin-top:10px">
        <button class="btn" data-edit-note="${note.id}">编辑</button>
        <button class="btn" data-card-note="${note.id}">做成卡片</button>
        <button class="btn" data-delete-note="${note.id}">删除</button>
      </div>
    </article>`;
}

async function saveNote(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    domain_id: Number(form.get("domain_id")),
    title: form.get("title"),
    body: form.get("body"),
  };
  const editing = state.editingNote;
  await api(editing ? `/api/notes/${editing.id}` : "/api/notes", {
    method: editing ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  state.editingNote = null;
  toast(editing ? "笔记已更新" : "笔记已记下");
  renderNotes();
}

async function importCards(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const domainId = Number(viewEl.querySelector("#note-form select").value);
  const result = await api("/api/import", {
    method: "POST",
    body: JSON.stringify({
      domain_id: domainId,
      text: form.get("text"),
      as_note_title: "导入的笔记",
    }),
  });
  toast(result.cards ? `已加入 ${result.cards} 张卡片` : "已存成笔记");
  renderNotes();
}

function bindNoteActions() {
  viewEl.querySelectorAll("[data-edit-note]").forEach((button) => {
    button.addEventListener("click", async () => {
      const notes = await api("/api/notes");
      state.editingNote = notes.find((note) => note.id === Number(button.dataset.editNote));
      renderNotes();
    });
  });
  viewEl.querySelectorAll("[data-delete-note]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("删除这篇笔记？已做成的卡片会保留。")) return;
      await api(`/api/notes/${button.dataset.deleteNote}`, { method: "DELETE" });
      renderNotes();
    });
  });
  viewEl.querySelectorAll("[data-card-note]").forEach((button) => {
    button.addEventListener("click", async () => {
      const notes = await api("/api/notes");
      const note = notes.find((item) => item.id === Number(button.dataset.cardNote));
      state.editingCard = {
        domain_id: note.domain_id,
        note_id: note.id,
        front: "",
        back: note.body.slice(0, 400),
      };
      state.view = "cards";
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === "cards"));
      render();
    });
  });
}

async function renderCards() {
  const query = state.domainId ? `?domain_id=${state.domainId}` : "";
  const cards = await api(`/api/cards${query}`);
  const progress = await interviewProgress();
  const creating = state.editingCard?.id ? null : state.editingCard;
  const domainId = creating?.domain_id || state.domainId || state.domains[0]?.id;
  const showProgress = state.domains.find((item) => item.id === state.domainId)?.name === "面试题库";
  viewEl.innerHTML = `
    ${showProgress ? progressLine(progress) : ""}
    <section class="panel">
      <form class="form" id="card-form">
        <label>领域<select name="domain_id">${domainOptions(domainId)}</select></label>
        <label>问题 / 正面<input name="front" required value="${escapeHtml(creating?.front || "")}" /></label>
        <label>答案 / 背面<textarea name="back" required>${escapeHtml(creating?.back || "")}</textarea></label>
        <input type="hidden" name="id" value="" />
        <input type="hidden" name="note_id" value="${creating?.note_id || ""}" />
        <div class="row">
          <button class="btn primary" type="submit">加入今天的复习</button>
          ${creating ? `<button class="btn" type="button" id="cancel-card">取消</button>` : ""}
        </div>
      </form>
    </section>
    <section class="list">
      ${cards.length ? cards.map(cardItem).join("") : `<p class="empty">还没有卡片。</p>`}
    </section>`;
  viewEl.querySelector("#card-form").addEventListener("submit", saveCard);
  viewEl.querySelector("#inline-card-form")?.addEventListener("submit", saveCard);
  viewEl.querySelector("#cancel-card")?.addEventListener("click", () => {
    state.editingCard = null;
    renderCards();
  });
  viewEl.querySelector("#cancel-inline-card")?.addEventListener("click", () => {
    state.editingCard = null;
    renderCards();
  });
  viewEl.querySelectorAll("[data-edit-card]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.editingCard = cards.find((card) => card.id === Number(button.dataset.editCard)) || null;
      if (!state.editingCard) return;
      await renderCards();
      const box = document.querySelector("#editing-card");
      box?.scrollIntoView({ behavior: "smooth", block: "center" });
      box?.querySelector("[name=front]")?.focus();
    });
  });
  viewEl.querySelectorAll("[data-delete-card]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("删除这张卡片？")) return;
      await api(`/api/cards/${button.dataset.deleteCard}`, { method: "DELETE" });
      renderCards();
    });
  });
  bindStudyActions();
}

function cardItem(card) {
  if (state.editingCard?.id === card.id) {
    return `
      <article class="item" id="editing-card" data-card-id="${card.id}">
        <p class="meta">${escapeHtml(card.domain)} · 正在编辑这道题</p>
        <form class="form" id="inline-card-form">
          <label>问题<textarea class="question" name="front" required>${escapeHtml(card.front)}</textarea></label>
          <label>答案<textarea class="answer" name="back" required>${escapeHtml(card.back)}</textarea></label>
          <input type="hidden" name="domain_id" value="${card.domain_id}" />
          <input type="hidden" name="note_id" value="${card.note_id || ""}" />
          <input type="hidden" name="id" value="${card.id}" />
          <div class="row">
            <button class="btn primary" type="submit">保存</button>
            <button class="btn" type="button" id="cancel-inline-card">取消</button>
          </div>
        </form>
      </article>`;
  }
  const highlight = isInterview(card);
  return `
    <article class="item" data-card-id="${card.id}">
      <p class="meta">${escapeHtml(card.domain)} · 下次 ${card.due} · 间隔 ${card.interval_days} 天</p>
      <h3>${renderRich(card.front, highlight)}</h3>
      <div class="row" style="margin:10px 0">
        <button type="button" class="btn" data-edit-card="${card.id}">编辑</button>
        <button type="button" class="btn" data-delete-card="${card.id}">删除</button>
      </div>
      ${masteryBar(card)}
      <p>${renderRich(card.back, highlight)}</p>
    </article>`;
}

async function saveCard(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const id = form.get("id");
  const noteId = form.get("note_id");
  const payload = {
    domain_id: Number(form.get("domain_id")),
    note_id: noteId ? Number(noteId) : null,
    front: form.get("front"),
    back: form.get("back"),
  };
  await api(id ? `/api/cards/${id}` : "/api/cards", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  state.editingCard = null;
  toast(id ? "卡片已更新" : "已放进今天的复习");
  await renderCards();
  if (id) document.querySelector(`[data-card-id="${id}"]`)?.scrollIntoView({ block: "center" });
}

async function renderStats() {
  const data = await api("/api/stats");
  const max = Math.max(1, ...data.days.map((day) => day.count));
  viewEl.innerHTML = `
    <section class="stats">
      <article class="stat"><span>连续天数</span><b>${data.streak}</b></article>
      <article class="stat"><span>今天已复习</span><b>${data.reviewed_today}</b></article>
      <article class="stat"><span>今天还欠</span><b>${data.due}</b></article>
      <article class="stat"><span>卡片总数</span><b>${data.total_cards}</b></article>
    </section>
    <section class="panel" style="margin-top:12px">
      <p class="kicker">近 7 天</p>
      <div class="bars">
        ${data.days.map((day) => `
          <div class="bar">
            <i style="height:${Math.max(6, (day.count / max) * 110)}px"></i>
            <em>${day.day}</em>
          </div>`).join("")}
      </div>
      <p class="hint">今天记住 ${data.remembered_today} 张（点了困难、记得或简单）。重来的卡片明天会再出现。</p>
    </section>
    <section class="panel" style="margin-top:12px">
      <p class="kicker">各领域</p>
      ${data.domains.map((domain) => `
        <div class="domain-line"><span>${escapeHtml(domain.name)}</span><b>${domain.cards}</b></div>
      `).join("")}
    </section>`;
}

async function boot() {
  if (!token()) {
    showGate();
    return;
  }
  try {
    const me = await api("/api/me");
    showDesk(me.username);
    await loadDomains();
    render();
  } catch (error) {
    showGate();
    if (error.message && error.message !== "请先登录") toast(error.message);
  }
}

boot();
