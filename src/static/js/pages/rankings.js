import { api } from "../api.js";
import {
  esc,
  eventBadge,
  formatResult,
  param,
  renderPagination,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
} from "../ui.js";

renderShell({ active: "rankings" });

const form = document.getElementById("filters");
const results = document.getElementById("results");
const pagination = document.getElementById("pagination");
const count = document.getElementById("result-count");
let page = 1;

function filters() {
  const values = {};
  for (const element of form.elements) {
    if (element.name && element.value) values[element.name] = element.value;
  }
  return values;
}

function syncUrl() {
  const query = new URLSearchParams(filters());
  history.replaceState(null, "", `/rankings.html?${query}`);
}

async function render() {
  const { event, type, country_id, continent_id } = filters();
  showLoading(results, "Loading rankings…");
  try {
    const data = await api(`/rankings/${encodeURIComponent(event)}`, {
      params: { kind: type ?? "single", country_id, continent_id, page, page_size: 100 },
    });
    count.textContent = `${data.total.toLocaleString()} ranked ${type === "average" ? "averages" : "singles"}`;
    if (!data.items.length) {
      showEmpty(results, "No rankings for this selection.");
      pagination.innerHTML = "";
      return;
    }
    results.innerHTML = `<div class="card">
      <h2>${eventBadge(event)} ${esc(type === "average" ? "Average" : "Single")} rankings</h2>
      <div class="table-wrap"><table class="wca-results">
        <thead><tr>
          <th class="num">#</th><th>Name</th><th>Country</th>
          <th class="num">${type === "average" ? "Average" : "Best"}</th>
          <th class="num">NR</th><th class="num">CR</th><th>Competition</th>
        </tr></thead>
        <tbody>${data.items
          .map((r) => {
            const value = type === "average" ? r.average : r.best;
            return `<tr>
              <td class="num">${r.rank}</td>
              <td><a href="/person.html?id=${encodeURIComponent(r.person_no)}">${esc(r.name)}</a>
                <span class="wca-id">${esc(r.wca_id ?? "")}</span></td>
              <td><a href="/country.html?country_id=${encodeURIComponent(r.country_id)}">${esc(r.country_name)}</a></td>
              <td class="num"><strong>${esc(formatResult(value, r.event_id ?? event, type))}</strong></td>
              <td class="num">${r.national_rank ?? "—"}</td>
              <td class="num">${r.continental_rank ?? "—"}</td>
              <td><a href="/competition.html?id=${encodeURIComponent(r.competition_id)}">${esc(r.competition_name ?? r.competition_id)}</a></td>
            </tr>`;
          })
          .join("")}</tbody></table></div>
      <div id="pager"></div>
    </div>`;
    renderPagination(document.getElementById("pager"), data, (next) => {
      page = next;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  } catch (error) {
    showError(results, error, render);
  }
}

form.addEventListener("change", () => {
  page = 1;
  syncUrl();
  render();
});
form.addEventListener("submit", (event) => event.preventDefault());

async function init() {
  try {
    const [events, countries] = await Promise.all([api("/events"), api("/countries")]);
    const eventSelect = document.getElementById("event");
    for (const event of events) {
      eventSelect.insertAdjacentHTML(
        "beforeend",
        `<option value="${esc(event.event_id)}">${esc(event.event_name)}</option>`
      );
    }
    const continentSelect = document.getElementById("continent");
    const countrySelect = document.getElementById("country");
    const groups = new Map();
    for (const country of countries) {
      if (!groups.has(country.continent_name)) groups.set(country.continent_name, []);
      groups.get(country.continent_name).push(country);
    }
    for (const [continent, list] of [...groups].sort((a, b) => a[0].localeCompare(b[0]))) {
      continentSelect.insertAdjacentHTML(
        "beforeend",
        `<option value="${esc(list[0].continent_id)}">${esc(continent)}</option>`
      );
      const group = document.createElement("optgroup");
      group.label = continent;
      for (const country of list) {
        group.insertAdjacentHTML(
          "beforeend",
          `<option value="${esc(country.country_id)}">${esc(country.name)}</option>`
        );
      }
      countrySelect.appendChild(group);
    }

    eventSelect.value = param("event", "333");
    document.getElementById("kind").value = param("type", "single");
    if (param("country_id")) countrySelect.value = param("country_id");
    if (param("continent_id")) continentSelect.value = param("continent_id");
  } catch (error) {
    showError(results, error, init);
    return;
  }
  setTitle("Rankings");
  render();
}

init();
