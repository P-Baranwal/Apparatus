import { api } from "../api.js";
import {
  confirmDialog,
  esc,
  eventBadge,
  formatDate,
  formatDateRange,
  formatDateTime,
  formatResult,
  param,
  renderPagination,
  renderResultsTable,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
  statusPill,
  toast,
} from "../ui.js";

const competitionId = param("id");
const tabs = document.getElementById("tabs");
const content = document.getElementById("tab-content");
const header = document.getElementById("competition-header");

let competition = null;
let activeTab = param("tab", "info");

renderShell({ active: "competitions" });

const TABS = [
  ["info", "General Info"],
  ["events", "Events"],
  ["results", "Results"],
  ["registrations", "Registrations"],
];

function renderHeader() {
  const rounds = competition.events.reduce((sum, e) => sum + e.rounds.length, 0);
  setTitle(competition.name);
  header.innerHTML = `
    <div class="page-head">
      <div>
        <h1>${esc(competition.name)}</h1>
        <p class="muted">
          ${esc(formatDateRange(competition.start_date, competition.end_date))} ·
          ${esc(competition.city ?? "")} · ${esc(competition.country_name)}
          ${competition.championship_type ? ` · <strong>${esc(competition.championship_type)}</strong> championship` : ""}
        </p>
        <span class="record-id">${esc(competition.competition_id)}</span>
      </div>
      <div>${statusPill(competition.status)}</div>
    </div>
    ${
      competition.status === "cancelled"
        ? `<div class="notice danger">This competition was cancelled${
            competition.cancelled_at ? ` on ${esc(formatDate(competition.cancelled_at))}` : ""
          }.</div>`
        : ""
    }
    ${
      competition.status === "upcoming" && activeTab !== "registrations"
        ? `<div class="notice">Registration is handled on the
             <a href="#" data-goto="registrations">Registrations</a> tab.
             <strong>${competition.registered_count}</strong> accepted${
             competition.competitor_limit ? ` of ${competition.competitor_limit}` : ""
           }.</div>`
        : ""
    }
    <p class="muted small">${competition.events.length} events · ${rounds} rounds · ${competition.registered_count} registered</p>`;
  header.querySelector("[data-goto]")?.addEventListener("click", (event) => {
    event.preventDefault();
    setTab("registrations");
  });
}

function renderTabs() {
  tabs.innerHTML = TABS.map(
    ([key, label]) =>
      `<button type="button" role="tab" data-tab="${key}" aria-selected="${key === activeTab}">${label}</button>`
  ).join("");
  tabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => setTab(button.dataset.tab));
  });
}

function setTab(tab, { push = true } = {}) {
  activeTab = tab;
  if (push) {
    const query = new URLSearchParams({ id: competitionId, tab });
    history.replaceState(null, "", `/competition.html?${query}`);
  }
  renderTabs();
  if (competition) renderHeader();
  renderTab();
}

/* --- General info --------------------------------------------------------- */

