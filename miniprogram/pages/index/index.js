const seed = require("../../seed");
const { wechatStore } = require("../../utils/store");
const { richHtml } = require("../../utils/rich");

const store = wechatStore(seed);
const LEVELS = ["一般", "基本掌握", "熟练"];
const MASTERY_COLORS = ["#c44536", "#d97706", "#0f766e", "#1d4e89", "#6d28d9", "#be185d", "#3f6212", "#b45309", "#0369a1", "#9f1239", "#0e7490", "#7c3aed"];

function randomMasteryColor(previous) {
  const choices = MASTERY_COLORS.filter((color) => color !== previous);
  return choices[Math.floor(Math.random() * choices.length)];
}

function levelStyle(card, level) {
  if (card.mastery !== level || !card.mastery_color) return "";
  return `background:${card.mastery_color};border-color:${card.mastery_color};color:#fffdf8`;
}

function weekday(date) {
  return ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()];
}

function todayLabel() {
  const date = new Date();
  return `${date.getMonth() + 1}月${date.getDate()}日${weekday(date)}`;
}

Page({
  data: {
    view: "review",
    domainId: null,
    domains: [],
    domainNames: [],
    todayLabel: "",
    syncUrl: "",
    addingDomain: false,
    domainName: "",
    progressText: "",
    review: null,
    noteForm: { domainIndex: 0, title: "", body: "", id: null },
    importText: "",
    notes: [],
    cardForm: { domainIndex: 0, front: "", back: "", id: null, noteId: null },
    cards: [],
    openCardId: null,
    editingCardId: null,
    reviewEditing: false,
    inlineFront: "",
    inlineBack: "",
    stats: null,
    queueIndex: 0,
    revealed: false,
  },

  onLoad() {
    this.setData({
      todayLabel: todayLabel(),
      syncUrl: wx.getStorageSync("study-sync-url") || "",
    });
    this.refresh();
  },

  domainIndex(domainId) {
    const index = this.data.domains.findIndex((item) => item.id === domainId);
    if (index >= 0) return index;
    if (this.data.domainId != null) {
      const selected = this.data.domains.findIndex((item) => item.id === this.data.domainId);
      if (selected >= 0) return selected;
    }
    return 0;
  },

  interviewId() {
    const found = this.data.domains.find((item) => item.name === "面试题库");
    return found ? found.id : null;
  },

  switchView(event) {
    this.data.view = event.currentTarget.dataset.view;
    this.data.revealed = false;
    this.data.queueIndex = 0;
    this.setData({ view: this.data.view, revealed: false, queueIndex: 0 });
    this.refresh();
  },

  switchDomain(event) {
    const raw = event.currentTarget.dataset.id;
    this.data.domainId = raw === "" || raw == null ? null : Number(raw);
    this.data.revealed = false;
    this.data.queueIndex = 0;
    this.data.openCardId = null;
    this.setData({
      domainId: this.data.domainId,
      revealed: false,
      queueIndex: 0,
      openCardId: null,
    });
    this.refresh();
  },

  onSyncUrl(event) {
    this.setData({ syncUrl: event.detail.value });
  },

  syncNow() {
    const url = String(this.data.syncUrl || "").trim().replace(/\/$/, "");
    if (!/^https?:\/\//.test(url)) {
      wx.showToast({ title: "先填写电脑上的地址", icon: "none" });
      return;
    }
    wx.setStorageSync("study-sync-url", url);
    wx.showLoading({ title: "同步中" });
    wx.request({
      url: `${url}/api/sync`,
      method: "POST",
      data: store.snapshot(),
      timeout: 20000,
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode !== 200 || !res.data || !res.data.cards) {
          wx.showToast({ title: "同步失败", icon: "none" });
          return;
        }
        store.applySnapshot(res.data);
        wx.showToast({ title: `已同步 ${res.data.cards.length} 张卡片`, icon: "none" });
        this.data.revealed = false;
        this.data.queueIndex = 0;
        this.refresh();
      },
      fail: () => {
        wx.hideLoading();
        wx.showToast({ title: "连不上电脑，确认同一 Wi-Fi", icon: "none" });
      },
    });
  },

  startDomain() {
    this.setData({ addingDomain: true, domainName: "" });
  },

  onDomainName(event) {
    this.setData({ domainName: event.detail.value });
  },

  saveDomain() {
    try {
      store.createDomain(this.data.domainName);
      this.setData({ addingDomain: false, domainName: "" });
      wx.showToast({ title: "领域已添加", icon: "none" });
      this.refresh();
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    }
  },

  refresh() {
    const domains = store.listDomains();
    this.data.domains = domains;
    this.setData({ domains, domainNames: domains.map((item) => item.name) });
    if (this.data.view === "review") this.refreshReview();
    if (this.data.view === "notes") this.refreshNotes();
    if (this.data.view === "cards") this.refreshCards();
    if (this.data.view === "stats") this.refreshStats();
  },

  refreshReview() {
    const queue = store.reviewQueue(this.data.domainId);
    let index = this.data.queueIndex;
    if (index >= queue.cards.length) index = 0;
    const interviewId = this.interviewId();
    if (!queue.cards.length) {
      const selected = this.data.domains.find((item) => item.id === this.data.domainId);
      const progress = selected && selected.name === "面试题库" ? store.progress(selected.id) : null;
      this.setData({
        queueIndex: 0,
        progressText: progress ? `今日复习进度 ${progress.reviewed}/${progress.total}` : "",
        review: {
          empty: true,
          emptyText: queue.next_due ? `下一张在 ${queue.next_due}。可以去笔记里再做几张，或切换领域看看。` : "库里还没有排期中的卡片。先写一张问答卡。",
        },
      });
      return;
    }
    const card = queue.cards[index];
    const highlight = card.domain === "面试题库";
    const progress = highlight && interviewId != null ? store.progress(interviewId) : null;
    this.setData({
      queueIndex: index,
      progressText: progress ? `今日复习进度 ${progress.reviewed}/${progress.total}` : "",
      review: {
        empty: false,
        id: card.id,
        kicker: `${card.domain} · ${index + 1} / ${queue.cards.length}`,
        frontHtml: richHtml(card.front, highlight),
        backHtml: richHtml(card.back, highlight),
        isInterview: highlight,
        mastery: card.mastery || "一般",
        styles: [levelStyle(card, "一般"), levelStyle(card, "基本掌握"), levelStyle(card, "熟练")],
        studiedToday: card.studied_today,
        revealed: this.data.revealed,
      },
    });
  },

  reveal() {
    this.setData({ revealed: true });
    this.refreshReview();
  },

  rate(event) {
    const card = this.data.review;
    if (!card || card.empty) return;
    const quality = Number(event.currentTarget.dataset.quality);
    const result = store.rate(card.id, quality);
    const when = result.interval_days === 1 ? "明天" : `${result.interval_days} 天后`;
    wx.showToast({ title: quality < 3 ? "这张明天再来" : `下次在${when}`, icon: "none" });
    this.data.revealed = false;
    this.setData({ revealed: false });
    this.refreshReview();
  },

  setMastery(event) {
    const level = event.currentTarget.dataset.level;
    const cardId = this.data.view === "cards"
      ? Number(event.currentTarget.dataset.id)
      : this.data.review.id;
    store.setMastery(cardId, level, randomMasteryColor(event.currentTarget.dataset.color || ""));
    wx.showToast({ title: `掌握程度：${level}`, icon: "none" });
    this.refresh();
  },

  markStudied(event) {
    const cardId = this.data.view === "cards"
      ? Number(event.currentTarget.dataset.id)
      : this.data.review.id;
    const result = store.markStudied(cardId);
    wx.showToast({
      title: result.counted ? "已计入今日进度" : "这题今天已经计入进度",
      icon: "none",
    });
    this.refresh();
  },

  refreshNotes() {
    const notes = store.listNotes(this.data.domainId).map((note) => Object.assign({}, note, {
      bodyHtml: richHtml(note.body, false),
    }));
    const form = this.data.noteForm;
    const domainIndex = form.domainIndex >= 0 && form.domainIndex < this.data.domains.length
      ? form.domainIndex
      : this.domainIndex(form.domainId || this.data.domainId);
    this.setData({ notes, "noteForm.domainIndex": domainIndex });
  },

  onNoteDomain(event) {
    this.setData({ "noteForm.domainIndex": Number(event.detail.value) });
  },

  onNoteTitle(event) {
    this.setData({ "noteForm.title": event.detail.value });
  },

  onNoteBody(event) {
    this.setData({ "noteForm.body": event.detail.value });
  },

  saveNote() {
    const form = this.data.noteForm;
    const domain = this.data.domains[form.domainIndex];
    if (!domain) return;
    try {
      store.saveNote({
        id: form.id,
        domain_id: domain.id,
        title: form.title,
        body: form.body,
      });
      wx.showToast({ title: form.id ? "笔记已更新" : "笔记已记下", icon: "none" });
      this.setData({ noteForm: { domainIndex: form.domainIndex, title: "", body: "", id: null } });
      this.refreshNotes();
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    }
  },

  editNote(event) {
    const note = this.data.notes.find((item) => item.id === Number(event.currentTarget.dataset.id));
    if (!note) return;
    this.setData({
      noteForm: {
        id: note.id,
        domainId: note.domain_id,
        domainIndex: this.domainIndex(note.domain_id),
        title: note.title,
        body: note.body,
      },
    });
    wx.pageScrollTo({ scrollTop: 0, duration: 200 });
  },

  cancelNote() {
    this.setData({
      noteForm: { domainIndex: this.domainIndex(this.data.domainId), title: "", body: "", id: null },
    });
  },

  deleteNote(event) {
    const id = Number(event.currentTarget.dataset.id);
    wx.showModal({
      title: "删除笔记",
      content: "删除这篇笔记？已做成的卡片会保留。",
      success: (result) => {
        if (!result.confirm) return;
        store.deleteNote(id);
        this.refreshNotes();
      },
    });
  },

  noteToCard(event) {
    const note = this.data.notes.find((item) => item.id === Number(event.currentTarget.dataset.id));
    if (!note) return;
    this.setData({
      view: "cards",
      cardForm: {
        id: null,
        noteId: note.id,
        domainIndex: this.domainIndex(note.domain_id),
        front: "",
        back: (note.body || "").slice(0, 400),
      },
    });
    this.refreshCards();
    wx.pageScrollTo({ scrollTop: 0, duration: 200 });
  },

  onImportText(event) {
    this.setData({ importText: event.detail.value });
  },

  importCards() {
    const domain = this.data.domains[this.data.noteForm.domainIndex];
    if (!domain) return;
    const result = store.importText(domain.id, this.data.importText);
    wx.showToast({ title: result.cards ? `已加入 ${result.cards} 张卡片` : "已存成笔记", icon: "none" });
    this.setData({ importText: "" });
    this.refreshNotes();
  },

  refreshCards() {
    const interviewId = this.interviewId();
    const selected = this.data.domains.find((item) => item.id === this.data.domainId);
    const progress = selected && selected.name === "面试题库" ? store.progress(selected.id) : null;
    const openCardId = this.data.openCardId;
    const cards = store.listCards(this.data.domainId).map((card) => {
      const highlight = card.domain === "面试题库";
      const open = openCardId === card.id;
      return {
        id: card.id,
        domain: card.domain,
        due: card.due,
        interval_days: card.interval_days,
        mastery: card.mastery || "一般",
        styles: [levelStyle(card, "一般"), levelStyle(card, "基本掌握"), levelStyle(card, "熟练")],
        studiedToday: card.studied_today,
        isInterview: highlight,
        open,
        editing: card.id === this.data.editingCardId,
        frontHtml: richHtml(card.front, highlight),
        backHtml: open ? richHtml(card.back, highlight) : "",
      };
    });
    const form = this.data.cardForm;
    const domainIndex = form.domainIndex >= 0 && form.domainIndex < this.data.domains.length
      ? form.domainIndex
      : this.domainIndex(form.domainId || this.data.domainId);
    this.setData({
      progressText: progress ? `今日复习进度 ${progress.reviewed}/${progress.total}` : "",
      cards,
      "cardForm.domainIndex": domainIndex,
    });
  },

  toggleCard(event) {
    const id = Number(event.currentTarget.dataset.id);
    this.setData({ openCardId: this.data.openCardId === id ? null : id });
    this.refreshCards();
  },

  onCardDomain(event) {
    this.setData({ "cardForm.domainIndex": Number(event.detail.value) });
  },

  onCardFront(event) {
    this.setData({ "cardForm.front": event.detail.value });
  },

  onCardBack(event) {
    this.setData({ "cardForm.back": event.detail.value });
  },

  saveCard() {
    const form = this.data.cardForm;
    const domain = this.data.domains[form.domainIndex];
    if (!domain) return;
    try {
      store.saveCard({
        id: form.id,
        note_id: form.noteId,
        domain_id: domain.id,
        front: form.front,
        back: form.back,
      });
      wx.showToast({ title: form.id ? "卡片已更新" : "已放进今天的复习", icon: "none" });
      this.setData({
        cardForm: { domainIndex: form.domainIndex, front: "", back: "", id: null, noteId: null },
      });
      this.refreshCards();
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    }
  },

  editCard(event) {
    const id = Number(event.currentTarget.dataset.id);
    const card = store.listCards(null).find((item) => item.id === id);
    if (!card) return;
    this.data.editingCardId = id;
    this.setData({ editingCardId: id, inlineFront: card.front, inlineBack: card.back });
    this.refreshCards();
  },

  onInlineFront(event) {
    this.data.inlineFront = event.detail.value;
  },

  onInlineBack(event) {
    this.data.inlineBack = event.detail.value;
  },

  saveInlineCard() {
    const card = store.listCards(null).find((item) => item.id === this.data.editingCardId);
    if (!card) return;
    try {
      store.saveCard({
        id: card.id,
        note_id: card.note_id,
        domain_id: card.domain_id,
        front: this.data.inlineFront,
        back: this.data.inlineBack,
      });
      this.data.editingCardId = null;
      this.setData({ editingCardId: null });
      wx.showToast({ title: "已改在这道题上", icon: "none" });
      this.refreshCards();
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    }
  },

  cancelInlineCard() {
    this.data.editingCardId = null;
    this.setData({ editingCardId: null });
    this.refreshCards();
  },

  startReviewEdit() {
    const card = store.listCards(null).find((item) => item.id === this.data.review.id);
    if (!card) return;
    this.setData({ reviewEditing: true, inlineFront: card.front, inlineBack: card.back });
  },

  saveReviewEdit() {
    const card = store.listCards(null).find((item) => item.id === this.data.review.id);
    if (!card) return;
    try {
      store.saveCard({
        id: card.id,
        note_id: card.note_id,
        domain_id: card.domain_id,
        front: this.data.inlineFront,
        back: this.data.inlineBack,
      });
      this.setData({ reviewEditing: false });
      wx.showToast({ title: "已改在这道题上", icon: "none" });
      this.refreshReview();
    } catch (error) {
      wx.showToast({ title: error.message, icon: "none" });
    }
  },

  cancelReviewEdit() {
    this.setData({ reviewEditing: false });
  },

  cancelCard() {
    this.setData({
      cardForm: { domainIndex: this.domainIndex(this.data.domainId), front: "", back: "", id: null, noteId: null },
    });
  },

  deleteCard(event) {
    const id = Number(event.currentTarget.dataset.id);
    wx.showModal({
      title: "删除卡片",
      content: "删除这张卡片？",
      success: (result) => {
        if (!result.confirm) return;
        store.deleteCard(id);
        this.refreshCards();
      },
    });
  },

  refreshStats() {
    const data = store.stats();
    const max = Math.max(1, ...data.days.map((day) => day.count));
    data.days = data.days.map((day) => Object.assign({}, day, {
      height: Math.max(12, Math.round((day.count / max) * 220)),
    }));
    this.setData({ stats: data, progressText: "" });
  },
});
