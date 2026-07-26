from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILES = {
    "lookup": APP_DIR / "seller_lookup_dashboard.csv",
    "health": APP_DIR / "seller_json_fetch_status.csv",
    "name_summary": APP_DIR / "seller_name_summary.csv",
    "id_summary": APP_DIR / "seller_id_summary.csv",
}

LOOKUP_REQUIRED_COLUMNS = {
    "source_name",
    "sellers_json_url",
    "seller_name",
    "seller_domain",
    "seller_id",
    "seller_type",
}
HEALTH_REQUIRED_COLUMNS = {
    "source_name",
    "sellers_json_url",
    "http_status",
    "fetch_success",
    "parsed_success",
    "records_parsed",
    "error_message",
}
SEARCH_FIELDS = {
    "Seller ID": ("seller_id", "matched seller ID"),
    "Seller Name": ("seller_name", "matched seller name"),
    "Seller Domain": ("seller_domain", "matched seller domain"),
    "Source Name": ("source_name", "matched source name"),
    "Sellers.json URL": ("sellers_json_url", "matched sellers.json URL"),
}
DEFAULT_RESULT_COLUMNS = [
    "source_name",
    "seller_id",
    "seller_name",
    "seller_domain",
    "seller_type",
    "sellers_json_url",
    "match_reason",
    "matched_terms",
]


