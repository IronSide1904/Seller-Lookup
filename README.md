# Seller Lookup

Simple Streamlit search dashboard for existing sellers.json records.

The dashboard is focused on one workflow:

1. Paste seller IDs, seller domains, seller names, source names, or sellers.json URLs.
2. Choose a search mode when needed.
3. Review matching seller records.
4. Download the filtered CSV results.

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

Live app:

```text
https://sellerlookup.streamlit.app/
```

Streamlit Community Cloud can hibernate inactive apps. This repository includes a keep-awake workflow, but Streamlit availability can still depend on Streamlit Cloud status, GitHub availability, and account/app limits.

## Search Examples

Single seller ID:

```text
34167
```

Multiple seller IDs:

```text
34167, 34197, 34114
```

Excel paste:

```text
34167	34197	34114
```

Domain search:

```text
zmaticoo.com
```

Source search:

```text
lkqd
```

Seller name search:

```text
Lacuna
```

## Search Modes

`Auto` searches across seller ID, seller name, seller domain, source name, and sellers.json URL.

`Seller ID` mode uses exact seller ID matching after trimming spaces. This is the best mode when pasting a column or row of seller IDs from Excel.

The other modes search one field with case-insensitive contains matching:

- `Seller Name`
- `Seller Domain`
- `Source Name`
- `Sellers.json URL`

Pasted terms can be separated by commas, spaces, new lines, tabs, semicolons, or pipes. Duplicate terms are removed while preserving order.

## Filters And Downloads

The sidebar keeps only simple lookup filters:

- Source name
- Seller type
- Seller domain contains
- Seller name contains
- Seller ID exact match

The Search tab includes:

- Matching seller records
- Match reason and matched terms
- Grouped summary by seller ID
- Grouped summary by seller domain
- CSV downloads for all filtered outputs

The Source Health tab reads `seller_json_fetch_status.csv`, shows source status KPIs, supports simple status filters, and downloads the filtered health table.

The Data Export tab lists available dashboard CSV files, shows row and column counts, and provides direct CSV download buttons.

## Data Files

Required:

```text
Seller Lookup & IVT/seller_lookup_dashboard.csv
Seller Lookup & IVT/seller_json_fetch_status.csv
```

Optional export files:

```text
Seller Lookup & IVT/seller_name_summary.csv
Seller Lookup & IVT/seller_id_summary.csv
```

The dashboard reads existing CSV files only. It does not refetch sellers.json URLs from the UI.

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
