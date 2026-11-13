import { api } from "./api.js";

/* --- escaping ------------------------------------------------------------- */

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

/* --- event metadata ------------------------------------------------------- */

const EVENT_SHORT = {
  "333": "3x3", "222": "2x2", "444": "4x4", "555": "5x5", "666": "6x6",
  "777": "7x7", "333bf": "3BLD", "333fm": "FMC", "333oh": "OH",
  clock: "Clock", minx: "Mega", pyram: "Pyra", skewb: "Skewb", sq1: "SQ1",
  "444bf": "4BLD", "555bf": "5BLD", "333mbf": "MBLD", "333ft": "Feet",
  magic: "Magic", mmagic: "MMagic", "333mbo": "MBO",
};

export function eventBadge(eventId, name) {
  const label = EVENT_SHORT[eventId] ?? name ?? eventId;
  return `<span class="event-badge" title="${esc(name ?? eventId)}">${esc(label)}</span>`;
}

/* --- result formatting (AGENTS.md section 8) ------------------------------ */

const DNF = -1;
const DNS = -2;

function formatTime(cs) {
  if (cs >= 600000) {
    const total = Math.round(cs / 100);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }
  const total = cs / 100;
  const minutes = Math.floor(total / 60);
  const seconds = total - minutes * 60;
  return minutes ? `${minutes}:${seconds.toFixed(2).padStart(5, "0")}` : seconds.toFixed(2);
}

export function formatMultiBlind(value) {
  if (value === DNF) return "DNF";
  if (value === DNS) return "DNS";
  if (value <= 0) return "—";
  const diff = 99 - Math.floor(value / 10000000);
  const missed = value % 100;
  const solved = diff + missed;
  const seconds = Math.floor(value / 100) % 100000;
  const time = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  return `${solved}/${solved + missed} ${time}`;
}

/**
 * Format a raw result value for display. `eventId` picks the encoding,
 * `kind` is "single" | "average".
 */
export function formatResult(value, eventId, kind = "single") {
  if (value == null) return "—";
  if (value === DNF) return "DNF";
  if (value === DNS) return "DNS";
  if (value === 0) return "—";

  if (eventId === "333mbf") return formatMultiBlind(value);
  if (eventId === "333fm") {
    return kind === "average" ? (value / 100).toFixed(2) : String(value);
  }
  return formatTime(value);
}

export function recordBadge(code) {
  if (!code) return "";
  const cls = code === "WR" ? "WR" : code === "NR" ? "NR" : "CR";
  return `<span class="rec rec-${cls}" title="${esc(code)} record">${esc(code)}</span>`;
}

export function statusPill(status) {
  const labels = {
    upcoming: "Upcoming",
    in_progress: "In progress",
    past: "Past",
    cancelled: "Cancelled",
  };
  return `<span class="status-pill status-${esc(status)}">${esc(labels[status] ?? status)}</span>`;
}

/* --- dates ---------------------------------------------------------------- */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function formatDateRange(start, end) {
  if (!start || !end || start === end) return formatDate(start);
  const [ys, ms, ds] = start.slice(0, 10).split("-").map(Number);
  const [ye, me, de] = end.slice(0, 10).split("-").map(Number);
  if (ys === ye && ms === me) return `${ds} – ${de} ${MONTHS[me - 1]} ${ye}`;
  if (ys === ye) return `${ds} ${MONTHS[ms - 1]} – ${de} ${MONTHS[me - 1]} ${ye}`;
  return `${formatDate(start)} – ${formatDate(end)}`;
}

export function formatDateTime(iso) {
  if (!iso) return "";
  return `${formatDate(iso)} ${iso.slice(11, 16)}`;
}

/* --- shell: header, footer, toasts ---------------------------------------- */

