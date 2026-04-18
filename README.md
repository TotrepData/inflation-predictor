# US Inflation Predictor

Pipeline para pronóstico de la inflación mensual de Estados Unidos combinando modelos econométricos y técnicas de aprendizaje automático.

**App desplegada:** https://inflation-predictor-ckxg3us8ypve3wud9adsyj.streamlit.app

## Resumen

El proyecto estima la **inflación mensual** (variación porcentual del CPI) a múltiples horizontes (h = 1, 3, 6, 12 meses) utilizando indicadores macroeconómicos de FRED y el Banco Mundial.

**Usuario objetivo:** analistas de mesa de tesorería y gestión de portafolios de renta fija. Los horizontes seleccionados corresponden a las ventanas de rebalanceo más comunes en esa actividad.

**Marco académico:** Curso *Aprendizaje Automático (MINE-4206)*, Maestría en Ingeniería de Información, Universidad de los Andes.

**Equipo:** Javier Mondragón, Jessica Joya, Alberth Pérez.

## Modelos

Se compara un benchmark econométrico contra tres modelos de ML representativos de las dos familias predominantes en la literatura:

| Modelo | Familia | Rol |
|---|---|---|
| ARIMA(1,1,1) | Econometría clásica | Benchmark |
| Elastic Net | Regularización lineal | Controla multicolinealidad entre PPI, M2 y Retail Sales |
| Random Forest | Árboles (bagging) | Captura no linealidad |
| XGBoost | Árboles (boosting) | Fuerte en períodos de alta volatilidad (Naghi et al., 2024) |

Validación mediante **walk-forward expanding window**. Interpretabilidad con **SHAP**.

## Dataset

408 observaciones mensuales (ene-1992 → dic-2025), 12 variables, sin nulos.

| Variable | Código | Fuente |
|---|---|---|
| CPI (objetivo) | CPIAUCSL | FRED |
| Federal Funds Rate | FEDFUNDS | FRED |
| Unemployment Rate | UNRATE | FRED |
| Industrial Production | INDPRO | FRED |
| Money Supply M2 | M2SL | FRED |
| Retail Sales | RRSFS | FRED |
| Capacity Utilization | TCU | FRED |
| 10Y Treasury Yield | GS10 | FRED |
| Producer Price Index | PPIACO | FRED |
| Consumer Sentiment | UMCSENT | FRED |
| Oil Price WTI | DCOILWTICO | FRED (agregado a mensual) |
| Gold Price | Pink Sheet | World Bank |

**Nota metodológica:** el CPI de octubre 2025 no fue publicado por el BLS al momento de descarga (probable retraso por shutdown del gobierno de EE.UU.). Se imputa con forward-fill, consistente con la metodología declarada en la propuesta.

## Estructura del proyecto

```
inflation-predictor/
├── data/
│   ├── raw/                    # Datos crudos (FRED, World Bank)
│   └── processed/              # Dataset integrado listo para modelar
├── figures/                    # Gráficos de EDA y modelado
├── models/                     # Modelos entrenados (.joblib)
├── notebooks/
│   ├── 01_data_engineering.ipynb   # Ingesta, limpieza, integración
│   ├── 02_eda.ipynb                # Análisis exploratorio
│   ├── 03_feature_engineering.ipynb  # Lags, MAs, MoM/YoY
│   ├── 04_modeling.ipynb             # ARIMA + 3 ML, walk-forward
│   └── 05_shap.ipynb                 # Interpretabilidad
├── mlruns/                     # Tracking de experimentos (MLflow)
├── app/                        # Aplicación Streamlit (pronóstico en vivo)
├── .env                        # FRED_API_KEY (no versionado)
├── requirements.txt
└── README.md
```

## Feature engineering

Variables derivadas generadas en `03_feature_engineering.ipynb`:

- **Rezagos** (1, 3, 6, 12 meses) por variable
- **Promedios móviles** (3, 6, 12 meses)
- **Variaciones porcentuales** mes a mes (MoM) y año a año (YoY)
- **Variables temporales**: mes, trimestre
- **Transformación logarítmica** para `gold_price` (no estacionaria ni en 1ª diferencia)
- **Target:** `inflation_mom = CPI.pct_change() * 100`

## Evaluación

- **Métricas:** RMSE, MAE, R² por modelo × horizonte
- **Validación:** walk-forward expanding window (entrenamiento solo con datos pasados)
- **Análisis comparativo:** pre-pandemia (1992–2019) vs post-pandemia (2020–2025)

## Quick Start

```bash
git clone https://github.com/TotrepData/inflation-predictor.git
cd inflation-predictor

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "FRED_API_KEY=tu_key_aqui" > .env

jupyter notebook  # correr notebooks 01 → 05 en orden
```

## Aplicación Streamlit

**Demo en línea:** https://inflation-predictor-ckxg3us8ypve3wud9adsyj.streamlit.app

Dashboard con pronóstico vigente usando datos frescos de FRED y modelos pre-entrenados. Cuatro vistas:

1. **Pronóstico vigente** — forecast del CPI a 1, 3, 6 y 12 meses, con comparación frente a la meta del 2 % de la Reserva Federal.
2. **Explorar variables macro** — series temporales, distribuciones y correlaciones por variable.
3. **Comparación de modelos** — tablas y gráficas RMSE / MAE / R² por modelo × horizonte, incluida la segmentación pre/post COVID.
4. **Interpretabilidad (SHAP)** — importancia global, distribución de efectos y waterfall del pronóstico más reciente.

### Correr localmente

```bash
cd app
pip install -r requirements.txt
cd ..
streamlit run app/app.py
```

La app lee `FRED_API_KEY` desde `.env` (en local) o `st.secrets` (en Streamlit Cloud). Si no hay key configurada, recurre al snapshot local `data/processed/dataset_modelo.csv`.

### Desplegar en Streamlit Community Cloud

1. Crear una app nueva en [share.streamlit.io](https://share.streamlit.io) conectada a este repositorio.
2. Configurar:
   - **Repository:** `TotrepData/inflation-predictor`
   - **Branch:** `master`
   - **Main file path:** `app/app.py`
   - **Python version:** 3.10 o 3.11
3. En *Advanced settings → Secrets* agregar:
   ```toml
   FRED_API_KEY = "tu_api_key_aqui"
   ```
4. Deploy. Streamlit Cloud detecta automáticamente `app/requirements.txt`.

## Stack técnico

**Datos:** pandas, numpy, requests, openpyxl
**ML:** scikit-learn, xgboost, statsmodels, shap, mlflow
**Visualización:** matplotlib, seaborn, plotly
**App:** streamlit

## Referencias

- Fondo Monetario Internacional (2024). *Mending the Crystal Ball: Enhanced Inflation Forecasts with Machine Learning.* IMF Working Paper WP/24/206.
- Medeiros, M. C., Vasconcelos, G. F., Veiga, Á., & Zilberman, E. (2021). Forecasting inflation in a data-rich environment: The benefits of machine learning methods. *Journal of Business & Economic Statistics*, 39(1), 98–119.
- Naghi, A., Castle, J. L., Doornik, J. A., & Hendry, D. F. (2024). The benefits of forecasting inflation with machine learning: New evidence. *Journal of Applied Econometrics.*
- Nguyen, T. T., Nguyen, H. G., Lee, J. Y., Wang, Y. L., & Tsai, C. S. (2023). The consumer price index prediction using machine learning approaches: Evidence from the United States. *Heliyon*, 9(10), e20730.
- Lundberg, S. M., & Lee, S. I. (2017). A unified approach to interpreting model predictions. *NeurIPS 30.*

## Licencia

MIT
