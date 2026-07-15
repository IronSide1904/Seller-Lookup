# Seller Lookup Dashboard

Local Streamlit dashboard for looking up seller names and seller IDs across already-scanned `sellers.json` sources.

## Files

The dashboard reads these generated files from this folder:

- `seller_lookup_dashboard.csv`
- `seller_name_summary.csv`
- `seller_id_summary.csv`
- `seller_json_fetch_status.csv`

The Excel workbook is:

- `seller_lookup_dashboard.xlsx`

The app does not rescan live `sellers.json` URLs when it opens. It displays already-scanned results.

## Install

From this folder:

```bash
pip install -r requirements.txt
```

## Run The Scan Builder

If the seller lookup CSV files are missing, run the builder from the project root:

```bash
python work\build_seller_lookup_dashboard.py
```

This builds:

- `outputs\seller_lookup\seller_lookup_dashboard.csv`
- `outputs\seller_lookup\seller_name_summary.csv`
- `outputs\seller_lookup\seller_id_summary.csv`
- `outputs\seller_lookup\seller_json_fetch_status.csv`
- `outputs\seller_lookup\seller_lookup_dashboard.xlsx`

## Run The Dashboard

From this folder:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

On the same machine, open:

```text
http://localhost:8501
```

## Run The Simplified Search Dashboard

From this folder:

```bash
streamlit run app_simple.py --server.address 0.0.0.0 --server.port 8506
```

On the same machine, open:

```text
http://localhost:8506
```

On the same WiFi network, open:

```text
http://LOCAL_MACHINE_IP:8506
```

## Media-Guard Seller ID Blacklist

This dashboard includes Media-Guard Pre-Bid data for:

```text
11/06/2026 to 18/06/2026
```

The `Seller ID Blacklist` tab analyzes every seller ID inside `Summary Sampled SChain`, not only `Summary Sampled Publisher ID`.

Example:

```text
1.0,1!limpid.tv,102387,1,,,!smaato.com,1100046578,1,,,!dauup.com,34104,1,,,
```

This row contributes attributed requests and IVT to seller IDs:

```text
102387, 1100046578, 34104
```

The default blacklist rule is:

```text
weighted IVT > 10% and total requests > 1,000,000
```

Generated files:

- `media_guard_prebid_2026-06-11_to_2026-06-18_raw.csv`
- `media_guard_prebid_2026-06-11_to_2026-06-18_exploded_schain_nodes.csv`
- `media_guard_seller_id_summary.csv`
- `media_guard_seller_id_blacklist.csv`
- `MG IVT - SCHAIN.xlsx`

The default blacklist is aggregated by SChain seller ID. A row's requests and IVT are attributed to each seller ID node in that row's SChain. Weighted IVT is calculated as:

```text
sum(invalid traffic count) / sum(total requests)
```

The `MG IVT - SCHAIN` tab displays the source workbook and supports searching by seller name, seller domain, SChain text, or `Relevant Pub ID Before dauup.com`.

## Share On The Same WiFi

Start the app with:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Find the local machine IP address.

Windows:

```bash
ipconfig
```

Mac/Linux:

```bash
ifconfig
```

Other users on the same WiFi network can open:

```text
http://LOCAL_MACHINE_IP:8501
```

Example:

```text
http://192.168.1.25:8501
```

This dashboard is intended for local network use only. Do not expose it directly to the public internet.

## Example Workflow

To check where Lacuna appears and which seller ID it has under each `sellers.json` source, open the `Seller Lookup` tab and search:

```text
Lacuna
```

To check where seller ID `34167` appears, search:

```text
34167
```

The main table shows:

- source name
- sellers.json URL
- seller name as written in that source
- Seller Domain
- seller ID used in that source
- match reason

The sidebar includes `Seller Domain` filters, both as a contains search and as a dropdown, so you can quickly narrow results to domains such as `lacunads.com` or `pubmatic.com`.

Use the `Seller Name Summary`, `Seller ID Summary`, and `Source Health` tabs for grouped lookup and fetch status.
