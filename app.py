"""
Vintage WACC: The International Cost of Capital Cellar
------------------------------------------------------
Streamlit app comparing a project's cost of equity and WACC in USD and in the
currency of any selected country.

Formulas (from class):
    WACC              = (1 - d) * Re + d * Rd * (1 - tau)
    (1 + Re*)         = (1 + Re) * (1 + Rf*) / (1 + Rf)
Same conversion is applied to the pre-tax cost of debt to get Rd*.

Data sources (fetched live, with labeled fallbacks):
    Unlevered industry betas  - Damodaran, betas.xls (U.S.)
    BBB USD spread            - Damodaran, ratings.html (Baa2/BBB, large non-financial firms)
    Corporate tax rates       - OECD Corporate Tax Statistics (combined statutory CIT rate)
    10-year government yields - Trading Economics
"""

import io
import re
import datetime as dt

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Page setup & theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Vintage WACC · International Cost of Capital",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="expanded",
)

PORT = "#6D1A36"        # Port wine
DOURO = "#9E2A4A"       # Douro red
GOLD = "#C9A227"        # Tawny / gold
AZUL = "#1F4E9A"        # Azulejo blue
CREAM = "#FBF7F0"
INK = "#2B1B20"

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;800&family=Inter:wght@400;600&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
h1, h2, h3, h4 {{ font-family: 'Playfair Display', serif !important; color: {PORT}; }}
.hero {{
  position: relative; border-radius: 18px; padding: 28px 32px; margin-bottom: 18px;
  color: white; overflow: hidden;
  background: linear-gradient(120deg, {PORT} 0%, {DOURO} 55%, #3a0d1f 100%);
  box-shadow: 0 10px 30px rgba(109,26,54,.25);
}}
.hero:after {{
  content: ""; position: absolute; right: 0; top: 0; bottom: 0; width: 34%;
  opacity: .18;
  background:
    radial-gradient(circle at 50% 50%, transparent 38%, white 39%, white 43%, transparent 44%) 0 0/48px 48px,
    linear-gradient(45deg, transparent 46%, white 47%, white 53%, transparent 54%) 0 0/48px 48px,
    linear-gradient(-45deg, transparent 46%, white 47%, white 53%, transparent 54%) 0 0/48px 48px;
}}
@media (max-width: 760px) {{ .hero-icons {{ display:none !important; }} .hero p {{ max-width:100%; }} }}
.hero h1 {{ color: white !important; margin: 0; font-size: 2.3rem; }}
.hero p {{ max-width: 62%; margin: 6px 0 0 0; opacity: .92; font-size: 1.02rem; }}
.hero .tag {{ display:inline-block; margin-top:12px; padding:4px 12px; border-radius:999px;
  background: rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.3); font-size:.82rem; }}
