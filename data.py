"""Data loading for the Sales Analysis Streamlit app.

The original data lives inside the compressed data model of `powerBISale.pbix`
and cannot be read directly. This module therefore loads data from a CSV if one
is available, and otherwise generates a realistic synthetic Global Superstore
dataset calibrated to the totals shown on the original Power BI dashboard
(~2.68M sales, ~307K profit, ~38K quantity across 2011-2012).
"""

from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd

# Canonical columns the app expects.
REQUIRED_COLUMNS = [
    "Order Date",
    "Region",
    "Country",
    "Category",
    "Sub-Category",
    "Ship Mode",
    "Sales",
    "Profit",
    "Quantity",
]

# Maps many common Superstore column-name variants to our canonical names.
COLUMN_ALIASES = {
    "order date": "Order Date",
    "orderdate": "Order Date",
    "region": "Region",
    "country": "Country",
    "country/region": "Country",
    "category": "Category",
    "sub-category": "Sub-Category",
    "subcategory": "Sub-Category",
    "sub category": "Sub-Category",
    "ship mode": "Ship Mode",
    "shipmode": "Ship Mode",
    "sales": "Sales",
    "profit": "Profit",
    "quantity": "Quantity",
    "qty": "Quantity",
}

REGIONS = [
    "Central", "South", "North", "Oceania", "West", "Southeast Asia",
    "EMEA", "East", "Africa", "North Asia", "Central Asia", "Caribbean",
]

# Representative countries per region (Global Superstore style).
COUNTRIES = {
    "Central": ["Germany", "France", "Austria", "Switzerland"],
    "South": ["Brazil", "Argentina", "Chile", "Colombia"],
    "North": ["United States", "Canada"],
    "Oceania": ["Australia", "New Zealand"],
    "West": ["United Kingdom", "Ireland", "Spain", "Portugal"],
    "Southeast Asia": ["Indonesia", "Thailand", "Vietnam", "Philippines"],
    "EMEA": ["Egypt", "Saudi Arabia", "Turkey", "Israel"],
    "East": ["China", "Japan", "South Korea"],
    "Africa": ["Nigeria", "South Africa", "Kenya", "Morocco"],
    "North Asia": ["Russia", "Mongolia", "Kazakhstan"],
    "Central Asia": ["India", "Pakistan", "Bangladesh"],
    "Caribbean": ["Cuba", "Dominican Republic", "Jamaica"],
}

CATEGORIES = {
    "Technology": ["Phones", "Accessories", "Machines", "Copiers"],
    "Furniture": ["Chairs", "Tables", "Bookcases", "Furnishings"],
    "Office Supplies": ["Storage", "Binders", "Art", "Paper", "Supplies"],
}

SHIP_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]
# Approx share seen on the original pie chart.
SHIP_MODE_WEIGHTS = [0.61, 0.19, 0.15, 0.05]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in COLUMN_ALIASES:
            renamed[col] = COLUMN_ALIASES[key]
    df = df.rename(columns=renamed)
    return df


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    df = df.dropna(subset=["Order Date"])
    for num_col in ("Sales", "Profit", "Quantity"):
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)
    df["Year"] = df["Order Date"].dt.year
    df["Month"] = df["Order Date"].dt.month
    df["Month Name"] = df["Order Date"].dt.strftime("%b")
    df["Year-Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
    return df.sort_values("Order Date").reset_index(drop=True)


def load_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize an arbitrary uploaded/loaded dataframe to the app schema."""
    df = _normalize_columns(df)
    missing = [c for c in ["Order Date", "Region", "Category", "Ship Mode",
                           "Sales", "Profit", "Quantity"] if c not in df.columns]
    if missing:
        raise ValueError(
            "The provided data is missing required columns: " + ", ".join(missing)
        )
    if "Country" not in df.columns:
        df["Country"] = "Unknown"
    if "Sub-Category" not in df.columns:
        df["Sub-Category"] = "Unknown"
    return _finalize(df)


def load_from_csv_bytes(data: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(data), encoding_errors="ignore")
    return load_from_dataframe(df)


def generate_synthetic(seed: int = 42, n_rows: int = 12000) -> pd.DataFrame:
    """Generate synthetic Global Superstore-like data for 2011-2012.

    Calibrated so aggregate totals land near the original dashboard:
    Sales ~2.68M, Profit ~307K, Quantity ~38K.
    """
    rng = np.random.default_rng(seed)

    # Dates across 2011-2012 with a mild upward trend (matches the rising
    # month-over-month line on the dashboard).
    start = pd.Timestamp("2011-01-01")
    day_span = (pd.Timestamp("2012-12-31") - start).days
    day_weights = np.linspace(0.7, 1.6, day_span + 1)
    day_weights /= day_weights.sum()
    day_offsets = rng.choice(day_span + 1, size=n_rows, p=day_weights)
    order_dates = start + pd.to_timedelta(day_offsets, unit="D")

    regions = rng.choice(REGIONS, size=n_rows)
    countries = np.array([rng.choice(COUNTRIES[r]) for r in regions])

    # Category mix roughly matches the bar chart (Technology highest).
    categories = rng.choice(
        list(CATEGORIES.keys()), size=n_rows, p=[0.4, 0.33, 0.27]
    )
    sub_categories = np.array([rng.choice(CATEGORIES[c]) for c in categories])

    ship_modes = rng.choice(SHIP_MODES, size=n_rows, p=SHIP_MODE_WEIGHTS)

    quantity = rng.integers(1, 8, size=n_rows)

    # Per-unit price depends on category; sales derived from quantity * price.
    price_base = {"Technology": 120, "Furniture": 90, "Office Supplies": 25}
    unit_price = np.array([price_base[c] for c in categories]) * rng.lognormal(
        mean=0.0, sigma=0.5, size=n_rows
    )
    sales = np.round(quantity * unit_price, 2)

    # Profit margin varies and can be negative for some orders.
    margin = rng.normal(0.12, 0.15, size=n_rows)
    profit = np.round(sales * margin, 2)

    df = pd.DataFrame(
        {
            "Order Date": order_dates,
            "Region": regions,
            "Country": countries,
            "Category": categories,
            "Sub-Category": sub_categories,
            "Ship Mode": ship_modes,
            "Sales": sales,
            "Profit": profit,
            "Quantity": quantity,
        }
    )

    # Scale sales/profit/quantity to match the dashboard headline numbers.
    df["Sales"] *= 2_680_000 / df["Sales"].sum()
    df["Profit"] *= 307_420 / df["Profit"].sum()
    df["Sales"] = df["Sales"].round(2)
    df["Profit"] = df["Profit"].round(2)
    # Quantity total tuned to ~38K.
    scale_q = 38_000 / df["Quantity"].sum()
    df["Quantity"] = np.maximum(1, np.round(df["Quantity"] * scale_q)).astype(int)

    return _finalize(df)


def load_default(folder: str | None = None) -> tuple[pd.DataFrame, str]:
    """Load `sales.csv` from the folder if present, else synthetic data.

    Returns the dataframe and a short label describing the source.
    """
    folder = folder or os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(folder, "sales.csv")
    if os.path.exists(csv_path):
        try:
            df = load_from_dataframe(pd.read_csv(csv_path, encoding_errors="ignore"))
            return df, f"Loaded from {os.path.basename(csv_path)}"
        except Exception as exc:  # noqa: BLE001
            return generate_synthetic(), (
                f"Could not read sales.csv ({exc}); using synthetic sample data"
            )
    return generate_synthetic(), "Synthetic sample data (no sales.csv found)"