function renderInfo() {
  const c = competition;
  const link = (person) =>
    `<a href="/person.html?id=${encodeURIComponent(person.person_no)}">${esc(person.name)}</a>`;
  const facts = [
    ["Date", esc(formatDateRange(c.start_date, c.end_date))],
    ["City", esc(c.city ?? "—")],
    ["Venue", esc(c.venue_name ?? "—")],
    ["Address", esc(c.street_address ?? "—")],
    ["Details", esc(c.venue_details ?? "—")],
    ["Website", c.website ? `<a href="${esc(c.website)}" rel="noopener noreferrer nofollow" target="_blank">${esc(c.website)}</a>` : "—"],
    ["Organizers", c.organizers.length ? c.organizers.map(link).join(", ") : '<span class="muted">No person organizers recorded</span>'],
    ["WCA Delegates", c.delegates.length ? c.delegates.map(link).join(", ") : "—"],
    ["Main event", c.main_event_id ? eventBadge(c.main_event_id) : "—"],
    ["Competitors", `${c.registered_count}${c.competitor_limit ? ` / ${c.competitor_limit}` : ""}`],
    ["Registration period", `${esc(formatDateTime(c.opens_at) || "—")} → ${esc(formatDateTime(c.closes_at) || "—")}`],
    ["Registration fee", c.amount != null ? `${esc(String(c.amount))} ${esc(c.currency_code ?? "")}` : "—"],
    ["Refund policy", c.refund_policy_percent != null ? `${c.refund_policy_percent}%` : "—"],
    ["Announced", esc(formatDateTime(c.announced_at) || "—")],
    ["Results posted", esc(formatDateTime(c.results_posted_at) || "—")],
  ];
  const podiumBlock = c.podiums.length
    ? `<h2>Highlights</h2>${renderResultsTable(c.podiums, { showEvent: true })}`
    : `<div class="state">No results have been posted for this competition.</div>`;

  content.innerHTML = `
    <div class="card">
      <h2>General Info</h2>
      <dl class="info">
        ${facts.map(([term, value]) => `<dt>${term}</dt><dd>${value}</dd>`).join("")}
      </dl>
    </div>
    <div class="card">${podiumBlock}</div>`;
}

/* --- Events --------------------------------------------------------------- */

function renderEvents() {
  const rows = competition.events
    .map((event) => {
      const cells = event.rounds
        .map((round) => {
          const cutoff = round.cutoff_value
            ? `${formatResult(round.cutoff_value, event.event_id)} (${round.cutoff_attempts ?? "?"} attempts)`
            : "—";
          const limit = round.per_attempt
            ? formatResult(round.per_attempt, event.event_id)
            : "Cumulative / none";
          const advance =
            round.adv_type === "ranking" && round.adv_level
              ? `Top ${round.adv_level}`
              : round.adv_type === "percent" && round.adv_level
                ? `Top ${round.adv_level}%`
                : "—";
          return `<tr>
            <td>${round.round_number}${round.is_dual ? ' <span class="muted small">(dual)</span>' : ""}</td>
            <td>${esc(round.format_name)}</td>
            <td class="num">${esc(limit)}</td>
            <td class="num">${esc(cutoff)}</td>
            <td>${esc(advance)}</td>
            <td class="nowrap">${esc(formatDate(round.last_day))}</td>
          </tr>`;
        })
        .join("");
      return `<tr>
        <td class="nowrap">${eventBadge(event.event_id, event.event_name)}<div class="small">${esc(event.event_name)}</div></td>
        <td colspan="5" style="padding:0">
          <div class="table-wrap"><table class="compact">
            <thead><tr><th>Round</th><th>Format</th><th class="num">Time limit</th>
              <th class="num">Cutoff</th><th>Proceed</th><th>Date</th></tr></thead>
            <tbody>${cells}</tbody></table></div>
        </td>
      </tr>`;
    })
    .join("");

  content.innerHTML = `
    <div class="card">
      <h2>Events</h2>
      ${
        competition.events.length
          ? `<div class="table-wrap"><table><tbody>${rows}</tbody></table></div>
             <p class="muted small" style="margin-top:12px">
               <strong>Time limit</strong> — the limit for each attempt.
               <strong>Cutoff</strong> — the result to beat to continue the round.
               <strong>Format</strong> — how rankings are decided (Regulation 9f).
               <strong>Proceed</strong> — the planned number advancing (Regulation 9g).
               Times are shown as <code>m:ss.cc</code> under 10 minutes and <code>m:ss</code> above.
             </p>`
          : '<div class="state">No rounds scheduled.</div>'
      }
    </div>`;
}

/* --- Results -------------------------------------------------------------- */

const resultsState = { tab: "podiums", event_id: "", round_number: "", page: 1 };

