# Seller Lookup + Ads.txt Line QA

Streamlit dashboard for sellers.json lookup and Ads.txt line QA.

The dashboard is intentionally simple and focused on search:

1. Search exact seller IDs, seller names, seller domains, source names, sellers.json URLs, Ads.txt URLs, or Ads.txt line text.
2. Review matching sellers and Ads.txt QA records.
3. Export the filtered results as CSV.

The app does not fetch live sellers.json or Ads.txt files during page load. Streamlit reads prebuilt CSV files from this repository so the deployed dashboard stays fast and predictable.

## Dashboard Tabs

The app has exactly three tabs:

1. `Search`
2. `Ads.txt Line QA`
3. `Health / Export`

Removed UI:

- IVT / Media-Guard tabs and IVT metrics
- quick-search buttons and shortcut buttons
- advanced seller-column dropdown table

## Run

From the repository root:

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

The root `app.py` launches `Seller Lookup & IVT/app.py`, which keeps Streamlit Community Cloud deployment simple.

## Streamlit Community Cloud

Use these deployment settings:

```text
Repository: IronSide1904/Seller-Lookup
Branch: main
Main file path: app.py
```

Live app:

```text
https://sellerlookup.streamlit.app/
```

Streamlit Community Cloud may hibernate inactive apps. This repository includes a weekly data-refresh workflow and can also be monitored externally if always-on availability is required.

## Search

Search supports:

- exact seller IDs
- seller names
- seller domains
- source names
- sellers.json URLs
- Ads.txt URLs
- Ads.txt line text

Seller ID matching is exact. For example, searching `5093` matches seller ID `5093`, but does not match `3320-50938`.

Multiple terms can be pasted with commas, spaces, tabs, or new lines.

Example:

```text
1100057305, 159942, 5093, 557914189
```

## Ads.txt Line QA

The Ads.txt QA pipeline reads:

```text
Seller Lookup & IVT/Ads-txt and lines.xlsx
```

Workbook sheets used:

- `Publisher Ads.txt`
- `Publishers Seller ID Tracker`
- `SSP Seller ID Tracker`
- `Supply Line`
- `Priority`

Generated CSV outputs:

- `Seller Lookup & IVT/required_lines.csv`
- `Seller Lookup & IVT/ads_txt_sources.csv`
- `Seller Lookup & IVT/parsed_ads_txt_rows.csv`
- `Seller Lookup & IVT/ads_txt_line_qa.csv`
- `Seller Lookup & IVT/missing_lines_action_list.csv`
- `Seller Lookup & IVT/ads_txt_fetch_status.csv`

Rebuild command:

```powershell
python scripts/build_ads_txt_qa.py
```

Optional custom paths:

```powershell
python scripts/build_ads_txt_qa.py --workbook "C:\path\to\Ads-txt and lines.xlsx" --output-dir "Seller Lookup & IVT"
```

## QA Logic

Line families:

- `Dauup Authorization`
- `Partner Demand Enablement`
- `TBD`

Statuses:

- `Found`
- `Missing`
- `Partial`
- `Failed`
- `TBD`

Match levels:

- `Exact`
- `Partial`
- `Missing`
- `Fetch Failed`
- `TBD`

Publisher authorization rows are matched to relevant publisher Ads.txt URLs when the workbook name can be mapped to a domain. Partner demand enablement lines are checked across publisher Ads.txt URLs. SSP destination rows are checked against the sellers.json lookup table.

## Data Refresh

The weekly GitHub Actions workflow refreshes sellers.json data and pushes updated CSV files back to the repository. Streamlit redeploys automatically after GitHub receives the updated files.

Ads.txt QA data is rebuilt with:

```powershell
python scripts/build_ads_txt_qa.py
```

Then commit and push the generated CSV files so Streamlit serves the updated dashboard.
