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

# Cargar API key (Streamlit Cloud usa st.secrets, local usa .env)
load_dotenv(REPO_ROOT / ".env")

FRIENDLY_NAMES = {
    "cpi": "CPI",
    "fed_rate": "Tasa de interés de la Fed",
    "oil_price": "Precio del petróleo",
    "unemployment": "Desempleo",
    "industrial_production": "Producción industrial",
    "money_supply_m2": "Oferta monetaria M2",
    "retail_sales": "Ventas minoristas",
    "capacity_utilization": "Utilización de capacidad",
    "treasury_10y": "Bono del Tesoro 10Y",
    "ppi": "Índice de precios al productor",
    "consumer_sentiment": "Confianza del consumidor",
    "gold_price": "Precio del oro",
}


def get_fred_api_key() -> str | None:
    """Obtiene la API key desde secrets de Streamlit o desde el archivo .env."""
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY")


# ------------------------------------------------------------------
# Estilo visual
# ------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.3rem;
            padding-bottom: 1.2rem;
        }

        .main-title {
            font-size: 2.15rem;
            font-weight: 800;
            margin-bottom: 0.15rem;
            letter-spacing: -0.02em;
        }

        .main-subtitle {
            color: #475569;
            font-size: 1rem;
            margin-bottom: 1rem;
        }

        .hero-box {
            background: linear-gradient(135deg, #f8fbff 0%, #eef4ff 100%);
            border: 1px solid #dbe7ff;
            border-radius: 18px;
            padding: 1.25rem 1.2rem;
            margin-bottom: 1rem;
        }

        .hero-badges {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 0.75rem;
        }

        .badge {
            background: white;
            border: 1px solid #dbeafe;
            color: #1e3a8a;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .section-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1rem 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }

        .metric-card {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
            margin-bottom: 0.5rem;
            min-height: 138px;
        }

        .metric-label {
            color: #64748b;
            font-size: 0.86rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }

        .metric-value {
            color: #0f172a;
            font-size: 1.75rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }

        .metric-sub {
            color: #334155;
            font-size: 0.84rem;
            line-height: 1.35;
        }

        .mini-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.6rem;
        }

        .mini-title {
            font-size: 0.80rem;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        .mini-value {
            font-size: 1.15rem;
            color: #0f172a;
            font-weight: 800;
        }

        .info-pill {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1d4ed8;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
            font-size: 0.92rem;
            margin-bottom: 1rem;
        }

        .footer-box {
            color: #64748b;
            font-size: 0.88rem;
            padding-top: 0.35rem;
            padding-bottom: 0.25rem;
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
        }

        div[data-baseweb="tab-list"] {
            gap: 0.4rem;
        }

        div[data-baseweb="tab"] {
            border-radius: 12px;
            padding: 0.45rem 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_big_card(title: str, value: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mini_card(title: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="mini-card">
            <div class="mini-title">{title}</div>
            <div class="mini-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pretty_name(variable: str) -> str:
    return FRIENDLY_NAMES.get(variable, variable)


# ------------------------------------------------------------------
# Carga de datos con caché
# ------------------------------------------------------------------

@st.cache_data(ttl=60 * 60 * 6, show_spinner="Descargando datos FRED...")
def load_panel(_cache_tag: str) -> pd.DataFrame:
    """Panel mensual con las 12 variables. Cachea 6 horas para no saturar FRED."""
    api_key = get_fred_api_key()
    if not api_key:
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
# Configuración general
# ------------------------------------------------------------------

st.set_page_config(
    page_title="US Inflation Predictor",
    page_icon="📈",
    layout="wide",
)

inject_css()

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

# ------------------------------------------------------------------
# Encabezado principal
# ------------------------------------------------------------------

st.markdown(
    """
    <div class="hero-box">
        <div class="main-title">US Inflation Predictor</div>
        <div class="main-subtitle">
            Aplicación para pronosticar la inflación mensual de Estados Unidos usando
            modelos econométricos y de machine learning con validación walk-forward.
            Universidad de los Andes
        </div>
        <div class="hero-badges">
            <div class="badge">Target: inflación mensual (MoM)</div>
            <div class="badge">Horizontes: 1, 3, 6 y 12 meses</div>
            <div class="badge">Fuente: FRED + World Bank</div>
            <div class="badge">Uso: análisis macro y renta fija</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Sidebar con metadata
# ------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Estado del pipeline")

    render_mini_card("Última observación", f"{panel.index.max():%Y-%m}")
    render_mini_card("Observaciones", f"{len(panel)}")
    render_mini_card("Variables macro", f"{panel.shape[1]}")
    render_mini_card("Features derivados", f"{features.shape[1] - 1}")

    st.markdown("---")
    st.caption(
        f"Período modelable: {features.index.min():%Y-%m} → {features.index.max():%Y-%m}"
    )

    if get_fred_api_key():
        st.success("Datos FRED en línea")
    else:
        st.warning("Sin API key: usando snapshot local")

# ------------------------------------------------------------------
# Tabs principales
# ------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "📍 Pronóstico vigente",
    "📊 Explorar variables",
    "📚 Comparación de modelos",
    "🔎 Interpretabilidad (SHAP)",
])

# ------------------------------------------------------------------
# Tab 1: Pronóstico vigente
# ------------------------------------------------------------------

with tab1:
    st.markdown(
        """
        <div class="info-pill">
            Esta vista muestra el objetivo principal del proyecto:
            <b>predecir la inflación mensual (% MoM)</b>, no el nivel del CPI.
            El CPI se usa como serie base para construir la inflación.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Pronóstico actual por horizonte")
    st.caption(
        "Cada horizonte usa el modelo ganador según RMSE en validación walk-forward. "
        "Los pronósticos se generan con la fila de features más reciente disponible."
    )

    last_row = features.drop(columns="inflation_mom").tail(1)

    try:
        preds = predict_all_horizons(last_row, MODELS_DIR, y_full=target_series)
    except Exception as e:
        st.error(f"Error generando pronóstico: {e}")
        st.stop()

    cols = st.columns(4)
    for i, (_, row) in enumerate(preds.iterrows()):
        annualized = row["prediction"] * 12
        with cols[i]:
            render_big_card(
                title=f"Horizonte h = {int(row['horizon'])} mes(es)",
                value=f"{row['prediction']:+.3f}%",
                subtitle=(
                    f"Modelo: <b>{row['model']}</b><br>"
                    f"Objetivo: <b>{row['target_date']:%Y-%m}</b><br>"
                    f"Anualizado aprox.: <b>{annualized:+.2f}%</b>"
                ),
            )

    st.markdown("### Evolución histórica y puntos de pronóstico")

    hist = target_series.rename("Inflación MoM observada (%)").to_frame()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist.index,
            y=hist["Inflación MoM observada (%)"],
            mode="lines",
            name="Observada",
            line=dict(width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=preds["target_date"],
            y=preds["prediction"],
            mode="markers+text",
            name="Pronóstico",
            marker=dict(size=12, symbol="diamond"),
            text=[f"h={h}" for h in preds["horizon"]],
            textposition="top center",
        )
    )
    fig.add_hline(
        y=2 / 12,
        line_dash="dot",
        annotation_text="Meta Fed 2% anual",
    )
    fig.update_layout(
        template="plotly_white",
        title="Inflación mensual observada vs pronósticos",
        xaxis_title="Fecha",
        yaxis_title="Inflación mensual (%)",
        hovermode="x unified",
        height=470,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", y=1.06, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Resumen de pronósticos")
    summary_preds = preds.copy()
    summary_preds["target_date"] = pd.to_datetime(summary_preds["target_date"]).dt.strftime("%Y-%m")
    summary_preds["prediction"] = summary_preds["prediction"].map(lambda x: f"{x:+.3f}%")
    summary_preds = summary_preds.rename(
        columns={
            "horizon": "Horizonte",
            "target_date": "Fecha objetivo",
            "model": "Modelo",
            "prediction": "Pronóstico",
        }
    )
    st.dataframe(summary_preds, use_container_width=True, hide_index=True)

    with st.expander("Ver nota metodológica"):
        st.markdown(
            """
            Los features en la fila **D** usan información hasta **D−1**
            porque fueron construidos con rezagos y medias móviles desplazadas.

            Por eso, cuando se usa el modelo del horizonte **h** sobre la última fila
            disponible, el pronóstico corresponde al mes objetivo **D + (h−1)**.

            En la app también se muestra una anualización aproximada multiplicando por 12,
            solo para facilitar la comparación con la meta de inflación anual de la Fed.
            """
        )

# ------------------------------------------------------------------
# Tab 2: Explorar variables
# ------------------------------------------------------------------

with tab2:
    st.subheader("Exploración visual de variables macroeconómicas")
    st.caption(
        "Puedes inspeccionar cada variable del panel mensual para entender su comportamiento, "
        "distribución y relación lineal con las demás series."
    )

    variable = st.selectbox(
        "Selecciona una variable",
        options=list(panel.columns),
        format_func=pretty_name,
    )

    serie = panel[variable].dropna()

    colA, colB, colC, colD = st.columns(4)
    with colA:
        render_mini_card("Media", f"{serie.mean():.2f}")
    with colB:
        render_mini_card("Desv. estándar", f"{serie.std():.2f}")
    with colC:
        render_mini_card("Último valor", f"{serie.iloc[-1]:.2f}")
    with colD:
        yoy_value = (
            f"{(serie.iloc[-1] / serie.iloc[-13] - 1) * 100:+.2f}%"
            if len(serie) >= 13 else "—"
        )
        render_mini_card("Cambio interanual", yoy_value)

    fig_ts = px.line(
        serie.reset_index(),
        x="date",
        y=variable,
        title=f"{pretty_name(variable)} — serie histórica",
        labels={"date": "Fecha", variable: pretty_name(variable)},
        template="plotly_white",
    )
    fig_ts.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    col1, col2 = st.columns([1.1, 1])

    with col1:
        fig_hist = px.histogram(
            serie,
            x=variable,
            nbins=40,
            title=f"Distribución de {pretty_name(variable)}",
            template="plotly_white",
        )
        fig_hist.update_layout(
            height=340,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col2:
        st.markdown(f"**Correlación de {pretty_name(variable)} con las demás variables**")
        corr_series = panel.corr(numeric_only=True)[variable].drop(variable).sort_values(
            key=lambda s: s.abs(),
            ascending=False,
        )
        corr_df = corr_series.round(3).to_frame("Correlación")
        corr_df.index = [pretty_name(idx) for idx in corr_df.index]
        st.dataframe(corr_df, use_container_width=True, height=340)

# ------------------------------------------------------------------
# Tab 3: Comparación de modelos
# ------------------------------------------------------------------

with tab3:
    st.subheader("Desempeño por modelo y horizonte")
    st.caption(
        "Aquí se comparan los modelos evaluados con validación walk-forward. "
        "La idea es ver cuál generaliza mejor según el horizonte de predicción."
    )

    try:
        metrics = pd.read_csv(MODELS_DIR / "metrics_by_horizon.csv")
    except FileNotFoundError:
        st.warning("No se encontró `metrics_by_horizon.csv`. Ejecuta el notebook 04 primero.")
        st.stop()

    meta = load_best_meta(MODELS_DIR)
    meta_df = pd.DataFrame([
        {
            "Horizonte": int(h),
            "Modelo ganador": v["model"],
            "RMSE": v["rmse"],
            "R²": v["r2"],
        }
        for h, v in meta.items()
    ]).sort_values("Horizonte")

    top1, top2 = st.columns(2)
    with top1:
        render_mini_card("Modelos evaluados", str(metrics["model"].nunique()))
    with top2:
        render_mini_card("Horizontes evaluados", str(metrics["horizon"].nunique()))

    st.markdown("### Tabla resumen de modelos ganadores")
    st.dataframe(meta_df.round(4), use_container_width=True, hide_index=True)

    pivot_rmse = metrics.pivot(index="model", columns="horizon", values="RMSE").round(4)
    pivot_r2 = metrics.pivot(index="model", columns="horizon", values="R2").round(4)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**RMSE por modelo × horizonte**")
        st.dataframe(pivot_rmse, use_container_width=True)
    with col2:
        st.markdown("**R² por modelo × horizonte**")
        st.dataframe(pivot_r2, use_container_width=True)

    fig_rmse = px.line(
        metrics,
        x="horizon",
        y="RMSE",
        color="model",
        markers=True,
        title="RMSE por horizonte",
        labels={"horizon": "Horizonte (meses)", "RMSE": "RMSE"},
        template="plotly_white",
    )
    fig_rmse.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_rmse, use_container_width=True)

    path_pp = MODELS_DIR / "metrics_pre_post_covid.csv"
    if path_pp.exists():
        st.markdown("### Comparación pre y post COVID")
        df_pp = pd.read_csv(path_pp)
        fig_pp = px.line(
            df_pp,
            x="horizon",
            y="RMSE",
            color="model",
            facet_col="regime",
            markers=True,
            title="RMSE pre vs post COVID",
            template="plotly_white",
        )
        fig_pp.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig_pp, use_container_width=True)

# ------------------------------------------------------------------
# Tab 4: Interpretabilidad (SHAP)
# ------------------------------------------------------------------

with tab4:
    st.subheader("Interpretabilidad del modelo")
    st.caption(
        "Las figuras fueron generadas en el notebook `05_shap.ipynb`. "
        "ARIMA no entra en este análisis porque es un modelo univariado."
    )

    horizon_choice = st.radio(
        "Horizonte a revisar",
        options=[1, 6],
        horizontal=True,
        index=0,
        help="Las visualizaciones SHAP disponibles fueron generadas para h=1 y h=6.",
    )

    def show_fig(name: str, caption: str):
        path = FIGURES_DIR / name
        if path.exists():
            st.image(str(path), caption=caption, use_container_width=True)
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
            f"Distribución y dirección de efectos — h = {horizon_choice}",
        )

    if horizon_choice == 1:
        st.markdown("### Análisis adicional para horizonte 1")
        col3, col4 = st.columns(2)
        with col3:
            show_fig(
                "shap_03_waterfall_last_h1.png",
                "Waterfall del pronóstico más reciente",
            )
        with col4:
            show_fig(
                "shap_04_pre_post_covid_h1.png",
                "Cambio de importancia pre vs post COVID",
            )

# ------------------------------------------------------------------
# Pie
# ------------------------------------------------------------------

st.markdown(
    """
    <div class="footer-box">
        Proyecto académico · MINE-4206 Aprendizaje Automático · Javier Mondragón, Jessica Joya, Alberth Pérez.<br>
        Fuentes: FRED (Federal Reserve Bank of St. Louis) y World Bank Pink Sheet.
    </div>
    """,
    unsafe_allow_html=True,
)