# Seller-Lookup

Streamlit dashboard for seller lookup, seller-domain IVT, Media-Guard SChain review, and SChain seller ID blacklist analysis.

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

The root `app.py` launches `Seller Lookup & IVT/app.py` so Streamlit Community Cloud can use a simple entrypoint path.

## Streamlit Community Cloud

Use these deployment settings:

```text
Repository: IronSide1904/Seller-Lookup
Branch: main
Main file path: app.py
```

Dependencies are declared in the root `requirements.txt`.

## Weekly sellers.json Updates

The repository includes a GitHub Actions workflow:

```text
.github/workflows/weekly-sellers-json-update.yml
```

It runs every Wednesday at `03:00 UTC`, refetches every source listed in:

```text
Seller Lookup & IVT/seller_json_fetch_status.csv
```

Then it rebuilds and commits:

```text
Seller Lookup & IVT/seller_lookup_dashboard.csv
Seller Lookup & IVT/seller_json_fetch_status.csv
Seller Lookup & IVT/seller_name_summary.csv
Seller Lookup & IVT/seller_id_summary.csv
```

Because Streamlit Cloud deploys from `main`, every automatic commit should trigger a Streamlit redeploy for:

```text
https://sellerlookup.streamlit.app/
```

You can also trigger the update manually from GitHub:

```text
Actions -> Weekly sellers.json update -> Run workflow
```

## Included Data

This repository includes the generated dashboard CSV/XLSX inputs needed by `Seller Lookup & IVT/app.py`, plus the sibling `resolved_schain_ivt/ivt_by_seller_domain_under_domain.csv` file expected by the Pre-Bid IVT tab.

## Notes

Large generated data files are committed because this dashboard is designed to run as a self-contained local package.
