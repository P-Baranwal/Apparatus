import { api } from "../api.js";
import {
  esc,
  eventBadge,
  param,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
} from "../ui.js";

renderShell({ active: "stats" });

const tabs = document.getElementById("tabs");
const content = document.getElementById("content");
let activeTab = param("tab", "medals");

const TABS = [
  ["medals", "Medal table"],
  ["countries", "Competitions by country"],
  ["records", "Record counts"],
];

function renderTabs() {
  tabs.innerHTML = TABS.map(
    ([key, label]) =>
      `<button type="button" role="tab" data-tab="${key}" aria-selected="${key === activeTab}">${label}</button>`
  ).join("");
  tabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.tab;
      history.replaceState(null, "", `/stats.html?tab=${activeTab}`);
      renderTabs();
      renderTab();
    });
  });
}

async function renderMedals() {
  const rows = await api("/stats/medals");
  if (!rows.length) {
    showEmpty(content, "No podiums recorded.");
    return;
  }
  content.innerHTML = `<div class="card">
    <h2>Medal table</h2>
    <p class="muted small">Podium finishes in the final round of each event, by represented country.</p>
    <div class="table-wrap"><table>
      <thead><tr>
        <th class="num">#</th><th>Country</th><th>Region</th>
        <th class="num">Gold</th><th class="num">Silver</th><th class="num">Bronze</th><th class="num">Total</th>
      </tr></thead>
      <tbody>${rows
        .map(
          (row, index) => `<tr>
            <td class="num">${index + 1}</td>
            <td><a href="/country.html?country_id=${encodeURIComponent(row.country_id)}">${esc(row.country_name)}</a></td>
            <td class="muted">${esc((row.continent_id ?? "").replace(/^_/, ""))}</td>
            <td class="num medal medal-1">${row.gold}</td>
            <td class="num medal medal-2">${row.silver}</td>
            <td class="num medal medal-3">${row.bronze}</td>
            <td class="num"><strong>${row.total}</strong></td>
          </tr>`
        )
        .join("")}</tbody></table></div>
  </div>`;
}

async function renderCountries() {
  const rows = await api("/stats/competitions-by-country");
  if (!rows.length) {
    showEmpty(content, "No competitions recorded.");
    return;
  }
  const byYear = new Map();
  for (const row of rows) {
    if (!byYear.has(row.year)) byYear.set(row.year, []);
    byYear.get(row.year).push(row);
  }
  content.innerHTML = `<div class="card">
    <h2>Competitions by country and year</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Year</th><th>Country</th><th class="num">Competitions</th></tr></thead>
      <tbody>${[...byYear]
        .sort((a, b) => b[0] - a[0])
        .map(([year, list]) =>
          list
            .map(
              (row, index) => `<tr>
                ${index === 0 ? `<td rowspan="${list.length}" class="nowrap"><strong>${year}</strong></td>` : ""}
                <td><a href="/country.html?country_id=${encodeURIComponent(row.country_id)}">${esc(row.country_name)}</a></td>
                <td class="num">${row.competition_count}</td>
              </tr>`
            )
            .join("")
        )
        .join("")}</tbody></table></div>
  </div>`;
}

async function renderRecords() {
  const rows = await api("/stats/records");
  if (!rows.length) {
    showEmpty(content, "No record marks recorded.");
    return;
  }
  content.innerHTML = `<div class="card">
    <h2>Record counts</h2>
    <p class="muted small"><a href="/records.html">Open the records page</a> for the full breakdown.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Event</th><th class="num">Record marks</th></tr></thead>
      <tbody>${[...rows
        .reduce((map, row) => map.set(row.event_id, (map.get(row.event_id) ?? 0) + row.count), new Map())
        .entries()]
        .map(
          ([eventId, total]) => `<tr>
            <td class="nowrap">${eventBadge(eventId)}</td>
            <td class="num">${total}</td>
          </tr>`
        )
        .join("")}</tbody></table></div>
  </div>`;
}

async function renderTab() {
  showLoading(content, "Loading statistics…");
  try {
    if (activeTab === "countries") await renderCountries();
    else if (activeTab === "records") renderRecords();
    else await renderMedals();
  } catch (error) {
    showError(content, error, renderTab);
  }
}

setTitle("Statistics");
renderTabs();
renderTab();
