# Frontend references

What each page was modelled on, what was verified against the live site, and what is an
assumption. Kept outside `src/` and not shipped, per INSTRUCTIONS.md §6.

Sources used (13 Nov 2026):

- `https://www.worldcubeassociation.org/` — homepage structure (hero copy, card grid, sections).
- `https://www.worldcubeassociation.org/competitions/IndianNationals2023` — competition page:
  results sub-nav (Results / Podiums / All / By Person / Scrambles), General Info field
  order, Events table, Highlights table columns (Event, Name, Best, Average, Representing,
  Solves), registration-requirements wording.
- `https://www.worldcubeassociation.org/persons/2012PARK03` — person page: details table
  (Region, WCA ID, Gender, Competitions, Completed Solves), Current Personal Records
  (Event, NR, CR, WR, Single, Average, WR, CR, NR), medal/record collection blocks,
  results-by-event tables (Competition, Round, Place, Single, Average, Solves).
- INSTRUCTIONS.md §4.1 colour tokens, §4.2 header/footer, §4.3 URL scheme, §4.4 page anatomy.
- Result display confirmed from live pages: `27/30 45:54` (multi-blind),
  `1:32.54` (6x6, under 10 minutes), record marker rendered after the value (`24.31 NR`),
  attempts shown without parentheses in podiums tables.

## Page mapping

| Ours | WCA reference | Pattern |
|---|---|---|
| `index.html` | `/` | Home + global search |
| `search.html?q=` | header omnisearch results | Q1 |
| `competitions.html` | `/competitions` | Q2 browse + filters + sort |
| `competition.html?id=` (`tab=info\|events\|results\|registrations`) | `/competitions/:id` + `/results/:view` | Q3 |
| `person.html?id=` | `/persons/:wca_id` | Q3, W2 |
| `country.html?country_id=` | `/persons?region=` / competition list by country | Q6 |
| `rankings.html?event=&type=` | `/results/rankings/:event/:type` | Q5 |
| `records.html` | `/results/records` | F4 (record counts) |
| `stats.html` | Statistics site | Q4 |
| `404.html` | — | error state |

## Verified vs assumed

| Item | Status |
|---|---|
| Link colour `#e64503`, brand `#375e97`, stripe `#e9e9e9`, nav hover `#f0f0f0`, record colours | Verified (INSTRUCTIONS.md §4.1, from the WCA repo SCSS) |
| Header layout: wordmark left, nav, right-aligned search box | Verified from fetched HTML |
| General Info field order | Verified from the fetched competition page |
| Person details + Personal Records column order | Verified from the fetched person page |
| Multi-blind, FMC and 10-minute time formatting | Verified against live result values |
| Font stack (Helvetica Neue/Arial), 14px base, 1170px container | Assumed (Bootstrap 3 defaults; no screenshot/devtools value) |
| Spacing scale, border colour `#ddd`, muted text `#767676` | Assumed |
| Medal colours (gold `#a4801c`, silver `#6b6b6b`, bronze `#8a5a2b`) | Assumed |
| Mobile breakpoint at 768px, nav collapses to a Menu button | Assumed, consistent with the Bootstrap grid the site uses |
| Event badges as text pills rather than the `@cubing/icons` font | Deliberate: no external fonts or CDNs (INSTRUCTIONS.md §5.3) |
| Registration form placement | Adapted: WCA uses `/competitions/:id/register` behind login; we show the same form in the Registrations tab on the competition page |
| Rankings table columns | Assumed: derived from our API (rank, name, country, value, NR, CR, competition) |
| Medal collection / record collection blocks on the person page | Omitted: the API does not expose per-person medal counts, so no invented numbers are shown |

## WCA features intentionally omitted

Information/Regulations/Forum/WCA Live menus, language selector, sign-in, map view on the
competitions list, scramble viewer, article tabs, and the competition schedule tab. They
are out of scope for the Phase 4 feature list and would be dead links.

## Screenshots

Captured from our app at 1280px and 375px into `docs/screenshots/`:

- `competitions.png`, `competition_info.png`, `competition_results.png`, `person.png`,
  `rankings.png`, `records.png`, `stats.png`, `country.png`, `search.png`,
  `registrations.png`, `register_after.png`
- `mobile_competitions.png`, `mobile_results.png`

No screenshots of the live WCA site were supplied, so pixel comparison was not possible;
comparisons above are structural (labels, columns, field order, URL scheme).
