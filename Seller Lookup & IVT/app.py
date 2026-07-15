from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
PRESET_FILE = APP_DIR / "column_presets.json"
MG_IVT_SCHAIN_FILE = APP_DIR / "MG IVT - SCHAIN.xlsx"
DATA_FILES = {
    "lookup": APP_DIR / "seller_lookup_dashboard.csv",
    "name_summary": APP_DIR / "seller_name_summary.csv",
    "id_summary": APP_DIR / "seller_id_summary.csv",
    "health": APP_DIR / "seller_json_fetch_status.csv",
    "under_domain": APP_DIR.parent / "resolved_schain_ivt" / "ivt_by_seller_domain_under_domain.csv",
    "media_guard_summary": APP_DIR / "media_guard_seller_id_summary.csv",
    "media_guard_blacklist": APP_DIR / "media_guard_seller_id_blacklist.csv",
}

MG_IVT_SCHAIN_COLUMNS = [
    "Summary Sampled Seller Name",
    "Summary Sampled Seller Domain",
    "Relevant Pub ID Before dauup.com",
    "Summary Sampled SChain",
    "Summary Sampled Total Requests",
    "Summary Sampled Invalid Traffic (IVT) #",
    "Summary Sampled Invalid Traffic (IVT) %",
]

PRE_BID_IVT_COLUMNS = [
    "sellers_domain",
    "appears_under_domain",
    "row_count",
    "unique_schain_count",
    "total_requests",
    "invalid_traffic_count",
    "weighted_ivt_pct_percent",
    "seller_names_found",
    "seller_types_found",
    "sample_hop_pairs",
    "sample_schains",
]

PRE_BID_IVT_DEFAULT_COLUMNS = [
    "sellers_domain",
    "appears_under_domain",
    "total_requests",
    "invalid_traffic_count",
    "weighted_ivt_pct_percent",
    "row_count",
    "unique_schain_count",
    "seller_names_found",
    "seller_types_found",
]

PRE_BID_IVT_COLUMN_LABELS = {
    "sellers_domain": "Sellers Domain",
    "appears_under_domain": "Appears Under Domain",
    "row_count": "Row Count",
    "unique_schain_count": "Unique S-chain Count",
    "total_requests": "Total Requests",
    "invalid_traffic_count": "Invalid Traffic Count",
    "weighted_ivt_pct_percent": "Weighted IVT %",
    "seller_names_found": "Seller Names Found",
    "seller_types_found": "Seller Types Found",
    "sample_hop_pairs": "Sample Hop Pairs",
    "sample_schains": "Sample S-chains",
}

REQUIRED_COLUMNS = {
    "lookup": {"source_name", "sellers_json_url", "seller_name", "seller_id", "seller_domain"},
    "name_summary": {
        "seller_name",
        "seller_ids_found",
        "number_of_sellers_json_sources",
        "source_names_found_in",
        "sellers_json_urls_found_in",
    },
    "id_summary": {
        "seller_id",
        "seller_names_found",
        "number_of_sellers_json_sources",
        "source_names_found_in",
        "sellers_json_urls_found_in",
    },
    "health": {
        "source_name",
        "sellers_json_url",
        "http_status",
        "fetch_success",
        "parsed_success",
        "records_parsed",
        "error_message",
    },
    "under_domain": {
        "sellers_domain",
        "appears_under_domain",
        "row_count",
        "unique_schain_count",
        "total_requests",
        "invalid_traffic_count",
        "weighted_ivt_pct",
        "seller_names_found",
        "seller_types_found",
        "sample_hop_pairs",
        "sample_schains",
    },
    "media_guard_summary": {
        "seller_id",
        "schain_seller_domains",
        "sampled_publisher_ids",
        "sampled_publisher_names",
        "row_count",
        "total_requests",
        "invalid_traffic_count",
        "weighted_ivt_pct",
        "max_row_ivt_pct",
        "unique_schain_count",
        "sample_schains",
    },
    "media_guard_blacklist": {
        "seller_id",
        "schain_seller_domains",
        "sampled_publisher_ids",
        "sampled_publisher_names",
        "row_count",
        "total_requests",
        "invalid_traffic_count",
        "weighted_ivt_pct",
        "blacklist_reason",
    },
}


