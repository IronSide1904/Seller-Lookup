from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "Seller Lookup & IVT"
DEFAULT_WORKBOOK = DASHBOARD_DIR / "Ads-txt and lines.xlsx"
SELLER_LOOKUP_FILE = DASHBOARD_DIR / "seller_lookup_dashboard.csv"

ADS_TXT_SOURCES_FILE = DASHBOARD_DIR / "ads_txt_sources.csv"
REQUIRED_LINES_FILE = DASHBOARD_DIR / "required_lines.csv"
ADS_TXT_FETCH_STATUS_FILE = DASHBOARD_DIR / "ads_txt_fetch_status.csv"
PARSED_ADS_TXT_ROWS_FILE = DASHBOARD_DIR / "parsed_ads_txt_rows.csv"
ADS_TXT_LINE_QA_FILE = DASHBOARD_DIR / "ads_txt_line_qa.csv"
MISSING_LINES_ACTION_LIST_FILE = DASHBOARD_DIR / "missing_lines_action_list.csv"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 Seller-Lookup-QA/1.0"
)
REQUEST_TIMEOUT_SECONDS = 12
MAX_FETCH_WORKERS = 10

LINE_COLUMNS = [
    "line_family",
    "line_source_tab",
    "requested_by",
    "implementer_type",
    "implementer_name",
    "line_destination",
    "required_line",
    "ad_system_domain",
    "seller_id",
    "relationship",
    "caid",
    "priority_flag",
    "is_tbd",
    "notes",
    "partner_name",
    "line_id",
]

