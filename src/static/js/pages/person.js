import { api } from "../api.js";
import {
  esc,
  eventBadge,
  formatDate,
  formatResult,
  param,
  recordBadge,
  renderPagination,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
  toast,
} from "../ui.js";

const personRef = param("id");
const header = document.getElementById("person-header");
const body = document.getElementById("person-body");
let person = null;
let countries = [];
let resultsPage = 1;

renderShell({ active: "persons" });

function renderHeader() {
  setTitle(person.name);
  header.innerHTML = `
    <div class="page-head">
      <div class="inline">
        <div class="avatar-ph" aria-hidden="true">${esc((person.name || "?").slice(0, 1).toUpperCase())}</div>
        <div>
          <h1>${esc(person.name)}</h1>
          ${person.local_name ? `<p class="muted">${esc(person.local_name)}</p>` : ""}
          <span class="record-id">Person_No ${person.person_no}</span>
        </div>
      </div>
    </div>`;
}

function renderSummary() {
  return `<div class="card">
    <div class="table-wrap"><table>
      <thead><tr><th>Region</th><th>WCA ID</th><th>Gender</th><th class="center">Competitions</th><th class="center">Podiums</th></tr></thead>
      <tbody><tr>
        <td><a href="/country.html?country_id=${encodeURIComponent(person.country_id)}">${esc(person.country_name)}</a></td>
        <td class="mono">${esc(person.wca_id ?? "—")}</td>
        <td>${esc({ m: "Male", f: "Female", o: "Other" }[person.gender] ?? person.gender)}</td>
        <td class="center">${person.competitions_count}</td>
        <td class="center">${person.podiums_count}</td>
      </tr></tbody></table></div>
    <p class="muted small" style="margin-top:10px">
      ${person.delegate_status ? `WCA Delegate (${esc(person.delegate_status)}). ` : ""}
      ${person.since_date ? `Representing ${esc(person.country_name)} since ${esc(formatDate(person.since_date))}.` : ""}
    </p>
  </div>`;
}

function renderRecords() {
  const records = person.personal_records;
  if (!records.length) {
    return `<div class="card"><h2>Current Personal Records</h2>
      <div class="state">No results yet. Personal records appear after a first competition.</div></div>`;
  }
  return `<div class="card">
    <h2>Current Personal Records</h2>
    <div class="table-wrap"><table class="wca-results">
      <thead><tr>
        <th>Event</th>
        <th class="num">NR</th><th class="num">CR</th><th class="num">WR</th>
        <th class="num">Single</th><th class="num">Average</th>
      </tr></thead>
      <tbody>${records
        .map(
          (r) => `<tr>
            <td class="nowrap"><a href="/rankings.html?event=${encodeURIComponent(r.event_id)}">${eventBadge(r.event_id, r.event_name)}</a> ${esc(r.event_name)}</td>
            <td class="num">${r.national_rank ?? "—"}</td>
            <td class="num">${r.continental_rank ?? "—"}</td>
            <td class="num">${r.world_rank ?? "—"}</td>
            <td class="num">${esc(formatResult(r.best, r.event_id, "single"))}</td>
            <td class="num">${esc(formatResult(r.average, r.event_id, "average"))}</td>
          </tr>`
        )
        .join("")}</tbody></table></div>
    <p class="muted small" style="margin-top:10px">
      NR / CR / WR are the person's rank by single within their country, continent and the world.
    </p>
  </div>`;
}

function renderChangeCountry() {
  return `<div class="card">
    <h2>Change represented country</h2>
    <p class="muted small">
      A person may change the country they represent at most once every 12 months.
      This updates <code>persons.Country_ID</code> and <code>persons.Since_Date</code>.
    </p>
    <form id="country-form" class="filters">
      <div class="field grow">
        <label for="new-country">New country</label>
        <select id="new-country">
          ${countries
            .map(
              (c) => `<option value="${esc(c.country_id)}" ${c.country_id === person.country_id ? "selected" : ""}>${esc(c.name)}</option>`
            )
            .join("")}
        </select>
      </div>
      <button class="btn btn-primary" type="submit">Change country</button>
    </form>
  </div>`;
}