st.set_page_config(
    page_title="Seller Lookup Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    return text.rstrip("/")


def normalize_domain(value: object) -> str:
    text = normalize_text(value)
    text = text.split("?", 1)[0].split("#", 1)[0].split("/", 1)[0]
    return text.rstrip(".").rstrip("/")


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def format_ivt_pct(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if pd.isna(number):
        return ""
    return f"{number:.2%}"


def numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for col in cleaned.columns:
        if pd.api.types.is_object_dtype(cleaned[col]) or pd.api.types.is_string_dtype(cleaned[col]):
            cleaned[col] = cleaned[col].fillna("").astype(str)
            cleaned[col] = cleaned[col].replace({"nan": "", "None": "", "<NA>": ""})
    return cleaned


def validate_columns(name: str, df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS[name] - set(df.columns))
    if missing:
        st.error(f"`{DATA_FILES[name].name}` is missing required columns: {', '.join(missing)}")
        st.stop()


def load_column_presets() -> dict[str, dict[str, list[str]]]:
    if not PRESET_FILE.exists():
        return {}
    try:
        data = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    presets: dict[str, dict[str, list[str]]] = {}
    for tab_key, tab_presets in data.items():
        if not isinstance(tab_key, str) or not isinstance(tab_presets, dict):
            continue
        presets[tab_key] = {}
        for name, columns in tab_presets.items():
            if isinstance(name, str) and isinstance(columns, list):
                presets[tab_key][name] = [str(column) for column in columns]
    return presets


def save_column_presets(presets: dict[str, dict[str, list[str]]]) -> None:
    PRESET_FILE.write_text(json.dumps(presets, indent=2, sort_keys=True), encoding="utf-8")


def valid_preset_columns(columns: Iterable[str], all_columns: list[str], default_columns: list[str]) -> list[str]:
    selected = [column for column in columns if column in all_columns]
    return selected or default_columns.copy()


def render_column_preset_controls(
    tab_key: str,
    all_columns: list[str],
    default_columns: list[str],
    column_labels: dict[str, str],
) -> list[str]:
    presets = load_column_presets()
    tab_presets = presets.get(tab_key, {})
    preset_names = ["Default", *sorted(tab_presets)]
    selected_preset = st.selectbox("Column preset", preset_names, key=f"{tab_key}_preset")
    base_columns = default_columns if selected_preset == "Default" else tab_presets.get(selected_preset, default_columns)
    preset_key = re.sub(r"[^a-zA-Z0-9_]+", "_", selected_preset).strip("_").lower() or "default"
    selected_columns = st.multiselect(
        "Visible columns",
        all_columns,
        default=valid_preset_columns(base_columns, all_columns, default_columns),
        format_func=lambda column: column_labels.get(column, column),
        key=f"{tab_key}_columns_{preset_key}",
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    preset_name = c1.text_input("Preset name", key=f"{tab_key}_preset_name", placeholder="e.g. Ops view")
    if c2.button("Save preset", key=f"{tab_key}_save_preset", use_container_width=True):
        clean_name = preset_name.strip()
        if not clean_name:
            st.warning("Enter a preset name before saving.")
        elif not selected_columns:
            st.warning("Select at least one column before saving.")
        else:
            presets.setdefault(tab_key, {})[clean_name] = selected_columns
            save_column_presets(presets)
            st.success(f"Saved preset: {clean_name}")
            st.rerun()
    if c3.button("Delete preset", key=f"{tab_key}_delete_preset", use_container_width=True):
        if selected_preset == "Default":
            st.warning("Default preset cannot be deleted.")
        elif selected_preset in presets.get(tab_key, {}):
            del presets[tab_key][selected_preset]
            save_column_presets(presets)
            st.success(f"Deleted preset: {selected_preset}")
            st.rerun()

    return valid_preset_columns(selected_columns, all_columns, default_columns)


@st.cache_data(show_spinner="Loading seller lookup CSVs...")
def load_csv(path: str, file_mtime: float) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", low_memory=False)


def data_signature() -> tuple[float, ...]:
    return tuple(DATA_FILES[name].stat().st_mtime for name in sorted(DATA_FILES))


def mg_ivt_schain_signature() -> float:
    return MG_IVT_SCHAIN_FILE.stat().st_mtime if MG_IVT_SCHAIN_FILE.exists() else 0


@st.cache_data(show_spinner="Preparing seller lookup data...")
def load_data(
    signature: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [path.name for path in DATA_FILES.values() if not path.exists()]
    if missing:
        st.error(
            "Missing seller lookup dashboard file(s): "
            + ", ".join(f"`{name}`" for name in missing)
            + ". Run `python ..\\..\\work\\build_seller_lookup_dashboard.py` first."
        )
        st.stop()

    lookup = clean_strings(load_csv(str(DATA_FILES["lookup"]), DATA_FILES["lookup"].stat().st_mtime))
    name_summary = clean_strings(load_csv(str(DATA_FILES["name_summary"]), DATA_FILES["name_summary"].stat().st_mtime))
    id_summary = clean_strings(load_csv(str(DATA_FILES["id_summary"]), DATA_FILES["id_summary"].stat().st_mtime))
    health = clean_strings(load_csv(str(DATA_FILES["health"]), DATA_FILES["health"].stat().st_mtime))
    under_domain = clean_strings(
        load_csv(str(DATA_FILES["under_domain"]), DATA_FILES["under_domain"].stat().st_mtime)
    )
    media_guard_summary = clean_strings(
        load_csv(str(DATA_FILES["media_guard_summary"]), DATA_FILES["media_guard_summary"].stat().st_mtime)
    )
    media_guard_blacklist = clean_strings(
        load_csv(str(DATA_FILES["media_guard_blacklist"]), DATA_FILES["media_guard_blacklist"].stat().st_mtime)
    )

    validate_columns("lookup", lookup)
    validate_columns("name_summary", name_summary)
    validate_columns("id_summary", id_summary)
    validate_columns("health", health)
    validate_columns("under_domain", under_domain)
    validate_columns("media_guard_summary", media_guard_summary)
    validate_columns("media_guard_blacklist", media_guard_blacklist)

    if "seller_domain" not in lookup.columns:
        lookup["seller_domain"] = lookup.get("seller_name_respective_domain", "")
    if "seller_domain_ivt_pct" not in lookup.columns:
        lookup["seller_domain_ivt_pct"] = ""
    if "seller_domain_ivt_pct" not in name_summary.columns:
        name_summary["seller_domain_ivt_pct"] = ""
    if "seller_domains_found" not in name_summary.columns:
        name_summary["seller_domains_found"] = ""
    if "seller_domains_found" not in id_summary.columns:
        id_summary["seller_domains_found"] = ""

    for col in [
        "seller_name",
        "seller_id",
        "source_name",
        "sellers_json_url",
        "seller_domain",
    ]:
        lookup[f"_norm_{col}"] = lookup[col].map(normalize_text)
    lookup["seller_domain_ivt_pct_numeric"] = pd.to_numeric(
        lookup["seller_domain_ivt_pct"], errors="coerce"
    )
    lookup["seller_domain_ivt_pct"] = lookup["seller_domain_ivt_pct_numeric"].map(format_ivt_pct)

    health["fetch_success"] = as_bool(health["fetch_success"])
    health["parsed_success"] = as_bool(health["parsed_success"])
    health["records_parsed_numeric"] = pd.to_numeric(health["records_parsed"], errors="coerce").fillna(0).astype(int)
    health["http_status_display"] = health["http_status"].replace({"nan": "", "None": ""})

    for col in ["row_count", "unique_schain_count", "total_requests", "invalid_traffic_count", "weighted_ivt_pct"]:
        under_domain[f"{col}_numeric"] = numeric_series(under_domain[col])
    under_domain["_norm_sellers_domain"] = under_domain["sellers_domain"].map(normalize_text)
    under_domain["_norm_appears_under_domain"] = under_domain["appears_under_domain"].map(normalize_text)
    under_domain["weighted_ivt_pct_display"] = under_domain["weighted_ivt_pct_numeric"].map(format_ivt_pct)
    under_domain["weighted_ivt_pct_percent"] = under_domain["weighted_ivt_pct_numeric"] * 100

    for df in [media_guard_summary, media_guard_blacklist]:
        for col in [
            "row_count",
            "total_requests",
            "invalid_traffic_count",
            "sophisticated_ivt_count",
            "general_ivt_count",
            "valid_traffic_count",
            "weighted_ivt_pct",
            "weighted_sophisticated_ivt_pct",
            "weighted_general_ivt_pct",
            "weighted_valid_traffic_pct",
            "max_row_ivt_pct",
            "unique_schain_count",
        ]:
            if col in df.columns:
                df[f"{col}_numeric"] = numeric_series(df[col])
        for col in [
            "seller_id",
            "media_guard_seller_names",
            "schain_seller_domains",
            "schain_node_names",
            "sampled_publisher_ids",
            "sampled_publisher_names",
            "seller_names_found",
            "seller_domains_found",
            "source_names_found_in",
            "upstream_domains",
        ]:
            if col not in df.columns:
                df[col] = ""
            df[f"_norm_{col}"] = df[col].map(normalize_text)
        if "weighted_ivt_pct_numeric" in df.columns:
            df["weighted_ivt_pct_percent"] = df["weighted_ivt_pct_numeric"] * 100
            df["weighted_ivt_pct_display"] = df["weighted_ivt_pct_numeric"].map(format_ivt_pct)
        if "max_row_ivt_pct_numeric" in df.columns:
            df["max_row_ivt_pct_display"] = df["max_row_ivt_pct_numeric"].map(format_ivt_pct)

    return lookup, name_summary, id_summary, health, under_domain, media_guard_summary, media_guard_blacklist


@st.cache_data(show_spinner="Loading MG IVT - SCHAIN workbook...")
def load_mg_ivt_schain(path: str, file_mtime: float) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, dtype=str)
    df = clean_strings(df)

    for col in MG_IVT_SCHAIN_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    numeric_columns = {
        "Summary Sampled Total Requests": "total_requests_numeric",
        "Summary Sampled Invalid Traffic (IVT) #": "invalid_traffic_numeric",
        "Summary Sampled Invalid Traffic (IVT) %": "ivt_pct_numeric",
    }
    for source_col, numeric_col in numeric_columns.items():
        df[numeric_col] = numeric_series(df[source_col])

    df["ivt_pct_percent"] = df["ivt_pct_numeric"] * 100
    for col in [
        "Summary Sampled Seller Name",
        "Summary Sampled Seller Domain",
        "Summary Sampled SChain",
        "Relevant Pub ID Before dauup.com",
    ]:
        df[f"_norm_{col}"] = df[col].map(normalize_text)
    return df


def unique_sorted(values: Iterable[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def filter_contains(df: pd.DataFrame, column: str, query: str) -> pd.DataFrame:
    term = normalize_text(query)
    if not term:
        return df
    return df[df[column].astype(str).map(normalize_text).str.contains(re.escape(term), case=False, na=False)]


def filter_multiselect(df: pd.DataFrame, column: str, values: list[str]) -> pd.DataFrame:
    if not values:
        return df
    return df[df[column].isin(values)]


def search_lookup(lookup: pd.DataFrame, query: str) -> pd.DataFrame:
    term = normalize_text(query)
    if not term:
        result = lookup.copy()
        result["match_reason"] = ""
        return result

    fields = [
        ("seller_name", "_norm_seller_name", "seller_name"),
        ("seller_id", "_norm_seller_id", "seller_id"),
        ("source_name", "_norm_source_name", "source_name"),
        ("sellers_json_url", "_norm_sellers_json_url", "sellers_json_url"),
    ]
    pattern = re.escape(term)
    combined = pd.Series(False, index=lookup.index)
    masks: list[tuple[str, pd.Series]] = []
    for _field, norm_col, reason in fields:
        mask = lookup[norm_col].str.contains(pattern, case=False, na=False)
        combined |= mask
        masks.append((reason, mask))

    result = lookup[combined].copy()
    result["match_reason"] = ""
    for reason, mask in masks:
        idx = result.index.intersection(mask[mask].index)
        if idx.empty:
            continue
        existing = result.loc[idx, "match_reason"]
        result.loc[idx, "match_reason"] = existing.where(existing.eq(""), existing + " | ") + reason
    return result


def apply_ivt_level_filter(
    df: pd.DataFrame,
    selected_levels: list[str],
    column: str = "seller_domain_ivt_pct_numeric",
) -> pd.DataFrame:
    if not selected_levels or column not in df.columns:
        return df

    ivt = df[column]
    mask = pd.Series(False, index=df.index)
    level_rules = {
        "Below 5%": ivt < 0.05,
        "Above 5%": ivt >= 0.05,
        "Below 10%": ivt < 0.10,
        "Above 10%": ivt >= 0.10,
        "Below 15%": ivt < 0.15,
        "Above 15%": ivt >= 0.15,
        "Below 20%": ivt < 0.20,
        "Above 20%": ivt >= 0.20,
    }
    for level in selected_levels:
        if level in level_rules:
            mask |= level_rules[level]
    return df[mask.fillna(False)]


def filter_under_domain_by_sidebar(
    under_domain: pd.DataFrame,
    lookup: pd.DataFrame,
    selected_sources: list[str],
    selected_urls: list[str],
    seller_id_search: str,
    selected_seller_ids: list[str],
    seller_domain_search: str,
    selected_seller_domains: list[str],
    selected_ivt_levels: list[str],
) -> pd.DataFrame:
    filtered = under_domain.copy()

    selected_owner_domains = {normalize_domain(url) for url in selected_urls if normalize_domain(url)}
    if selected_sources:
        source_owner_domains = lookup.loc[
            lookup["source_name"].isin(selected_sources),
            "sellers_json_url",
        ].map(normalize_domain)
        selected_owner_domains.update(domain for domain in source_owner_domains if domain)
    if selected_owner_domains:
        filtered = filtered[filtered["appears_under_domain"].map(normalize_domain).isin(selected_owner_domains)]

    seller_domains_from_ids: set[str] = set()
    if seller_id_search:
        seller_id_term = normalize_text(seller_id_search)
        matched_lookup = lookup[lookup["seller_id"].map(normalize_text).str.contains(re.escape(seller_id_term), na=False)]
        seller_domains_from_ids.update(
            domain for domain in matched_lookup["seller_domain"].map(normalize_domain) if domain
        )
    if selected_seller_ids:
        matched_lookup = lookup[lookup["seller_id"].isin(selected_seller_ids)]
        seller_domains_from_ids.update(
            domain for domain in matched_lookup["seller_domain"].map(normalize_domain) if domain
        )
    if seller_id_search or selected_seller_ids:
        filtered = filtered[filtered["sellers_domain"].map(normalize_domain).isin(seller_domains_from_ids)]

    filtered = filter_contains(filtered, "sellers_domain", seller_domain_search)
    if selected_seller_domains:
        selected_seller_domain_set = {normalize_domain(domain) for domain in selected_seller_domains}
        filtered = filtered[filtered["sellers_domain"].map(normalize_domain).isin(selected_seller_domain_set)]
    filtered = apply_ivt_level_filter(filtered, selected_ivt_levels, column="weighted_ivt_pct_numeric")
    return filtered


def download_csv(df: pd.DataFrame, filename: str, label: str) -> None:
    export = df.drop(columns=[col for col in df.columns if col.startswith("_")], errors="ignore")
    st.download_button(
        label,
        export.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def render_kpis(lookup: pd.DataFrame, health: pd.DataFrame) -> None:
    cols = st.columns(6)
    cols[0].metric("Total Seller Records", f"{len(lookup):,}")
    cols[1].metric("Unique Seller Names", f"{lookup['seller_name'].replace('', pd.NA).dropna().nunique():,}")
    cols[2].metric("Unique Seller IDs", f"{lookup['seller_id'].replace('', pd.NA).dropna().nunique():,}")
    cols[3].metric("sellers.json Sources", f"{health['sellers_json_url'].nunique():,}")
    cols[4].metric("Parsed Sources", f"{int(health['parsed_success'].sum()):,}")
    cols[5].metric("Failed Sources", f"{int((~health['parsed_success']).sum()):,}")


def render_lookup_tab(lookup: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Seller Lookup")
    if "seller_lookup_query" not in st.session_state:
        st.session_state["seller_lookup_query"] = ""

    button_cols = st.columns(6)
    quick_terms = ["Lacuna", "zMaticoo", "PubMatic", "InMobi", "34167", "34197"]
    for term, col in zip(quick_terms, button_cols):
        if col.button(term, key=f"quick_{term.lower()}", use_container_width=True):
            st.session_state["seller_lookup_query"] = term

    query = st.text_input(
        "Search seller name or seller ID",
        placeholder="Lacuna, zMaticoo, PubMatic, 34167, 34197",
        key="seller_lookup_query",
    )
    filtered = search_lookup(lookup, query)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Matched Rows", f"{len(filtered):,}")
    metric_cols[1].metric("Unique Sources", f"{filtered['source_name'].nunique():,}")
    metric_cols[2].metric("Seller IDs Found", f"{filtered['seller_id'].replace('', pd.NA).dropna().nunique():,}")
    metric_cols[3].metric("Seller Names Found", f"{filtered['seller_name'].replace('', pd.NA).dropna().nunique():,}")

    columns = [
        "source_name",
        "sellers_json_url",
        "seller_name",
        "seller_domain",
        "seller_domain_ivt_pct",
        "seller_id",
        "match_reason",
    ]
    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={
            "seller_domain": st.column_config.TextColumn("Seller Domain"),
            "seller_domain_ivt_pct": st.column_config.TextColumn("Seller Domain IVT %"),
        },
    )
    download_csv(filtered[columns], "filtered_seller_lookup_results.csv", "Download filtered Seller Lookup results")
    return filtered


def render_name_summary_tab(name_summary: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Seller Name Summary")
    c1, c2, c3, c4 = st.columns(4)
    seller_name = c1.text_input("Seller name search", key="name_summary_seller_name")
    seller_id = c2.text_input("Seller ID contains", key="name_summary_seller_id")
    source_name = c3.text_input("Source name contains", key="name_summary_source_name")
    seller_domain = c4.text_input("Seller Domain contains", key="name_summary_seller_domain")

    filtered = filter_contains(name_summary, "seller_name", seller_name)
    filtered = filter_contains(filtered, "seller_ids_found", seller_id)
    filtered = filter_contains(filtered, "source_names_found_in", source_name)
    filtered = filter_contains(filtered, "seller_domains_found", seller_domain)

    columns = [
        "seller_name",
        "seller_ids_found",
        "seller_domains_found",
        "seller_domain_ivt_pct",
        "number_of_sellers_json_sources",
        "source_names_found_in",
        "sellers_json_urls_found_in",
    ]
    st.dataframe(filtered[columns], use_container_width=True, hide_index=True, height=650)
    download_csv(filtered[columns], "filtered_seller_name_summary.csv", "Download filtered Seller Name Summary")
    return filtered


def render_id_summary_tab(id_summary: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Seller ID Summary")
    c1, c2, c3 = st.columns(3)
    seller_id = c1.text_input("Seller ID search", key="id_summary_seller_id")
    seller_name = c2.text_input("Seller name contains", key="id_summary_seller_name")
    source_name = c3.text_input("Source name contains", key="id_summary_source_name")

    filtered = filter_contains(id_summary, "seller_id", seller_id)
    filtered = filter_contains(filtered, "seller_names_found", seller_name)
    filtered = filter_contains(filtered, "source_names_found_in", source_name)

    columns = [
        "seller_id",
        "seller_names_found",
        "seller_domains_found",
        "number_of_sellers_json_sources",
        "source_names_found_in",
        "sellers_json_urls_found_in",
    ]
    st.dataframe(filtered[columns], use_container_width=True, hide_index=True, height=650)
    download_csv(filtered[columns], "filtered_seller_id_summary.csv", "Download filtered Seller ID Summary")
    return filtered


def render_source_explorer_tab(lookup: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Source Explorer")
    st.caption("Inspect every seller row loaded from a specific sellers.json source.")

    c1, c2, c3 = st.columns([2, 1, 1])
    source_query = c1.text_input(
        "Source name or sellers.json URL contains",
        value="lkqd",
        placeholder="e.g. lkqd, lkqd.net, https://lkqd.com/sellers.json",
        key="source_explorer_source_query",
    )
    seller_id_query = c2.text_input(
        "Seller ID contains",
        placeholder="e.g. 476",
        key="source_explorer_seller_id_query",
    )
    seller_domain_query = c3.text_input(
        "Seller Domain contains",
        placeholder="e.g. nexstardigital.com",
        key="source_explorer_seller_domain_query",
    )

    filtered = lookup.copy()
    source_term = normalize_text(source_query)
    if source_term:
        source_mask = (
            filtered["_norm_source_name"].str.contains(re.escape(source_term), case=False, na=False)
            | filtered["_norm_sellers_json_url"].str.contains(re.escape(source_term), case=False, na=False)
        )
        filtered = filtered[source_mask]
    filtered = filter_contains(filtered, "seller_id", seller_id_query)
    filtered = filter_contains(filtered, "seller_domain", seller_domain_query)

    metric_cols = st.columns(5)
    metric_cols[0].metric("Rows", f"{len(filtered):,}")
    metric_cols[1].metric("Unique Seller IDs", f"{filtered['seller_id'].replace('', pd.NA).dropna().nunique():,}")
    metric_cols[2].metric("Unique Seller Names", f"{filtered['seller_name'].replace('', pd.NA).dropna().nunique():,}")
    metric_cols[3].metric("Unique Domains", f"{filtered['seller_domain'].replace('', pd.NA).dropna().nunique():,}")
    metric_cols[4].metric("Sources", f"{filtered['sellers_json_url'].replace('', pd.NA).dropna().nunique():,}")

    columns = [
        "source_name",
        "sellers_json_url",
        "seller_id",
        "seller_name",
        "seller_domain",
        "seller_type",
        "seller_domain_ivt_pct",
    ]
    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "sellers_json_url": st.column_config.LinkColumn("sellers.json URL"),
            "seller_id": st.column_config.TextColumn("Seller ID"),
            "seller_name": st.column_config.TextColumn("Seller Name"),
            "seller_domain": st.column_config.TextColumn("Seller Domain"),
            "seller_type": st.column_config.TextColumn("Seller Type"),
            "seller_domain_ivt_pct": st.column_config.TextColumn("Seller Domain IVT %"),
        },
    )
    download_csv(filtered[columns], "filtered_source_explorer.csv", "Download filtered Source Explorer results")
    return filtered


def render_health_tab(health: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Source Health")
    c1, c2, c3, c4 = st.columns(4)
    fetch_success = c1.multiselect("Fetch success", ["True", "False"])
    parsed_success = c2.multiselect("Parsed success", ["True", "False"])
    source_names = c3.multiselect("Source name", unique_sorted(health["source_name"]))
    http_status = c4.multiselect("HTTP status", unique_sorted(health["http_status_display"]))

    filtered = health.copy()
    if fetch_success:
        filtered = filtered[filtered["fetch_success"].isin({value == "True" for value in fetch_success})]
    if parsed_success:
        filtered = filtered[filtered["parsed_success"].isin({value == "True" for value in parsed_success})]
    filtered = filter_multiselect(filtered, "source_name", source_names)
    filtered = filter_multiselect(filtered, "http_status_display", http_status)

    columns = [
        "source_name",
        "sellers_json_url",
        "http_status",
        "fetch_success",
        "parsed_success",
        "records_parsed",
        "error_message",
    ]
    st.dataframe(filtered[columns], use_container_width=True, hide_index=True, height=650)
    download_csv(filtered[columns], "filtered_seller_json_fetch_status.csv", "Download Source Health table")
    return filtered


def render_under_domain_tab(under_domain: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Pre-Bid IVT")
    if "under_domain_seller_query" not in st.session_state:
        st.session_state["under_domain_seller_query"] = ""

    button_cols = st.columns(5)
    if button_cols[0].button("samsung.com", key="quick_under_samsung", use_container_width=True):
        st.session_state["under_domain_seller_query"] = "samsung.com"

    c1, c2 = st.columns(2)
    sellers_domain = c1.text_input(
        "Sellers Domain contains",
        key="under_domain_seller_query",
        placeholder="e.g. samsung.com",
    )
    appears_under_domain = c2.text_input(
        "Appears Under Domain contains",
        key="under_domain_appears_query",
        placeholder="e.g. pubmatic.com, openx.com",
    )

    filtered = under_domain.copy()
    seller_term = normalize_text(sellers_domain)
    if seller_term:
        filtered = filtered[filtered["_norm_sellers_domain"].str.contains(re.escape(seller_term), case=False, na=False)]
    under_term = normalize_text(appears_under_domain)
    if under_term:
        filtered = filtered[
            filtered["_norm_appears_under_domain"].str.contains(re.escape(under_term), case=False, na=False)
        ]
    filtered = filtered.sort_values(
        ["invalid_traffic_count_numeric", "weighted_ivt_pct_numeric", "total_requests_numeric"],
        ascending=[False, False, False],
    )

    total_requests = filtered["total_requests_numeric"].sum()
    invalid_traffic = filtered["invalid_traffic_count_numeric"].sum()
    weighted_ivt = invalid_traffic / total_requests if total_requests else 0

    metric_cols = st.columns(4)
    metric_cols[0].metric("Total Requests", f"{total_requests:,.0f}")
    metric_cols[1].metric("Invalid Traffic Count", f"{invalid_traffic:,.0f}")
    metric_cols[2].metric("Weighted IVT %", f"{weighted_ivt:.2%}")
    metric_cols[3].metric("Under-Domains", f"{filtered['appears_under_domain'].nunique():,}")

    selected_columns = render_column_preset_controls(
        "pre_bid_ivt",
        PRE_BID_IVT_COLUMNS,
        PRE_BID_IVT_DEFAULT_COLUMNS,
        PRE_BID_IVT_COLUMN_LABELS,
    )
    st.dataframe(
        filtered[selected_columns],
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "sellers_domain": st.column_config.TextColumn("Sellers Domain"),
            "appears_under_domain": st.column_config.TextColumn("Appears Under Domain"),
            "weighted_ivt_pct_percent": st.column_config.NumberColumn("Weighted IVT %", format="%.2f%%"),
        },
    )
    download_csv(
        filtered[selected_columns],
        "filtered_pre_bid_ivt.csv",
        "Download filtered Pre-Bid IVT",
    )
    return filtered


def render_seller_id_blacklist_tab(
    media_guard_summary: pd.DataFrame,
    media_guard_blacklist: pd.DataFrame,
) -> pd.DataFrame:
    st.subheader("Seller ID Blacklist")
    st.caption(
        "Media-Guard Pre-Bid data period: 11/06/2026 to 18/06/2026. "
        "Default blacklist rule: SChain seller ID weighted IVT above 10% and attributed total requests above 1,000,000."
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    min_requests = c1.number_input(
        "Minimum requests",
        min_value=0,
        value=1_000_000,
        step=100_000,
        format="%d",
        key="blacklist_min_requests",
    )
    min_ivt_pct = c2.number_input(
        "Minimum weighted IVT %",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=0.5,
        format="%.2f",
        key="blacklist_min_ivt_pct",
    )
    search = c3.text_input(
        "Search seller ID, seller name, domain, source, or SChain domain",
        placeholder="e.g. 102387, 1100046578, 34104, smaato.com, Lacuna",
        key="blacklist_search",
    )

    filtered = media_guard_summary.copy()
    filtered = filtered[
        (filtered["total_requests_numeric"] > min_requests)
        & (filtered["weighted_ivt_pct_numeric"] > (min_ivt_pct / 100))
    ]

    term = normalize_text(search)
    if term:
        search_mask = pd.Series(False, index=filtered.index)
        for col in [
            "_norm_seller_id",
            "_norm_media_guard_seller_names",
            "_norm_schain_seller_domains",
            "_norm_schain_node_names",
            "_norm_sampled_publisher_ids",
            "_norm_sampled_publisher_names",
            "_norm_seller_names_found",
            "_norm_seller_domains_found",
            "_norm_source_names_found_in",
            "_norm_upstream_domains",
        ]:
            if col in filtered.columns:
                search_mask |= filtered[col].str.contains(re.escape(term), case=False, na=False)
        filtered = filtered[search_mask]

    filtered = filtered.sort_values(
        ["weighted_ivt_pct_numeric", "total_requests_numeric"],
        ascending=[False, False],
    )

    total_requests = filtered["total_requests_numeric"].sum()
    invalid_traffic = filtered["invalid_traffic_count_numeric"].sum()
    weighted_ivt = invalid_traffic / total_requests if total_requests else 0

    metric_cols = st.columns(5)
    metric_cols[0].metric("Blacklisted SChain Seller IDs", f"{filtered['seller_id'].nunique():,}")
    metric_cols[1].metric("Attributed Requests", f"{total_requests:,.0f}")
    metric_cols[2].metric("Attributed Invalid Traffic", f"{invalid_traffic:,.0f}")
    metric_cols[3].metric("Weighted IVT %", f"{weighted_ivt:.2%}")
    metric_cols[4].metric("Default Rule IDs", f"{media_guard_blacklist['seller_id'].nunique():,}")

    columns = [
        "seller_id",
        "schain_seller_domains",
        "schain_node_names",
        "sampled_publisher_ids",
        "sampled_publisher_names",
        "seller_names_found",
        "seller_domains_found",
        "source_names_found_in",
        "total_requests",
        "invalid_traffic_count",
        "weighted_ivt_pct_percent",
        "max_row_ivt_pct_display",
        "row_count",
        "unique_schain_count",
        "upstream_domains",
        "sample_schains",
    ]
    columns = [col for col in columns if col in filtered.columns]

    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "seller_id": st.column_config.TextColumn("SChain Seller ID"),
            "schain_seller_domains": st.column_config.TextColumn("SChain Seller Domain"),
            "schain_node_names": st.column_config.TextColumn("SChain Node Name"),
            "sampled_publisher_ids": st.column_config.TextColumn("Sampled Publisher IDs"),
            "sampled_publisher_names": st.column_config.TextColumn("Sampled Publisher Names"),
            "seller_names_found": st.column_config.TextColumn("sellers.json Seller Names"),
            "seller_domains_found": st.column_config.TextColumn("sellers.json Seller Domains"),
            "source_names_found_in": st.column_config.TextColumn("sellers.json Sources"),
            "total_requests": st.column_config.NumberColumn("Attributed Requests", format="%d"),
            "invalid_traffic_count": st.column_config.NumberColumn("Attributed Invalid Traffic", format="%d"),
            "weighted_ivt_pct_percent": st.column_config.NumberColumn("Weighted IVT %", format="%.2f%%"),
            "max_row_ivt_pct_display": st.column_config.TextColumn("Max Row IVT %"),
            "row_count": st.column_config.NumberColumn("Rows", format="%d"),
            "unique_schain_count": st.column_config.NumberColumn("Unique SChains", format="%d"),
        },
    )
    download_csv(
        filtered[columns],
        "seller_id_blacklist_current_filters.csv",
        "Download current Seller ID Blacklist",
    )

    st.download_button(
        "Download default Seller ID Blacklist CSV",
        media_guard_blacklist.drop(columns=[col for col in media_guard_blacklist.columns if col.startswith("_")], errors="ignore")
        .to_csv(index=False)
        .encode("utf-8-sig"),
        file_name="media_guard_seller_id_blacklist.csv",
        mime="text/csv",
        use_container_width=True,
    )
    return filtered


def render_mg_ivt_schain_tab(mg_ivt_schain: pd.DataFrame) -> pd.DataFrame:
    st.subheader("MG IVT - SCHAIN")
    st.caption(
        "Source workbook: `MG IVT - SCHAIN.xlsx`. The `Relevant Pub ID Before dauup.com` column is parsed from the SChain node immediately before `dauup.com`."
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    search = c1.text_input(
        "Search seller name, domain, SChain, or relevant pub ID",
        placeholder="e.g. Lacuna, openx.com, 559913615, dauup.com",
        key="mg_ivt_schain_search",
    )
    min_requests = c2.number_input(
        "Minimum requests",
        min_value=0,
        value=0,
        step=100_000,
        format="%d",
        key="mg_ivt_schain_min_requests",
    )
    min_ivt_pct = c3.number_input(
        "Minimum IVT %",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.5,
        format="%.2f",
        key="mg_ivt_schain_min_ivt_pct",
    )

    filtered = mg_ivt_schain.copy()
    filtered = filtered[filtered["total_requests_numeric"] >= min_requests]
    filtered = filtered[filtered["ivt_pct_numeric"] >= (min_ivt_pct / 100)]

    term = normalize_text(search)
    if term:
        search_mask = pd.Series(False, index=filtered.index)
        for col in [
            "_norm_Summary Sampled Seller Name",
            "_norm_Summary Sampled Seller Domain",
            "_norm_Summary Sampled SChain",
            "_norm_Relevant Pub ID Before dauup.com",
        ]:
            search_mask |= filtered[col].str.contains(re.escape(term), case=False, na=False)
        filtered = filtered[search_mask]

    filtered = filtered.sort_values(
        ["invalid_traffic_numeric", "ivt_pct_numeric", "total_requests_numeric"],
        ascending=[False, False, False],
    )

    total_requests = filtered["total_requests_numeric"].sum()
    invalid_traffic = filtered["invalid_traffic_numeric"].sum()
    weighted_ivt = invalid_traffic / total_requests if total_requests else 0

    metric_cols = st.columns(5)
    metric_cols[0].metric("Rows", f"{len(filtered):,}")
    metric_cols[1].metric("Relevant Pub IDs", f"{filtered['Relevant Pub ID Before dauup.com'].replace('', pd.NA).dropna().nunique():,}")
    metric_cols[2].metric("Total Requests", f"{total_requests:,.0f}")
    metric_cols[3].metric("Invalid Traffic", f"{invalid_traffic:,.0f}")
    metric_cols[4].metric("Weighted IVT %", f"{weighted_ivt:.2%}")

    columns = [col for col in MG_IVT_SCHAIN_COLUMNS if col in filtered.columns]
    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "Summary Sampled Seller Name": st.column_config.TextColumn("Seller Name"),
            "Summary Sampled Seller Domain": st.column_config.TextColumn("Seller Domain"),
            "Relevant Pub ID Before dauup.com": st.column_config.TextColumn("Relevant Pub ID Before dauup.com"),
            "Summary Sampled SChain": st.column_config.TextColumn("SChain"),
            "Summary Sampled Total Requests": st.column_config.NumberColumn("Total Requests", format="%d"),
            "Summary Sampled Invalid Traffic (IVT) #": st.column_config.NumberColumn("Invalid Traffic", format="%d"),
            "Summary Sampled Invalid Traffic (IVT) %": st.column_config.NumberColumn("IVT %", format="%.4f"),
        },
    )
    download_csv(
        filtered[columns],
        "filtered_mg_ivt_schain.csv",
        "Download filtered MG IVT - SCHAIN",
    )
    st.download_button(
        "Download source MG IVT - SCHAIN workbook",
        MG_IVT_SCHAIN_FILE.read_bytes(),
        file_name="MG IVT - SCHAIN.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    return filtered


def main() -> None:
    st.title("Seller Lookup Dashboard")
    st.caption(
        "Displays already-scanned sellers.json records with IVT from resolved S-chain seller domains. "
        "The app does not rescan live URLs on open."
    )

    (
        lookup,
        name_summary,
        id_summary,
        health,
        under_domain,
        media_guard_summary,
        media_guard_blacklist,
    ) = load_data(data_signature())
    if not MG_IVT_SCHAIN_FILE.exists():
        st.error(f"Missing `{MG_IVT_SCHAIN_FILE.name}` in the dashboard folder.")
        st.stop()
    mg_ivt_schain = load_mg_ivt_schain(str(MG_IVT_SCHAIN_FILE), mg_ivt_schain_signature())

    st.sidebar.header("Sidebar Filters")
    selected_sources = st.sidebar.multiselect("Source names", unique_sorted(lookup["source_name"]))
    selected_urls = st.sidebar.multiselect("sellers.json URLs", unique_sorted(lookup["sellers_json_url"]))
    seller_id_search = st.sidebar.text_input("Seller ID contains", placeholder="e.g. 34167, pub_11138")
    selected_seller_ids = st.sidebar.multiselect("Seller IDs", unique_sorted(lookup["seller_id"]))
    seller_domain_search = st.sidebar.text_input(
        "Seller Domain contains",
        placeholder="e.g. lacunads.com, pubmatic.com",
    )
    selected_seller_domains = st.sidebar.multiselect(
        "Seller Domains",
        unique_sorted(lookup["seller_domain"]),
    )
    selected_ivt_levels = st.sidebar.multiselect(
        "IVT Levels",
        [
            "Below 5%",
            "Above 5%",
            "Below 10%",
            "Above 10%",
            "Below 15%",
            "Above 15%",
            "Below 20%",
            "Above 20%",
        ],
    )
    filtered_lookup = filter_multiselect(lookup, "source_name", selected_sources)
    filtered_lookup = filter_multiselect(filtered_lookup, "sellers_json_url", selected_urls)
    filtered_lookup = filter_contains(filtered_lookup, "seller_id", seller_id_search)
    filtered_lookup = filter_multiselect(filtered_lookup, "seller_id", selected_seller_ids)
    filtered_lookup = filter_contains(
        filtered_lookup,
        "seller_domain",
        seller_domain_search,
    )
    filtered_lookup = filter_multiselect(
        filtered_lookup,
        "seller_domain",
        selected_seller_domains,
    )
    filtered_lookup = apply_ivt_level_filter(filtered_lookup, selected_ivt_levels)
    filtered_under_domain = filter_under_domain_by_sidebar(
        under_domain,
        lookup,
        selected_sources,
        selected_urls,
        seller_id_search,
        selected_seller_ids,
        seller_domain_search,
        selected_seller_domains,
        selected_ivt_levels,
    )

    render_kpis(filtered_lookup, health)
    st.divider()

    tab_lookup, tab_name, tab_id, tab_source, tab_blacklist, tab_mg_ivt_schain, tab_under_domain, tab_health = st.tabs(
        [
            "Seller Lookup",
            "Seller Name Summary",
            "Seller ID Summary",
            "Source Explorer",
            "Seller ID Blacklist",
            "MG IVT - SCHAIN",
            "Pre-Bid IVT",
            "Source Health",
        ]
    )

    with tab_lookup:
        render_lookup_tab(filtered_lookup)
    with tab_name:
        render_name_summary_tab(name_summary)
    with tab_id:
        render_id_summary_tab(id_summary)
    with tab_source:
        render_source_explorer_tab(lookup)
    with tab_blacklist:
        render_seller_id_blacklist_tab(media_guard_summary, media_guard_blacklist)
    with tab_mg_ivt_schain:
        render_mg_ivt_schain_tab(mg_ivt_schain)
    with tab_under_domain:
        render_under_domain_tab(filtered_under_domain)
    with tab_health:
        render_health_tab(health)


if __name__ == "__main__":
    main()
