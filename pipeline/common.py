from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = ROOT / "cache"
DATA.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
API = "https://www.worldcubeassociation.org/api/v0"
EXPORT_URL = f"{API}/export/public"
UA = {"User-Agent": "wca-demo-pipeline/1.0"}

SHORTLIST = [
    "WC2025",
    "WC2023",
    "RubiksWCAAsianChampionship2024",
    "IndianNationals2023",
    "IndianEliteChampionship2026",
    "CubingATMOSphere2026",
    "IndianFMCChampionship2026",
    "IISERKolkataAutumnOpen2026",
    "BigNBlindBengaluruSep2026",
    "DCHydCubeOpenNovember2026",
    "IndianPBQChampionship2026",
    "CubeXWinterOpenBengaluru2026",
    "MohaliCubeOpen2026",
    "DCHyderabadOpenDecember2024",
    "BengalCubeOpen2025",
]
POOL_COMPS = {"WC2025", "WC2023", "RubiksWCAAsianChampionship2024"}
UPCOMING = [
    "DCHydCubeOpenNovember2026",
    "IndianPBQChampionship2026",
    "CubeXWinterOpenBengaluru2026",
]
CANCELLED = {"MohaliCubeOpen2026"}


def _get(url: str, path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def ensure_export() -> zipfile.ZipFile:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = sorted(CACHE.glob("*.tsv.zip"))
    if not cached:
        meta = _get(EXPORT_URL, CACHE / "export.json")
        req = urllib.request.Request(meta["tsv_url"], headers=UA)
        part = CACHE / "export.tsv.zip.part"
        with urllib.request.urlopen(req, timeout=1800) as resp, open(part, "wb") as fh:
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                fh.write(chunk)
            name = Path(urllib.parse.urlparse(resp.geturl()).path).name
        part.replace(CACHE / name)
        cached = [CACHE / name]
    return zipfile.ZipFile(cached[-1])


def export_rows(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as fh:
        yield from csv.DictReader(
            io.TextIOWrapper(fh, encoding="utf-8"), delimiter="\t"
        )


def competition(cid: str):
    return _get(f"{API}/competitions/{cid}", CACHE / "competitions" / f"{cid}.json")


def wcif(cid: str):
    return _get(
        f"{API}/competitions/{cid}/wcif/public", CACHE / "wcif" / f"{cid}.json"
    )


def delegates():
    path = CACHE / "delegates.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    out = []
    page = 1
    while True:
        data = _get(
            f"{API}/delegates?page={page}",
            CACHE / "delegates" / f"page{page:02d}.json",
        )
        out.extend(data)
        if len(data) < 25:
            break
        page += 1
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def teams():
    groups = _get(
        f"{API}/user_groups?groupType=teams_committees&sort=name&isActive=true&isHidden=false",
        CACHE / "teams_groups.json",
    )
    groups += _get(
        f"{API}/user_groups?groupType=board&sort=name&isActive=true&isHidden=false",
        CACHE / "board_groups.json",
    )
    for group in groups:
        fid = group["metadata"].get("friendly_id") or "board"
        group["_fid"] = fid
        group["_roles"] = _get(
            f"{API}/user_roles?groupId={group['id']}&isActive=true&sort=status:desc,name",
            CACHE / "teams" / f"{fid}.json",
        )
    return groups


def shortlist_results():
    path = CACHE / "shortlist_results.tsv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))
    zf = ensure_export()
    rows = [
        r
        for r in export_rows(zf, "WCA_export_results.tsv")
        if r["competition_id"] in SHORTLIST
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def selected_results():
    rows = shortlist_results()
    out = []
    for cid in POOL_COMPS:
        comp_rows = [r for r in rows if r["competition_id"] == cid]
        keep = {r["person_id"] for r in comp_rows if r["round_type_id"] in ("c", "f")}
        keep |= {
            r["person_id"] for r in comp_rows if r["person_country_id"] == "India"
        }
        out.extend(r for r in comp_rows if r["person_id"] in keep)
    out.extend(r for r in rows if r["competition_id"] not in POOL_COMPS)
    return out


def api_json(path: str, cache_name: str):
    return _get(f"{API}{path}", CACHE / cache_name)


def delegate_roles():
    path = CACHE / "delegate_roles.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    out = []
    for lead in ("true", "false"):
        page = 1
        while True:
            data = _get(
                f"{API}/user_roles?groupType=delegate_regions&isActive=true"
                f"&isLead={lead}&sort=name&page={page}",
                CACHE / "delegate_roles" / f"{lead}_{page:02d}.json",
            )
            out.extend(data)
            if len(data) < 25:
                break
            page += 1
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out