function renderResults() {
  content.innerHTML = `
    <div class="card">
      <div class="filters" style="margin-bottom:14px">
        <div class="field">
          <label for="res-tab">View</label>
          <select id="res-tab">
            <option value="podiums">Podiums</option>
            <option value="all">All results</option>
            <option value="by_person">By person</option>
          </select>
        </div>
        <div class="field">
          <label for="res-event">Event</label>
          <select id="res-event"><option value="">All events</option>
            ${competition.events
              .map((e) => `<option value="${esc(e.event_id)}">${esc(e.event_name)}</option>`)
              .join("")}
          </select>
        </div>
        <div class="field">
          <label for="res-round">Round</label>
          <input id="res-round" type="number" min="1" max="10" inputmode="numeric" placeholder="Any" />
        </div>
      </div>
      <div id="results-body"></div>
      <div id="results-pagination"></div>
    </div>`;

  document.getElementById("res-tab").value = resultsState.tab;
  document.getElementById("res-event").value = resultsState.event_id;
  document.getElementById("res-round").value = resultsState.round_number;

  document.getElementById("res-tab").addEventListener("change", (event) => {
    resultsState.tab = event.target.value;
    resultsState.page = 1;
    loadResults();
  });
  document.getElementById("res-event").addEventListener("change", (event) => {
    resultsState.event_id = event.target.value;
    resultsState.page = 1;
    loadResults();
  });
  document.getElementById("res-round").addEventListener("change", (event) => {
    resultsState.round_number = event.target.value;
    resultsState.page = 1;
    loadResults();
  });
  loadResults();
}

async function loadResults() {
  const body = document.getElementById("results-body");
  const pager = document.getElementById("results-pagination");
  if (!body) return;
  showLoading(body, "Loading results…");
  try {
    const data = await api(`/competitions/${encodeURIComponent(competitionId)}/results`, {
      params: {
        tab: resultsState.tab,
        event_id: resultsState.event_id,
        round_number: resultsState.round_number,
        page: resultsState.page,
        page_size: 50,
      },
    });
    if (!data.items.length) {
      showEmpty(body, "No results match this view.");
      pager.innerHTML = "";
      return;
    }
    body.innerHTML = renderResultsTable(data.items, {
      showEvent: resultsState.tab !== "all" || !resultsState.event_id,
    });
    renderPagination(pager, data, (next) => {
      resultsState.page = next;
      loadResults();
    });
  } catch (error) {
    showError(body, error, loadResults);
  }
}

/* --- Registrations (W1 create, W4 status, W3 delete) ---------------------- */

async function renderRegistrations() {
  content.innerHTML = `
    <div class="card">
      <div class="section-title">
        <h2>Registrations</h2>
        <div class="inline">
          <label class="skip-link" for="reg-status">Filter by status</label>
          <select id="reg-status">
            <option value="">All statuses</option>
            <option value="accepted">Accepted</option>
            <option value="waiting_list">Waiting list</option>
            <option value="pending">Pending</option>
            <option value="cancelled">Cancelled</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>
      <div id="reg-body"></div>
      <div id="reg-pagination"></div>
    </div>
    <div class="card">
      <h2>Register a person</h2>
      <p class="muted small">
        Registration closes ${esc(formatDateTime(competition.closes_at) || "when the organiser closes it")}.
        Accepted registrations: <strong>${competition.registered_count}</strong>${
          competition.competitor_limit ? ` of ${competition.competitor_limit}` : ""
        }. When the limit is reached, new registrations join the waiting list.
      </p>
      <form id="register-form">
        <div class="field">
          <label for="person-search">Find the person</label>
          <input id="person-search" type="search" placeholder="Type a name or WCA ID" autocomplete="off" />
          <div class="hint">Results appear below; pick one to select that person.</div>
        </div>
        <div id="person-results"></div>
        <div class="field">
          <span id="events-label" style="display:block;font-weight:600;margin-bottom:4px">Events</span>
          <div class="checkbox-grid" id="event-choices" role="group" aria-labelledby="events-label"></div>
        </div>
        <div class="field" style="max-width:180px">
          <label for="guests">Guests (0–10)</label>
          <input id="guests" type="number" min="0" max="10" value="0" inputmode="numeric" />
        </div>
        <button class="btn btn-primary" type="submit" id="register-submit" disabled>Register</button>
        <p class="hint" id="selected-person-label">No person selected.</p>
      </form>
    </div>`;

  const statusSelect = document.getElementById("reg-status");
  statusSelect.addEventListener("change", () => loadRegistrations());
  loadRegistrations();
  wireRegistrationForm();
}

