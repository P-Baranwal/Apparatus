# INSTRUCTIONS.md: Reproducing the WCA website's look and flows

For any AI agent (with web search/fetch, and ideally a shell) building the frontend in `src/static/`. Read `AGENTS.md` first; its rules win. This file only covers **how to find out what the WCA site looks like and how to recreate it** inside our constraints: plain HTML/CSS/JS, no framework, no npm, no build step, no external CDN.

Verified on 13 Nov 2026 against worldcubeassociation.org and `github.com/thewca/worldcubeassociation.org` (branch `main`). The site changes; re-check anything marked "verify".

---

## 1. What an agent can and cannot get

| Source | Gives | Does not give |
|---|---|---|
| Web fetch of live pages | Nav menus, labels, link targets, copy, table headers, section order (as markdown) | CSS, colours, spacing, fonts, screenshots |
| Same, for React-rendered pages | Only the shell (header, footer). The Competitions list, Rankings and Records pages come back without their filters or tables | The actual filters/tables |
| Same, some URLs | Blocked by `robots` or bot detection (seen on `/results/rankings/...`, `/results/records`, GitHub `tree/` pages) | Anything |
| **The public GitHub repo** (GPL-3.0) | Real SCSS (colour variables, widths, table rules), ERB view templates (page anatomy, tab order), React components (filter controls) | Rendered output |
| Screenshots from the user | Everything visual | Nothing structural |

So "as close as possible" is reachable for **structure, navigation, labels, colours, table layouts and flows**. Pixel-exact fonts and spacing are not, unless the user supplies screenshots (section 7). Do not claim pixel fidelity.

**If a page is blocked, do not work around it** (no curl/mirror/cache tricks). Use the repo source for that page, or ask the user for a screenshot.

## 2. Source priority

