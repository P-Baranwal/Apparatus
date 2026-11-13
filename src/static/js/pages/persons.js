import { api } from "../api.js";
import {
  debounce,
  esc,
  renderPagination,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
} from "../ui.js";

renderShell({ active: "persons" });

const form = document.getElementById("filters");
const results = document.getElementById("results");
const pagination = document.getElementById("pagination");
const count = document.getElementById("result-count");
let page = 1;

for (const [key, value] of new URLSearchParams(location.search)) {
  const field = form.elements.namedItem(key);
  if (field) field.value = value;
}

function filters() {
  const values = {};
  for (const element of form.elements) {
    if (element.name && element.value) values[element.name] = element.value;
  }
  return values;
}

function syncUrl() {
  const query = new URLSearchParams(filters());
  history.replaceState(null, "", query.toString() ? `/persons.html?${query}` : "/persons.html");
}

async function render() {
  showLoading(results, "Loading persons…");
  try {
    const data = await api("/persons", { params: { ...filters(), page, page_size: 25 } });
    count.textContent = `${data.total.toLocaleString()} person${data.total === 1 ? "" : "s"}`;
    if (!data.items.length) {
      showEmpty(results, "No persons match this search.");
      pagination.innerHTML = "";
      return;
    }
    results.innerHTML = `<div class="table-wrap"><table>
      <thead><tr>
        <th>Name</th><th>WCA ID</th><th>Country</th>
        <th class="center">Competitions</th><th class="center">Podiums</th>
      </tr></thead>
      <tbody>${data.items
        .map(
          (p) => `<tr>
            <td><a href="/person.html?id=${encodeURIComponent(p.person_no)}">${esc(p.name)}</a>
              <span class="record-id">Person_No ${p.person_no}</span></td>
            <td class="mono">${esc(p.wca_id ?? "—")}</td>
            <td><a href="/country.html?country_id=${encodeURIComponent(p.country_id)}">${esc(p.country_name)}</a></td>
            <td class="center">${p.competitions_count}</td>
            <td class="center">${p.podiums_count}</td>
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

const debounced = debounce(() => {
  page = 1;
  syncUrl();
  render();
}, 300);

form.addEventListener("input", (event) => {
  if (event.target.name === "q") debounced();
});
form.addEventListener("change", () => {
  page = 1;
  syncUrl();
  render();
});
form.addEventListener("submit", (event) => event.preventDefault());

async function init() {
  try {
    const countries = await api("/countries");
    const select = document.getElementById("country_id");
    const groups = new Map();
    for (const country of countries) {
      if (!groups.has(country.continent_name)) groups.set(country.continent_name, []);
      groups.get(country.continent_name).push(country);
    }
    for (const [continent, list] of [...groups].sort((a, b) => a[0].localeCompare(b[0]))) {
      const group = document.createElement("optgroup");
      group.label = continent;
      for (const country of list) {
        group.insertAdjacentHTML(
          "beforeend",
          `<option value="${esc(country.country_id)}">${esc(country.name)}</option>`
        );
      }
      select.appendChild(group);
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

setTitle("Persons");
init();