st.set_page_config(
    page_title="Seller Lookup",
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


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def required_file_signature() -> tuple[float, float]:
    return (
        DATA_FILES["lookup"].stat().st_mtime if DATA_FILES["lookup"].exists() else 0,
        DATA_FILES["health"].stat().st_mtime if DATA_FILES["health"].exists() else 0,
    )


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


@st.cache_data(show_spinner="Loading seller lookup data...")
def load_seller_lookup(signature: tuple[float, float]) -> pd.DataFrame:
    if not DATA_FILES["lookup"].exists():
        friendly_missing_file(DATA_FILES["lookup"])

    lookup = load_csv(str(DATA_FILES["lookup"]), DATA_FILES["lookup"].stat().st_mtime)
    validate_columns(lookup, LOOKUP_REQUIRED_COLUMNS, DATA_FILES["lookup"].name)

    for column in LOOKUP_REQUIRED_COLUMNS:
        lookup[column] = lookup[column].fillna("").astype(str)
        lookup[f"_norm_{column}"] = lookup[column].map(normalize_for_search)
    return lookup


@st.cache_data(show_spinner="Loading source health data...")
def load_source_health(signature: tuple[float, float]) -> pd.DataFrame:
    if not DATA_FILES["health"].exists():
        friendly_missing_file(DATA_FILES["health"])

    health = load_csv(str(DATA_FILES["health"]), DATA_FILES["health"].stat().st_mtime)
    validate_columns(health, HEALTH_REQUIRED_COLUMNS, DATA_FILES["health"].name)
    health["fetch_success"] = as_bool(health["fetch_success"])
    health["parsed_success"] = as_bool(health["parsed_success"])
    health["records_parsed_numeric"] = pd.to_numeric(health["records_parsed"], errors="coerce").fillna(0).astype(int)
    health["http_status_display"] = health["http_status"].fillna("").astype(str)
    for column in ["source_name", "sellers_json_url"]:
        health[f"_norm_{column}"] = health[column].map(normalize_for_search)
    return health


def apply_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    source_names = st.sidebar.multiselect("Source name", unique_sorted(df["source_name"]))
    seller_types = st.sidebar.multiselect("Seller type", unique_sorted(df["seller_type"]))
    seller_domain = st.sidebar.text_input("Seller domain contains", placeholder="e.g. pubmatic.com")
    seller_name = st.sidebar.text_input("Seller name contains", placeholder="e.g. Lacuna")
    seller_id = st.sidebar.text_input("Seller ID exact match", placeholder="e.g. 34167, 34197, 34114")

    filtered = df.copy()
    if source_names:
        filtered = filtered[filtered["source_name"].isin(source_names)]
    if seller_types:
        filtered = filtered[filtered["seller_type"].isin(seller_types)]
    for column, value in [
        ("seller_domain", seller_domain),
        ("seller_name", seller_name),
    ]:
        terms = parse_search_terms(value)
        if terms:
            mask = pd.Series(False, index=filtered.index)
            for term in terms:
                normalized_term = normalize_for_search(term)
                if normalized_term:
                    mask |= filtered[f"_norm_{column}"].str.contains(
                        re.escape(normalized_term),
                        case=False,
                        na=False,
                    )
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


def add_match_reason(df: pd.DataFrame, terms: list[str], mode: str) -> pd.DataFrame:
    result = df.copy()
    result["match_reason"] = ""
    result["matched_terms"] = ""

    if not terms:
        return result

    if mode == "Seller ID":
        normalized_terms = {
            normalize_for_search(term): term
            for term in terms
            if normalize_for_search(term)
        }
        result = result[result["_norm_seller_id"].isin(normalized_terms)].copy()
        result["match_reason"] = "matched seller ID"
        result["matched_terms"] = result["_norm_seller_id"].map(normalized_terms).fillna("")
        return result

    field_items = SEARCH_FIELDS.items() if mode == "Auto" else [(mode, SEARCH_FIELDS[mode])]
    keep_mask = pd.Series(False, index=result.index)
    row_reasons: dict[int, set[str]] = {idx: set() for idx in result.index}
    row_terms: dict[int, list[str]] = {idx: [] for idx in result.index}

    for term in terms:
        term_mask = pd.Series(False, index=result.index)
        for _mode_name, (field, reason) in field_items:
            exact_id = field == "seller_id" and mode == "Seller ID"
            field_mask = match_field(result[f"_norm_{field}"], term, exact=exact_id)
            if mode == "Auto" and field == "seller_id":
                field_mask |= match_field(result[f"_norm_{field}"], term, exact=True)
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
        result.at[idx, "match_reason"] = (
            "matched multiple fields" if len(reasons) > 1 else next(iter(reasons), "")
        )
        result.at[idx, "matched_terms"] = ", ".join(row_terms[idx])
    return result


def apply_search(df: pd.DataFrame, terms: list[str], mode: str) -> pd.DataFrame:
    return add_match_reason(df, terms, mode)


def join_unique(values: Iterable[object]) -> str:
    return ", ".join(unique_sorted(values))


def group_by_seller_id(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "seller_id",
                "seller_names_found",
                "seller_domains_found",
                "source_names_found_in",
                "source_count",
            ]
        )
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
        return pd.DataFrame(
            columns=[
                "seller_domain",
                "seller_names_found",
                "seller_ids_found",
                "source_names_found_in",
                "source_count",
            ]
        )
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
    st.download_button(
        label,
        to_csv_download(df),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def render_result_kpis(df: pd.DataFrame) -> None:
    cols = st.columns(5)
    cols[0].metric("Matching rows", f"{len(df):,}")
    cols[1].metric("Unique seller IDs", f"{df['seller_id'].replace('', pd.NA).dropna().nunique():,}")
    cols[2].metric("Unique seller names", f"{df['seller_name'].replace('', pd.NA).dropna().nunique():,}")
    cols[3].metric("Unique seller domains", f"{df['seller_domain'].replace('', pd.NA).dropna().nunique():,}")
    cols[4].metric("Unique sources", f"{df['source_name'].replace('', pd.NA).dropna().nunique():,}")


def render_search_tab(lookup: pd.DataFrame) -> None:
    search_text = st.text_area(
        "Search seller IDs, seller name, seller domain, source name, or sellers.json URL",
        placeholder="Paste one or many seller IDs, domains, names, sources, or URLs",
        height=120,
    )
    mode = st.selectbox(
        "Search mode",
        ["Auto", "Seller ID", "Seller Name", "Seller Domain", "Source Name", "Sellers.json URL"],
        index=0,
    )
    terms = parse_search_terms(search_text)

    with st.expander("Parsed search terms", expanded=False):
        st.write(f"{len(terms):,} parsed terms")
        if terms:
            st.dataframe(pd.DataFrame({"term": terms}), use_container_width=True, hide_index=True, height=220)
        else:
            st.caption("No search terms entered.")

    filtered = apply_search(lookup, terms, mode)
    render_result_kpis(filtered)

    seller_id_summary = group_by_seller_id(filtered)
    seller_domain_summary = group_by_seller_domain(filtered)

    st.subheader("Matching Seller Records")
    visible_columns = [column for column in DEFAULT_RESULT_COLUMNS if column in filtered.columns]
    st.dataframe(
        filtered[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "sellers_json_url": st.column_config.LinkColumn("sellers.json URL"),
            "seller_id": st.column_config.TextColumn("Seller ID"),
            "seller_name": st.column_config.TextColumn("Seller Name"),
            "seller_domain": st.column_config.TextColumn("Seller Domain"),
            "source_name": st.column_config.TextColumn("Source Name"),
            "seller_type": st.column_config.TextColumn("Seller Type"),
        },
    )
    download_csv(filtered[visible_columns], "filtered_seller_results.csv", "Download filtered seller results as CSV")

    advanced_columns = [
        column
        for column in filtered.columns
        if column not in visible_columns and not column.startswith("_")
    ]
    if advanced_columns:
        with st.expander("Advanced columns", expanded=False):
            st.dataframe(
                filtered[advanced_columns],
                use_container_width=True,
                hide_index=True,
                height=360,
            )

    st.subheader("Grouped Summaries")
    col_left, col_right = st.columns(2)
    with col_left:
        st.caption("Grouped by Seller ID")
        st.dataframe(seller_id_summary, use_container_width=True, hide_index=True, height=360)
        download_csv(seller_id_summary, "grouped_by_seller_id.csv", "Download grouped by seller ID as CSV")
    with col_right:
        st.caption("Grouped by Seller Domain")
        st.dataframe(seller_domain_summary, use_container_width=True, hide_index=True, height=360)
        download_csv(seller_domain_summary, "grouped_by_seller_domain.csv", "Download grouped by seller domain as CSV")


def render_source_health_tab(health: pd.DataFrame) -> None:
    st.subheader("Source Health")
    c1, c2, c3, c4, c5 = st.columns([1.4, 1.4, 1, 1, 1])
    source_query = c1.text_input("Source name contains", placeholder="e.g. lkqd", key="health_source")
    url_query = c2.text_input("URL contains", placeholder="e.g. sellers.json", key="health_url")
    fetch_success = c3.multiselect("Fetch success", ["True", "False"], key="health_fetch")
    parsed_success = c4.multiselect("Parsed success", ["True", "False"], key="health_parsed")
    http_status = c5.multiselect("HTTP status", unique_sorted(health["http_status_display"]), key="health_status")

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

    columns = [
        "source_name",
        "sellers_json_url",
        "http_status",
        "fetch_success",
        "parsed_success",
        "records_parsed",
        "error_message",
    ]
    if "last_scanned_at" in filtered.columns:
        columns.append("last_scanned_at")
    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        height=620,
        column_config={"sellers_json_url": st.column_config.LinkColumn("sellers.json URL")},
    )
    download_csv(filtered[columns], "filtered_source_health.csv", "Download filtered Source Health as CSV")