.card {{
  background: white; border-radius: 16px; padding: 18px 22px; border: 1px solid #eadfd3;
  border-top: 6px solid {PORT}; box-shadow: 0 4px 16px rgba(43,27,32,.06); height: 100%;
}}
.card.foreign {{ border-top-color: {AZUL}; }}
.card h3 {{ margin: 0 0 4px 0; }}
.card .sub {{ color:#7a6a6f; font-size:.86rem; margin-bottom: 10px; }}
.row {{ display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #eee; }}
.row span:last-child {{ font-weight:600; color:{INK}; }}
.big {{ font-family:'Playfair Display',serif; font-size:2.4rem; font-weight:800; color:{PORT}; line-height:1.1; }}
.card.foreign .big {{ color:{AZUL}; }}
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600; }}
.pill.live {{ background:#e5f4ea; color:#1d6b3a; }}
.pill.fallback {{ background:#fdf0d8; color:#8a5a00; }}
.pill.manual {{ background:#e6ecf8; color:{AZUL}; }}
.pairing {{
  border-radius: 14px; padding: 14px 18px; margin-top: 14px;
  background: linear-gradient(90deg, #fff7ea, #fbeef1); border: 1px solid #f0dcc4;
}}
.footer {{ text-align:center; color:#8b7a7f; font-size:.85rem; margin-top: 30px; }}
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #fbf3ef 0%, #f6ece6 100%); }}
div.stButton > button, div.stDownloadButton > button {{
  border-radius: 999px; border: 1px solid {PORT}; color: {PORT}; font-weight: 600;
}}
div.stButton > button:hover, div.stDownloadButton > button:hover {{ background:{PORT}; color:white; }}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Icons (hand-drawn inline SVG: wine glass, wine bottle, electric guitar)
# ---------------------------------------------------------------------------
def wine_glass_svg(size=28, color="#FFFFFF", wine="#C9184A"):
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"
 style="vertical-align:middle"><path d="M18 6h28c1 12-2 24-14 26C20 30 17 18 18 6z" fill="none"
 stroke="{color}" stroke-width="3"/><path d="M19.5 16h25c-1 8-4 13-12.5 14C24 29 20.5 24 19.5 16z" fill="{wine}"/>
 <path d="M32 32v20M22 58h20" stroke="{color}" stroke-width="3" stroke-linecap="round"/></svg>"""


def wine_bottle_svg(size=28, color="#FFFFFF", label="#C9A227"):
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"
 style="vertical-align:middle"><path d="M27 4h10v14c0 4 7 7 7 15v25c0 2-1 3-3 3H23c-2 0-3-1-3-3V33c0-8 7-11 7-15z"
 fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/><rect x="23" y="36" width="18" height="14"
 rx="2" fill="{label}"/><rect x="27" y="4" width="10" height="5" fill="{color}"/></svg>"""


def guitar_svg(size=28, color="#FFFFFF", body="#C9A227"):
    """Generic solid-body electric guitar (not modeled on any brand)."""
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"
 style="vertical-align:middle"><g transform="rotate(45 32 32)">
 <path d="M30 40 C28 36 26 30 21 28 C17 27 16 33 18 38 C14 42 13 50 17 55 C21 60 28 61 33 60
 C40 60 47 57 48 50 C49 45 46 42 45 39 C47 35 47 31 44 30 C40 29 37 35 35 40 Z"
 fill="{body}" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>
 <rect x="30" y="5" width="4" height="38" fill="{color}"/>
 <path d="M28 1 h8 l1 8 h-10 z" fill="{color}"/>
 <rect x="26" y="43" width="12" height="2.6" rx="1" fill="{color}"/>
 <rect x="26" y="48.5" width="12" height="2.6" rx="1" fill="{color}"/>
 <rect x="27" y="54" width="10" height="2" rx="1" fill="{color}"/>
 <circle cx="42" cy="51" r="1.7" fill="{color}"/><circle cx="41" cy="56" r="1.7" fill="{color}"/>
</g></svg>"""


def divider(n=7):
    """A row alternating wine glasses and guitars, used between sections."""
    icons = []
    for i in range(n):
        icons.append(wine_glass_svg(22, PORT, DOURO) if i % 2 == 0 else guitar_svg(22, PORT, GOLD))
    return (f"<div style='display:flex;align-items:center;gap:10px;margin:18px 0'>"
            f"<div style='flex:1;height:1px;background:#e3d3c7'></div>{''.join(icons)}"
            f"<div style='flex:1;height:1px;background:#e3d3c7'></div></div>")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URLS = [
    "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html",
    "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html",
]
OECD_URL = (
    "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
    "full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb"
)
OECD_SDMX_URL = (
    "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,/all"
    "?startPeriod=2020&dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
)
TE_URL = "https://tradingeconomics.com/bonds"
TE_COUNTRY_URL = "https://tradingeconomics.com/{slug}/government-bond-yield"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"

# ---------------------------------------------------------------------------
# Country metadata (flag + currency) and name harmonization
# ---------------------------------------------------------------------------
COUNTRY_META = {
    "United States": ("US", "USD"), "Portugal": ("PT", "EUR"), "Germany": ("DE", "EUR"),
    "France": ("FR", "EUR"), "Italy": ("IT", "EUR"), "Spain": ("ES", "EUR"),
    "Netherlands": ("NL", "EUR"), "Belgium": ("BE", "EUR"), "Austria": ("AT", "EUR"),
    "Ireland": ("IE", "EUR"), "Greece": ("GR", "EUR"), "Finland": ("FI", "EUR"),
    "Slovakia": ("SK", "EUR"), "Slovenia": ("SI", "EUR"), "Lithuania": ("LT", "EUR"),
    "Latvia": ("LV", "EUR"), "Estonia": ("EE", "EUR"), "Luxembourg": ("LU", "EUR"),
    "Croatia": ("HR", "EUR"), "Cyprus": ("CY", "EUR"), "Malta": ("MT", "EUR"),
    "United Kingdom": ("GB", "GBP"), "Switzerland": ("CH", "CHF"), "Norway": ("NO", "NOK"),
    "Sweden": ("SE", "SEK"), "Denmark": ("DK", "DKK"), "Iceland": ("IS", "ISK"),
    "Poland": ("PL", "PLN"), "Czech Republic": ("CZ", "CZK"), "Hungary": ("HU", "HUF"),
    "Romania": ("RO", "RON"), "Bulgaria": ("BG", "BGN"), "Serbia": ("RS", "RSD"),
    "Turkey": ("TR", "TRY"), "Russia": ("RU", "RUB"), "Ukraine": ("UA", "UAH"),
    "Canada": ("CA", "CAD"), "Mexico": ("MX", "MXN"), "Brazil": ("BR", "BRL"),
    "Argentina": ("AR", "ARS"), "Chile": ("CL", "CLP"), "Colombia": ("CO", "COP"),
    "Peru": ("PE", "PEN"), "Costa Rica": ("CR", "CRC"), "Japan": ("JP", "JPY"),
    "China": ("CN", "CNY"), "Hong Kong": ("HK", "HKD"), "South Korea": ("KR", "KRW"),
    "Taiwan": ("TW", "TWD"), "India": ("IN", "INR"), "Indonesia": ("ID", "IDR"),
    "Malaysia": ("MY", "MYR"), "Philippines": ("PH", "PHP"), "Singapore": ("SG", "SGD"),
    "Thailand": ("TH", "THB"), "Vietnam": ("VN", "VND"), "Pakistan": ("PK", "PKR"),
    "Bangladesh": ("BD", "BDT"), "Sri Lanka": ("LK", "LKR"), "Australia": ("AU", "AUD"),
    "New Zealand": ("NZ", "NZD"), "Israel": ("IL", "ILS"), "Saudi Arabia": ("SA", "SAR"),
    "Qatar": ("QA", "QAR"), "United Arab Emirates": ("AE", "AED"), "Egypt": ("EG", "EGP"),
    "South Africa": ("ZA", "ZAR"), "Nigeria": ("NG", "NGN"), "Kenya": ("KE", "KES"),
    "Morocco": ("MA", "MAD"), "Namibia": ("NA", "NAD"), "Botswana": ("BW", "BWP"),
    "Uganda": ("UG", "UGX"), "Zambia": ("ZM", "ZMW"), "Mauritius": ("MU", "MUR"),
    "Kazakhstan": ("KZ", "KZT"), "Jordan": ("JO", "JOD"), "Bahrain": ("BH", "BHD"),
}

ALIASES = {
    "US": "United States", "U.S.": "United States", "USA": "United States",
    "United States of America": "United States", "UK": "United Kingdom",
    "Britain": "United Kingdom", "Great Britain": "United Kingdom",
    "Korea": "South Korea", "Republic of Korea": "South Korea", "Korea, Republic of": "South Korea",
    "Czechia": "Czech Republic", "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Slovak Republic": "Slovakia", "China (People's Republic of)": "China",
    "People's Republic of China": "China", "Hong Kong, China": "Hong Kong",
    "Hong Kong (China)": "Hong Kong", "Russian Federation": "Russia", "Viet Nam": "Vietnam",
    "Chinese Taipei": "Taiwan", "UAE": "United Arab Emirates",
}


def norm_country(name: str) -> str:
    n = re.sub(r"\s+", " ", str(name)).strip()
    n = re.sub(r"\s*\d+\s*Y(ear)?$", "", n, flags=re.I).strip()  # drop "10Y"
    return ALIASES.get(n, n)


def flag(country: str) -> str:
    iso = COUNTRY_META.get(country, (None, None))[0]
    if not iso:
        return "🏳️"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)


def ccy(country: str) -> str:
    return COUNTRY_META.get(country, (None, "LCY"))[1]


# ---------------------------------------------------------------------------
# Fallback snapshots (used only if live fetch fails; clearly labeled in the UI)
# ---------------------------------------------------------------------------
FALLBACK_BETAS = {
    "Advertising": 0.86, "Aerospace/Defense": 0.86, "Air Transport": 0.61,
    "Apparel": 0.84, "Auto & Truck": 1.25, "Auto Parts": 0.89,
    "Bank (Money Center)": 0.38, "Banks (Regional)": 0.36, "Beverage (Alcoholic)": 0.68,
    "Beverage (Soft)": 0.62, "Broadcasting": 0.45, "Brokerage & Investment Banking": 0.43,
    "Building Materials": 0.93, "Business & Consumer Services": 0.85,
    "Cable TV": 0.53, "Chemical (Basic)": 0.73, "Chemical (Diversified)": 0.79,
    "Chemical (Specialty)": 0.82, "Coal & Related Energy": 0.95,
    "Computer Services": 0.92, "Computers/Peripherals": 1.13,
    "Construction Supplies": 0.94, "Diversified": 0.80, "Drugs (Biotechnology)": 1.10,
    "Drugs (Pharmaceutical)": 0.87, "Education": 0.85, "Electrical Equipment": 1.01,
    "Electronics (Consumer & Office)": 0.97, "Electronics (General)": 0.94,
    "Engineering/Construction": 0.93, "Entertainment": 0.92,
    "Environmental & Waste Services": 0.77, "Farming/Agriculture": 0.74,
    "Financial Svcs. (Non-bank & Insurance)": 0.24, "Food Processing": 0.53,
    "Food Wholesalers": 0.65, "Furn/Home Furnishings": 0.83, "Green & Renewable Energy": 0.51,
    "Healthcare Products": 0.92, "Healthcare Support Services": 0.75,
    "Heathcare Information and Technology": 1.07, "Homebuilding": 0.95,
    "Hospitals/Healthcare Facilities": 0.60, "Hotel/Gaming": 0.82,
    "Household Products": 0.73, "Information Services": 0.87, "Insurance (General)": 0.63,
    "Insurance (Life)": 0.42, "Insurance (Prop/Cas.)": 0.56, "Investments & Asset Management": 0.55,
    "Machinery": 0.93, "Metals & Mining": 0.93, "Office Equipment & Services": 0.83,
    "Oil/Gas (Integrated)": 0.79, "Oil/Gas (Production and Exploration)": 0.80,
    "Oil/Gas Distribution": 0.60, "Oilfield Svcs/Equip.": 0.86, "Packaging & Container": 0.68,
    "Paper/Forest Products": 0.75, "Power": 0.42, "Precious Metals": 0.99,
    "Publishing & Newspapers": 0.62, "R.E.I.T.": 0.58, "Real Estate (Development)": 0.67,
    "Real Estate (General/Diversified)": 0.69, "Real Estate (Operations & Services)": 0.79,
    "Recreation": 0.92, "Reinsurance": 0.48, "Restaurant/Dining": 0.82,
    "Retail (Automotive)": 0.95, "Retail (Building Supply)": 1.07, "Retail (Distributors)": 0.80,
    "Retail (General)": 0.87, "Retail (Grocery and Food)": 0.42, "Retail (REITs)": 0.62,
    "Retail (Special Lines)": 0.88, "Rubber& Tires": 0.66, "Semiconductor": 1.39,
    "Semiconductor Equip": 1.30, "Shipbuilding & Marine": 0.62, "Shoe": 1.07,
    "Software (Entertainment)": 1.09, "Software (Internet)": 1.43,
    "Software (System & Application)": 1.24, "Steel": 0.92, "Telecom (Wireless)": 0.53,
    "Telecom. Equipment": 0.97, "Telecom. Services": 0.48, "Tobacco": 0.68,
    "Transportation": 0.79, "Transportation (Railroads)": 0.79, "Trucking": 0.93,
    "Utility (General)": 0.37, "Utility (Water)": 0.50, "Total Market": 0.80,
}

FALLBACK_SPREAD = 0.0111   # Baa2/BBB, large non-financial firms (Damodaran, Jan-2025 table)

# OECD Corporate Tax Statistics 2024, combined (central + sub-central) statutory CIT rates, 2024
FALLBACK_TAX = {
    "United States": 25.8, "Portugal": 31.5, "Germany": 29.9, "France": 25.8, "Italy": 27.8,
    "Spain": 25.0, "Netherlands": 25.8, "Belgium": 25.0, "Austria": 23.0, "Ireland": 12.5,
    "Greece": 22.0, "Finland": 20.0, "Slovakia": 21.0, "Slovenia": 22.0, "Lithuania": 15.0,
    "Latvia": 20.0, "Estonia": 20.0, "Luxembourg": 24.9, "Croatia": 18.0, "Cyprus": 12.5,
    "Malta": 35.0, "United Kingdom": 25.0, "Switzerland": 19.6, "Norway": 22.0, "Sweden": 20.6,
    "Denmark": 22.0, "Iceland": 21.0, "Poland": 19.0, "Czech Republic": 21.0, "Hungary": 9.0,
    "Romania": 16.0, "Bulgaria": 10.0, "Turkey": 25.0, "Canada": 26.1, "Mexico": 30.0,
    "Brazil": 34.0, "Argentina": 35.0, "Chile": 27.0, "Colombia": 35.0, "Peru": 29.5,
    "Costa Rica": 30.0, "Japan": 29.7, "China": 25.0, "Hong Kong": 16.5, "South Korea": 26.4,
    "India": 25.2, "Indonesia": 22.0, "Malaysia": 24.0, "Philippines": 25.0, "Singapore": 17.0,
    "Thailand": 20.0, "Vietnam": 20.0, "Australia": 30.0, "New Zealand": 28.0, "Israel": 23.0,
    "Saudi Arabia": 20.0, "South Africa": 27.0, "Nigeria": 30.0, "Kenya": 30.0, "Egypt": 22.5,
    "Morocco": 31.0, "Russia": 20.0, "Kazakhstan": 20.0, "Pakistan": 29.0, "Sri Lanka": 30.0,
    "Botswana": 22.0, "Namibia": 30.0, "Uganda": 30.0, "Zambia": 30.0, "Mauritius": 15.0,
    "Qatar": 10.0, "United Arab Emirates": 9.0, "Jordan": 20.0, "Bahrain": 0.0,
    "Taiwan": 20.0, "Serbia": 15.0, "Ukraine": 18.0, "Bangladesh": 27.5,
}

# Illustrative 10Y yields (%) used only if Trading Economics cannot be reached
FALLBACK_YIELDS = {
    "United States": 4.15, "Portugal": 3.05, "Germany": 2.60, "France": 3.40, "Italy": 3.55,
    "Spain": 3.20, "Netherlands": 2.85, "Belgium": 3.20, "Austria": 3.00, "Ireland": 2.90,
    "Greece": 3.35, "Finland": 2.95, "United Kingdom": 4.55, "Switzerland": 0.40,
    "Norway": 4.00, "Sweden": 2.45, "Denmark": 2.40, "Poland": 5.50, "Czech Republic": 4.30,
    "Hungary": 6.80, "Romania": 7.20, "Turkey": 30.0, "Russia": 14.5, "Canada": 3.30,
    "Mexico": 9.00, "Brazil": 13.6, "Chile": 5.50, "Colombia": 11.2, "Peru": 6.40,
    "Japan": 1.70, "China": 1.80, "Hong Kong": 3.20, "South Korea": 3.00, "India": 6.40,
    "Indonesia": 6.60, "Malaysia": 3.50, "Philippines": 6.20, "Singapore": 2.30,
    "Thailand": 1.80, "Vietnam": 3.20, "Australia": 4.40, "New Zealand": 4.50,
    "Israel": 4.30, "South Africa": 9.80, "Nigeria": 17.0, "Kenya": 13.5, "Egypt": 22.0,
}


def _now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _get(url, timeout=25):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def _pct(x):
    """Parse '1.59%' / 1.59 / 0.0159 into a decimal."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).replace("%", "").replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return np.nan
    return v / 100.0


# ---------------------------------------------------------------------------
# Live fetchers (cached; "Uncork fresh data" clears the cache)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_betas():
    try:
        r = _get(BETAS_URL)
        book = pd.read_excel(io.BytesIO(r.content), sheet_name=None, header=None, engine="xlrd")
        sheet = None
        for name, df in book.items():
            if "industry" in name.lower() and "average" in name.lower():
                sheet = df
                break
        if sheet is None:
            sheet = next(iter(book.values()))
        hdr = None
        for i in range(min(40, len(sheet))):
            vals = [str(v).strip() for v in sheet.iloc[i].tolist()]
            if "Industry Name" in vals:
                hdr = i
                break
        if hdr is None:
            raise ValueError("Header 'Industry Name' not found")
        cols = [str(c).strip() for c in sheet.iloc[hdr].tolist()]
        df = sheet.iloc[hdr + 1:].copy()
        df.columns = cols
        ub_col = next(c for c in cols if c.lower() == "unlevered beta")
        out = df[["Industry Name", ub_col]].rename(columns={ub_col: "Unlevered beta"})
        out["Unlevered beta"] = pd.to_numeric(out["Unlevered beta"], errors="coerce")
        out = out.dropna()
        out["Industry Name"] = out["Industry Name"].astype(str).str.strip()
        out = out[out["Industry Name"] != ""].reset_index(drop=True)

        # Data date: look for "Date updated" in the top rows
        date_str = "see file header"
        for i in range(hdr):
            row = sheet.iloc[i].tolist()
            for j, v in enumerate(row):
                if "date" in str(v).lower() and "updat" in str(v).lower():
                    for w in row[j + 1:]:
                        if pd.notna(w) and str(w).strip():
                            d = pd.to_datetime(w, errors="coerce")
                            date_str = d.strftime("%b %d, %Y") if pd.notna(d) else str(w)
                            break
        return {"df": out, "status": "Live", "date": date_str, "fetched": _now(), "error": None}
    except Exception as e:  # noqa: BLE001
        df = pd.DataFrame(sorted(FALLBACK_BETAS.items()), columns=["Industry Name", "Unlevered beta"])
        return {"df": df, "status": "Fallback", "date": "Jan 2025 snapshot", "fetched": _now(),
                "error": f"{type(e).__name__}: {e}"}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_bbb_spread():
    err = None
    for url in RATINGS_URLS:
        try:
            r = _get(url)
            html = r.text
            tables = pd.read_html(io.StringIO(html))
            spread = None
            for t in tables:  # first table = large non-financial service firms
                for _, row in t.astype(str).iterrows():
                    cells = [c.strip() for c in row.tolist()]
                    if any(re.search(r"Baa2\s*/\s*BBB", c) for c in cells):
                        pcts = [c for c in cells if "%" in c]
                        cand = pcts[-1] if pcts else cells[-1]
                        spread = _pct(cand)
                        break
                if spread is not None and not np.isnan(spread):
                    break
            if spread is None or np.isnan(spread):
                raise ValueError("Baa2/BBB row not found")
            text = BeautifulSoup(html, "html.parser").get_text(" ")
            m = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|"
                r"November|December)\s+(20\d\d)", text)
            date_str = f"{m.group(1)} {m.group(2)}" if m else "see page"
            return {"value": spread, "status": "Live", "date": date_str, "fetched": _now(),
                    "error": None, "url": url}
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
    return {"value": FALLBACK_SPREAD, "status": "Fallback", "date": "Jan 2025 snapshot",
            "fetched": _now(), "error": err, "url": RATINGS_URLS[0]}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_tax_rates():
    """Try the OECD SDMX API, then the publication page; else the OECD 2024 snapshot."""
    errors = []
    # 1) OECD Data Explorer (SDMX) - combined statutory CIT rate
    try:
        r = _get(OECD_SDMX_URL, timeout=40)
        df = pd.read_csv(io.StringIO(r.text))
        label_cols = [c for c in df.columns if df[c].dtype == object]
        mask = np.zeros(len(df), dtype=bool)
        for c in label_cols:
            mask |= df[c].astype(str).str.contains("combined", case=False, na=False)
        sub = df[mask].copy()
        area_col = next(c for c in df.columns if "reference area" in c.lower())
        sub = sub.dropna(subset=["OBS_VALUE"])
        sub["TIME_PERIOD"] = pd.to_numeric(sub["TIME_PERIOD"], errors="coerce")
        latest = sub.sort_values("TIME_PERIOD").groupby(area_col).tail(1)
        rates = {norm_country(a): float(v) for a, v in zip(latest[area_col], latest["OBS_VALUE"])}
        if len(rates) < 20:
            raise ValueError("Too few countries parsed")
        year = int(latest["TIME_PERIOD"].max())
        return {"rates": rates, "status": "Live", "date": f"{year} statutory rates",
                "fetched": _now(), "error": None}
    except Exception as e:  # noqa: BLE001
        errors.append(f"SDMX {type(e).__name__}: {e}")
    # 2) Publication page HTML tables
    try:
        r = _get(OECD_URL)
        tables = pd.read_html(io.StringIO(r.text))
        rates = {}
        for t in tables:
            t = t.copy()
            t.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
            name_col = t.columns[0]
            num_cols = [c for c in t.columns[1:] if pd.to_numeric(t[c], errors="coerce").notna().mean() > .6]
            if not num_cols:
                continue
            col = num_cols[-1]
            for n, v in zip(t[name_col], pd.to_numeric(t[col], errors="coerce")):
                if pd.notna(v) and 0 <= v <= 60:
                    rates[norm_country(n)] = float(v)
        if len(rates) < 20:
            raise ValueError("No usable rate table on page (chart is rendered by JavaScript)")
        return {"rates": rates, "status": "Live", "date": "2024 publication", "fetched": _now(),
                "error": None}
    except Exception as e:  # noqa: BLE001
        errors.append(f"Page {type(e).__name__}: {e}")
    return {"rates": dict(FALLBACK_TAX), "status": "Fallback",
            "date": "2024 rates (OECD Corporate Tax Statistics 2024)", "fetched": _now(),
            "error": " | ".join(errors)}


def _get_te(url, timeout=25):
    """Fetch a Trading Economics page. Plain requests first; if TE's bot protection refuses it,
    retry with curl_cffi, which presents a real Chrome TLS fingerprint."""
    errs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 5000:
            return r.text, "requests"
        errs.append(f"requests HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        errs.append(f"requests {type(e).__name__}")
    try:
        from curl_cffi import requests as creq
        r = creq.get(url, impersonate="chrome", timeout=timeout,
                     headers={"Accept-Language": "en-US,en;q=0.9"})
        if r.status_code == 200:
            return r.text, "curl_cffi"
        errs.append(f"curl_cffi HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        errs.append(f"curl_cffi {type(e).__name__}: {e}")
    raise RuntimeError("; ".join(errs))


def _parse_te_bonds(html):
    """Return {country: yield_decimal} and {country: quote_date} from the /bonds page HTML."""
    rows, dates = {}, {}
    # A) pandas over every table that has a 'Yield' column
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        tables = []
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        t.columns = cols
        ycol = next((c for c in cols if c.lower() == "yield"), None)
        if ycol is None:
            continue
        name_col = next((c for c in cols if t[c].dtype == object and c != ycol), None)
        if name_col is None:
            continue
        dcol = next((c for c in cols if c.lower() == "date"), None)
        for _, row in t.iterrows():
            name = norm_country(row[name_col])
            y = pd.to_numeric(str(row[ycol]).replace("%", ""), errors="coerce")
            if name and name.lower() != "nan" and pd.notna(y) and name not in rows:
                rows[name] = float(y) / 100.0
                dates[name] = str(row[dcol]) if dcol else ""
    # B) raw <tr> rows: a cell ending in '10Y' or a country name, followed by a number
    if len(rows) < 10:
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.select("tr"):
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            tds = [x for x in tds if x]
            if len(tds) < 2:
                continue
            name = norm_country(tds[0])
            y = pd.to_numeric(tds[1].replace("%", ""), errors="coerce")
            if name and pd.notna(y) and name not in rows and not name[0].isdigit():
                rows[name] = float(y) / 100.0
                dates[name] = tds[-1]
    return rows, dates


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yields():
    """Single source for all countries: tradingeconomics.com/bonds."""
    try:
        html, via = _get_te(TE_URL)
        rows, dates = _parse_te_bonds(html)
        if len(rows) < 10:
            raise ValueError(
                f"Page downloaded via {via} ({len(html):,} chars) but the bond table was not in the "
                "HTML (TE may be filling it with JavaScript for this server)")
        return {"yields": rows, "quote_dates": dates, "status": "Live",
                "date": f"Quotes as of {dt.date.today():%b %d, %Y}", "fetched": _now(),
                "error": None, "via": via}
    except Exception as e:  # noqa: BLE001
        return {"yields": {k: v / 100 for k, v in FALLBACK_YIELDS.items()}, "quote_dates": {},
                "status": "Fallback", "date": "Illustrative snapshot (not market data)",
                "fetched": _now(), "error": f"{type(e).__name__}: {e}", "via": None}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_country_yield(country: str):
    """Primary source for the two yields the model uses: each country's own Trading Economics
    page. Unlike /bonds (whose table is filled by JavaScript), these pages state the latest
    quote in plain text, e.g. 'The yield on Belgium 10Y Bond Yield rose to 3.15% on
    February 19, 2026'."""
    slug = re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")
    url = TE_COUNTRY_URL.format(slug=slug)
    try:
        html, _ = _get_te(url)
        soup = BeautifulSoup(html, "html.parser")
        texts = []
        for attrs in ({"name": "description"}, {"property": "og:description"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content"):
                texts.append(m["content"])
        texts.append(soup.get_text(" "))
        pat_full = re.compile(
            r"(?:rose|fell|increased|decreased|declined|climbed|was|edged up|edged down|held|"
            r"remained|stood|steady)\s+(?:to|at)?\s*(-?\d+(?:\.\d+)?)%\s+on\s+"
            r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})")
        for t in texts:
            m = pat_full.search(t)
            if m:
                return {"value": float(m.group(1)) / 100.0, "date": m.group(2), "status": "Live",
                        "url": url, "error": None, "fetched": _now()}
        for t in texts:
            m = re.search(r"(?:yield|Yield)[^%]{0,80}?(-?\d+\.\d+)%", t)
            if m:
                return {"value": float(m.group(1)) / 100.0, "date": "latest quote", "status": "Live",
                        "url": url, "error": None, "fetched": _now()}
        raise ValueError("Yield not found on country page")
    except Exception as e:  # noqa: BLE001
        return {"value": None, "date": None, "status": "Failed", "url": url,
                "error": f"{type(e).__name__}: {e}", "fetched": _now()}


# ---------------------------------------------------------------------------
# Core finance
# ---------------------------------------------------------------------------
def cost_of_capital(beta_u, erp, d, tax, rf_us, rf_f, spread_us, spread_f_override=None):
    """All inputs in decimals. Returns a dict of USD and foreign-currency results."""
    de = d / (1 - d)
    beta_l = beta_u * (1 + (1 - tax) * de)                 # Hamada relevering
    re_us = rf_us + beta_l * erp                           # CAPM in USD
    rd_us = rf_us + spread_us                              # pre-tax USD cost of debt
    conv = (1 + rf_f) / (1 + rf_us)                        # interest-rate-parity factor
    re_f = (1 + re_us) * conv - 1                          # (1+Re*) = (1+Re)(1+Rf*)/(1+Rf)
    rd_f_auto = (1 + rd_us) * conv - 1
    spread_f_auto = rd_f_auto - rf_f
    if spread_f_override is None:
        rd_f, spread_f = rd_f_auto, spread_f_auto
    else:
        spread_f = spread_f_override
        rd_f = rf_f + spread_f
    wacc_us = (1 - d) * re_us + d * rd_us * (1 - tax)
    wacc_f = (1 - d) * re_f + d * rd_f * (1 - tax)
    return {
        "beta_l": beta_l, "de": de, "conv": conv,
        "re_us": re_us, "rd_us": rd_us, "rd_us_at": rd_us * (1 - tax), "wacc_us": wacc_us,
        "re_f": re_f, "rd_f": rd_f, "rd_f_at": rd_f * (1 - tax), "wacc_f": wacc_f,
        "spread_f": spread_f, "spread_f_auto": spread_f_auto,
    }


def wine_pairing(wacc):
    if wacc < 0.06:
        return "🥂 **Vinho Verde**: light, fresh and low hurdle. Easy-drinking projects clear this bar."
    if wacc < 0.08:
        return "🍷 **Douro DOC red**: balanced structure, moderate tannins, a classic hurdle rate."
    if wacc < 0.10:
        return "🍷 **Alentejo Reserva**: fuller-bodied. Projects need some real fruit to justify it."
    if wacc < 0.14:
        return "🍇 **LBV Port**: rich and demanding. Only robust cash flows pair with this."
    return "🏺 **Vintage Port**: intense, and it takes decades to pay off. Proceed with caution."


def fmt(x, nd=2):
    return f"{x * 100:.{nd}f}%"


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"<h2>{wine_glass_svg(30, PORT, DOURO)} The Tasting Menu</h2>"
                f"<div style='margin:-6px 0 10px 0'>{guitar_svg(22, PORT, GOLD)} {wine_bottle_svg(22, PORT, GOLD)} "
                f"{guitar_svg(22, PORT, GOLD)} {wine_bottle_svg(22, PORT, GOLD)} {guitar_svg(22, PORT, GOLD)}</div>",
                unsafe_allow_html=True)
    if st.button("🍾 Uncork fresh data", use_container_width=True,
                 help="Clear the cache and re-fetch every source"):
        st.cache_data.clear()
        st.session_state["last_refresh"] = _now()
        st.rerun()

with st.spinner("Decanting data from Damodaran, the OECD and Trading Economics…"):
    betas = fetch_betas()
    spread_src = fetch_bbb_spread()
    tax_src = fetch_tax_rates()
    yld_src = fetch_yields()

beta_df = betas["df"]
industries = beta_df["Industry Name"].tolist()
tax_rates = tax_src["rates"]
yields = dict(yld_src["yields"])
countries = sorted(set(yields) | {DEFAULT_COUNTRY})

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    ind_idx = industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0
    industry = st.selectbox("🏭 Industry", industries, index=ind_idx)
    country = st.selectbox(
        "🌍 Target country", countries, index=countries.index(DEFAULT_COUNTRY),
        format_func=lambda c: f"{flag(c)}  {c}  ({ccy(c)})",
    )
    tax_choice = st.radio(
        "🧾 Project tax rate", ["U.S.", "Selected country"], index=0, horizontal=True,
        help="One rate is applied to both currencies, so the comparison stays apples-to-apples.",
    )
    erp = st.slider("📈 Equity risk premium", 3.0, 10.0, 6.5, 0.1, format="%.1f%%") / 100
    d = st.slider("⚖️ Target debt share, D/(D+E)", 0, 80, 30, 1, format="%d%%") / 100

    st.markdown("---")
    st.markdown("### 🎛️ Blend your own")
    st.caption("Switch on any input to overwrite the fetched value.")

    def override(label, key, fetched, minv, maxv, step, suffix="%", scale=100.0):
        on = st.toggle(label, key=f"ov_{key}")
        if on:
            v = st.number_input(
                f"{label} ({suffix.strip() or 'x'})", min_value=minv, max_value=maxv,
                value=float(round(fetched * scale, 4)), step=step, key=f"val_{key}",
                label_visibility="collapsed",
            )
            return v / scale, True
        return fetched, False

    beta_fetched = float(beta_df.loc[beta_df["Industry Name"] == industry, "Unlevered beta"].iloc[0])
    us_tax_fetched = tax_rates.get("United States", FALLBACK_TAX["United States"]) / 100
    f_tax_raw = tax_rates.get(country)
    f_tax_missing = f_tax_raw is None
    f_tax_fetched = (f_tax_raw if f_tax_raw is not None else tax_rates.get("United States", 25.8)) / 100
    # The two yields the model uses come from each country's own TE page (most reliable),
    # then the /bonds table, then the labeled snapshot.
    yield_info = {}
    pages = {}
    for cname in dict.fromkeys(["United States", country]):
        if yld_src["status"] == "Live" and cname in yld_src["yields"]:
            qd = yld_src["quote_dates"].get(cname, "")
            yield_info[cname] = ("Live", f"TE /bonds {qd}".strip(), TE_URL)
            continue
        page = fetch_country_yield(cname)          # backup: same source, country page
        pages[cname] = page
        if page["value"] is not None:
            yields[cname] = page["value"]
            yield_info[cname] = ("Live", f"TE country page, {page['date']}", page["url"])
        else:
            yield_info[cname] = ("Fallback", yld_src["date"], TE_URL)
    us_page = pages.get("United States", {"fetched": yld_src["fetched"], "error": None})
    f_page = pages.get(country, {"error": None})
    rf_us_fetched = yields.get("United States", FALLBACK_YIELDS["United States"] / 100)
    rf_f_fetched = yields.get(country, rf_us_fetched)

    beta_u, ov_beta = override("Unlevered beta", "beta", beta_fetched, 0.0, 5.0, 0.01, "x", 1.0)
    us_tax, ov_ustax = override("U.S. tax rate", "ustax", us_tax_fetched, 0.0, 60.0, 0.1)
    f_tax, ov_ftax = override(f"{country} tax rate", "ftax", f_tax_fetched, 0.0, 60.0, 0.1)
    spread_us, ov_spread = override("USD BBB spread", "spread", spread_src["value"], 0.0, 15.0, 0.01)
    rf_us, ov_rfus = override("U.S. 10Y yield", "rfus", rf_us_fetched, -2.0, 50.0, 0.01)
    rf_f, ov_rff = override(f"{country} 10Y yield", "rff", rf_f_fetched, -2.0, 80.0, 0.01)

    tax = us_tax if tax_choice == "U.S." else f_tax

    # Foreign BBB spread: auto by default, manual if switched on
    auto = cost_of_capital(beta_u, erp, d, tax, rf_us, rf_f, spread_us)
    ov_fspread = st.toggle(f"{country} BBB spread", key="ov_fspread")
    if ov_fspread:
        spread_f_in = st.number_input(
            "Foreign BBB spread (%)", 0.0, 30.0, float(round(auto["spread_f_auto"] * 100, 4)),
            0.01, key="val_fspread", label_visibility="collapsed") / 100
    else:
        spread_f_in = None
        st.caption(f"Auto: **{fmt(auto['spread_f_auto'])}**, implied by converting the USD "
                   "cost of debt with the parity formula.")

    if "last_refresh" in st.session_state:
        st.caption(f"Last uncorked: {st.session_state['last_refresh']}")

res = cost_of_capital(beta_u, erp, d, tax, rf_us, rf_f, spread_us, spread_f_in)
fc = ccy(country)

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
yld_used_status = "Live" if all(v[0] == "Live" for v in yield_info.values()) else "Fallback"
yld_used = {
    "status": yld_used_status,
    "date": " · ".join(f"{k}: {v[1]}" for k, v in yield_info.items()) if country != "United States"
            else f"United States: {yield_info['United States'][1]}",
    "fetched": us_page["fetched"],
    "error": " | ".join(e for e in [us_page.get("error"), f_page.get("error"),
                                     yld_src.get("error")] if e) or None,
}
statuses = [betas["status"], spread_src["status"], tax_src["status"], yld_used_status]
live_n = statuses.count("Live")
st.markdown(
    f"""
<div class="hero">
  <div class="hero-icons" style="position:absolute;right:28px;top:50%;transform:translateY(-50%);display:flex;gap:14px;align-items:center;z-index:1">
    {wine_bottle_svg(70)}{guitar_svg(84)}{wine_glass_svg(66)}
  </div>
  <h1>{wine_glass_svg(40)} Vintage WACC {guitar_svg(40)}</h1>
  <p>The International Cost of Capital Cellar · compare a project's cost of equity and WACC
     in <b>USD</b> and <b>{fc}</b>, with the cellar stocked live from Damodaran, the OECD and Trading Economics.</p>
  <span class="tag">🏭 {industry}</span>
  <span class="tag">{flag(country)} {country}</span>
  <span class="tag">🧾 Tax: {tax_choice} ({fmt(tax, 1)})</span>
  <span class="tag">📡 {live_n}/4 sources live</span>
</div>
""",
    unsafe_allow_html=True,
)

if f_tax_missing and not ov_ftax:
    st.warning(f"No OECD tax rate found for {country}; using the U.S. rate. "
               "Switch on the override in the sidebar to enter one.")
if yld_used_status != "Live" and not (ov_rfus and ov_rff):
    st.error("The 10-year yields could not be fetched live, so the app is using an illustrative "
             "snapshot that is NOT current market data. Type today's yields from "
             "tradingeconomics.com into the overrides in the sidebar.")
if live_n < 4:
    st.info("Some sources couldn't be reached, so labeled fallback snapshots are in use. "
            "See **The Cellar** tab for details, or click **Uncork fresh data** to retry.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🍷 Tasting Notes · Results",
    "🎸 The Line-Up · All Industries",
    "📜 Liner Notes · Assumptions",
    "🗄️ The Cellar · Data & Sources",
])

# ---------------------------------------------------------------------------
# Tab 1: side-by-side results
# ---------------------------------------------------------------------------
with tab1:
    c1, c2 = st.columns(2, gap="large")

    def card(col, title, sub, cls, rf, spread, re_, rd, rd_at, wacc, icon=""):
        col.markdown(
            f"""
<div class="card {cls}">
  <h3>{icon} {title}</h3>
  <div class="sub">{sub}</div>
  <div style="color:#7a6a6f;font-size:.85rem">WACC</div>
  <div class="big">{fmt(wacc)}</div>
  <div style="margin-top:12px">
    <div class="row"><span>10Y government yield (R<sub>f</sub>)</span><span>{fmt(rf)}</span></div>
    <div class="row"><span>Levered beta</span><span>{res['beta_l']:.3f}</span></div>
    <div class="row"><span>Cost of equity (R<sub>e</sub>)</span><span>{fmt(re_)}</span></div>
    <div class="row"><span>BBB spread</span><span>{fmt(spread)}</span></div>
    <div class="row"><span>Pre-tax cost of debt (R<sub>d</sub>)</span><span>{fmt(rd)}</span></div>
    <div class="row"><span>After-tax cost of debt</span><span>{fmt(rd_at)}</span></div>
    <div class="row"><span>Weights E / D</span><span>{(1-d)*100:.0f}% / {d*100:.0f}%</span></div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    card(c1, "🇺🇸 U.S. dollar", "United States · USD", "", rf_us, spread_us,
         res["re_us"], res["rd_us"], res["rd_us_at"], res["wacc_us"],
         icon=wine_glass_svg(30, PORT, DOURO))
    card(c2, f"{flag(country)} {fc}", f"{country} · converted via interest-rate parity",
         "foreign", rf_f, res["spread_f"], res["re_f"], res["rd_f"], res["rd_f_at"], res["wacc_f"],
         icon=guitar_svg(30, AZUL, GOLD))

    gap = res["wacc_f"] - res["wacc_us"]
    st.markdown(
        f"""<div class="pairing">{wine_bottle_svg(26, PORT, GOLD)} <b>Sommelier's note:</b> the {fc} WACC is
        <b>{gap*100:+.2f} pp</b> vs USD, driven by the yield gap
        ({fmt(rf_f)} vs {fmt(rf_us)}; parity factor {res['conv']:.4f}).<br>
        Pairing for a {fmt(res['wacc_f'])} hurdle: {wine_pairing(res['wacc_f'])}</div>""",
        unsafe_allow_html=True,
    )

    st.markdown(divider(), unsafe_allow_html=True)
    st.markdown("#### Component comparison")
    comp = pd.DataFrame({
        "Metric": ["Risk-free rate", "Cost of equity", "Pre-tax cost of debt",
                   "After-tax cost of debt", "WACC"],
        "USD": [rf_us, res["re_us"], res["rd_us"], res["rd_us_at"], res["wacc_us"]],
        fc if fc != "USD" else "USD (selected)":
            [rf_f, res["re_f"], res["rd_f"], res["rd_f_at"], res["wacc_f"]],
    })
    long = comp.melt(id_vars="Metric", var_name="Currency", value_name="Rate")
    fig = px.bar(long, x="Metric", y="Rate", color="Currency", barmode="group",
                 color_discrete_sequence=[PORT, AZUL], text=long["Rate"].map(lambda v: f"{v*100:.2f}%"))
    fig.update_layout(yaxis_tickformat=".1%", plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                      legend_title_text="", height=380, margin=dict(t=20, b=10, l=10, r=10))
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    results_df = pd.DataFrame([
        ["Industry", industry, industry],
        ["Country", "United States", country],
        ["Currency", "USD", fc],
        ["Unlevered beta", beta_u, beta_u],
        ["Target debt share d", d, d],
        ["D/E", res["de"], res["de"]],
        ["Levered beta", res["beta_l"], res["beta_l"]],
        ["Equity risk premium", erp, erp],
        ["Project tax rate", tax, tax],
        ["10Y government yield", rf_us, rf_f],
        ["BBB spread", spread_us, res["spread_f"]],
        ["Cost of equity", res["re_us"], res["re_f"]],
        ["Pre-tax cost of debt", res["rd_us"], res["rd_f"]],
        ["After-tax cost of debt", res["rd_us_at"], res["rd_f_at"]],
        ["WACC", res["wacc_us"], res["wacc_f"]],
    ], columns=["Item", "USD", fc if fc != "USD" else "Selected (USD)"])

    with st.expander("📋 Full results table"):
        show = results_df.copy()
        for col in show.columns[1:]:
            show[col] = [
                v if isinstance(v, str) else (f"{v:.3f}" if item in ("Unlevered beta", "Levered beta", "D/E")
                                              else f"{v*100:.2f}%")
                for item, v in zip(show["Item"], show[col])
            ]
        st.dataframe(show, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 2: all-industry comparison
# ---------------------------------------------------------------------------
with tab2:
    rows = []
    for _, r in beta_df.iterrows():
        o = cost_of_capital(r["Unlevered beta"], erp, d, tax, rf_us, rf_f, spread_us, spread_f_in)
        rows.append({
            "Industry": r["Industry Name"], "Unlevered beta": r["Unlevered beta"],
            "Levered beta": o["beta_l"],
            "Cost of equity (USD)": o["re_us"], f"Cost of equity ({fc})": o["re_f"],
            "WACC (USD)": o["wacc_us"], f"WACC ({fc})": o["wacc_f"],
        })
    all_df = pd.DataFrame(rows)
    if fc == "USD":
        all_df = all_df.loc[:, ~all_df.columns.duplicated()]
    wacc_f_col = f"WACC ({fc})"
    all_df = all_df.sort_values(wacc_f_col, ascending=False).reset_index(drop=True)

    st.markdown(f"<h4>{guitar_svg(30, PORT, GOLD)} The Line-Up: every industry's WACC in USD vs {fc}</h4>",
                unsafe_allow_html=True)
    st.caption("Same country, tax rate, ERP, debt share and spreads; only the unlevered beta changes. "
               f"Your pick, **{industry}**, is highlighted in gold.")

    k1, k2, k3, k4 = st.columns(4)
    rank = int(all_df.index[all_df["Industry"] == industry][0]) + 1
    k1.metric("Industries", len(all_df))
    k2.metric(f"Median WACC ({fc})", fmt(all_df[wacc_f_col].median()))
    k3.metric("Your industry's rank", f"#{rank}", help="1 = highest WACC")
    k4.metric("Spread top vs bottom", f"{(all_df[wacc_f_col].max()-all_df[wacc_f_col].min())*100:.2f} pp")

    plot_df = all_df.iloc[::-1]
    colors = [GOLD if i == industry else (AZUL if fc != "USD" else PORT) for i in plot_df["Industry"]]
    fig2 = go.Figure()
    if fc != "USD":
        fig2.add_trace(go.Bar(y=plot_df["Industry"], x=plot_df["WACC (USD)"], orientation="h",
                              name="WACC (USD)", marker_color="rgba(109,26,54,.35)"))
    fig2.add_trace(go.Bar(y=plot_df["Industry"], x=plot_df[wacc_f_col], orientation="h",
                          name=wacc_f_col, marker_color=colors))
    fig2.update_layout(barmode="group", height=max(500, 18 * len(plot_df) * (2 if fc != "USD" else 1)),
                       xaxis_tickformat=".1%", plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                       margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=1.01),
                       yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig2, use_container_width=True)

    fmt_cols = {c: "{:.2%}" for c in all_df.columns if "WACC" in c or "Cost" in c}
    fmt_cols.update({"Unlevered beta": "{:.2f}", "Levered beta": "{:.2f}"})
    st.dataframe(all_df.style.format(fmt_cols), hide_index=True, use_container_width=True, height=420)

# ---------------------------------------------------------------------------
# Tab 3: assumptions
# ---------------------------------------------------------------------------
with tab3:
    st.markdown("#### 📜 Liner Notes: how the blend is made")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("**1. Relever the industry beta** (Hamada, at the target debt share)")
        st.latex(r"\beta_L=\beta_U\left[1+(1-\tau)\frac{d}{1-d}\right]")
        st.markdown("**2. USD cost of equity** (CAPM, U.S. 10Y as the risk-free rate)")
        st.latex(r"R_e = R_f + \beta_L \times ERP")
        st.markdown("**3. USD pre-tax cost of debt**")
        st.latex(r"R_d = R_f + \text{BBB spread}_{USD}")
        st.markdown("**4. WACC** (as defined in class)")
        st.latex(r"WACC=(1-d)\,R_e+d\,R_d\,(1-\tau)")
    with b:
        st.markdown("**5. Convert to the foreign currency** (method from class)")
        st.latex(r"(1+R_e^*)=(1+R_e)\frac{1+R_f^*}{1+R_f}")
        st.markdown("The same conversion gives the foreign pre-tax cost of debt, and the implied "
                    "foreign BBB spread (unless you overwrite it):")
        st.latex(r"(1+R_d^*)=(1+R_d)\frac{1+R_f^*}{1+R_f},\quad s^*=R_d^*-R_f^*")
        st.latex(r"WACC^*=(1-d)\,R_e^*+d\,R_d^*\,(1-\tau)")

    st.markdown("**Key assumptions**")
    st.markdown(f"""
- **Same project, two currencies.** Debt share (**{d:.0%}**), ERP (**{erp:.1%}**) and tax rate
  (**{tax:.1%}**, {tax_choice}) are identical in both columns, so differences come only from the currency.
- **Interest-rate parity.** The ratio of 10-year government yields captures expected inflation and
  currency differences. It assumes the 10Y yields are close to risk-free; for countries with
  meaningful sovereign default risk, the local yield also embeds a default premium.
- **U.S. industry betas.** Damodaran's U.S. unlevered betas (*Unlevered beta* column) are applied to every country.
- **BBB spread.** The USD Baa2/BBB spread is for large non-financial service firms. The foreign spread is
  implied by parity unless you enter one manually.
- **Single, constant rates.** Flat term structure, constant capital structure and tax rate over the project life.
- **The ERP is a USD premium**, applied in USD and then converted, not added to the foreign risk-free rate.
""")
    st.markdown(f"**This run, step by step:** β_L = {beta_u:.2f} × [1 + (1 − {tax:.3f}) × {res['de']:.3f}] "
                f"= **{res['beta_l']:.3f}** → R_e = {fmt(rf_us)} + {res['beta_l']:.3f} × {fmt(erp,1)} "
                f"= **{fmt(res['re_us'])}** → R_e* = (1 + {fmt(res['re_us'])}) × {res['conv']:.4f} − 1 "
                f"= **{fmt(res['re_f'])}**.")

# ---------------------------------------------------------------------------
# Tab 4: data & sources
# ---------------------------------------------------------------------------
def pill(status, manual=False):
    if manual:
        return '<span class="pill manual">Manual override</span>'
    cls = "live" if status == "Live" else "fallback"
    return f'<span class="pill {cls}">{status}</span>'


with tab4:
    st.markdown("#### 🗄️ The Cellar: sources, vintages & freshness")
    src_rows = [
        ("Unlevered industry beta", f"{beta_fetched:.2f} ({industry})", "Damodaran, betas.xls",
         BETAS_URL, betas, ov_beta),
        ("USD BBB spread (Baa2/BBB, large non-fin.)", fmt(spread_src["value"]), "Damodaran, ratings.html",
         spread_src["url"], spread_src, ov_spread),
        ("Corporate tax rate", f"U.S. {fmt(us_tax_fetched,1)} · {country} {fmt(f_tax_fetched,1)}",
         "OECD Corporate Tax Statistics", OECD_URL, tax_src, ov_ustax or ov_ftax),
        ("10Y government yields", f"U.S. {fmt(rf_us_fetched)} · {country} {fmt(rf_f_fetched)}",
         "Trading Economics /bonds", TE_URL, yld_used, ov_rfus or ov_rff),
    ]
    html = ["<table style='width:100%;border-collapse:collapse'>",
            "<tr style='text-align:left;border-bottom:2px solid #6D1A36'>"
            "<th>Input</th><th>Fetched value</th><th>Source</th><th>Status</th>"
            "<th>Data date</th><th>Fetched at</th></tr>"]
    for name, val, src, url, meta, ov in src_rows:
        html.append(
            f"<tr style='border-bottom:1px solid #eee'><td>{name}</td><td>{val}</td>"
            f"<td><a href='{url}' target='_blank'>{src}</a></td><td>{pill(meta['status'], ov)}</td>"
            f"<td>{meta['date']}</td><td>{meta['fetched']}</td></tr>")
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.caption("“Manual override” means you've overwritten that fetched value in the sidebar. "
               "“Fallback” means the site couldn't be reached, so a labeled snapshot is in use.")

    errs = [(n, m["error"]) for n, _, _, _, m, _ in src_rows if m.get("error")]
    if errs:
        with st.expander("🔧 Sound check: fetch errors"):
            for n, e in errs:
                st.code(f"{n}: {e}")

    e1, e2 = st.columns(2)
    with e1:
        with st.expander("10Y government yields (all countries)"):
            ydf = pd.DataFrame(
                [(f"{flag(k)} {k}", v * 100,
                  yield_info[k][1] if k in yield_info and yield_info[k][0] == "Live"
                  else (yld_src["quote_dates"].get(k, "") if yld_src["status"] == "Live" else "snapshot, not live"))
                 for k, v in yields.items()],
                columns=["Country", "Yield (%)", "Quote date"]).sort_values("Country")
            st.dataframe(ydf, hide_index=True, use_container_width=True)
    with e2:
        with st.expander("Corporate tax rates (all countries)"):
            tdf = pd.DataFrame([(f"{flag(k)} {k}", v) for k, v in tax_rates.items()],
                               columns=["Country", "Tax rate (%)"]).sort_values("Country")
            st.dataframe(tdf, hide_index=True, use_container_width=True)
    with st.expander("Industry unlevered betas"):
        st.dataframe(beta_df, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
st.markdown(divider(9), unsafe_allow_html=True)
st.markdown(f"<h3>{wine_bottle_svg(32, PORT, GOLD)} Take a bottle home</h3>", unsafe_allow_html=True)
inputs_df = pd.DataFrame([
    ["Industry", industry], ["Country", country], ["Foreign currency", fc],
    ["Project tax basis", tax_choice], ["Project tax rate", tax], ["Equity risk premium", erp],
    ["Target debt share", d], ["Unlevered beta", beta_u], ["USD BBB spread", spread_us],
    ["U.S. 10Y yield", rf_us], [f"{country} 10Y yield", rf_f],
    ["Foreign BBB spread", f"manual {spread_f_in:.4f}" if spread_f_in is not None else "auto (parity)"],
    ["Generated", _now()],
], columns=["Input", "Value"])
sources_df = pd.DataFrame([
    {"Input": n, "Source": s, "URL": u, "Status": "Manual override" if ov else m["status"],
     "Data date": m["date"], "Fetched at": m["fetched"]}
    for n, _, s, u, m, ov in src_rows
])

xbuf = io.BytesIO()
with pd.ExcelWriter(xbuf, engine="openpyxl") as xw:
    inputs_df.astype(str).to_excel(xw, sheet_name="Inputs", index=False)
    results_df.to_excel(xw, sheet_name="Results", index=False)
    all_df.to_excel(xw, sheet_name="All industries", index=False)
    sources_df.to_excel(xw, sheet_name="Sources", index=False)

dl1, dl2, dl3 = st.columns(3)
dl1.download_button("📊 Full workbook (.xlsx)", xbuf.getvalue(),
                    file_name=f"vintage_wacc_{country.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
dl2.download_button("🍷 Results (.csv)", results_df.to_csv(index=False).encode(),
                    file_name=f"wacc_results_{country.replace(' ', '_')}.csv", mime="text/csv",
                    use_container_width=True)
dl3.download_button("🎸 All industries (.csv)", all_df.to_csv(index=False).encode(),
                    file_name=f"wacc_all_industries_{country.replace(' ', '_')}.csv", mime="text/csv",
                    use_container_width=True)

st.markdown(
    f"<div class='footer'>{wine_glass_svg(20, PORT, DOURO)} {guitar_svg(20, PORT, GOLD)} {wine_glass_svg(20, PORT, DOURO)}<br>Aged in Damodaran oak, bottled with OECD and Trading Economics data, "
    "served loud. 🎸 Saúde e obrigado, Professor! 🇵🇹</div>",
    unsafe_allow_html=True,
)