let registrationState = { status: "", page: 1 };

async function loadRegistrations() {
  const body = document.getElementById("reg-body");
  const pager = document.getElementById("reg-pagination");
  const statusSelect = document.getElementById("reg-status");
  if (!body) return;
  showLoading(body, "Loading registrations…");
  try {
    const data = await api(`/competitions/${encodeURIComponent(competitionId)}/registrations`, {
      params: { status: statusSelect?.value ?? "", page: registrationState.page, page_size: 50 },
    });
    if (!data.items.length) {
      showEmpty(body, "No registrations match this filter.");
      pager.innerHTML = "";
      return;
    }
    body.innerHTML = `<div class="table-wrap"><table>
      <thead><tr>
        <th class="num">#</th><th>Person</th><th>Events</th><th>Status</th>
        <th>Registered</th><th class="num">Guests</th><th>Actions</th>
      </tr></thead>
      <tbody>${data.items
        .map(
          (r) => `<tr>
            <td class="num">${r.registrant_no}</td>
            <td><a href="/person.html?id=${encodeURIComponent(r.person_no)}">${esc(r.name ?? "")}</a>
              <span class="record-id">${esc(r.wca_id ?? "no WCA ID")}</span></td>
            <td>${r.events.map((e) => eventBadge(e)).join(" ")}</td>
            <td class="status-${esc(r.status)}">${esc(r.status.replace("_", " "))}</td>
            <td class="nowrap small">${esc(formatDateTime(r.registered_at))}</td>
            <td class="num">${r.guests}</td>
            <td class="nowrap">
              <button class="btn btn-sm" data-action="status" data-no="${r.registrant_no}"
                      data-status="${r.status === "accepted" ? "waiting_list" : "accepted"}">
                ${r.status === "accepted" ? "Waitlist" : "Accept"}
              </button>
              <button class="btn btn-sm btn-danger" data-action="delete" data-no="${r.registrant_no}"
                      data-name="${esc(r.name ?? "")}">Delete</button>
            </td>
          </tr>`
        )
        .join("")}</tbody></table></div>`;
    renderPagination(pager, data, (next) => {
      registrationState.page = next;
      loadRegistrations();
    });
    body.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.action === "status") {
          changeStatus(Number(button.dataset.no), button.dataset.status);
        } else {
          removeRegistration(Number(button.dataset.no), button.dataset.name);
        }
      });
    });
  } catch (error) {
    showError(body, error, loadRegistrations);
  }
}

