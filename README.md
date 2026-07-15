# Seller-Lookup

Streamlit dashboard for seller lookup, seller-domain IVT, Media-Guard SChain review, and SChain seller ID blacklist analysis.

## Run

From the repository root:

```powershell
cd "Seller Lookup & IVT"
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8505
```

Open:

```text
http://localhost:8505
```

## Included Data

This repository includes the generated dashboard CSV/XLSX inputs needed by `Seller Lookup & IVT/app.py`, plus the sibling `resolved_schain_ivt/ivt_by_seller_domain_under_domain.csv` file expected by the Pre-Bid IVT tab.

## Notes

Large generated data files are committed because this dashboard is designed to run as a self-contained local package.
