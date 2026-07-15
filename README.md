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

## Included Data

This repository includes the generated dashboard CSV/XLSX inputs needed by `Seller Lookup & IVT/app.py`, plus the sibling `resolved_schain_ivt/ivt_by_seller_domain_under_domain.csv` file expected by the Pre-Bid IVT tab.

## Notes

Large generated data files are committed because this dashboard is designed to run as a self-contained local package.