const NAV = [
  { href: "/competitions.html", label: "Competitions", key: "competitions" },
  { href: "/persons.html", label: "Persons", key: "persons" },
  { href: "/rankings.html", label: "Rankings", key: "rankings" },
  { href: "/records.html", label: "Records", key: "records" },
  { href: "/stats.html", label: "Statistics", key: "stats" },
];

export function renderShell({ active = "", home = false } = {}) {
  if (home) document.body.classList.add("home");

  const header = document.querySelector("[data-shell=header]");
  if (header) {
    const nav = NAV.map(
      (item) =>
        `<a href="${item.href}"${item.key === active ? ' aria-current="page"' : ""}>${item.label}</a>`
    ).join("");
    header.className = "site-header";
    header.innerHTML = `
      <div class="container">
        <a class="wordmark" href="/">WCA<span>course project</span></a>
        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
        <nav class="site-nav" id="site-nav" aria-label="Main">${nav}</nav>
        <form class="header-search" role="search" action="/search.html">
          <label class="skip-link" for="global-q">Search</label>
          <input id="global-q" type="search" name="q" placeholder="Search competitions and persons" autocomplete="off" />
          <button type="submit">Search</button>
        </form>
      </div>`;

    const toggle = header.querySelector(".nav-toggle");
    const menu = header.querySelector(".site-nav");
    toggle?.addEventListener("click", () => {
      const open = menu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  const footer = document.querySelector("[data-shell=footer]");
  if (footer) {
    footer.className = "site-footer";
    footer.innerHTML = `
      <div class="container">
        <nav aria-label="Footer">
          <a href="/competitions.html">Competitions</a>
          <a href="/persons.html">Persons</a>
          <a href="/rankings.html">Rankings</a>
          <a href="/records.html">Records</a>
          <a href="/stats.html">Statistics</a>
        </nav>
        <p>UI modelled on worldcubeassociation.org (course project, not affiliated).
           Data is a frozen WCA export snapshot plus synthetic fields.</p>
      </div>`;
  }

  let toasts = document.querySelector(".toasts");
  if (!toasts) {
    toasts = document.createElement("div");
    toasts.className = "toasts";
    toasts.setAttribute("role", "status");
    toasts.setAttribute("aria-live", "polite");
    document.body.appendChild(toasts);
  }
}

export function toast(message, kind = "info", timeout = 5000) {
  const root = document.querySelector(".toasts");
  if (!root) return;
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.innerHTML = `<button class="close" type="button" aria-label="Dismiss">×</button><span>${esc(message)}</span>`;
  node.querySelector(".close").addEventListener("click", () => node.remove());
  root.appendChild(node);
  if (timeout) setTimeout(() => node.remove(), timeout);
}

export function confirmDialog(message, { title = "Please confirm", confirmLabel = "Confirm" } = {}) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.innerHTML = `
      <h2>${esc(title)}</h2>
      <p>${esc(message)}</p>
      <div class="actions">
        <button class="btn" value="cancel" type="button">Cancel</button>
        <button class="btn btn-danger" value="confirm" type="button">${esc(confirmLabel)}</button>
      </div>`;
    document.body.appendChild(dialog);
    dialog.showModal();
    const finish = (value) => {
      dialog.close();
      dialog.remove();
      resolve(value);
    };
    dialog.querySelector('[value="cancel"]').addEventListener("click", () => finish(false));
    dialog.querySelector('[value="confirm"]').addEventListener("click", () => finish(true));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(false);
    });
  });
}

/* --- page states ---------------------------------------------------------- */

export function showLoading(target, message = "Loading…") {
  target.innerHTML = `<div class="state"><div class="spinner"></div>${esc(message)}</div>`;
}

export function showEmpty(target, message = "Nothing to show.", action = "") {
  target.innerHTML = `<div class="state"><p>${esc(message)}</p>${action}</div>`;
}

export function showError(target, error, retry) {
  target.innerHTML = `<div class="state error"><p>${esc(error?.message ?? error)}</p>${
    retry ? '<button class="btn btn-sm" type="button">Try again</button>' : ""
  }</div>`;
  if (retry) target.querySelector("button")?.addEventListener("click", retry);
}

