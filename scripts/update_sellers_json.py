from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "Seller Lookup & IVT"
LOOKUP_FILE = DASHBOARD_DIR / "seller_lookup_dashboard.csv"
NAME_SUMMARY_FILE = DASHBOARD_DIR / "seller_name_summary.csv"
ID_SUMMARY_FILE = DASHBOARD_DIR / "seller_id_summary.csv"
HEALTH_FILE = DASHBOARD_DIR / "seller_json_fetch_status.csv"

LOOKUP_COLUMNS = [
    "source_name",
    "sellers_json_url",
    "seller_name",
    "seller_id",
    "seller_domain",
    "seller_type",
    "raw_record",
    "seller_domain_ivt_pct",
]

HEALTH_COLUMNS = [
    "source_name",
    "sellers_json_url",
    "http_status",
    "fetch_success",
    "parsed_success",
    "records_parsed",
    "error_message",
]

REQUEST_TIMEOUT_SECONDS = 45
USER_AGENT = "Seller-Lookup-Dashboard-Updater/1.0"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def unique_join(values: pd.Series) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return " | ".join(out)


def domain_ivt_pairs(group: pd.DataFrame) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for _, row in group.iterrows():
        domain = clean_text(row.get("seller_domain"))
        ivt = clean_text(row.get("seller_domain_ivt_pct"))
        if not domain or not ivt:
            continue
        try:
            ivt_text = f"{float(ivt):.2%}"
        except ValueError:
            ivt_text = ivt
        pair = f"{domain}: {ivt_text}"
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return " | ".join(out)


def load_sources() -> pd.DataFrame:
    health = pd.read_csv(HEALTH_FILE, dtype=str, encoding="utf-8-sig").fillna("")
    sources = health[["source_name", "sellers_json_url"]].drop_duplicates()
    sources = sources[sources["sellers_json_url"].map(clean_text).ne("")]
    return sources.reset_index(drop=True)


def load_domain_ivt_map() -> dict[str, str]:
    if not LOOKUP_FILE.exists():
        return {}

    lookup = pd.read_csv(
        LOOKUP_FILE,
        dtype=str,
        encoding="utf-8-sig",
        usecols=lambda col: col in {"seller_domain", "seller_domain_ivt_pct"},
        low_memory=False,
    ).fillna("")
    mapping: dict[str, str] = {}
    for _, row in lookup.iterrows():
        domain = clean_text(row.get("seller_domain")).lower()
        ivt = clean_text(row.get("seller_domain_ivt_pct"))
        if domain and ivt and domain not in mapping:
            mapping[domain] = ivt
    return mapping


def fetch_sellers_json(source_name: str, url: str, domain_ivt: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, str]]:
    health = {
        "source_name": source_name,
        "sellers_json_url": url,
        "http_status": "",
        "fetch_success": "False",
        "parsed_success": "False",
        "records_parsed": "0",
        "error_message": "",
    }
    rows: list[dict[str, str]] = []

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        health["http_status"] = str(response.status_code)
        response.raise_for_status()
        health["fetch_success"] = "True"
    except requests.RequestException as exc:
        health["error_message"] = str(exc)
        return rows, health

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        health["error_message"] = f"JSON parse error: {exc}"
        return rows, health

    sellers = data.get("sellers") if isinstance(data, dict) else None
    if not isinstance(sellers, list):
        health["error_message"] = "Missing or invalid `sellers` array"
        return rows, health

    for record in sellers:
        if not isinstance(record, dict):
            continue
        seller_domain = clean_text(record.get("domain"))
        rows.append(
            {
                "source_name": source_name,
                "sellers_json_url": url,
                "seller_name": clean_text(record.get("name")),
                "seller_id": clean_text(record.get("seller_id")),
                "seller_domain": seller_domain,
                "seller_type": clean_text(record.get("seller_type")),
                "raw_record": json.dumps(record, ensure_ascii=False, sort_keys=True),
                "seller_domain_ivt_pct": domain_ivt.get(seller_domain.lower(), ""),
            }
        )

    health["parsed_success"] = "True"
    health["records_parsed"] = str(len(rows))
    return rows, health


