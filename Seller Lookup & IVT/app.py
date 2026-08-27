from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILES = {
    "lookup": APP_DIR / "seller_lookup_dashboard.csv",
    "seller_health": APP_DIR / "seller_json_fetch_status.csv",
    "name_summary": APP_DIR / "seller_name_summary.csv",
    "id_summary": APP_DIR / "seller_id_summary.csv",
    "required_lines": APP_DIR / "required_lines.csv",
    "ads_sources": APP_DIR / "ads_txt_sources.csv",
    "parsed_ads": APP_DIR / "parsed_ads_txt_rows.csv",
    "ads_qa": APP_DIR / "ads_txt_line_qa.csv",
    "missing_lines": APP_DIR / "missing_lines_action_list.csv",
    "ads_health": APP_DIR / "ads_txt_fetch_status.csv",
}

LOOKUP_REQUIRED_COLUMNS = {
    "source_name",
    "sellers_json_url",
    "seller_name",
    "seller_domain",
    "seller_id",
    "seller_type",
}
SELLER_HEALTH_REQUIRED_COLUMNS = {
    "source_name",
    "sellers_json_url",
    "http_status",
    "fetch_success",
    "parsed_success",
    "records_parsed",
    "error_message",
}
SELLER_RESULT_COLUMNS = [
    "source_name",
    "seller_id",
    "seller_name",
    "seller_domain",
    "seller_type",
    "sellers_json_url",
    "match_reason",
    "matched_terms",
]
ADS_QA_DEFAULT_COLUMNS = [
    "line_family",
    "status",
    "implementer_type",
    "implementer_name",
    "publisher_name",
    "ads_txt_url",
    "required_line",
    "ad_system_domain",
    "seller_id",
    "relationship",
    "caid",
    "match_level",
    "mismatch_reason",
    "line_source_tab",
    "priority_flag",
]
SELLER_SEARCH_FIELDS = {
    "Seller ID": ("seller_id", "matched seller ID"),
    "Seller Name": ("seller_name", "matched seller name"),
    "Seller Domain": ("seller_domain", "matched seller domain"),
    "Source Name": ("source_name", "matched source name"),
    "Sellers.json URL": ("sellers_json_url", "matched sellers.json URL"),
}
ADS_SEARCH_FIELDS = {
    "Seller ID": [("seller_id", "matched seller ID", True)],
    "Seller Name": [
        ("publisher_name", "matched seller name", False),
        ("implementer_name", "matched seller name", False),
        ("partner_name", "matched seller name", False),
    ],
    "Seller Domain": [("ad_system_domain", "matched seller domain", False)],
    "Source Name": [
        ("line_source_tab", "matched source name", False),
        ("requested_by", "matched source name", False),
        ("partner_name", "matched source name", False),
    ],
    "Ads.txt URL": [("ads_txt_url", "matched Ads.txt URL", False)],
    "Line Text": [
        ("required_line", "matched line text", False),
        ("matched_line", "matched line text", False),
        ("raw_line", "matched line text", False),
    ],
}
SEARCH_MODE_OPTIONS = [
    "Auto",
    "Seller ID",
    "Seller Name",
    "Seller Domain",
    "Source Name",
    "Sellers.json URL",
    "Ads.txt URL",
    "Line Text",
]


st.set_page_config(
    page_title="Seller Lookup + Ads.txt QA",
    layout="wide",
    initial_sidebar_state="expanded",
)


def clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for col in cleaned.columns:
        if pd.api.types.is_object_dtype(cleaned[col]) or pd.api.types.is_string_dtype(cleaned[col]):
            cleaned[col] = cleaned[col].fillna("").astype(str)
            cleaned[col] = cleaned[col].replace({"nan": "", "None": "", "<NA>": ""})
    return cleaned