/* --- pagination ----------------------------------------------------------- */

export function renderPagination(target, { page, page_size, total }, onChange) {
  const pages = Math.max(1, Math.ceil(total / page_size));
  if (pages <= 1) {
    target.innerHTML = "";
    return;
  }
  const windowStart = Math.max(1, Math.min(page - 2, pages - 4));
  const windowEnd = Math.min(pages, windowStart + 4);
  let html = `<button type="button" data-page="${page - 1}" ${page === 1 ? "disabled" : ""}>Prev</button>`;
  for (let p = windowStart; p <= windowEnd; p += 1) {
    html += `<button type="button" data-page="${p}" ${p === page ? 'aria-current="true"' : ""}>${p}</button>`;
  }
  html += `<button type="button" data-page="${page + 1}" ${page === pages ? "disabled" : ""}>Next</button>`;
  html += `<span class="muted small">${total.toLocaleString()} total</span>`;
  target.className = "pagination";
  target.innerHTML = html;
  target.querySelectorAll("button[data-page]").forEach((button) => {
    button.addEventListener("click", () => {
      const next = Number(button.dataset.page);
      if (next >= 1 && next <= pages && next !== page) onChange(next);
    });
  });
}

/* --- results tables ------------------------------------------------------- */

export function renderResultsTable(rows, { showEvent = false, showRound = false } = {}) {
  if (!rows.length) return `<div class="state">No results yet.</div>`;
  const head = [
    "Pos",
    showEvent ? "Event" : null,
    "Name",
    "Best",
    "Average",
    "Representing",
    "Solves",
  ].filter(Boolean);

  const body = rows
    .map((row) => {
      const solves = (row.solves ?? [])
        .map(
          (value) =>
            `<span>${esc(formatResult(value, row.event_id, "single"))}</span>`
        )
        .join("");
      const event = showEvent
        ? `<td class="nowrap">${eventBadge(row.event_id)}</td>`
        : "";
      const round = showRound
        ? `<td class="muted small">${esc(String(row.round_number))}</td>`
        : "";
      return `<tr>
        <td class="num">${row.position ?? "—"}</td>
        ${event}
        <td class="name"><a href="/person.html?id=${encodeURIComponent(row.person_no)}">${esc(row.name ?? "")}</a>
          ${row.wca_id ? `<span class="wca-id">${esc(row.wca_id)}</span>` : ""}${round}</td>
        <td class="num">${esc(formatResult(row.best, row.event_id, "single"))}${recordBadge(row.single_record)}</td>
        <td class="num">${esc(formatResult(row.average, row.event_id, "average"))}${recordBadge(row.average_record)}</td>
        <td class="nowrap">${esc(row.country_id ?? "")}</td>
        <td class="solves">${solves || '<span class="muted">—</span>'}</td>
      </tr>`;
    })
    .join("");

  return `<div class="table-wrap"><table class="wca-results">
    <thead><tr>${head
      .map((h) => `<th${["Pos", "Best", "Average"].includes(h) ? ' class="num"' : ""}>${h}</th>`)
      .join("")}</tr></thead>
    <tbody>${body}</tbody>
  </table></div>`;
}

/* --- small helpers -------------------------------------------------------- */

export function param(name, fallback = null) {
  const value = new URLSearchParams(location.search).get(name);
  return value === null || value === "" ? fallback : value;
}

export function setTitle(text) {
  document.title = text ? `${text} | World Cube Association` : "World Cube Association";
}

export function debounce(fn, delay = 250) {
  let handle;
  return (...args) => {
    clearTimeout(handle);
    handle = setTimeout(() => fn(...args), delay);
  };
}

export async function loadLookups() {
  const [countries, events] = await Promise.all([
    api("/countries"),
    api("/events", { params: { include_retired: "false" } }),
  ]);
  return { countries, events };
}