1. **Repo source** (best signal; section 3).
2. **Fetched live pages** for nav, labels, copy and URL scheme (section 4 already records what was seen; don't refetch needlessly).
3. **User screenshots** for anything client-rendered (Competitions list, Rankings, Records).
4. **Guess last**, and label every guess `/* assumption */` in CSS or in the notes file.

## 3. Reading the repo

Clone metadata only, outside the project tree (never commit it):

```bash
D=<scratch dir>/wca_src && mkdir -p "$D" && cd "$D"
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/thewca/worldcubeassociation.org repo
cd repo
git ls-tree -r --name-only HEAD | grep -E '\.(scss|css)$' | grep -v semantic   # stylesheet list
git show HEAD:app/assets/stylesheets/variables.scss                            # read single files
```

Files worth reading (all confirmed to exist):

- Styles: `app/assets/stylesheets/{variables,wca,navbar-static-top,results,persons,competitions,competition_tabs,registrations}.scss`; `app/webpacker/stylesheets/{homepage,competition_results,event_navigation,override}.scss`
- Competition pages: `app/views/competitions/{index,show,_nav,_competition_info,_events_tab,_registration_requirements,_results_table,show_podiums,show_all_results,show_results_by_person}.html.erb`
- Person pages: `app/views/persons/{index,show,_details,_personal_records,_results_by_event,_medal_collection,_record_collection}.html.erb`
- Rankings/records: `app/views/results/{rankings,records}.html.erb`, `app/webpacker/components/Results/` (`ResultsFilter.jsx`, `Rankings/RankingsTable.jsx`, `Records/*`, `TableColumns.jsx`, `TableCells.jsx`)
- Competitions list filters: `app/webpacker/components/CompetitionsOverview/` (`CompetitionsFilters.jsx`, `ListView.js`, `MapView.js`)
- Header search: `app/webpacker/components/SearchWidget/`; navbar markup lives somewhere under `app/views/layouts/` (not yet located; verify)

Two frontends exist in the repo: the legacy Rails app in `app/` (ERB + Bootstrap 3 + `semantic-ui-react` components) and a newer `next-frontend/` (Next.js, Chakra UI v3). The live pages fetched (competitions, persons, competition detail) are still the Rails ones (Rails CSRF meta tags, Sprockets asset paths). **Model the Rails site.** `next-frontend/` is a redesign in progress; its directory page was blocked, so treat it as unverified.

**Licence and branding rules.** The repo is GPL-3.0. Read it to learn values (hex codes, widths, column order, tab order) and rewrite everything in our own CSS/JS. Do not paste SCSS, templates or components, and do not copy the WCA logo or image assets. Use a plain text wordmark, and add a footer line such as "UI modelled on worldcubeassociation.org (course project, not affiliated)". We do not use Bootstrap, Semantic UI, Chakra or any WCA package, and adding one requires asking first (AGENTS.md section 12).

## 4. Verified reference notes

### 4.1 Colours (`variables.scss`, `results.scss`, `homepage.scss`, `navbar-static-top.scss`)

Put these in `:root` in `style.css` as CSS custom properties:

```css
:root {
  --link: #e64503;            /* $link-color: links are orange-red, not blue */
  --brand: #375e97;           /* $blue / $brand-primary */
  --dark-blue: #082c52;
  --bright-blue: #007bff;
  --orange: #fc4a0a;
  --orange-bg: #ffeca8;
  --green: #c4e8b5;
  --dark-green: #245011;
  --dark-red: #701203;
  --row-highlight: #ffff94;   /* highlighted table row */
  --table-stripe: #e9e9e9;    /* $table-bg-accent */
  --home-bg: #f8f8f8;         /* homepage body background */
  --nav-hover: #f0f0f0;       /* top-nav item hover */
  --rec-wr: #0366d6;          /* world record */
  --rec-cr: #d00404;          /* continental record */
  --rec-nr: #28a745;          /* national record */
  --rec-pb: #fc4a0a;          /* personal best */
}
```

- Event-filter "All"/active buttons: base colour = link colour, hover = darker link colour, **active = brand blue** (`results.scss`).
- Verify: font family and base size. `variables.scss` only overrides link colour and brand colour, so Bootstrap 3 defaults likely apply (Helvetica Neue/Arial stack, 14px base, container widths 750/970/1170px, breakpoints 768/992/1200px). Treat as an assumption until a screenshot or devtools value confirms it.

### 4.2 Header and footer (fetched HTML + `navbar-static-top.scss`)

- Light top navbar, logo at left (about 50px tall on desktop, 56px on the mobile brand), nav hover background `#f0f0f0`, a search box (the "omnisearch") at the right: 230px wide, 500px at viewport >= 1500px, full width in the collapsed mobile menu.
- Live top-level menus: **Information** (About the WCA, Documents, Officers & Board, Delegates, Teams and Committees, Regional Organizations, Translators, FAQ, Educational resources, Contact, Speedcubing History, Media Submission, Privacy, Disclaimer, Tools, Logo), **Competitions** (All, My Competitions), **Results** (Rankings, Records, Persons, Statistics, Multimedia, Results Export, Developer Export), **Regulations**, **Find us** (social links), **Forum**, **WCA Live**, a language selector, **Sign in**.
- Footer: About us, FAQ, Contact, GitHub, Privacy, Disclaimer, plus a cookie notice.
- **Ours (keep it small, no dead links):** wordmark, **Competitions** (All), **Results** (Rankings, Records, Persons, Statistics), header search box, footer with the attribution line. Leave out Information, Regulations, Forum, Live, locale and sign-in (out of scope per Phase 1, and no auth).

### 4.3 URL scheme (fetched links) and our equivalents

| WCA URL | Our page (query-string style) | Plan pattern |
|---|---|---|
| `/competitions` | `competitions.html` | Q2 |
| `/competitions/:id` | `competition.html?id=WC2025` | Q3 |
| `/competitions/:id/results/podiums`, `/all`, `/by_person` | tabs inside `competition.html` (`&tab=podiums\|all\|by_person`) | Q3 |
| `/competitions/:id/register` | register form (`register.html?id=`) | W1 |
| `/persons` | `persons.html` | Q1, Q6 |
| `/persons/:wca_id` | `person.html?id=2012PARK03` | Q3 |
| `/results/rankings/:event/:type` (`single`/`average`) | `rankings.html?event=333&type=single` | Q5 |
| `/results/records` | `records.html` | Q4 |
| statistics (a separate site) | `stats.html` | Q4 |

### 4.4 Page anatomy

**Competitions list** (React `CompetitionsOverview`; shell only when fetched). Filter form top to bottom: event icon-selector with All/Clear, Region selector, "Search" text input, a time-state button group (present is confirmed; check the rest in `CompetitionsFilters.jsx`). Results are a list grouped into sections such as "Competitions in progress (N)", rows showing date, name, location/venue; there is also a map view (skip it).

**Competition page** (`show.html.erb`, fetched):
- Page title, then a results sub-nav (Results: Podiums / All / By Person; Scrambles).
- Tab strip: General Info, Events, Schedule, then organiser-defined tabs.
- General Info field order: Date (with calendar link), City, Venue, Address, Details, Contact, Organizers, WCA Delegates, then a free-text Information block, then Main event, Competitors (count), Registration period, Registration requirements, Highlights.
- Highlights/podium table columns: Event, Name, Best, Average, Representing, Solves (5 attempt columns).
- Events table: Event, Format, Time Limit, Cutoff, Proceed (advancement), with glossary headings for Time limit / Cutoff / Format / Advancement condition.

**Results tables** (`wca.scss`, `results.scss`): `table.wca-results` columns Pos, Name, Best, Average, Representing, Solves. Record markers coloured with the `--rec-*` tokens. Attempts that were dropped from an average render in parentheses; other attempts reserve invisible parentheses so numbers stay aligned. WCA IDs use a monospace font.

**Persons list** (`persons.scss`): columns Name (40%), WCA ID (10%, monospace), Country (30%), Competitions (10%, centred), Podiums (10%, centred).

**Person page** (`persons/show.html.erb`): details block, personal records table, then a row with medal collection and record collection (shown only when non-zero), then justified tabs: Results (by event), Records, Championship podiums, Competitions map. Skip the map tab.

**Rankings / Records** (React `ResultsRankings`, not fetchable): a title, a "last updated" line, a selector bar (event icons plus Region, Type single/average, Years, Show, Gender) and a table. Exact columns are in `Results/TableColumns.jsx`; read that file or ask for a screenshot.

**Homepage** (`homepage.scss`): body background `#f8f8f8`, a tall cover banner (min-height 500px) with the title and three cards vertically centred. We replace it with hero + search + a "latest competitions" and "records" panel (Plan section 9).

## 5. How to build it

1. **Tokens first.** Paste the section 4.1 block into `style.css`; every colour in the app uses a variable. Add spacing/radius/font variables of your own, marked as assumptions.
2. **Shared pieces in `ui.js`:** `renderHeader()` (nav + search), `renderFooter()`, `eventBadge(eventId)`, `recordBadge(code)`, `formatResult(value, eventId, kind)` (AGENTS.md section 8), `renderResultsTable(rows)`, tabs helper, pagination.
3. **Event icons:** WCA uses the `@cubing/icons` font (an npm package). Default to a small rounded text badge showing the event name or ID (`3x3x3 Cube`, `333`). Only bring in an icon font after asking, and check its licence first.
4. **Tables:** striped rows (`--table-stripe`), right-aligned numeric columns, sticky header optional, horizontal scroll wrapper below 768px.
5. **Header search = Q1:** a text box that groups results as Competitions and Persons (WCA's `SearchWidget` shows competition and user items). Submitting goes to a results page; rows link to `competition.html` / `person.html`.
6. **Responsiveness:** collapse the nav into a menu button below ~768px, stack the filter bar, single-column cards. Check at ~375px, ~768px and desktop.
7. **Writes (our additions):** WCA's own registration needs login and payment, neither of which we have. Make the Register, Edit and Delete controls simple forms and buttons in the same visual style (orange-red link buttons, brand-blue primary), placed where a user would expect them (the competition page and the person/registration view).
8. **Do not fetch data from the WCA site at runtime.** All data comes through our API and database. (Population data is the DB teammate's job; for reference, WCA publishes a Results Export, with its README describing the value encoding.)

## 6. Keep a notes file

Maintain `docs/frontend_references.md` (outside `src/`, not shipped) with, per page: which WCA URL and repo files were used, what was verified vs assumed, and any user screenshot filenames. The README's "modelled on" statement and the video opening should match what is in this file.

## 7. What to ask the user for

The Competitions list, Rankings and Records pages cannot be read through fetch. Ask for **full-page screenshots at desktop width, plus one at phone width, of**:

1. `/competitions` (with one filter applied)
2. `/competitions/<any past competition id>` (General Info and Results tabs)
3. `/persons/2012PARK03`
4. `/results/rankings/333/single`
5. `/results/records`

Also ask which font the page renders in if it is not obvious (browser devtools, Computed tab). Until screenshots arrive, build from sections 4.1-4.4 and mark gaps as assumptions. This matches Plan Phase 0 ("screenshot its main pages and note navigation and flows").

## 8. Verification checklist

- [ ] Every colour in `style.css` comes from a `--variable`; every non-verified value is commented `assumption`.
- [ ] Nav labels, URL-style routes (section 4.3) and table column order match section 4.4.
- [ ] Record colours and the parenthesised-attempt convention work in the results tables.
- [ ] No Bootstrap/Semantic/Chakra, no CDN links, no WCA logo or copied assets; the attribution footer line is present.
- [ ] Every query-feature and write-feature (AGENTS.md section 7) is reachable from a natural control on the page that WCA would show it on.
- [ ] Side-by-side comparison with the live site or screenshots at 375px, 768px and desktop; differences logged in `docs/frontend_references.md`.