QA_COLUMNS = [
    "line_family",
    "line_source_tab",
    "requested_by",
    "implementer_type",
    "implementer_name",
    "line_destination",
    "publisher_name",
    "ads_txt_url",
    "required_line",
    "ad_system_domain",
    "seller_id",
    "relationship",
    "caid",
    "status",
    "match_level",
    "matched_line",
    "mismatch_reason",
    "mapping_confidence",
    "is_tbd",
    "priority_flag",
    "partner_name",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


def normalize_text(value: Any) -> str:
    return clean_text(value).lower()


def normalize_domain(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    return text.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].rstrip(".")


def normalize_url(value: Any) -> str:
    text = clean_text(value).strip().strip("'\"<>")
    if not text:
        return ""
    if not re.match(r"^https?://", text, flags=re.IGNORECASE):
        text = "https://" + text
    parsed = urlsplit(text)
    if not parsed.netloc:
        return ""
    path = parsed.path or ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def publisher_name_from_url(url: str) -> str:
    domain = normalize_domain(url)
    if not domain:
        return ""
    return domain.split(":")[0]


def split_urls(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    url_like = re.findall(r"(?:https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s,;]*)?", text)
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in url_like:
        url = normalize_url(candidate.rstrip(".,;)"))
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def find_header_row(raw: pd.DataFrame, required_labels: list[str], max_rows: int = 12) -> int:
    required = {label.lower() for label in required_labels}
    for idx in range(min(max_rows, len(raw))):
        labels = {clean_text(value).lower() for value in raw.iloc[idx].tolist()}
        if required.issubset(labels):
            return idx
    return 0


def sheet_as_table(raw: pd.DataFrame, required_labels: list[str]) -> pd.DataFrame:
    header_row = find_header_row(raw, required_labels)
    headers = [clean_text(value) or f"Column_{idx + 1}" for idx, value in enumerate(raw.iloc[header_row].tolist())]
    table = raw.iloc[header_row + 1 :].copy()
    table.columns = headers
    return table.fillna("")


def parse_required_line(line: Any) -> dict[str, str]:
    required_line = clean_text(line)
    parts = [part.strip() for part in required_line.split(",")]
    while len(parts) < 4:
        parts.append("")
    return {
        "required_line": required_line,
        "ad_system_domain": normalize_domain(parts[0]),
        "seller_id": clean_text(parts[1]),
        "relationship": clean_text(parts[2]).upper(),
        "caid": clean_text(parts[3]).lower(),
    }


def classify_line_family(parsed_line: dict[str, str], source_tab: str) -> str:
    if source_tab in {"Publishers Seller ID Tracker", "SSP Seller ID Tracker"}:
        return "Dauup Authorization"
    if source_tab == "Priority" and parsed_line["ad_system_domain"] == "dauup.com":
        return "Dauup Authorization"
    if parsed_line["ad_system_domain"]:
        return "Partner Demand Enablement"
    return "TBD"


def required_row(
    *,
    source_tab: str,
    requested_by: str,
    implementer_type: str,
    implementer_name: str,
    line_destination: str,
    required_line: str,
    priority_flag: bool,
    notes: str = "",
    partner_name: str = "",
    line_id: str = "",
) -> dict[str, str]:
    parsed = parse_required_line(required_line)
    is_tbd = not clean_text(implementer_name) or "*" in parsed["seller_id"] or not parsed["seller_id"]
    family = classify_line_family(parsed, source_tab)
    name = clean_text(implementer_name) or "TBD"
    return {
        "line_family": "TBD" if is_tbd and not parsed["ad_system_domain"] else family,
        "line_source_tab": source_tab,
        "requested_by": requested_by,
        "implementer_type": implementer_type,
        "implementer_name": name,
        "line_destination": line_destination,
        "required_line": parsed["required_line"],
        "ad_system_domain": parsed["ad_system_domain"],
        "seller_id": parsed["seller_id"],
        "relationship": parsed["relationship"],
        "caid": parsed["caid"],
        "priority_flag": str(bool(priority_flag)),
        "is_tbd": str(bool(is_tbd)),
        "notes": notes,
        "partner_name": partner_name,
        "line_id": line_id,
    }


def extract_publisher_ads_txt_sources(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_idx, row in raw.iterrows():
        notes = " | ".join(clean_text(value) for value in row.tolist()[1:] if clean_text(value))
        for cell in row.tolist():
            for url in split_urls(cell):
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "publisher_name": publisher_name_from_url(url),
                        "ads_txt_url": url,
                        "source_row": str(row_idx + 1),
                        "notes": notes,
                    }
                )
    return pd.DataFrame(rows, columns=["publisher_name", "ads_txt_url", "source_row", "notes"])


def extract_required_lines(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    publishers = sheet_as_table(sheets["Publishers Seller ID Tracker"], ["Name of Publisher/App", "dauup.com ID Given"])
    for _, row in publishers.iterrows():
        name = clean_text(row.get("Name of Publisher/App"))
        seller_id = clean_text(row.get("dauup.com ID Given"))
        line = clean_text(row.get("dauup.com DIRECT Line")) or (f"dauup.com, {seller_id}, DIRECT" if seller_id else "")
        if not seller_id and not line:
            continue
        rows.append(
            required_row(
                source_tab="Publishers Seller ID Tracker",
                requested_by="Dauup",
                implementer_type="Publisher",
                implementer_name=name,
                line_destination="Publisher Ads.txt",
                required_line=line,
                priority_flag=False,
            )
        )

    ssps = sheet_as_table(sheets["SSP Seller ID Tracker"], ["Name of SSP/Publisher/App", "dauup.com ID Given"])
    for _, row in ssps.iterrows():
        name = clean_text(row.get("Name of SSP/Publisher/App"))
        seller_id = clean_text(row.get("dauup.com ID Given"))
        line = clean_text(row.get("dauup.com DIRECT Line")) or (f"dauup.com, {seller_id}, DIRECT" if seller_id else "")
        if not seller_id and not line:
            continue
        rows.append(
            required_row(
                source_tab="SSP Seller ID Tracker",
                requested_by="Dauup",
                implementer_type="SSP",
                implementer_name=name,
                line_destination="SSP Ads.txt / Sellers.json",
                required_line=line,
                priority_flag=False,
            )
        )

    supply_sheet_name = "Supply Line" if "Supply Line" in sheets else "Supply lines"
    supply = sheet_as_table(sheets[supply_sheet_name], ["Partner Name", "Line"])
    for _, row in supply.iterrows():
        partner = clean_text(row.get("Partner Name"))
        line = clean_text(row.get("Line"))
        if not line:
            continue
        rows.append(
            required_row(
                source_tab="Supply Line",
                requested_by="SSP / Partner",
                implementer_type="Publisher",
                implementer_name=partner,
                line_destination="Publisher Ads.txt",
                required_line=line,
                priority_flag=False,
                partner_name=partner,
                line_id=clean_text(row.get("Line ID")),
            )
        )

    priority = sheet_as_table(sheets["Priority"], ["Partner Name", "Line"])
    for _, row in priority.iterrows():
        partner = clean_text(row.get("Partner Name"))
        line = clean_text(row.get("Line"))
        if not line:
            continue
        parsed = parse_required_line(line)
        family = classify_line_family(parsed, "Priority")
        rows.append(
            required_row(
                source_tab="Priority",
                requested_by="Dauup" if family == "Dauup Authorization" else "Partner",
                implementer_type="Publisher",
                implementer_name=partner,
                line_destination="Publisher Ads.txt",
                required_line=line,
                priority_flag=True,
                notes=f"Format: {clean_text(row.get('Format'))}" if clean_text(row.get("Format")) else "",
                partner_name=partner,
            )
        )

    required = pd.DataFrame(rows, columns=LINE_COLUMNS)
    return required.drop_duplicates(
        subset=["line_family", "line_source_tab", "implementer_type", "implementer_name", "required_line"],
        keep="first",
    ).reset_index(drop=True)


def fetch_ads_txt_url(source: dict[str, str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    status = {
        "publisher_name": source["publisher_name"],
        "ads_txt_url": source["ads_txt_url"],
        "http_status": "",
        "fetch_success": "False",
        "parsed_success": "False",
        "rows_parsed": "0",
        "error_message": "",
        "last_scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        status["error_message"] = "curl not found"
        return status, []

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [
                curl,
                "-L",
                "--silent",
                "--show-error",
                "--compressed",
                "--connect-timeout",
                "6",
                "--max-time",
                str(REQUEST_TIMEOUT_SECONDS),
                "-A",
                USER_AGENT,
                "-H",
                "Accept: text/plain,*/*",
                "-o",
                str(tmp_path),
                "-w",
                "%{http_code}",
                source["ads_txt_url"],
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=REQUEST_TIMEOUT_SECONDS + 5,
        )
    except subprocess.TimeoutExpired:
        status["error_message"] = f"curl timeout after {REQUEST_TIMEOUT_SECONDS + 5} seconds"
        tmp_path.unlink(missing_ok=True)
        return status, []

    status["http_status"] = clean_text(proc.stdout)[:20]
    if proc.returncode != 0:
        status["error_message"] = clean_text(proc.stderr) or f"curl failed with exit code {proc.returncode}"
        tmp_path.unlink(missing_ok=True)
        return status, []
    if status["http_status"] and not status["http_status"].startswith("2"):
        status["error_message"] = f"HTTP {status['http_status']}"
        tmp_path.unlink(missing_ok=True)
        return status, []

    response_text = tmp_path.read_text(encoding="utf-8-sig", errors="replace")
    tmp_path.unlink(missing_ok=True)
    status["fetch_success"] = "True"

    rows = parse_ads_txt_content(response_text, source["publisher_name"], source["ads_txt_url"])
    status["parsed_success"] = "True" if rows else "False"
    status["rows_parsed"] = str(len(rows))
    if not rows:
        status["error_message"] = "No parseable Ads.txt rows"
    return status, rows


def parse_ads_txt_content(content: str, publisher_name: str, ads_txt_url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(content.splitlines(), start=1):
        raw_line = raw.strip().lstrip("\ufeff")
        if not raw_line or raw_line.startswith("#"):
            continue
        line_without_comment = raw_line.split("#", 1)[0].strip()
        parts = [part.strip() for part in line_without_comment.split(",")]
        if len(parts) < 3:
            continue
        parsed = {
            "publisher_name": publisher_name,
            "ads_txt_url": ads_txt_url,
            "ad_system_domain": normalize_domain(parts[0]),
            "seller_id": clean_text(parts[1]),
            "relationship": clean_text(parts[2]).upper(),
            "caid": clean_text(parts[3]).lower() if len(parts) > 3 else "",
            "raw_line": raw_line,
            "line_number": str(line_number),
        }
        if parsed["ad_system_domain"] and parsed["seller_id"] and parsed["relationship"]:
            rows.append(parsed)
    return rows


def normalized_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def matching_sources_for_required_line(required: pd.Series, ads_sources: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if clean_text(required["line_destination"]) != "Publisher Ads.txt":
        return ads_sources.iloc[0:0], "low"

    if clean_text(required["line_source_tab"]) == "Publishers Seller ID Tracker":
        wanted = normalized_name(required["implementer_name"])
        if wanted and wanted != "tbd":
            source_names = ads_sources["_norm_publisher_name"]
            mask = source_names.apply(lambda value: bool(value and (wanted in value or value in wanted)))
            matches = ads_sources[mask]
            if not matches.empty:
                return matches, "high"
        return ads_sources.iloc[0:0], "low"

    return ads_sources, "low"


def choose_best_ads_txt_match(required: pd.Series, domain_rows: list[dict[str, str]]) -> tuple[str, str, str, str]:
    if clean_text(required["is_tbd"]).lower() == "true":
        return "TBD", "TBD", "", "TBD implementer"

    if not domain_rows:
        return "Missing", "Missing", "", "seller ID missing"

    required_seller_id = normalize_text(required["seller_id"])
    id_rows = [row for row in domain_rows if normalize_text(row.get("seller_id")) == required_seller_id]
    if not id_rows:
        return "Partial", "Domain Only", clean_text(domain_rows[0].get("raw_line")), "ad system domain only"

    relationship_rows = [row for row in id_rows if clean_text(row.get("relationship")) == required["relationship"]]
    if not relationship_rows:
        return "Partial", "Partial Match", clean_text(id_rows[0].get("raw_line")), "relationship mismatch"

    required_caid = normalize_text(required["caid"])
    if not required_caid:
        return "Found", "Found Core", clean_text(relationship_rows[0].get("raw_line")), ""

    exact_rows = [row for row in relationship_rows if clean_text(row.get("caid")) == required_caid]
    if exact_rows:
        return "Found", "Found Exact", clean_text(exact_rows[0].get("raw_line")), ""

    matched = relationship_rows[0]
    mismatch = "CAID missing" if not clean_text(matched.get("caid")) else "CAID mismatch"
    return "Found", "Found Core", clean_text(matched.get("raw_line")), mismatch


def choose_best_sellers_json_match(
    required: pd.Series,
    seller_exact_index: dict[tuple[str, str], dict[str, str]],
    seller_domain_index: dict[str, dict[str, str]],
) -> tuple[str, str, str, str, str]:
    if clean_text(required["is_tbd"]).lower() == "true":
        return "", "TBD", "TBD", "", "TBD implementer"

    domain = clean_text(required["ad_system_domain"])
    seller_id = normalize_text(required["seller_id"])
    row = seller_exact_index.get((domain, seller_id))
    if row:
        return clean_text(row["sellers_json_url"]), "Found", "Found Core", json.dumps(row, ensure_ascii=False), ""

    row = seller_domain_index.get(domain)
    if row:
        return clean_text(row["sellers_json_url"]), "Partial", "Domain Only", json.dumps(row, ensure_ascii=False), "ad system domain only"
    return "", "Missing", "Missing", "", "seller ID missing"


def qa_record(
    required: pd.Series,
    *,
    publisher_name: str,
    ads_txt_url: str,
    status: str,
    match_level: str,
    matched_line: str,
    mismatch_reason: str,
    mapping_confidence: str,
) -> dict[str, str]:
    implementer_name = publisher_name if clean_text(required["line_destination"]) == "Publisher Ads.txt" and publisher_name else clean_text(required["implementer_name"])
    return {
        "line_family": required["line_family"],
        "line_source_tab": required["line_source_tab"],
        "requested_by": required["requested_by"],
        "implementer_type": required["implementer_type"],
        "implementer_name": implementer_name,
        "line_destination": required["line_destination"],
        "publisher_name": publisher_name,
        "ads_txt_url": ads_txt_url,
        "required_line": required["required_line"],
        "ad_system_domain": required["ad_system_domain"],
        "seller_id": required["seller_id"],
        "relationship": required["relationship"],
        "caid": required["caid"],
        "status": status,
        "match_level": match_level,
        "matched_line": matched_line,
        "mismatch_reason": mismatch_reason,
        "mapping_confidence": mapping_confidence,
        "is_tbd": required["is_tbd"],
        "priority_flag": required["priority_flag"],
        "partner_name": required["partner_name"],
    }


def build_ads_txt_line_qa(
    required_lines: pd.DataFrame,
    ads_sources: pd.DataFrame,
    ads_fetch_status: pd.DataFrame,
    parsed_ads_rows: pd.DataFrame,
    seller_lookup: pd.DataFrame,
) -> pd.DataFrame:
    ads_sources = ads_sources.copy()
    ads_sources["_norm_publisher_name"] = ads_sources["publisher_name"].map(normalized_name)

    parsed_index: dict[str, dict[str, list[dict[str, str]]]] = {}
    for record in parsed_ads_rows.to_dict("records"):
        url = clean_text(record.get("ads_txt_url"))
        domain = clean_text(record.get("ad_system_domain"))
        if not url or not domain:
            continue
        parsed_index.setdefault(url, {}).setdefault(domain, []).append(record)
    status_by_url = {row["ads_txt_url"]: row for _, row in ads_fetch_status.iterrows()}

    seller_exact_index: dict[tuple[str, str], dict[str, str]] = {}
    seller_domain_index: dict[str, dict[str, str]] = {}
    if not seller_lookup.empty:
        for record in seller_lookup.to_dict("records"):
            domain = normalize_domain(record.get("seller_domain"))
            seller_id = normalize_text(record.get("seller_id"))
            if domain:
                seller_domain_index.setdefault(domain, record)
            if domain and seller_id:
                seller_exact_index.setdefault((domain, seller_id), record)

    qa_rows: list[dict[str, str]] = []

    for _, required in required_lines.iterrows():
        if clean_text(required["line_destination"]) == "SSP Ads.txt / Sellers.json":
            url, status, match_level, matched_line, mismatch = choose_best_sellers_json_match(
                required,
                seller_exact_index,
                seller_domain_index,
            )
            qa_rows.append(
                qa_record(
                    required,
                    publisher_name="",
                    ads_txt_url=url,
                    status=status,
                    match_level=match_level,
                    matched_line=matched_line,
                    mismatch_reason=mismatch,
                    mapping_confidence="low",
                )
            )
            continue

        sources, mapping_confidence = matching_sources_for_required_line(required, ads_sources)
        if sources.empty:
            qa_rows.append(
                qa_record(
                    required,
                    publisher_name="",
                    ads_txt_url="",
                    status="TBD" if clean_text(required["is_tbd"]).lower() == "true" else "Missing",
                    match_level="TBD" if clean_text(required["is_tbd"]).lower() == "true" else "Missing",
                    matched_line="",
                    mismatch_reason="TBD implementer" if clean_text(required["is_tbd"]).lower() == "true" else "no matching Ads.txt URL mapping",
                    mapping_confidence=mapping_confidence,
                )
            )
            continue

        for _, source in sources.iterrows():
            url = clean_text(source["ads_txt_url"])
            fetch_status = status_by_url.get(url)
            if fetch_status is None or clean_text(fetch_status.get("parsed_success")).lower() != "true":
                qa_rows.append(
                    qa_record(
                        required,
                        publisher_name=clean_text(source["publisher_name"]),
                        ads_txt_url=url,
                        status="Failed",
                        match_level="URL Failed",
                        matched_line="",
                        mismatch_reason="URL failed",
                        mapping_confidence=mapping_confidence,
                    )
                )
                continue
            domain_rows = parsed_index.get(url, {}).get(clean_text(required["ad_system_domain"]), [])
            status, match_level, matched_line, mismatch = choose_best_ads_txt_match(required, domain_rows)
            qa_rows.append(
                qa_record(
                    required,
                    publisher_name=clean_text(source["publisher_name"]),
                    ads_txt_url=url,
                    status=status,
                    match_level=match_level,
                    matched_line=matched_line,
                    mismatch_reason=mismatch,
                    mapping_confidence=mapping_confidence,
                )
            )

    return pd.DataFrame(qa_rows, columns=QA_COLUMNS)


def build_missing_lines_action_list(qa: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "line_family",
        "implementer_type",
        "implementer_name",
        "publisher_name",
        "ads_txt_url",
        "required_line",
        "status",
        "mismatch_reason",
        "line_source_tab",
        "priority_flag",
        "requested_by",
    ]
    action = qa[qa["status"].isin(["Missing", "Partial", "Failed", "TBD"])].copy()
    return action[columns].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Ads.txt line QA CSVs for the Seller Lookup dashboard.")
    parser.add_argument("--workbook", default=str(DEFAULT_WORKBOOK), help="Path to Ads-txt and lines workbook.")
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    sheets = pd.read_excel(workbook_path, sheet_name=None, header=None, dtype=str, engine="openpyxl").copy()
    sheets = {name: df.fillna("") for name, df in sheets.items()}

    ads_sources = extract_publisher_ads_txt_sources(sheets["Publisher Ads.txt"])
    required_lines = extract_required_lines(sheets)
    seller_lookup = (
        pd.read_csv(SELLER_LOOKUP_FILE, dtype=str, encoding="utf-8-sig", low_memory=False).fillna("")
        if SELLER_LOOKUP_FILE.exists()
        else pd.DataFrame()
    )

    fetch_status_rows: list[dict[str, str]] = []
    parsed_rows: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=MAX_FETCH_WORKERS) as pool:
        futures = [pool.submit(fetch_ads_txt_url, row.to_dict()) for _, row in ads_sources.iterrows()]
        for future in as_completed(futures):
            status, rows = future.result()
            fetch_status_rows.append(status)
            parsed_rows.extend(rows)
            print(
                f"{status['ads_txt_url']}: fetched={status['fetch_success']} "
                f"parsed={status['parsed_success']} rows={status['rows_parsed']}"
            )

    fetch_status = pd.DataFrame(fetch_status_rows)
    parsed_ads_rows = pd.DataFrame(
        parsed_rows,
        columns=["publisher_name", "ads_txt_url", "ad_system_domain", "seller_id", "relationship", "caid", "raw_line", "line_number"],
    )
    qa = build_ads_txt_line_qa(required_lines, ads_sources, fetch_status, parsed_ads_rows, seller_lookup)
    missing = build_missing_lines_action_list(qa)

    ads_sources.to_csv(ADS_TXT_SOURCES_FILE, index=False, encoding="utf-8-sig")
    required_lines.to_csv(REQUIRED_LINES_FILE, index=False, encoding="utf-8-sig")
    fetch_status.to_csv(ADS_TXT_FETCH_STATUS_FILE, index=False, encoding="utf-8-sig")
    parsed_ads_rows.to_csv(PARSED_ADS_TXT_ROWS_FILE, index=False, encoding="utf-8-sig")
    qa.to_csv(ADS_TXT_LINE_QA_FILE, index=False, encoding="utf-8-sig")
    missing.to_csv(MISSING_LINES_ACTION_LIST_FILE, index=False, encoding="utf-8-sig")

    print(f"required_lines={len(required_lines):,}")
    print(f"ads_txt_urls={len(ads_sources):,}")
    print(f"ads_txt_urls_fetched_successfully={(fetch_status['fetch_success'].astype(str).str.lower() == 'true').sum():,}")
    print(f"ads_txt_urls_failed={(fetch_status['fetch_success'].astype(str).str.lower() != 'true').sum():,}")
    print(f"parsed_ads_txt_rows={len(parsed_ads_rows):,}")
    print(f"ads_txt_line_qa_rows={len(qa):,}")
    print(f"missing_lines_action_rows={len(missing):,}")


if __name__ == "__main__":
    main()
