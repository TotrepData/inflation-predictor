# US Inflation Predictor

Pipeline para el pronóstico de inflación mensual de Estados Unidos combinando modelos econométricos y técnicas de aprendizaje automático, con una prueba de concepto de despliegue cloud-native en AWS.

**App desplegada:** https://inflation-predictor-ckxg3us8ypve3wud9adsyj.streamlit.app  
**Repositorio:** https://github.com/TotrepData/inflation-predictor

---

## Contenido

- [Resumen](#resumen)
- [Modelos](#modelos)
- [Dataset](#dataset)
- [Feature Engineering](#feature-engineering)
- [Evaluación](#evaluación)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Quick Start](#quick-start)
- [Aplicación Streamlit](#aplicación-streamlit)
- [PoC Cloud-Native en AWS](#poc-cloud-native-en-aws)
- [Stack técnico](#stack-técnico)
- [Referencias](#referencias)
- [Licencia](#licencia)

---

## Resumen

El proyecto estima la **inflación mensual** (variación porcentual del CPI) a múltiples horizontes (h = 1, 3, 6, 12 meses) utilizando indicadores macroeconómicos de FRED y el Banco Mundial.

**Usuario objetivo:** analistas de mesa de tesorería y gestión de portafolios de renta fija. Los horizontes seleccionados corresponden a las ventanas de rebalanceo más comunes en esa actividad.

**Marco académico:** Cursos *Análisis con Machine Learning (MINE-4206)* y *Soluciones de Datos en la Nube (MINE4105)*, Maestría en Ingeniería de Información, Universidad de los Andes.

---

## Modelos

Se compara un benchmark econométrico contra tres modelos de ML representativos de las dos familias predominantes en la literatura:

| Modelo | Familia | Rol |
|---|---|---|
| ARIMA(1,1,1) | Econometría clásica | Benchmark |
| Elastic Net | Regularización lineal | Controla multicolinealidad entre PPI, M2 y Retail Sales |
| Random Forest | Árboles (bagging) | Captura no linealidad |
| XGBoost | Árboles (boosting) | Fuerte en períodos de alta volatilidad |

Validación mediante **walk-forward expanding window**. Interpretabilidad con **SHAP**.

### Resultados (Random Forest h=1)

| Métrica | Valor |
|---|---|
| RMSE | 0.209 |
| MAE | 0.153 |
| R² | 0.468 |

---

## Dataset

408 observaciones mensuales (ene-1992 a dic-2025), 12 variables, sin nulos.

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
| Oil Price WTI | DCOILWTICO | FRED |
| Gold Price | Pink Sheet | World Bank |

**Nota metodológica:** el CPI de octubre 2025 no fue publicado por el BLS al momento de descarga (probable retraso por shutdown del gobierno de EE.UU.). Se imputa con forward-fill, consistente con la metodología declarada en la propuesta.

---

## Feature Engineering

Variables derivadas generadas en `03_feature_engineering.ipynb`:

- Rezagos (1, 3, 6, 12 meses) por variable
- Promedios móviles (3, 6, 12 meses)
- Variaciones porcentuales mes a mes (MoM) y año a año (YoY)
- Variables temporales: mes, trimestre
- Transformación logarítmica para `gold_price`
- Target: `inflation_mom = CPI.pct_change() * 100`

---

## Evaluación

- **Métricas:** RMSE, MAE, R² por modelo y horizonte
- **Validación:** walk-forward expanding window (entrenamiento solo con datos pasados)
- **Análisis comparativo:** pre-pandemia (1992-2019) vs post-pandemia (2020-2025)

---

## Estructura del proyecto

```
inflation-predictor/
├── data/
│   ├── raw/                        # Datos crudos (FRED, World Bank)
│   └── processed/                  # Dataset integrado listo para modelar
├── figures/                        # Gráficos de EDA y modelado
├── models/                         # Modelos entrenados (.joblib)
├── notebooks/
│   ├── 01_data_engineering.ipynb   # Ingesta, limpieza, integración
│   ├── 02_eda.ipynb                # Análisis exploratorio
│   ├── 03_feature_engineering.ipynb
│   ├── 04_modeling.ipynb           # ARIMA + 3 ML, walk-forward
│   └── 05_shap.ipynb               # Interpretabilidad
├── mlruns/                         # Tracking de experimentos (MLflow)
├── app/                            # Aplicación Streamlit
├── .env                            # FRED_API_KEY (no versionado)
├── poc_inflation_endpoint.ipynb    # Notebook PoC cloud-native AWS
├── requirements.txt
└── README.md
```

---

## Quick Start

```bash
git clone https://github.com/TotrepData/inflation-predictor.git
cd inflation-predictor

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "FRED_API_KEY=tu_key_aqui" > .env

jupyter notebook  # ejecutar notebooks 01 a 05 en orden
```

---

## Aplicación Streamlit

**Demo en línea:** https://inflation-predictor-ckxg3us8ypve3wud9adsyj.streamlit.app

Dashboard con pronóstico vigente usando datos frescos de FRED y modelos pre-entrenados. Cuatro vistas:

1. **Pronóstico vigente** — forecast del CPI a 1, 3, 6 y 12 meses con comparación frente a la meta del 2% de la Reserva Federal.
2. **Explorar variables macro** — series temporales, distribuciones y correlaciones.
3. **Comparación de modelos** — tablas y gráficas RMSE / MAE / R² por modelo y horizonte, segmentadas pre/post COVID.
4. **Interpretabilidad (SHAP)** — importancia global, distribución de efectos y waterfall del pronóstico más reciente.

### Correr localmente

```bash
cd app
pip install -r requirements.txt
cd ..
streamlit run app/app.py
```

### Desplegar en Streamlit Community Cloud

1. Crear una app en [share.streamlit.io](https://share.streamlit.io) conectada al repositorio.
2. Configurar:
   - Repository: `TotrepData/inflation-predictor`
   - Branch: `master`
   - Main file path: `app/app.py`
   - Python version: 3.10 o 3.11
3. En Advanced settings → Secrets agregar:
   ```toml
   FRED_API_KEY = "tu_api_key_aqui"
   ```

---

## PoC Cloud-Native en AWS

Prueba de concepto que valida el requisito de latencia del curso MINE4105: predicción de inflación end-to-end en menos de 5 segundos, desplegada sobre AWS con arquitectura medallón.

### Arquitectura

```
FRED API → S3 Bronze/Silver/Gold → SageMaker Notebook → Random Forest h1 → Bedrock Claude Haiku 4.5 → Narrativa ejecutiva
```

### Infraestructura

| Servicio | Recurso | Propósito |
|---|---|---|
| Amazon S3 | `poc-inflation-predictor` | Data lake con capas Silver (datos) y Gold (modelos) |
| Amazon SageMaker | `poc-inflation-nb` (ml.t3.medium) | Notebook de inferencia cloud-native |
| Amazon Bedrock | Claude Haiku 4.5 | Generación de narrativa ejecutiva en lenguaje natural |
| AWS IAM | Usuario `poc-inflation` | Acceso con privilegios mínimos (S3, SageMaker, Bedrock, CloudWatch) |

### Resultados

| Criterio | Meta | Resultado |
|---|---|---|
| Latencia ML p50 | — | 45 ms |
| Latencia ML p95 | < 2000 ms | 47 ms |
| Latencia e2e p95 | < 5000 ms | < 5000 ms |
| Predicción CPI MoM h1 | — | 0.2305% (ene-2026) |
| R² Random Forest h1 | > 0.45 | 0.468 |

### Estado actual

Las celdas 1, 2 y 3 están operativas y validadas. La celda 4 (narrativa con Bedrock) está pendiente por una restricción de quota en cuenta nueva de AWS. Se abrió el caso de soporte #177951229800224 el 22 de mayo de 2026 solicitando aumento de quota para Claude Haiku 4.5. Pendiente revisar plan B (API Anthropic).

### Reproducir la PoC

#### Pre-requisitos

- Cuenta AWS activa con acceso a SageMaker y Bedrock
- FRED API Key (gratuita en https://fred.stlouisfed.org/docs/api/api_key.html)
- AWS CLI v2 instalado y configurado

#### 1. Configurar credenciales AWS

```bash
aws configure
# AWS Access Key ID:     <access key del usuario poc-inflation>
# AWS Secret Access Key: <secret key>
# Default region:        us-east-1
# Default output format: json
```

Verificar autenticación:

```bash
aws sts get-caller-identity
```

#### 2. Crear bucket S3 y subir artefactos

```bash
aws s3 mb s3://poc-inflation-predictor --region us-east-1
aws s3 cp data/processed/ s3://poc-inflation-predictor/silver/ --recursive
aws s3 cp models/ s3://poc-inflation-predictor/models/ --recursive
```

#### 3. Levantar notebook en SageMaker

Ir a AWS Console → Amazon SageMaker AI → Notebooks → `poc-inflation-nb` → Open JupyterLab.

El repositorio ya está clonado en la instancia. Abrir `poc_inflation_endpoint.ipynb` y ejecutar las celdas en orden.

#### 4. Configurar FRED API Key en el notebook

```python
import os
os.environ['FRED_API_KEY'] = 'tu_key_aqui'
```

### Acceso para el equipo

- Console URL: https://793239448746.signin.aws.amazon.com/console
- Usuario IAM: `poc-inflation`
- Región: us-east-1

Solicitar credenciales al administrador de la cuenta.

---

## Stack técnico

| Capa | Tecnologías |
|---|---|
| Datos | pandas, numpy, requests, openpyxl |
| ML | scikit-learn, xgboost, statsmodels, shap, mlflow |
| Visualización | matplotlib, seaborn, plotly |
| App | streamlit |
| Cloud | AWS S3, SageMaker, Bedrock, IAM, CloudWatch |

---

## Referencias

- Fondo Monetario Internacional (2024). *Mending the Crystal Ball: Enhanced Inflation Forecasts with Machine Learning.* IMF Working Paper WP/24/206.
- Medeiros, M. C., Vasconcelos, G. F., Veiga, Á., & Zilberman, E. (2021). Forecasting inflation in a data-rich environment: The benefits of machine learning methods. *Journal of Business & Economic Statistics*, 39(1), 98-119.
- Naghi, A., Castle, J. L., Doornik, J. A., & Hendry, D. F. (2024). The benefits of forecasting inflation with machine learning: New evidence. *Journal of Applied Econometrics.*
- Nguyen, T. T., et al. (2023). The consumer price index prediction using machine learning approaches: Evidence from the United States. *Heliyon*, 9(10), e20730.
- Lundberg, S. M., & Lee, S. I. (2017). A unified approach to interpreting model predictions. *NeurIPS 30.*

---

## Licencia

MIT
