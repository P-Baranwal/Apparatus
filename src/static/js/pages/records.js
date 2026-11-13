import { api } from "../api.js";
import {
  esc,
  eventBadge,
  recordBadge,
  renderShell,
  setTitle,
  showEmpty,
  showError,
  showLoading,
} from "../ui.js";

renderShell({ active: "records" });

const target = document.getElementById("results");
const RECORD_LABELS = {
  WR: "World record",
  NR: "National record",
  AsR: "Asian record",
  ER: "European record",
  NAR: "North American record",
  SAR: "South American record",
  AfR: "African record",
  OcR: "Oceanian record",
};

async function boot() {
  showLoading(target, "Loading records…");
  try {
    const rows = await api("/stats/records");
    if (!rows.length) {
      showEmpty(target, "No record marks in this dataset.");
      return;
    }
    const byEvent = new Map();
    for (const row of rows) {
      if (!byEvent.has(row.event_id)) byEvent.set(row.event_id, []);
      byEvent.get(row.event_id).push(row);
    }
    target.innerHTML = `<div class="card">
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Event</th><th>Type</th><th>Record</th><th class="num">Count</th>
        </tr></thead>
        <tbody>${[...byEvent]
          .map(([eventId, list]) =>
            list
              .map(
                (row, index) => `<tr>
                  ${index === 0 ? `<td rowspan="${list.length}" class="nowrap">${eventBadge(eventId)}</td>` : ""}
                  <td>${esc(row.kind === "average" ? "Average" : "Single")}</td>
                  <td nowrap>${recordBadge(row.record_code)}
                    <span class="muted small">${esc(RECORD_LABELS[row.record_code] ?? "Record")}</span></td>
                  <td class="num">${row.count}</td>
                </tr>`
              )
              .join("")
          )
          .join("")}</tbody></table></div>
      <p class="muted small" style="margin-top:10px">
        Counts include a result only when the export carries an explicit marker, so
        they reflect marked records in these 15 competitions rather than all-time totals.
      </p>
    </div>`;
  } catch (error) {
    showError(target, error, boot);
  }
}

setTitle("Records");
boot();