async function changeStatus(registrantNo, status) {
  try {
    const result = await api(
      `/competitions/${encodeURIComponent(competitionId)}/registrations/${registrantNo}`,
      { method: "PATCH", body: { status } }
    );
    toast(
      `Registrant #${registrantNo} is now ${status.replace("_", " ")}.` +
        (result.promoted ? ` #${result.promoted.registrant_no} (${result.promoted.name}) was promoted from the waiting list.` : ""),
      "success"
    );
    await refreshCompetition();
    loadRegistrations();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function removeRegistration(registrantNo, name) {
  const ok = await confirmDialog(
    `Delete the registration of ${name || `#${registrantNo}`}? Its event selections are removed too.`,
    { title: "Delete registration", confirmLabel: "Delete registration" }
  );
  if (!ok) return;
  try {
    await api(`/competitions/${encodeURIComponent(competitionId)}/registrations/${registrantNo}`, {
      method: "DELETE",
    });
    toast("Registration deleted.", "success");
    await refreshCompetition();
    loadRegistrations();
  } catch (error) {
    toast(error.message, "error");
  }
}

function wireRegistrationForm() {
  const form = document.getElementById("register-form");
  if (!form) return;
  const search = document.getElementById("person-search");
  const personResults = document.getElementById("person-results");
  const choices = document.getElementById("event-choices");
  const submit = document.getElementById("register-submit");
  const label = document.getElementById("selected-person-label");
  let selected = null;

  choices.innerHTML = competition.events
    .map(
      (event) => `<label>
        <input type="checkbox" name="event" value="${esc(event.event_id)}" />
        ${eventBadge(event.event_id, event.event_name)} ${esc(event.event_name)}
      </label>`
    )
    .join("");

  if (!competition.events.length) {
    choices.innerHTML = '<p class="muted">No events are offered, so registration is not possible.</p>';
    submit.disabled = true;
  }

  let timer;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    const q = search.value.trim();
    if (!q) {
      personResults.innerHTML = "";
      return;
    }
    timer = setTimeout(async () => {
      try {
        const data = await api("/search", { params: { q, limit: 6 } });
        if (!data.persons.length) {
          personResults.innerHTML = `<p class="muted small">No person matches “${esc(q)}”.</p>`;
          return;
        }
        personResults.innerHTML = `<div class="table-wrap"><table class="compact">
          <tbody>${data.persons
            .map(
              (p) => `<tr><td><button class="btn btn-sm" type="button"
                  data-person="${p.person_no}" data-name="${esc(p.name)}">Select</button></td>
                <td>${esc(p.name)}<span class="record-id">${esc(p.wca_id ?? "no WCA ID")}</span></td>
                <td>${esc(p.country_id)}</td></tr>`
            )
            .join("")}</tbody></table></div>`;
        personResults.querySelectorAll("button[data-person]").forEach((button) => {
          button.addEventListener("click", () => {
            selected = { person_no: Number(button.dataset.person), name: button.dataset.name };
            label.innerHTML = `Selected: <strong>${esc(selected.name)}</strong> (Person_No ${selected.person_no})`;
            submit.disabled = false;
            personResults.innerHTML = "";
            search.value = selected.name;
          });
        });
      } catch (error) {
        personResults.innerHTML = `<p class="muted small">${esc(error.message)}</p>`;
      }
    }, 250);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selected) {
      toast("Select a person first.", "error");
      return;
    }
    const events = [...form.querySelectorAll('input[name="event"]:checked')].map((i) => i.value);
    if (!events.length) {
      toast("Select at least one event.", "error");
      return;
    }
    submit.disabled = true;
    try {
      const created = await api(
        `/competitions/${encodeURIComponent(competitionId)}/registrations`,
        {
          method: "POST",
          body: { person_no: selected.person_no, events, guests: Number(document.getElementById("guests").value) },
        }
      );
      toast(
        `Registered ${created.name} as #${created.registrant_no} (${created.status.replace("_", " ")}).`,
        "success"
      );
      form.reset();
      selected = null;
      label.textContent = "No person selected.";
      submit.disabled = true;
      personResults.innerHTML = "";
      await refreshCompetition();
      loadRegistrations();
    } catch (error) {
      toast(error.message, "error");
      submit.disabled = false;
    }
  });
}

/* --- boot ----------------------------------------------------------------- */

async function refreshCompetition() {
  competition = await api(`/competitions/${encodeURIComponent(competitionId)}`);
}

function renderTab() {
  if (activeTab === "info") renderInfo();
  else if (activeTab === "events") renderEvents();
  else if (activeTab === "results") renderResults();
  else renderRegistrations();
}

async function boot() {
  if (!competitionId) {
    showError(content, new Error("No competition id given. Try ?id=WC2025."));
    return;
  }
  showLoading(content, "Loading competition…");
  try {
    await refreshCompetition();
  } catch (error) {
    showError(content, error, boot);
    return;
  }
  renderTabs();
  renderHeader();
  renderTab();
}

boot();
