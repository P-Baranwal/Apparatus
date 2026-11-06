#!/usr/bin/env python3

import csv

from common import DATA, api_json, delegates

REGIONS_ACTIVE = (
    "/user_groups?groupType=delegate_regions&sort=name&isActive=true&isHidden=false"
)
REGIONS_INACTIVE = (
    "/user_groups?groupType=delegate_regions&sort=name&isActive=false&isHidden=false"
)
TEAMS_ACTIVE = (
    "/user_groups?groupType=teams_committees&sort=name&isActive=true&isHidden=false"
)
BOARD_ACTIVE = "/user_groups?groupType=board&sort=name&isActive=true&isHidden=false"
TEAMS_INACTIVE = (
    "/user_groups?groupType=teams_committees&sort=name&isActive=false&isHidden=false"
)


def write_csv(name, header, rows):
    path = DATA / name
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{name:16s} {len(rows):4d} rows -> {path}")


active = api_json(REGIONS_ACTIVE, "regions_active.json")
inactive = api_json(REGIONS_INACTIVE, "regions_inactive.json")
used_region_ids = {d["region_id"] for d in delegates() if d.get("region_id")}
assert used_region_ids <= {g["id"] for g in active}
assert used_region_ids == {g["id"] for g in active}, "active region without delegates"

all_regions = active + inactive
parent_ids = {
    g["parent_group_id"] for g in all_regions if g["parent_group_id"] is not None
}
active_names = {g["name"] for g in active}
inactive_leaves = sorted(
    (
        g
        for g in inactive
        if g["id"] not in used_region_ids
        and g["id"] not in parent_ids
        and g["name"] not in active_names
    ),
    key=lambda g: g["id"],
)
assert len(inactive_leaves) >= 8, len(inactive_leaves)
demo_regions = inactive_leaves[:8]

region_rows = [
    [g["id"], g["name"], g["parent_group_id"] if g["parent_group_id"] is not None else ""]
    for g in sorted(active + demo_regions, key=lambda g: g["id"])
]
ids = {r[0] for r in region_rows}
assert len(ids) == len(region_rows)
assert len({r[1] for r in region_rows}) == len(region_rows)
assert all(r[2] == "" or r[2] in ids for r in region_rows)

parent = {r[0]: (r[2] if r[2] != "" else None) for r in region_rows}
for start in parent:
    seen = set()
    node = start
    while node is not None:
        assert node not in seen, f"region cycle at {start}"
        seen.add(node)
        node = parent[node]
assert used_region_ids <= ids

write_csv(
    "regions.csv", ["Region_ID", "Region_Name", "Parent_Region_ID"], region_rows
)

active_groups = (
    api_json(TEAMS_ACTIVE, "teams_groups.json")
    + api_json(BOARD_ACTIVE, "board_groups.json")
)
inactive_groups = api_json(TEAMS_INACTIVE, "teams_inactive.json")

team_rows = []
for group in sorted(active_groups + inactive_groups, key=lambda g: g["id"]):
    if group["group_type"] == "board":
        team_id = "board"
        kind = "board"
    else:
        team_id = group["metadata"]["friendly_id"]
        kind = "committee" if group["name"].endswith("Committee") else "team"
    email = group["metadata"].get("email") or ""
    assert team_id, group["name"]
    assert kind in {"board", "committee", "team"}, group["name"]
    assert (
        "@" in email and email.split("@", 1)[1] == "worldcubeassociation.org"
    ), (group["name"], email)
    team_rows.append([team_id, group["name"], kind, email])

team_rows.sort(key=lambda r: r[0])
assert len({r[0] for r in team_rows}) == len(team_rows)
assert len({r[1] for r in team_rows}) == len(team_rows)

write_csv("teams.csv", ["Team_ID", "Team_Name", "Kind", "Contact_Email"], team_rows)

role_counts = {}
for group in active_groups + inactive_groups:
    team_id = "board" if group["group_type"] == "board" else group["metadata"]["friendly_id"]
    roles = api_json(
        f"/user_roles?groupId={group['id']}&isActive=true&sort=status:desc,name",
        f"teams/{team_id}.json",
    )
    if group in inactive_groups:
        assert len(roles) == 0, f"inactive team {team_id} has active roles"
    role_counts[team_id] = len(roles)
inactive_team_ids = {g["metadata"]["friendly_id"] for g in inactive_groups}

print()
print(f"active regions: {len(active)} | demo leaves added: {len(demo_regions)}")
print(
    "demo-safe regions: "
    + ", ".join(f"{g['id']}={g['name']}" for g in demo_regions)
)
print(f"region roots: {sum(1 for r in region_rows if r[2] == '')}")
print(f"teams: {len(team_rows)} (board/committee/team: "
      f"{sum(1 for r in team_rows if r[2]=='board')}/"
      f"{sum(1 for r in team_rows if r[2]=='committee')}/"
      f"{sum(1 for r in team_rows if r[2]=='team')})")
print("active role counts: " + ", ".join(f"{k}={v}" for k, v in sorted(role_counts.items())))
print("inactive teams with zero active roles: " + ", ".join(
    sorted(t for t in inactive_team_ids if role_counts[t] == 0)
))
