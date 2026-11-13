import { api } from "../api.js";
import {
  esc,
  eventBadge,
  formatDateRange,
  param,
  renderPagination,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
  statusPill,
} from "../ui.js";

const countryId = param("country_id");
const header = document.getElementById("country-header");
const tabs = document.getElementById("tabs");
const content = document.getElementById("country-content");

let country = null;
let activeTab = param("tab", "persons");
let page = 1;

renderShell({ active: "persons" });

const TABS = [
  ["persons", "Persons"],
  ["competitions", "Competitions"],
];

function renderHeader() {
  setTitle(country.name);
  header.innerHTML = `
    <div class="page-head">
      <div>
        <h1>${esc(country.name)}</h1>
        <p class="muted">${esc(country.continent_name)} · ISO2 ${esc(country.iso2 ?? "—")}</p>
        <span class="record-id">${esc(country.country_id)}</span>
      </div>
    </div>`;
}

function renderTabs() {
  tabs.innerHTML = TABS.map(
    ([key, label]) =>
      `<button type="button" role="tab" data-tab="${key}" aria-selected="${key === activeTab}">${label}</button>`
  ).join("");
  tabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      activeTab = button.dataset.tab;
      page = 1;
      history.replaceState(
        null,
        "",
        `/country.html?country_id=${encodeURIComponent(countryId)}&tab=${activeTab}`
      );
      renderTabs();
      renderTab();
    });
  });
}

async function renderTab() {
  showLoading(content, "Loading…");
  try {
    if (activeTab === "competitions") {
      const data = await api("/competitions", {
        params: { country_id: countryId, sort: "date_desc", page, page_size: 25 },
      });
      if (!data.items.length) {
        showEmpty(content, "No competitions recorded for this country.");
        return;
      }
      content.innerHTML = `<div class="card"><div class="table-wrap"><table>
        <thead><tr><th>Date</th><th>Competition</th><th>City</th><th class="center">Registered</th></tr></thead>
        <tbody>${data.items
          .map(
            (c) => `<tr>
              <td class="nowrap">${esc(formatDateRange(c.start_date, c.end_date))}</td>
              <td><a href="/competition.html?id=${encodeURIComponent(c.competition_id)}">${esc(c.name)}</a>
                ${statusPill(c.status)}${c.main_event_id ? eventBadge(c.main_event_id) : ""}</td>
              <td>${esc(c.city ?? "")}</td>
              <td class="center">${c.registered_count}</td>
            </tr>`
          )
          .join("")}</tbody></table></div><div id="pager"></div></div>`;
      renderPagination(document.getElementById("pager"), data, (next) => {
        page = next;
        renderTab();
      });
      return;
    }

    const data = await api(`/countries/${encodeURIComponent(countryId)}/persons`, {
      params: { page, page_size: 25, sort: "name" },
    });
    if (!data.items.length) {
      showEmpty(content, "No persons recorded for this country.");
      return;
    }
    content.innerHTML = `<div class="card"><div class="table-wrap"><table>
      <thead><tr><th>Name</th><th>WCA ID</th><th class="center">Competitions</th><th class="center">Podiums</th></tr></thead>
      <tbody>${data.items
        .map(
          (p) => `<tr>
            <td><a href="/person.html?id=${encodeURIComponent(p.person_no)}">${esc(p.name)}</a></td>
            <td class="mono">${esc(p.wca_id ?? "—")}</td>
            <td class="center">${p.competitions_count}</td>
            <td class="center">${p.podiums_count}</td>
          </tr>`
        )
        .join("")}</tbody></table></div><div id="pager"></div></div>`;
    renderPagination(document.getElementById("pager"), data, (next) => {
      page = next;
      renderTab();
    });
  } catch (error) {
    showError(content, error, renderTab);
  }
}

async function boot() {
  if (!countryId) {
    showError(content, new Error("No country given. Try ?country_id=India."));
    return;
  }
  showLoading(content, "Loading…");
  try {
    country = await api(`/countries/${encodeURIComponent(countryId)}`);
  } catch (error) {
    showError(content, error, boot);
    return;
  }
  renderHeader();
  renderTabs();
  renderTab();
}

boot();
