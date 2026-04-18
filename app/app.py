"""App Streamlit — Pronóstico de inflación mensual de EE.UU.

Usuario objetivo: analistas de mesa de tesorería y renta fija.

Tabs:
1. Pronóstico vigente — datos frescos de FRED + modelos ganadores por horizonte.
2. Explorar variables — serie de tiempo y distribución por variable macro.
3. Comparación de modelos — métricas walk-forward.
4. Interpretabilidad (SHAP) — figuras generadas en el notebook 05.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Streamlit no añade el directorio del script al sys.path, así que lo hacemos
# manualmente para que funcionen los imports locales cuando la app se lanza
# desde el directorio raíz del repositorio.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from data_client import build_monthly_panel
from feature_pipeline import build_features
from forecast import predict_all_horizons, load_best_meta

REPO_ROOT = APP_DIR.parent
MODELS_DIR = REPO_ROOT / "models"
GOLD_PATH = REPO_ROOT / "data" / "raw" / "gold_price_raw.csv"
FIGURES_DIR = REPO_ROOT / "figures"
FEATURES_CSV_PATH = REPO_ROOT / "data" / "processed" / "features.csv"

# Cargar API key (Streamlit Cloud usa st.secrets, local usa .env)
load_dotenv(REPO_ROOT / ".env")


def get_fred_api_key() -> str | None:
    # Preferir secrets de Streamlit si existen
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY")


# ------------------------------------------------------------------
# Carga de datos con caché
# ------------------------------------------------------------------

@st.cache_data(ttl=60 * 60 * 6, show_spinner="Descargando datos FRED...")
def load_panel(_cache_tag: str) -> pd.DataFrame:
    """Panel mensual con las 12 variables. Cachea 6 horas para no saturar FRED."""
    api_key = get_fred_api_key()
    if not api_key:
        # Fallback: cargar desde dataset_modelo.csv (snapshot del notebook 01)
        df = pd.read_csv(
            REPO_ROOT / "data" / "processed" / "dataset_modelo.csv",
            parse_dates=["date"],
        )
        return df.set_index("date").sort_index()
    return build_monthly_panel(api_key, GOLD_PATH)


@st.cache_data(ttl=60 * 60 * 6, show_spinner="Calculando features...")
def load_features(panel_parquet_bytes: bytes) -> pd.DataFrame:
    """Dataset de features + target. Toma bytes para invalidar caché con cambios del panel."""
    panel = pd.read_parquet(pd.io.common.BytesIO(panel_parquet_bytes))
    return build_features(panel)


def _panel_as_bytes(panel: pd.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    panel.to_parquet(buf)
    return buf.getvalue()


# ------------------------------------------------------------------
# Render
# ------------------------------------------------------------------

st.set_page_config(
    page_title="US Inflation Predictor",
    page_icon="📊",
    layout="wide",
)

st.title("📊 US Inflation Predictor")
st.caption(
    "Pronóstico mensual del CPI de EE.UU. para analistas de mesa de tesorería. "
    "Modelos entrenados con validación walk-forward · Universidad de los Andes"
)

# ------------------------------------------------------------------
# Carga datos una vez, reusado en todas las tabs
# ------------------------------------------------------------------
try:
    panel = load_panel(_cache_tag="v1")
    panel_bytes = _panel_as_bytes(panel)
    features = load_features(panel_bytes)
    target_series = features["inflation_mom"]
except Exception as e:
    st.error(f"No se pudieron cargar los datos: {e}")
    st.stop()

# Sidebar con metadata
with st.sidebar:
    st.header("Estado del pipeline")
    st.metric("Última observación", f"{panel.index.max():%Y-%m}")
    st.metric("Observaciones", len(panel))
    st.metric("Variables macro", panel.shape[1])
    st.divider()
    st.caption(
        f"Features derivados: {features.shape[1] - 1}"
        f" · Período modelable: {features.index.min():%Y-%m} → {features.index.max():%Y-%m}"
    )
    if get_fred_api_key():
        st.success("Datos FRED en línea")
    else:
        st.warning("Sin API key — usando snapshot local")

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Pronóstico vigente",
    "🔍 Explorar variables",
    "⚖️ Comparación de modelos",
    "🧠 Interpretabilidad (SHAP)",
])

# ------------------------------------------------------------------
# Tab 1: Pronóstico vigente
# ------------------------------------------------------------------
with tab1:
    st.subheader("Pronóstico del CPI a múltiples horizontes")
    st.caption(
        "Cada horizonte usa el modelo ganador según RMSE en walk-forward. "
        "Los pronósticos se generan a partir de la fila de features más reciente."
    )

    # Usar la última fila disponible de features para predecir
    last_row = features.drop(columns="inflation_mom").tail(1)
    try:
        preds = predict_all_horizons(last_row, MODELS_DIR, y_full=target_series)
    except Exception as e:
        st.error(f"Error generando pronóstico: {e}")
        st.stop()

    # Tarjetas
    cols = st.columns(4)
    for i, row in preds.iterrows():
        with cols[i]:
            delta_vs_fed = row["prediction"] * 12 - 2.0  # anualizado menos meta 2%
            st.metric(
                label=f"h = {row['horizon']} mes(es)",
                value=f"{row['prediction']:+.3f}%",
                delta=f"{row['prediction']*12:+.2f}% anualizado (meta Fed 2%)",
                delta_color="inverse",
            )
            st.caption(f"Modelo: **{row['model']}** · Objetivo: {row['target_date']:%Y-%m}")

    st.divider()

    # Gráfico histórico + pronósticos
    hist = target_series.rename("Inflación MoM observada (%)").to_frame()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist["Inflación MoM observada (%)"],
        mode="lines", name="Observada", line=dict(color="#1f77b4", width=1.5),
    ))
    # Puntos de pronóstico
    fig.add_trace(go.Scatter(
        x=preds["target_date"], y=preds["prediction"],
        mode="markers+text", name="Pronóstico",
        marker=dict(size=12, color="#d62728", symbol="diamond"),
        text=[f"h={h}" for h in preds["horizon"]],
        textposition="top center",
    ))
    fig.add_hline(y=2/12, line_dash="dot", line_color="green",
                  annotation_text="Meta Fed 2% anual")
    fig.update_layout(
        title="Inflación mensual — histórica y pronósticos",
        xaxis_title="Fecha", yaxis_title="Inflación MoM (%)",
        height=420, hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("Nota metodológica sobre los horizontes"):
        st.markdown("""
        Los features en la fila *D* usan información hasta *D−1* (todos son rezagados
        o medias móviles desfasadas). Por tanto, al predecir con el modelo de horizonte
        *h* sobre la última fila disponible, el pronóstico corresponde a la inflación
        del mes **D + (h−1)**. La columna *Objetivo* refleja esa fecha objetivo.

        Los pronósticos se anualizan por composición simple (× 12) para poder compararse
        con la meta del 2% interanual de la Reserva Federal.
        """)

# ------------------------------------------------------------------
# Tab 2: Explorar variables
# ------------------------------------------------------------------
with tab2:
    st.subheader("Exploración por variable macroeconómica")
    variable = st.selectbox(
        "Variable",
        options=list(panel.columns),
        index=0,
        help="Selecciona una de las 12 variables del modelo para ver su serie de tiempo y distribución.",
    )
    serie = panel[variable].dropna()

    colA, colB, colC, colD = st.columns(4)
    colA.metric("Media", f"{serie.mean():.2f}")
    colB.metric("Std", f"{serie.std():.2f}")
    colC.metric("Último valor", f"{serie.iloc[-1]:.2f}")
    colD.metric(
        "Cambio YoY",
        f"{(serie.iloc[-1] / serie.iloc[-13] - 1) * 100:+.2f}%" if len(serie) >= 13 else "—",
    )

    # Serie de tiempo
    fig_ts = px.line(
        serie.reset_index(), x="date", y=variable,
        title=f"{variable} — serie completa",
        labels={"date": "Fecha"},
    )
    fig_ts.update_layout(height=400)
    st.plotly_chart(fig_ts, width="stretch")

    # Distribución
    col1, col2 = st.columns(2)
    with col1:
        fig_hist = px.histogram(
            serie, x=variable, nbins=40,
            title="Distribución de valores",
        )
        fig_hist.update_layout(height=320)
        st.plotly_chart(fig_hist, width="stretch")

    with col2:
        # Correlación con CPI (en niveles)
        corr_with_cpi = panel.corr()[variable].drop(variable).sort_values(key=abs, ascending=False)
        st.write("**Correlación de Pearson con las demás variables (en niveles):**")
        st.dataframe(
            corr_with_cpi.round(3).to_frame("Correlación"),
            width="stretch",
            height=320,
        )

# ------------------------------------------------------------------
# Tab 3: Comparación de modelos
# ------------------------------------------------------------------
with tab3:
    st.subheader("Métricas walk-forward por modelo × horizonte")
    try:
        metrics = pd.read_csv(MODELS_DIR / "metrics_by_horizon.csv")
    except FileNotFoundError:
        st.warning("No se encontró `metrics_by_horizon.csv`. Ejecuta el notebook 04 primero.")
        st.stop()

    # Tabla
    pivot_rmse = metrics.pivot(index="model", columns="horizon", values="RMSE").round(4)
    pivot_r2 = metrics.pivot(index="model", columns="horizon", values="R2").round(4)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**RMSE por modelo × horizonte**")
        st.dataframe(pivot_rmse, width="stretch")
    with col2:
        st.markdown("**R² por modelo × horizonte**")
        st.dataframe(pivot_r2, width="stretch")

    # Gráfico RMSE
    fig = px.line(
        metrics, x="horizon", y="RMSE", color="model",
        markers=True, title="RMSE por horizonte",
        labels={"horizon": "Horizonte (meses)", "RMSE": "RMSE (pp)"},
    )
    st.plotly_chart(fig, width="stretch")

    # Pre vs Post COVID si está disponible
    path_pp = MODELS_DIR / "metrics_pre_post_covid.csv"
    if path_pp.exists():
        st.divider()
        st.markdown("**Métricas segmentadas pre/post COVID (mar-2020)**")
        df_pp = pd.read_csv(path_pp)
        fig_pp = px.line(
            df_pp, x="horizon", y="RMSE", color="model",
            facet_col="regime", markers=True,
            title="RMSE pre vs post COVID",
        )
        st.plotly_chart(fig_pp, width="stretch")

    # Ganador
    st.divider()
    st.markdown("**Modelo ganador por horizonte (RMSE mínimo):**")
    meta = load_best_meta(MODELS_DIR)
    meta_df = pd.DataFrame([
        {"horizon": int(h), "model": v["model"], "RMSE": v["rmse"], "R²": v["r2"]}
        for h, v in meta.items()
    ]).sort_values("horizon")
    st.dataframe(meta_df.round(4), width="stretch", hide_index=True)

# ------------------------------------------------------------------
# Tab 4: Interpretabilidad (SHAP)
# ------------------------------------------------------------------
with tab4:
    st.subheader("Análisis SHAP — importancia y dirección de variables")
    st.caption(
        "Generado por el notebook `05_shap.ipynb`. ARIMA queda fuera del análisis "
        "por ser univariado; se usa el mejor modelo ML por horizonte."
    )

    horizon_choice = st.radio(
        "Horizonte", options=[1, 6], horizontal=True, index=0,
        help="El análisis SHAP se generó para horizontes 1 y 6 meses.",
    )

    def show_fig(name: str, caption: str):
        path = FIGURES_DIR / name
        if path.exists():
            st.image(str(path), caption=caption, width="stretch")
        else:
            st.info(f"Figura no encontrada: `{name}`. Ejecuta el notebook 05 primero.")

    col1, col2 = st.columns(2)
    with col1:
        show_fig(
            f"shap_01_global_importance_h{horizon_choice}.png",
            f"Importancia global — h = {horizon_choice}",
        )
    with col2:
        show_fig(
            f"shap_02_beeswarm_h{horizon_choice}.png",
            f"Distribución y dirección — h = {horizon_choice}",
        )

    if horizon_choice == 1:
        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            show_fig(
                "shap_03_waterfall_last_h1.png",
                "Explicación del pronóstico más reciente (waterfall)",
            )
        with col4:
            show_fig(
                "shap_04_pre_post_covid_h1.png",
                "Cambio de importancia pre vs post COVID",
            )

# ------------------------------------------------------------------
# Pie
# ------------------------------------------------------------------
st.divider()
st.caption(
    "Proyecto académico · MINE-4206 Aprendizaje Automático · Javier Mondragón, Jessica Joya, Alberth Pérez. "
    "Fuentes: FRED (Federal Reserve Bank of St. Louis) y World Bank Pink Sheet."
)
