"""Utilidades de predicción.

Carga los modelos persistidos por el notebook 04 y produce pronósticos para
horizontes h = 1, 3, 6, 12 a partir de una fila de features.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

HORIZONS = [1, 3, 6, 12]


def load_best_meta(models_dir: Path) -> dict:
    with open(models_dir / "best_model_per_horizon.json") as f:
        return json.load(f)


def predict_all_horizons(
    features_row: pd.DataFrame,
    models_dir: Path,
    y_full: pd.Series | None = None,
) -> pd.DataFrame:
    """Genera pronósticos para cada horizonte usando el modelo ganador.

    Parameters
    ----------
    features_row : DataFrame con 1 fila (la más reciente disponible); sus
        columnas deben coincidir con las usadas durante el entrenamiento.
    models_dir : Path hacia `models/`.
    y_full : Serie `inflation_mom` completa; requerida solo si algún ganador
        por horizonte es ARIMA, dado que ARIMA usa la historia univariada.

    Returns
    -------
    DataFrame con columnas [horizon, target_date, model, prediction].
    """
    meta = load_best_meta(models_dir)
    origin_date = features_row.index[-1]
    rows = []

    for h in HORIZONS:
        entry = meta[str(h)]
        model_name = entry["model"]
        artifact = entry["artifact"]
        target_date = origin_date + pd.DateOffset(months=(h - 1))

        model = joblib.load(models_dir / artifact)

        if model_name == "ARIMA":
            if y_full is None:
                raise ValueError("ARIMA requiere pasar y_full (inflation_mom histórica).")
            forecast = model.forecast(steps=int(h))
            prediction = float(forecast.iloc[h - 1])
        else:
            prediction = float(model.predict(features_row)[0])

        rows.append({
            "horizon": h,
            "target_date": target_date,
            "model": model_name,
            "prediction": prediction,
        })

    return pd.DataFrame(rows)