function renderHistory() {
  return `<div class="card">
    <div class="section-title"><h2>Results</h2>
      <div class="inline">
        <label class="small" for="event-filter">Event</label>
        <select id="event-filter"><option value="">All events</option>
          ${person.personal_records
            .map((r) => `<option value="${esc(r.event_id)}">${esc(r.event_name)}</option>`)
            .join("")}
        </select>
      </div>
    </div>
    <div id="history"></div>
    <div id="history-pagination"></div>
  </div>`;
}

async function loadHistory() {
  const target = document.getElementById("history");
  const pager = document.getElementById("history-pagination");
  const eventFilter = document.getElementById("event-filter");
  if (!target) return;
  showLoading(target, "Loading results…");
  try {
    const data = await api(`/persons/${encodeURIComponent(person.person_no)}/results`, {
      params: { event_id: eventFilter?.value ?? "", page: resultsPage, page_size: 25 },
    });
    if (!data.items.length) {
      showEmpty(target, "No results match this view.");
      pager.innerHTML = "";
      return;
    }
    const grouped = new Map();
    for (const row of data.items) {
      if (!grouped.has(row.event_id)) grouped.set(row.event_id, []);
      grouped.get(row.event_id).push(row);
    }
    target.innerHTML = [...grouped]
      .map(
        ([eventId, rows]) => `
        <h3 class="inline">${eventBadge(eventId)}</h3>
        <div class="table-wrap"><table class="wca-results compact">
          <thead><tr><th>Competition</th><th class="center">Round</th><th class="num">Place</th>
            <th class="num">Single</th><th class="num">Average</th><th>Solves</th></tr></thead>
          <tbody>${rows
            .map(
              (r) => `<tr>
                <td><a href="/competition.html?id=${encodeURIComponent(r.competition_id)}">${esc(r.competition_name ?? r.competition_id)}</a></td>
                <td class="center">${r.round_number}</td>
                <td class="num">${r.position ?? "—"}</td>
                <td class="num">${esc(formatResult(r.best, eventId, "single"))}${recordBadge(r.single_record)}</td>
                <td class="num">${esc(formatResult(r.average, eventId, "average"))}${recordBadge(r.average_record)}</td>
                <td class="solves">${(r.solves ?? []).map((v) => `<span>${esc(formatResult(v, eventId, "single"))}</span>`).join("")}</td>
              </tr>`
            )
            .join("")}</tbody></table></div>`
      )
      .join("");
    renderPagination(pager, data, (next) => {
      resultsPage = next;
      loadHistory();
    });
  } catch (error) {
    showError(target, error, loadHistory);
  }
}

function renderAll() {
  renderHeader();
  body.innerHTML = `${renderSummary()}${renderRecords()}${renderChangeCountry()}${renderHistory()}`;
  document.getElementById("event-filter").addEventListener("change", () => {
    resultsPage = 1;
    loadHistory();
  });
  document.getElementById("country-form").addEventListener("submit", changeCountry);
  loadHistory();
}

async function changeCountry(event) {
  event.preventDefault();
  const select = document.getElementById("new-country");
  try {
    const updated = await api(`/persons/${encodeURIComponent(person.person_no)}/country`, {
      method: "PUT",
      body: { country_id: select.value },
    });
    person = updated;
    toast(`Now representing ${updated.country_name}.`, "success");
    renderAll();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function boot() {
  if (!personRef) {
    showError(body, new Error("No person given. Try ?id=2012PARK03 or ?id=190."));
    return;
  }
  showLoading(body, "Loading person…");
  try {
    const [personData, countryList] = await Promise.all([
      api(`/persons/${encodeURIComponent(personRef)}`),
      api("/countries"),
    ]);
    person = personData;
    countries = countryList;
  } catch (error) {
    showError(body, error, boot);
    return;
  }
  renderAll();
}

boot();
