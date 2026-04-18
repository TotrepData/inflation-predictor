"""Cliente de datos para la app Streamlit.

Combina dos fuentes:
- FRED API (11 series macroeconómicas de EE.UU.)
- Archivo local del Pink Sheet del Banco Mundial (gold_price)

Expone una única función pública `build_monthly_panel` que retorna el
dataset en formato compatible con `notebooks/03_feature_engineering.ipynb`
(index mensual, 12 columnas numéricas, sin nulos dentro del rango).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import requests

FRED_SERIES: dict[str, str] = {
    "CPIAUCSL": "cpi",
    "FEDFUNDS": "fed_rate",
    "DCOILWTICO": "oil_price",
    "UNRATE": "unemployment",
    "INDPRO": "industrial_production",
    "M2SL": "money_supply_m2",
    "RRSFS": "retail_sales",
    "TCU": "capacity_utilization",
    "GS10": "treasury_10y",
    "PPIACO": "ppi",
    "UMCSENT": "consumer_sentiment",
}

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(series_id: str, api_key: str, start: str = "1990-01-01") -> pd.DataFrame:
    """Descarga una serie de FRED y retorna DataFrame con columnas ['date', 'value']."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
    }
    r = requests.get(FRED_URL, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", np.nan), errors="coerce")
    return df


def _monthly_from_daily(df: pd.DataFrame, colname: str) -> pd.DataFrame:
    """Agrega una serie diaria a frecuencia mensual por promedio."""
    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    monthly = df.groupby("month")["value"].mean().reset_index()
    return monthly.rename(columns={"month": "date", "value": colname})


def load_gold_from_disk(path: Path) -> pd.DataFrame:
    """Lee el gold price previamente procesado por el notebook 01 en raw/."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.rename(columns={"value": "gold_price"})[["date", "gold_price"]]


def build_monthly_panel(api_key: str, gold_path: Path) -> pd.DataFrame:
    """Construye el panel mensual con 12 variables.

    Replica la lógica del notebook 01 pero sin escribir a disco: descarga FRED,
    agrega oil a mensual, integra gold desde disco, filtra desde 1992-01 hasta
    la última fecha con cobertura en gold (serie que no se puede actualizar
    automáticamente por ser manual del Banco Mundial), y aplica forward-fill
    para huecos internos.

    Retorna un DataFrame indexado por fecha con las 12 columnas del modelo.
    """
    clean = {}
    for code, name in FRED_SERIES.items():
        df = fetch_fred_series(code, api_key)
        df = df.rename(columns={"value": name})
        clean[name] = df[["date", name]]

    # Oil price es diario; agregar a mensual
    clean["oil_price"] = _monthly_from_daily(
        clean["oil_price"].rename(columns={"oil_price": "value"}), "oil_price"
    )

    # Gold desde disco (Banco Mundial, no hay API automática)
    gold = load_gold_from_disk(gold_path)

    # Integración por fecha
    panel = clean["cpi"]
    for name, df in clean.items():
        if name == "cpi":
            continue
        panel = panel.merge(df, on="date", how="outer")
    panel = panel.merge(gold, on="date", how="outer").sort_values("date").reset_index(drop=True)

    # Ventana de análisis: 1992-01 → último mes con dato real en gold
    start = pd.Timestamp("1992-01-01")
    end = gold["date"].max()
    panel = panel[(panel["date"] >= start) & (panel["date"] <= end)].copy()

    # Imputación forward-fill (coherente con la propuesta, nota al pie 5)
    panel = panel.sort_values("date").ffill()
    panel = panel.dropna().reset_index(drop=True)

    return panel.set_index("date")
