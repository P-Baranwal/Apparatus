import { api } from "../api.js";
import {
  esc,
  formatDate,
  param,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
} from "../ui.js";

renderShell({ active: "" });

const form = document.getElementById("search-form");
const input = document.getElementById("q");
const results = document.getElementById("results");

input.value = param("q", "");

async function run(query) {
  if (!query.trim()) {
    results.innerHTML = `<div class="state">Enter a competition name, city, venue, person name or WCA ID.</div>`;
    return;
  }
  setTitle(`Search: ${query}`);
  history.replaceState(null, "", `/search.html?q=${encodeURIComponent(query)}`);
  showLoading(results, "Searching…");
  try {
    const data = await api("/search", { params: { q: query, limit: 20 } });
    if (!data.competitions.length && !data.persons.length) {
      showEmpty(results, `No matches for “${query}”.`);
      return;
    }
    results.innerHTML = `
      <section class="card">
        <h2>Competitions <span class="muted small">(${data.competitions.length})</span></h2>
        ${
          data.competitions.length
            ? `<div class="table-wrap"><table>
                 <thead><tr><th>Date</th><th>Competition</th><th>City</th><th>Country</th></tr></thead>
                 <tbody>${data.competitions
                   .map(
                     (c) => `<tr>
                       <td class="nowrap">${esc(formatDate(c.start_date))}</td>
                       <td><a href="/competition.html?id=${encodeURIComponent(c.competition_id)}">${esc(c.name)}</a>
                         <span class="record-id">${esc(c.competition_id)}</span></td>
                       <td>${esc(c.city ?? "")}</td>
                       <td>${esc(c.country_id)}</td>
                     </tr>`
                   )
                   .join("")}</tbody></table></div>`
            : '<p class="muted">No competitions matched.</p>'
        }
      </section>
      <section class="card">
        <h2>Persons <span class="muted small">(${data.persons.length})</span></h2>
        ${
          data.persons.length
            ? `<div class="table-wrap"><table>
                 <thead><tr><th>Name</th><th>WCA ID</th><th>Country</th></tr></thead>
                 <tbody>${data.persons
                   .map(
                     (p) => `<tr>
                       <td><a href="/person.html?id=${encodeURIComponent(p.person_no)}">${esc(p.name)}</a></td>
                       <td class="mono">${esc(p.wca_id ?? "—")}</td>
                       <td>${esc(p.country_id)}</td>
                     </tr>`
                   )
                   .join("")}</tbody></table></div>`
            : '<p class="muted">No persons matched.</p>'
        }
      </section>`;
  } catch (error) {
    showError(results, error, () => run(query));
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  run(input.value);
});

if (input.value) run(input.value);
else results.innerHTML = `<div class="state">Enter a competition name, city, venue, person name or WCA ID.</div>`;