def rebuild_name_summary(lookup: pd.DataFrame) -> pd.DataFrame:
    base = lookup[lookup["seller_name"].map(clean_text).ne("")].copy()
    source_counts = base.groupby("seller_name")["sellers_json_url"].nunique()
    grouped = base.groupby("seller_name", sort=True)
    summary = grouped.agg(
        seller_ids_found=("seller_id", unique_join),
        seller_domains_found=("seller_domain", unique_join),
        source_names_found_in=("source_name", unique_join),
        sellers_json_urls_found_in=("sellers_json_url", unique_join),
    ).reset_index()
    summary["seller_domain_ivt_pct"] = [domain_ivt_pairs(group) for _, group in grouped]
    summary["number_of_sellers_json_sources"] = summary["seller_name"].map(source_counts).fillna(0).astype(int)
    return summary[
        [
            "seller_name",
            "seller_ids_found",
            "seller_domains_found",
            "seller_domain_ivt_pct",
            "number_of_sellers_json_sources",
            "source_names_found_in",
            "sellers_json_urls_found_in",
        ]
    ].sort_values(["number_of_sellers_json_sources", "seller_name"], ascending=[False, True])


def rebuild_id_summary(lookup: pd.DataFrame) -> pd.DataFrame:
    base = lookup[lookup["seller_id"].map(clean_text).ne("")].copy()
    source_counts = base.groupby("seller_id")["sellers_json_url"].nunique()
    summary = base.groupby("seller_id", sort=True).agg(
        seller_names_found=("seller_name", unique_join),
        seller_domains_found=("seller_domain", unique_join),
        source_names_found_in=("source_name", unique_join),
        sellers_json_urls_found_in=("sellers_json_url", unique_join),
    ).reset_index()
    summary["number_of_sellers_json_sources"] = summary["seller_id"].map(source_counts).fillna(0).astype(int)
    return summary[
        [
            "seller_id",
            "seller_names_found",
            "seller_domains_found",
            "number_of_sellers_json_sources",
            "source_names_found_in",
            "sellers_json_urls_found_in",
        ]
    ].sort_values(["number_of_sellers_json_sources", "seller_id"], ascending=[False, True])


def main() -> None:
    sources = load_sources()
    domain_ivt = load_domain_ivt_map()

    lookup_rows: list[dict[str, str]] = []
    health_rows: list[dict[str, str]] = []
    for _, source in sources.iterrows():
        rows, health = fetch_sellers_json(
            clean_text(source["source_name"]),
            clean_text(source["sellers_json_url"]),
            domain_ivt,
        )
        lookup_rows.extend(rows)
        health_rows.append(health)
        print(
            f"{health['source_name']}: fetched={health['fetch_success']} "
            f"parsed={health['parsed_success']} records={health['records_parsed']} url={health['sellers_json_url']}"
        )

    lookup = pd.DataFrame(lookup_rows, columns=LOOKUP_COLUMNS)
    health = pd.DataFrame(health_rows, columns=HEALTH_COLUMNS)
    name_summary = rebuild_name_summary(lookup)
    id_summary = rebuild_id_summary(lookup)

    lookup.to_csv(LOOKUP_FILE, index=False, encoding="utf-8-sig")
    health.to_csv(HEALTH_FILE, index=False, encoding="utf-8-sig")
    name_summary.to_csv(NAME_SUMMARY_FILE, index=False, encoding="utf-8-sig")
    id_summary.to_csv(ID_SUMMARY_FILE, index=False, encoding="utf-8-sig")

    print(f"lookup rows: {len(lookup):,}")
    print(f"sources: {len(health):,}")
    print(f"name summary rows: {len(name_summary):,}")
    print(f"id summary rows: {len(id_summary):,}")


if __name__ == "__main__":
    main()