def normalize_for_search(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    return text.rstrip("/")


def parse_search_terms(search_text: str) -> list[str]:
    raw_terms = re.split(r"[\s,;|]+", str(search_text or ""))
    terms: list[str] = []
    seen: set[str] = set()
    for raw_term in raw_terms:
        term = str(raw_term).strip()
        if not term:
            continue
        key = normalize_for_search(term)
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def unique_sorted(values: Iterable[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def normalize_seller_type(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.upper()
    if normalized == "ONO":
        return "O&O"
    return normalized


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def file_signature(*keys: str) -> tuple[float, ...]:
    return tuple(DATA_FILES[key].stat().st_mtime if DATA_FILES[key].exists() else 0 for key in keys)


def optional_file_signature(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0


def friendly_missing_file(path: Path) -> None:
    st.error(
        f"Missing required file: `{path.name}`. "
        "Place the CSV in the dashboard folder and refresh the app."
    )
    st.stop()


def validate_columns(df: pd.DataFrame, required_columns: set[str], filename: str) -> None:
    missing = sorted(required_columns - set(df.columns))
    if missing:
        st.error(f"`{filename}` is missing required columns: {', '.join(missing)}")
        st.stop()


@st.cache_data(show_spinner="Loading CSV...")
def load_csv(path: str, file_mtime: float) -> pd.DataFrame:
    return clean_strings(pd.read_csv(path, dtype=str, encoding="utf-8-sig", low_memory=False))


def load_optional_csv(key: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = DATA_FILES[key]
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    return load_csv(str(path), optional_file_signature(path))


@st.cache_data(show_spinner="Loading seller lookup data...")
def load_seller_lookup(signature: tuple[float, ...]) -> pd.DataFrame:
    if not DATA_FILES["lookup"].exists():
        friendly_missing_file(DATA_FILES["lookup"])
    lookup = load_csv(str(DATA_FILES["lookup"]), DATA_FILES["lookup"].stat().st_mtime)
    validate_columns(lookup, LOOKUP_REQUIRED_COLUMNS, DATA_FILES["lookup"].name)
    for column in LOOKUP_REQUIRED_COLUMNS:
        lookup[column] = lookup[column].fillna("").astype(str)
        lookup[f"_norm_{column}"] = lookup[column].map(normalize_for_search)
    lookup["_seller_type_filter"] = lookup["seller_type"].map(normalize_seller_type)
    return lookup


@st.cache_data(show_spinner="Loading sellers.json health data...")
def load_seller_health(signature: tuple[float, ...]) -> pd.DataFrame:
    if not DATA_FILES["seller_health"].exists():
        friendly_missing_file(DATA_FILES["seller_health"])
    health = load_csv(str(DATA_FILES["seller_health"]), DATA_FILES["seller_health"].stat().st_mtime)
    validate_columns(health, SELLER_HEALTH_REQUIRED_COLUMNS, DATA_FILES["seller_health"].name)
    health["fetch_success"] = as_bool(health["fetch_success"])
    health["parsed_success"] = as_bool(health["parsed_success"])
    health["records_parsed_numeric"] = pd.to_numeric(health["records_parsed"], errors="coerce").fillna(0).astype(int)
    health["http_status_display"] = health["http_status"].fillna("").astype(str)
    for column in ["source_name", "sellers_json_url"]:
        health[f"_norm_{column}"] = health[column].map(normalize_for_search)
    return health


def prepare_ads_qa(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in ADS_QA_DEFAULT_COLUMNS + ["matched_line", "raw_line", "requested_by", "partner_name"]:
        if column not in prepared.columns:
            prepared[column] = ""
    for column in [
        "publisher_name",
        "implementer_name",
        "partner_name",
        "ads_txt_url",
        "required_line",
        "matched_line",
        "raw_line",
        "ad_system_domain",
        "seller_id",
        "line_source_tab",
        "requested_by",
    ]:
        prepared[f"_norm_{column}"] = prepared[column].map(normalize_for_search)
    return prepared


def load_ads_qa() -> pd.DataFrame:
    return prepare_ads_qa(load_optional_csv("ads_qa", ADS_QA_DEFAULT_COLUMNS))


def load_ads_health() -> pd.DataFrame:
    df = load_optional_csv("ads_health")
    if df.empty:
        return df
    if "fetch_success" in df.columns:
        df["fetch_success"] = as_bool(df["fetch_success"])
    if "parsed_success" in df.columns:
        df["parsed_success"] = as_bool(df["parsed_success"])
    rows_parsed = df["rows_parsed"] if "rows_parsed" in df.columns else pd.Series(0, index=df.index)
    df["rows_parsed_numeric"] = pd.to_numeric(rows_parsed, errors="coerce").fillna(0).astype(int)
    return df


def apply_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Seller Filters")
    source_names = st.sidebar.multiselect("Source name", unique_sorted(df["source_name"]))
    seller_types = st.sidebar.multiselect("Seller type", unique_sorted(df["_seller_type_filter"]))
    seller_domain = st.sidebar.text_input("Seller domain contains", placeholder="e.g. pubmatic.com")
    seller_name = st.sidebar.text_input("Seller name contains", placeholder="e.g. Lacuna")
    seller_id = st.sidebar.text_input("Seller ID exact match", placeholder="e.g. 34167, 34197, 34114")

    filtered = df.copy()
    if source_names:
        filtered = filtered[filtered["source_name"].isin(source_names)]
    if seller_types:
        filtered = filtered[filtered["_seller_type_filter"].isin(seller_types)]
    for column, value in [("seller_domain", seller_domain), ("seller_name", seller_name)]:
        terms = parse_search_terms(value)
        if terms:
            mask = pd.Series(False, index=filtered.index)
            for term in terms:
                normalized_term = normalize_for_search(term)
                if normalized_term:
                    mask |= filtered[f"_norm_{column}"].str.contains(re.escape(normalized_term), case=False, na=False)
            filtered = filtered[mask]
    seller_id_terms = [normalize_for_search(term) for term in parse_search_terms(seller_id)]
    seller_id_terms = [term for term in seller_id_terms if term]
    if seller_id_terms:
        filtered = filtered[filtered["_norm_seller_id"].isin(set(seller_id_terms))]
    return filtered


def match_field(series: pd.Series, term: str, exact: bool = False) -> pd.Series:
    normalized_term = normalize_for_search(term)
    if not normalized_term:
        return pd.Series(False, index=series.index)
    if exact:
        return series.eq(normalized_term)
    return series.str.contains(re.escape(normalized_term), case=False, na=False)


def looks_like_seller_id(term: str) -> bool:
    normalized_term = normalize_for_search(term)
    if not normalized_term:
        return False
    if any(marker in normalized_term for marker in ["/", "."]):
        return False
    return bool(re.search(r"\d", normalized_term)) and bool(re.fullmatch(r"[a-z0-9:_-]+", normalized_term))


def apply_seller_search(df: pd.DataFrame, terms: list[str], mode: str) -> pd.DataFrame:
    result = df.copy()
    result["match_reason"] = ""
    result["matched_terms"] = ""
    if not terms:
        return result
    if mode not in SELLER_SEARCH_FIELDS and mode != "Auto":
        return result.iloc[0:0].copy()
    if mode == "Seller ID":
        normalized_terms = {normalize_for_search(term): term for term in terms if normalize_for_search(term)}
        result = result[result["_norm_seller_id"].isin(normalized_terms)].copy()
        result["match_reason"] = "matched seller ID"
        result["matched_terms"] = result["_norm_seller_id"].map(normalized_terms).fillna("")
        return result

    field_items = SELLER_SEARCH_FIELDS.items() if mode == "Auto" else [(mode, SELLER_SEARCH_FIELDS[mode])]
    keep_mask = pd.Series(False, index=result.index)
    row_reasons: dict[int, set[str]] = {idx: set() for idx in result.index}
    row_terms: dict[int, list[str]] = {idx: [] for idx in result.index}
    for term in terms:
        term_mask = pd.Series(False, index=result.index)
        if mode == "Auto":
            seller_id_mask = match_field(result["_norm_seller_id"], term, exact=True)
            if seller_id_mask.any() or looks_like_seller_id(term):
                term_mask = seller_id_mask
                if seller_id_mask.any():
                    for idx in seller_id_mask[seller_id_mask].index:
                        row_reasons[idx].add("matched seller ID")
                    keep_mask |= term_mask
                    for idx in term_mask[term_mask].index:
                        if term not in row_terms[idx]:
                            row_terms[idx].append(term)
                continue
        for _mode_name, (field, reason) in field_items:
            exact_id = field == "seller_id"
            field_mask = match_field(result[f"_norm_{field}"], term, exact=exact_id)
            term_mask |= field_mask
            for idx in field_mask[field_mask].index:
                row_reasons[idx].add(reason)
        keep_mask |= term_mask
        for idx in term_mask[term_mask].index:
            if term not in row_terms[idx]:
                row_terms[idx].append(term)

    result = result[keep_mask].copy()
    for idx in result.index:
        reasons = row_reasons[idx]
        result.at[idx, "match_reason"] = "matched multiple fields" if len(reasons) > 1 else next(iter(reasons), "")
        result.at[idx, "matched_terms"] = ", ".join(row_terms[idx])
    return result


def apply_ads_txt_search(df: pd.DataFrame, terms: list[str], mode: str) -> pd.DataFrame:
    result = df.copy()
    result["match_reason"] = ""
    result["matched_terms"] = ""
    if df.empty or not terms:
        return result
    if mode == "Sellers.json URL":
        return result.iloc[0:0].copy()
    if mode == "Auto":
        field_specs = [
            ("ads_txt_url", "matched Ads.txt URL", False),
            ("required_line", "matched line text", False),
            ("matched_line", "matched line text", False),
            ("raw_line", "matched line text", False),
            ("ad_system_domain", "matched seller domain", False),
            ("seller_id", "matched seller ID", True),
            ("publisher_name", "matched seller name", False),
            ("implementer_name", "matched seller name", False),
            ("partner_name", "matched seller name", False),
            ("line_source_tab", "matched source name", False),
        ]
    else:
        field_specs = ADS_SEARCH_FIELDS.get(mode, [])
    if not field_specs:
        return result.iloc[0:0].copy()

    keep_mask = pd.Series(False, index=result.index)
    row_reasons: dict[int, set[str]] = {idx: set() for idx in result.index}
    row_terms: dict[int, list[str]] = {idx: [] for idx in result.index}
    for term in terms:
        term_mask = pd.Series(False, index=result.index)
        if mode == "Auto":
            seller_id_mask = match_field(result["_norm_seller_id"], term, exact=True)
            if seller_id_mask.any() or looks_like_seller_id(term):
                term_mask = seller_id_mask
                if seller_id_mask.any():
                    for idx in seller_id_mask[seller_id_mask].index:
                        row_reasons[idx].add("matched seller ID")
                    keep_mask |= term_mask
                    for idx in term_mask[term_mask].index:
                        if term not in row_terms[idx]:
                            row_terms[idx].append(term)
                continue
        for field, reason, exact in field_specs:
            norm_col = f"_norm_{field}"
            if norm_col not in result.columns:
                continue
            field_mask = match_field(result[norm_col], term, exact=exact)
            term_mask |= field_mask
            for idx in field_mask[field_mask].index:
                row_reasons[idx].add(reason)
        keep_mask |= term_mask
        for idx in term_mask[term_mask].index:
            if term not in row_terms[idx]:
                row_terms[idx].append(term)

    result = result[keep_mask].copy()
    for idx in result.index:
        reasons = row_reasons[idx]
        result.at[idx, "match_reason"] = "matched multiple fields" if len(reasons) > 1 else next(iter(reasons), "")
        result.at[idx, "matched_terms"] = ", ".join(row_terms[idx])
    return result


def join_unique(values: Iterable[object]) -> str:
    return ", ".join(unique_sorted(values))


def group_by_seller_id(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["seller_id", "seller_names_found", "seller_domains_found", "source_names_found_in", "source_count"])
    grouped = (
        df.groupby("seller_id", dropna=False)
        .agg(
            seller_names_found=("seller_name", join_unique),
            seller_domains_found=("seller_domain", join_unique),
            source_names_found_in=("source_name", join_unique),
            source_count=("source_name", lambda values: len(set(v for v in values if str(v).strip()))),
        )
        .reset_index()
    )
    return grouped.sort_values(["source_count", "seller_id"], ascending=[False, True])


def group_by_seller_domain(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["seller_domain", "seller_names_found", "seller_ids_found", "source_names_found_in", "source_count"])
    grouped = (
        df.groupby("seller_domain", dropna=False)
        .agg(
            seller_names_found=("seller_name", join_unique),
            seller_ids_found=("seller_id", join_unique),
            source_names_found_in=("source_name", join_unique),
            source_count=("source_name", lambda values: len(set(v for v in values if str(v).strip()))),
        )
        .reset_index()
    )
    return grouped.sort_values(["source_count", "seller_domain"], ascending=[False, True])


def to_csv_download(df: pd.DataFrame) -> bytes:
    export = df.drop(columns=[col for col in df.columns if col.startswith("_")], errors="ignore")
    return export.to_csv(index=False).encode("utf-8-sig")


def download_csv(df: pd.DataFrame, filename: str, label: str) -> None:
    st.download_button(label, to_csv_download(df), file_name=filename, mime="text/csv", use_container_width=True)


def render_seller_kpis(df: pd.DataFrame) -> None:
    cols = st.columns(5)
    cols[0].metric("Matching seller rows", f"{len(df):,}")
    cols[1].metric("Unique seller IDs", f"{df['seller_id'].replace('', pd.NA).dropna().nunique():,}")
    cols[2].metric("Unique seller names", f"{df['seller_name'].replace('', pd.NA).dropna().nunique():,}")
    cols[3].metric("Unique seller domains", f"{df['seller_domain'].replace('', pd.NA).dropna().nunique():,}")
    cols[4].metric("Unique sellers.json sources", f"{df['source_name'].replace('', pd.NA).dropna().nunique():,}")


def render_ads_qa_kpis(df: pd.DataFrame) -> None:
    cols = st.columns(5)
    required_key = [
        column
        for column in ["line_source_tab", "implementer_type", "implementer_name", "required_line"]
        if column in df.columns
    ]
    required_count = df.drop_duplicates(required_key).shape[0] if required_key else len(df)
    cols[0].metric("Required lines", f"{required_count:,}")
    cols[1].metric("Found", f"{int(df['status'].eq('Found').sum()) if 'status' in df else 0:,}")
    cols[2].metric("Missing", f"{int(df['status'].eq('Missing').sum()) if 'status' in df else 0:,}")
    cols[3].metric("Partial", f"{int(df['status'].eq('Partial').sum()) if 'status' in df else 0:,}")
    cols[4].metric("Failed", f"{int(df['status'].eq('Failed').sum()) if 'status' in df else 0:,}")
    cols2 = st.columns(4)
    cols2[0].metric("TBD", f"{int(df['status'].eq('TBD').sum()) if 'status' in df else 0:,}")
    cols2[1].metric("Dauup Authorization", f"{int(df['line_family'].eq('Dauup Authorization').sum()) if 'line_family' in df else 0:,}")
    cols2[2].metric("Partner Demand Enablement", f"{int(df['line_family'].eq('Partner Demand Enablement').sum()) if 'line_family' in df else 0:,}")
    cols2[3].metric("Priority lines", f"{int(df['priority_flag'].astype(str).str.lower().eq('true').sum()) if 'priority_flag' in df else 0:,}")


def render_search_tab(lookup: pd.DataFrame, ads_qa: pd.DataFrame) -> None:
    search_text = st.text_area(
        "Search seller IDs, seller name, seller domain, source name, URL, or line text",
        placeholder="Paste one or many seller IDs, domains, names, sources, URLs, or lines",
        height=120,
    )
    mode = st.selectbox("Search mode", SEARCH_MODE_OPTIONS, index=0)
    terms = parse_search_terms(search_text)

    with st.expander("Parsed search terms", expanded=False):
        st.write(f"{len(terms):,} parsed terms")
        if terms:
            st.dataframe(pd.DataFrame({"term": terms}), use_container_width=True, hide_index=True, height=220)
        else:
            st.caption("No search terms entered.")

    seller_results = apply_seller_search(lookup, terms, mode)
    ads_results = apply_ads_txt_search(ads_qa, terms, mode)

    render_seller_kpis(seller_results)
    st.subheader("Matching Seller Records")
    visible_columns = [column for column in SELLER_RESULT_COLUMNS if column in seller_results.columns]
    st.dataframe(
        seller_results[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={"sellers_json_url": st.column_config.LinkColumn("sellers.json URL")},
    )
    download_csv(seller_results[visible_columns], "filtered_seller_results.csv", "Download filtered seller results as CSV")

    seller_id_summary = group_by_seller_id(seller_results)
    seller_domain_summary = group_by_seller_domain(seller_results)
    st.subheader("Grouped Seller Summaries")
    col_left, col_right = st.columns(2)
    with col_left:
        st.caption("Grouped by Seller ID")
        st.dataframe(seller_id_summary, use_container_width=True, hide_index=True, height=320)
        download_csv(seller_id_summary, "grouped_by_seller_id.csv", "Download grouped by seller ID as CSV")
    with col_right:
        st.caption("Grouped by Seller Domain")
        st.dataframe(seller_domain_summary, use_container_width=True, hide_index=True, height=320)
        download_csv(seller_domain_summary, "grouped_by_seller_domain.csv", "Download grouped by seller domain as CSV")

    st.subheader("Matching Ads.txt Line QA")
    if ads_results.empty and ads_qa.empty:
        st.info("Ads.txt QA files have not been built yet.")
        return
    qa_columns = [column for column in ADS_QA_DEFAULT_COLUMNS + ["match_reason", "matched_terms"] if column in ads_results.columns]
    st.dataframe(
        ads_results[qa_columns],
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={"ads_txt_url": st.column_config.LinkColumn("Ads.txt URL")},
    )
    download_csv(ads_results[qa_columns], "filtered_search_ads_txt_qa.csv", "Download matching Ads.txt QA results")


def apply_ads_qa_filters(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns(4)
    line_family = c1.selectbox("Line family", ["All", "Dauup Authorization", "Partner Demand Enablement", "TBD"])
    status = c2.selectbox("Status", ["All", "Found", "Partial", "Missing", "Failed", "TBD"])
    source_tab = c3.selectbox("Line source tab", ["All", "Publishers Seller ID Tracker", "SSP Seller ID Tracker", "Supply Line", "Priority"])
    implementer_type = c4.selectbox("Implementer type", ["All", "Publisher", "SSP", "Unknown"])
    search_text = st.text_input(
        "Search QA rows",
        placeholder="Publisher/app, SSP, implementer, ad system domain, seller ID, Ads.txt URL, or required line",
    )

    filtered = df.copy()
    if line_family != "All":
        filtered = filtered[filtered["line_family"].eq(line_family)]
    if status != "All":
        filtered = filtered[filtered["status"].eq(status)]
    if source_tab != "All":
        filtered = filtered[filtered["line_source_tab"].eq(source_tab)]
    if implementer_type != "All":
        filtered = filtered[filtered["implementer_type"].eq(implementer_type)]
    return apply_ads_txt_search(filtered, parse_search_terms(search_text), "Auto")


def render_ads_txt_qa_tab(ads_qa: pd.DataFrame) -> None:
    st.subheader("Ads.txt Line QA")
    if ads_qa.empty:
        st.info("No Ads.txt QA data found. Run `python scripts/build_ads_txt_qa.py` first.")
        return

    filtered = apply_ads_qa_filters(ads_qa)
    render_ads_qa_kpis(filtered)
    visible_columns = [column for column in ADS_QA_DEFAULT_COLUMNS if column in filtered.columns]
    st.dataframe(
        filtered[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={"ads_txt_url": st.column_config.LinkColumn("Ads.txt URL")},
    )
    download_csv(filtered[visible_columns], "filtered_ads_txt_line_qa.csv", "Download filtered Ads.txt QA results")

    advanced_columns = [column for column in filtered.columns if column not in visible_columns and not column.startswith("_")]
    if advanced_columns:
        with st.expander("Advanced QA columns", expanded=False):
            st.dataframe(filtered[advanced_columns], use_container_width=True, hide_index=True, height=320)

    missing = load_optional_csv("missing_lines")
    parsed_ads = load_optional_csv("parsed_ads")
    ads_health = load_ads_health()
    col1, col2, col3 = st.columns(3)
    with col1:
        download_csv(missing, "missing_lines_action_list.csv", "Download missing lines action list")
    with col2:
        download_csv(parsed_ads, "parsed_ads_txt_rows.csv", "Download parsed Ads.txt rows")
    with col3:
        download_csv(ads_health, "ads_txt_fetch_status.csv", "Download Ads.txt fetch status")


def render_seller_health_section(health: pd.DataFrame) -> None:
    st.subheader("Sellers.json Health")
    c1, c2, c3, c4, c5 = st.columns([1.4, 1.4, 1, 1, 1])
    source_query = c1.text_input("Source name contains", placeholder="e.g. lkqd", key="seller_health_source")
    url_query = c2.text_input("URL contains", placeholder="e.g. sellers.json", key="seller_health_url")
    fetch_success = c3.multiselect("Fetch success", ["True", "False"], key="seller_health_fetch")
    parsed_success = c4.multiselect("Parsed success", ["True", "False"], key="seller_health_parsed")
    http_status = c5.multiselect("HTTP status", unique_sorted(health["http_status_display"]), key="seller_health_status")

    filtered = health.copy()
    source_term = normalize_for_search(source_query)
    if source_term:
        filtered = filtered[filtered["_norm_source_name"].str.contains(re.escape(source_term), case=False, na=False)]
    url_term = normalize_for_search(url_query)
    if url_term:
        filtered = filtered[filtered["_norm_sellers_json_url"].str.contains(re.escape(url_term), case=False, na=False)]
    if fetch_success:
        filtered = filtered[filtered["fetch_success"].isin({value == "True" for value in fetch_success})]
    if parsed_success:
        filtered = filtered[filtered["parsed_success"].isin({value == "True" for value in parsed_success})]
    if http_status:
        filtered = filtered[filtered["http_status_display"].isin(http_status)]

    cols = st.columns(4)
    cols[0].metric("Total sources", f"{len(filtered):,}")
    cols[1].metric("Parsed sources", f"{int(filtered['parsed_success'].sum()):,}")
    cols[2].metric("Failed sources", f"{int((~filtered['parsed_success']).sum()):,}")
    cols[3].metric("Total records parsed", f"{int(filtered['records_parsed_numeric'].sum()):,}")
    columns = ["source_name", "sellers_json_url", "http_status", "fetch_success", "parsed_success", "records_parsed", "error_message"]
    if "last_scanned_at" in filtered.columns:
        columns.append("last_scanned_at")
    st.dataframe(filtered[columns], use_container_width=True, hide_index=True, height=360)
    download_csv(filtered[columns], "filtered_seller_json_fetch_status.csv", "Download filtered Sellers.json Health")


def render_ads_health_section(ads_health: pd.DataFrame) -> None:
    st.subheader("Ads.txt Health")
    if ads_health.empty:
        st.info("No Ads.txt fetch status file found.")
        return
    cols = st.columns(4)
    cols[0].metric("Ads.txt URLs", f"{len(ads_health):,}")
    cols[1].metric("Fetched", f"{int(ads_health['fetch_success'].sum()):,}")
    cols[2].metric("Failed", f"{int((~ads_health['fetch_success']).sum()):,}")
    cols[3].metric("Parsed rows", f"{int(ads_health['rows_parsed_numeric'].sum()):,}")
    columns = [
        "publisher_name",
        "ads_txt_url",
        "http_status",
        "fetch_success",
        "parsed_success",
        "rows_parsed",
        "error_message",
        "last_scanned_at",
    ]
    columns = [column for column in columns if column in ads_health.columns]
    st.dataframe(ads_health[columns], use_container_width=True, hide_index=True, height=360)
    download_csv(ads_health[columns], "ads_txt_fetch_status.csv", "Download Ads.txt Health")


def render_data_downloads() -> None:
    st.subheader("Data Downloads")
    export_order = [
        "lookup",
        "seller_health",
        "required_lines",
        "ads_sources",
        "parsed_ads",
        "ads_qa",
        "missing_lines",
        "ads_health",
        "name_summary",
        "id_summary",
    ]
    summary_rows: list[dict[str, object]] = []
    available: list[tuple[str, pd.DataFrame]] = []
    for key in export_order:
        path = DATA_FILES[key]
        filename = path.name
        if not path.exists():
            summary_rows.append({"file name": filename, "row count": "missing", "column count": "missing"})
            continue
        df = load_csv(str(path), optional_file_signature(path))
        available.append((filename, df))
        summary_rows.append({"file name": filename, "row count": len(df), "column count": len(df.columns)})

    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    for filename, df in available:
        st.download_button(
            f"Download {filename}",
            to_csv_download(df),
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )


def render_health_export_tab(seller_health: pd.DataFrame, ads_health: pd.DataFrame) -> None:
    render_seller_health_section(seller_health)
    st.divider()
    render_ads_health_section(ads_health)
    st.divider()
    render_data_downloads()


def main() -> None:
    st.title("Seller Lookup + Ads.txt Line QA")
    st.caption("Search sellers.json records, verify required Ads.txt lines, and download action lists.")

    lookup = load_seller_lookup(file_signature("lookup"))
    seller_health = load_seller_health(file_signature("seller_health"))
    ads_qa = load_ads_qa()
    ads_health = load_ads_health()
    filtered_lookup = apply_sidebar_filters(lookup)

    tab_search, tab_ads_qa, tab_health_export = st.tabs(["Search", "Ads.txt Line QA", "Health / Export"])
    with tab_search:
        render_search_tab(filtered_lookup, ads_qa)
    with tab_ads_qa:
        render_ads_txt_qa_tab(ads_qa)
    with tab_health_export:
        render_health_export_tab(seller_health, ads_health)


if __name__ == "__main__":
    main()
