import { api } from "../api.js";
import {
  debounce,
  esc,
  eventBadge,
  formatDateRange,
  loadLookups,
  renderPagination,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
  statusPill,
} from "../ui.js";

renderShell({ active: "competitions" });

const form = document.getElementById("filters");
const results = document.getElementById("results");
const pagination = document.getElementById("pagination");
const count = document.getElementById("result-count");

const params = new URLSearchParams(location.search);
let page = 1;

for (const [key, value] of params) {
  const field = form.elements.namedItem(key);
  if (field) field.value = value;
}

function currentFilters() {
  const values = {};
  for (const element of form.elements) {
    if (element.name && element.value) values[element.name] = element.value;
  }
  return values;
}

function syncUrl() {
  const query = new URLSearchParams(currentFilters());
  history.replaceState(null, "", query.toString() ? `/competitions.html?${query}` : "/competitions.html");
}

async function render() {
  const filters = currentFilters();
  showLoading(results, "Loading competitions…");
  try {
    const data = await api("/competitions", { params: { ...filters, page, page_size: 20 } });
    count.textContent = `${data.total.toLocaleString()} competition${data.total === 1 ? "" : "s"}`;

    if (!data.items.length) {
      showEmpty(
        results,
        "No competitions match these filters.",
        '<button class="btn btn-sm" type="button" id="reset-empty">Clear filters</button>'
      );
      document.getElementById("reset-empty")?.addEventListener("click", () => {
        form.reset();
        page = 1;
        syncUrl();
        render();
      });
      pagination.innerHTML = "";
      return;
    }

    results.innerHTML = `<div class="table-wrap"><table>
      <thead><tr>
        <th class="nowrap">Date</th><th>Competition</th><th>Location</th>
        <th>Country</th><th class="center">Competitors</th>
      </tr></thead>
      <tbody>${data.items
        .map(
          (c) => `<tr>
            <td class="nowrap">${esc(formatDateRange(c.start_date, c.end_date))}</td>
            <td>
              <a href="/competition.html?id=${encodeURIComponent(c.competition_id)}">${esc(c.name)}</a>
              ${statusPill(c.status)}
              ${c.main_event_id ? eventBadge(c.main_event_id) : ""}
              <span class="record-id">${esc(c.competition_id)}</span>
            </td>
            <td>${esc(c.city ?? "")}</td>
            <td><a href="/country.html?country_id=${encodeURIComponent(c.country_id)}">${esc(c.country_name)}</a></td>
            <td class="center">${c.registered_count}${
              c.competitor_limit ? `<span class="muted small"> / ${c.competitor_limit}</span>` : ""
            }</td>
          </tr>`
        )
        .join("")}</tbody></table></div>`;

    renderPagination(pagination, data, (next) => {
      page = next;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  } catch (error) {
    showError(results, error, render);
  }
}

const reload = debounce(() => {
  page = 1;
  syncUrl();
  render();
}, 300);

form.addEventListener("input", (event) => {
  if (event.target.name === "q" || event.target.name === "year") reload();
});
form.addEventListener("change", () => {
  page = 1;
  syncUrl();
  render();
});
form.addEventListener("submit", (event) => event.preventDefault());
document.getElementById("clear").addEventListener("click", () => {
  form.reset();
  page = 1;
  syncUrl();
  render();
});

async function init() {
  try {
    const { countries } = await loadLookups();
    const countrySelect = document.getElementById("country_id");
    const grouped = new Map();
    for (const country of countries) {
      if (!grouped.has(country.continent_name)) grouped.set(country.continent_name, []);
      grouped.get(country.continent_name).push(country);
    }
    const regionSelect = document.getElementById("continent_id");
    for (const [continent, list] of [...grouped].sort((a, b) => a[0].localeCompare(b[0]))) {
      regionSelect.insertAdjacentHTML(
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

    const events = await api("/events");
    const eventSelect = document.getElementById("event_id");
    for (const event of events) {
      eventSelect.insertAdjacentHTML(
        "beforeend",
        `<option value="${esc(event.event_id)}">${esc(event.event_name)}</option>`
      );
    }
    for (const [key, value] of new URLSearchParams(location.search)) {
      const field = form.elements.namedItem(key);
      if (field) field.value = value;
    }
  } catch (error) {
    showError(results, error, init);
    return;
  }
  render();
}

setTitle("Competitions");
init();
