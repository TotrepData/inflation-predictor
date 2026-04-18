"""Ingeniería de características: replica el pipeline del notebook 03.

Convierte el panel mensual (salida de `data_client.build_monthly_panel`) en el
dataset de features con el mismo esquema de columnas usado para entrenar los
modelos en `notebooks/04_modeling.ipynb`.

Función pública: `build_features(panel)`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = [1, 3, 6, 12]
MOVING_AVG_WINDOWS = [3, 6, 12]


def _add_lags(df: pd.DataFrame, lags: list[int]) -> pd.DataFrame:
    out = {}
    for col in df.columns:
        for k in lags:
            out[f"{col}_lag{k}"] = df[col].shift(k)
    return pd.DataFrame(out, index=df.index)


def _add_moving_averages(df: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    out = {}
    for col in df.columns:
        shifted = df[col].shift(1)
        for w in windows:
            out[f"{col}_ma{w}"] = shifted.rolling(window=w, min_periods=w).mean()
    return pd.DataFrame(out, index=df.index)


def _add_pct_changes(df: pd.DataFrame, exclude: list[str] | None = None) -> pd.DataFrame:
    exclude = set(exclude or [])
    out = {}
    for col in df.columns:
        if col in exclude:
            continue
        shifted = df[col].shift(1)
        out[f"{col}_mom"] = shifted.pct_change(periods=1) * 100
        out[f"{col}_yoy"] = shifted.pct_change(periods=12) * 100
    return pd.DataFrame(out, index=df.index)


def _add_gold_special(df: pd.DataFrame) -> pd.DataFrame:
    gold_log = np.log(df["gold_price"])
    return pd.DataFrame({
        "gold_price_log_lag1":   gold_log.shift(1),
        "gold_price_log_diff1":  gold_log.diff(1).shift(1),
        "gold_price_log_diff12": gold_log.diff(12).shift(1),
    }, index=df.index)


def _add_time(df: pd.DataFrame) -> pd.DataFrame:
    month = df.index.month
    quarter = df.index.quarter
    out = pd.DataFrame({
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
    }, index=df.index)
    for q in [1, 2, 3, 4]:
        out[f"quarter_{q}"] = (quarter == q).astype(int)
    return out


def _add_autoreg(target: pd.Series, lags: list[int], windows: list[int]) -> pd.DataFrame:
    out = {f"inflation_mom_lag{k}": target.shift(k) for k in lags}
    target_shifted1 = target.shift(1)
    for w in windows:
        out[f"inflation_mom_ma{w}"] = target_shifted1.rolling(window=w, min_periods=w).mean()
    return pd.DataFrame(out, index=target.index)


def build_features(panel: pd.DataFrame, drop_na: bool = True) -> pd.DataFrame:
    """Construye el dataset de features idéntico al de `notebooks/03_feature_engineering.ipynb`.

    `panel` debe tener índice DateTime mensual y columnas: cpi, fed_rate, oil_price,
    unemployment, industrial_production, money_supply_m2, retail_sales,
    capacity_utilization, treasury_10y, ppi, consumer_sentiment, gold_price.
    """
    target = panel["cpi"].pct_change() * 100
    target.name = "inflation_mom"

    df_lags = _add_lags(panel, LAGS)
    df_ma = _add_moving_averages(panel, MOVING_AVG_WINDOWS)
    df_pct = _add_pct_changes(panel, exclude=["cpi"])
    df_gold = _add_gold_special(panel)
    df_time = _add_time(panel)
    df_autoreg = _add_autoreg(target, LAGS, MOVING_AVG_WINDOWS)

    features = pd.concat([df_lags, df_ma, df_pct, df_gold, df_time, df_autoreg], axis=1)
    out = features.copy()
    out["inflation_mom"] = target

    if drop_na:
        out = out.dropna()
    return out
