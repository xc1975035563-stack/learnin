const TERMS = require("./terms");
const TERM_PATTERN = new RegExp(TERMS.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g");

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function emphasize(html) {
  return html.split(/(<[^>]+>)/).map((part) => (
    part.startsWith("<") ? part : part.replace(TERM_PATTERN, "<strong>$&</strong>")
  )).join("");
}

function richHtml(value, highlight) {
  let html = escapeHtml(value || "")
    .replace(/\[\[red\]\]/g, '<span style="color:#9f2d20;font-weight:650;">')
    .replace(/\[\[\/red\]\]/g, "</span>");
  if (highlight) html = emphasize(html);
  return `<div style="white-space:pre-wrap;line-height:1.6;">${html}</div>`;
}

module.exports = { richHtml };