def render_data_export_tab() -> None:
    st.subheader("Data Export")
    export_files = [
        ("seller_lookup_dashboard.csv", DATA_FILES["lookup"]),
        ("seller_name_summary.csv", DATA_FILES["name_summary"]),
        ("seller_id_summary.csv", DATA_FILES["id_summary"]),
        ("seller_json_fetch_status.csv", DATA_FILES["health"]),
    ]

    available: list[tuple[str, Path, pd.DataFrame]] = []
    summary_rows: list[dict[str, object]] = []
    for filename, path in export_files:
        if not path.exists():
            summary_rows.append(
                {"file name": filename, "row count": "missing", "column count": "missing"}
            )
            continue
        df = load_csv(str(path), optional_file_signature(path))
        available.append((filename, path, df))
        summary_rows.append(
            {"file name": filename, "row count": len(df), "column count": len(df.columns)}
        )

    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    for filename, _path, df in available:
        st.download_button(
            f"Download {filename}",
            to_csv_download(df),
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )

    if available:
        preview_name = st.selectbox("Preview file", [filename for filename, _path, _df in available])
        preview_df = next(df for filename, _path, df in available if filename == preview_name)
        st.dataframe(preview_df.head(100), use_container_width=True, hide_index=True, height=420)


def main() -> None:
    st.title("Seller Lookup")
    st.caption("Search existing sellers.json records, review matches, and download filtered results.")

    signature = required_file_signature()
    lookup = load_seller_lookup(signature)
    health = load_source_health(signature)
    filtered_lookup = apply_sidebar_filters(lookup)

    tab_search, tab_health, tab_export = st.tabs(["Search", "Source Health", "Data Export"])
    with tab_search:
        render_search_tab(filtered_lookup)
    with tab_health:
        render_source_health_tab(health)
    with tab_export:
        render_data_export_tab()


if __name__ == "__main__":
    main()
