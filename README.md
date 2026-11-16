# 🍷 Vintage WACC: International Cost of Capital App

A Streamlit app that compares a project's **cost of equity** and **WACC** in **USD** and in the currency of any selected country. It's themed as a Portuguese wine cellar with a rock soundtrack.

## Features
- **Live data, with sources and dates shown**
  - U.S. industry **unlevered betas**: Damodaran, `betas.xls` (*Unlevered beta* column)
  - **BBB USD spread**: Damodaran, `ratings.html` (Baa2/BBB, large non-financial service firms)
  - **Corporate tax rates**: OECD Corporate Tax Statistics (combined statutory CIT rate)
  - **10-year government yields**: Trading Economics `/bonds` (scraped, no API key)
- **🍾 Uncork fresh data** button clears the cache and re-fetches every source.
- Pick an **industry** and a **target country**, and adjust the **ERP** and **target debt share**.
- **Manual overrides** for the unlevered beta, U.S. and foreign tax rates, USD BBB spread, and both 10Y yields.
- **Foreign BBB spread**: auto-calculated by parity, or manual when switched on.
- **Tax switch**: apply either the U.S. or the selected country's rate to both currencies.
- Side-by-side results, an all-industry comparison, assumptions with formulas, and downloads (.xlsx and .csv).
- If a source can't be reached, the app uses a clearly labeled fallback snapshot so it still runs.

## Defaults
Software (System & Application) · United States · U.S. tax rate · ERP 6.5% · debt share 30%.

## Method
1. Relever the beta (Hamada): `βL = βU × [1 + (1 − τ) × d/(1 − d)]`
2. USD cost of equity (CAPM): `Re = Rf + βL × ERP`
3. USD pre-tax cost of debt: `Rd = Rf + BBB spread`
4. `WACC = (1 − d) Re + d Rd (1 − τ)`
5. Convert to foreign currency: `(1 + Re*) = (1 + Re)(1 + Rf*)/(1 + Rf)`. The same conversion gives `Rd*`, and the implied foreign spread is `Rd* − Rf*`.
6. `WACC* = (1 − d) Re* + d Rd* (1 − τ)`, using the same d, τ and ERP.

**Check:** with the United States selected, both columns are identical, as they should be.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (GitHub + Streamlit Community Cloud)
1. Create a new public GitHub repository, e.g. `international-wacc-app`.
2. Upload `app.py`, `requirements.txt` and `README.md`.
3. Go to https://share.streamlit.io, click **New app**, choose the repo, set the branch to `main` and the main file to `app.py`, then click **Deploy**.

## Notes
- The OECD page draws its chart with JavaScript, so the app tries the OECD SDMX data API first, then the page, and falls back to the 2024 OECD rates table.
- Trading Economics sometimes blocks cloud servers. If that happens, the app tries each country's own yield page and otherwise uses a labeled snapshot. You can always type yields in manually.
