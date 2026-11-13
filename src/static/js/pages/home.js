import { api } from "../api.js";
import {
  esc,
  formatDateRange,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
  statusPill,
} from "../ui.js";

renderShell({ home: true });

async function loadLatest() {
  const target = document.getElementById("latest-competitions");
  showLoading(target);
  try {
    const { items } = await api("/competitions", {
      params: { sort: "date_desc", page_size: 5 },
    });
    if (!items.length) {
      showEmpty(target, "No competitions yet.");
      return;
    }
    target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Date</th><th>Competition</th><th>Location</th></tr></thead>
      <tbody>${items
        .map(
          (c) => `<tr>
            <td class="nowrap">${esc(formatDateRange(c.start_date, c.end_date))}</td>
            <td><a href="/competition.html?id=${encodeURIComponent(c.competition_id)}">${esc(c.name)}</a>
              ${statusPill(c.status)}
              <span class="record-id">${esc(c.competition_id)}</span></td>
            <td>${esc(c.city ?? "")}<div class="muted small">${esc(c.country_name)}</div></td>
          </tr>`
        )
        .join("")}</tbody></table></div>`;
  } catch (error) {
    showError(target, error, loadLatest);
  }
}

async function loadMedals() {
  const target = document.getElementById("medal-table");
  showLoading(target);
  try {
    const rows = await api("/stats/medals");
    const top = rows.slice(0, 8);
    if (!top.length) {
      showEmpty(target, "No podiums yet.");
      return;
    }
    target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Country</th><th class="num">Gold</th><th class="num">Silver</th><th class="num">Bronze</th></tr></thead>
      <tbody>${top
        .map(
          (m) => `<tr>
            <td><a href="/country.html?country_id=${encodeURIComponent(m.country_id)}">${esc(m.country_name)}</a></td>
            <td class="num medal medal-1">${m.gold}</td>
            <td class="num medal medal-2">${m.silver}</td>
            <td class="num medal medal-3">${m.bronze}</td>
          </tr>`
        )
        .join("")}</tbody></table></div>`;
  } catch (error) {
    showError(target, error, loadMedals);
  }
}

setTitle("");
loadLatest();
loadMedals();
