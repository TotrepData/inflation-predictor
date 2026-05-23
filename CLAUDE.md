# PoC Inflation Predictor — Contexto para Claude Code

## Objetivo
Implementar el pipeline cloud-native end-to-end de la PoC del proyecto MINE4105 (Soluciones de Datos en la Nube, Uniandes). El flujo final debe ser:

```
FRED API → Lambda Collector → S3 Bronze (parquet)
                            → Lambda ETL       → S3 Silver (dataset_modelo.parquet)
                                               → Lambda Features → S3 Gold (features.parquet)
                                                                 → SageMaker Notebook (inferencia RF + narrativa Anthropic API)
```

---

## Infraestructura AWS ya desplegada

| Recurso         | Valor                                   |
|----------------|-----------------------------------------|
| AWS Account    | 793239448746                            |
| Región         | us-east-1                               |
| S3 Bucket      | `poc-inflation-predictor`               |
| IAM User       | `poc-inflation`                         |
| SageMaker NB   | `poc-inflation-nb` (ml.t3.medium)       |

### Estructura actual del bucket S3
```
poc-inflation-predictor/
  silver/
    features.csv        ← datos procesados (395 filas × 124 columnas)
  models/
    best_RandomForest_h1.joblib
    best_RandomForest_h3.joblib
    best_RandomForest_h6.joblib
    best_RandomForest_h12.joblib
    best_ElasticNet_h1.joblib  ... (16 modelos en total)
    best_model_per_horizon.json
    metrics_by_horizon.csv
```

### Estructura objetivo del bucket S3 (a crear)
```
poc-inflation-predictor/
  bronze/                              ← CSV, fiel a la fuente (mismo formato que data/raw/)
    cpi_raw.csv
    fed_rate_raw.csv
    oil_price_raw.csv                  ← diario, sin agregar todavía
    unemployment_raw.csv
    industrial_production_raw.csv
    money_supply_m2_raw.csv
    retail_sales_raw.csv
    capacity_utilization_raw.csv
    treasury_10y_raw.csv
    ppi_raw.csv
    consumer_sentiment_raw.csv
    gold_price_raw.csv                 ← World Bank (subido manualmente como semilla)
  silver/
    dataset_modelo.parquet             ← merge + limpieza de los 12 bronze
    features.csv                       ← mantener existente para no romper NB actual
  gold/
    features.parquet                   ← feature engineering completo, listo para ML
  models/
    ... (sin cambios)
```

**Principio de formato por capa:**
- Bronze = CSV — mismo formato que la fuente, cero transformación, máxima fidelidad
- Silver = Parquet — primera vez que se agrega valor (merge + limpieza), se optimiza formato
- Gold   = Parquet — feature engineering, listo para ML y consultas analíticas

---

## Flujo de datos en los notebooks (referencia para las Lambdas)

```
NB 01 (data_engineering):
  Lee:    data/raw/cpi_raw.csv
          data/raw/fed_rate_raw.csv
          data/raw/oil_price_raw.csv   ← diario, se mensualiza por promedio
          data/raw/unemployment_raw.csv
          data/raw/industrial_production_raw.csv
          data/raw/money_supply_m2_raw.csv
          data/raw/retail_sales_raw.csv
          data/raw/capacity_utilization_raw.csv
          data/raw/treasury_10y_raw.csv
          data/raw/ppi_raw.csv
          data/raw/consumer_sentiment_raw.csv
          data/raw/gold_price_raw.csv  ← extraído del Excel World Bank (manual)
  Escribe: data/processed/dataset_modelo.csv  (408 filas × 13 columnas, rango 1992-2025)

NB 02 (EDA): solo lee dataset_modelo.csv, no escribe nada

NB 03 (feature_engineering):
  Lee:    data/processed/dataset_modelo.csv
  Escribe: data/processed/features.csv  (395 filas × 124 columnas)

NB 04 (modeling): lee features.csv, escribe models/*.joblib y métricas
NB 05 (SHAP):     lee features.csv + models/*.joblib, solo visualizaciones
```

**Mapeo notebooks → Lambdas:**
- Lambda Collector = NB 01 parte 1: descarga las 11 series de FRED → `bronze/fred_raw.parquet`
- Lambda ETL       = NB 01 parte 2: merge + limpieza de fred_raw + gold → `silver/dataset_modelo.parquet`
- Lambda Features  = NB 03 completo: feature engineering → `gold/features.parquet`

**gold_price_raw.csv**: viene de un Excel del World Bank que se recibe manualmente.
Ya existe en `data/raw/gold_price_raw.csv`. El script de deploy lo sube una vez a
`s3://poc-inflation-predictor/bronze/gold_price_raw.parquet` como dato semilla.
No intentar descargarlo automáticamente desde el Lambda.

## Archivos relevantes del repositorio local

```
inflation-predictor/
  notebooks/
    01_data_engineering.ipynb   ← lógica para Lambda Collector + Lambda ETL
    03_feature_engineering.ipynb ← lógica para Lambda Features
  data/
    raw/
      cpi_raw.csv               ← FRED CPIAUCSL
      fed_rate_raw.csv          ← FRED FEDFUNDS
      oil_price_raw.csv         ← FRED DCOILWTICO (diario)
      unemployment_raw.csv      ← FRED UNRATE
      industrial_production_raw.csv ← FRED INDPRO
      money_supply_m2_raw.csv   ← FRED M2SL
      retail_sales_raw.csv      ← FRED RRSFS
      capacity_utilization_raw.csv  ← FRED TCU
      treasury_10y_raw.csv      ← FRED GS10
      ppi_raw.csv               ← FRED PPIACO
      consumer_sentiment_raw.csv ← FRED UMCSENT
      gold_price_raw.csv        ← World Bank (extraído del Excel, ya procesado)
      CMO-Historical-Data-Monthly.xlsx ← Excel original World Bank (no usar en Lambda)
    processed/
      dataset_modelo.csv        ← output NB 01 (408 filas × 13 col, referencia)
      features.csv              ← output NB 03 (395 filas × 124 col, referencia)
  models/
    best_RandomForest_h1.joblib ← modelo entrenado (ya en S3, no tocar)
  poc_inflation_endpoint.ipynb  ← PoC notebook (celdas 1-3 OK, celda 4 falla por Bedrock)
```

---

## Tarea 1 — Crear Lambda Collector (`fn-poc-collector`)

**Responsabilidad:** Descargar las 11 series de FRED API y guardarlas como parquet en S3 Bronze.

**Fuente de referencia:** `notebooks/01_data_engineering.ipynb`, celdas 7-8 (descarga FRED) y celda 19 (agregación mensual del oil price).

**Variables de entorno necesarias:**
- `FRED_API_KEY` — API key de FRED (gratuita en fred.stlouisfed.org)
- `S3_BUCKET` — `poc-inflation-predictor`

**Series a descargar (exactamente estas):**
```python
series_fred = {
    "CPIAUCSL": "cpi",
    "FEDFUNDS": "fed_rate",
    "DCOILWTICO": "oil_price",   # frecuencia diaria → agregar a mensual por promedio
    "UNRATE": "unemployment",
    "INDPRO": "industrial_production",
    "M2SL": "money_supply_m2",
    "RRSFS": "retail_sales",
    "TCU": "capacity_utilization",
    "GS10": "treasury_10y",
    "PPIACO": "ppi",
    "UMCSENT": "consumer_sentiment"
}
```

**Output:** un CSV por serie en Bronze, espejando exactamente `data/raw/` local:
- `s3://poc-inflation-predictor/bronze/cpi_raw.csv`
- `s3://poc-inflation-predictor/bronze/fed_rate_raw.csv`
- `s3://poc-inflation-predictor/bronze/oil_price_raw.csv`  (diario, sin agregar todavía)
- ... (un archivo por cada serie del dict `series_fred`)
- Guardar con las columnas originales de FRED (`date`, `value`) sin renombrar
- El `gold_price_raw.csv` **no** lo genera este Lambda — ya está en Bronze como semilla

**Nota sobre gold_price:** El precio del oro viene del World Bank (archivo Excel manual). Para la PoC, usar el archivo local `data/raw/gold_price_raw.csv` que ya existe en el repo. El Lambda debe leerlo de `s3://poc-inflation-predictor/bronze/gold_price_raw.parquet` (subirlo primero como parte del deploy). No intentar descargar el Excel de World Bank automáticamente.

**Código clave del notebook 01 a adaptar:**
```python
import requests
import pandas as pd
import numpy as np

url = "https://api.stlouisfed.org/fred/series/observations"

def descargar_serie(codigo, api_key):
    params = {"series_id": codigo, "api_key": api_key, "file_type": "json"}
    response = requests.get(url, params=params)
    data = response.json()
    df = pd.DataFrame(data["observations"])[['date', 'value']]
    df['date'] = pd.to_datetime(df['date'])
    df['value'] = df['value'].replace('.', np.nan)
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    return df

# Oil price es diario → agregar a mensual
def mensualizar_oil(df_oil):
    df_oil['month'] = df_oil['date'].dt.to_period('M').dt.to_timestamp()
    return df_oil.groupby('month').agg({'oil_price': 'mean'}).reset_index().rename(columns={'month': 'date'})
```

---

## Tarea 2 — Crear Lambda ETL (`fn-poc-etl`)

**Responsabilidad:** Leer `bronze/fred_raw.parquet` y `bronze/gold_price_raw.parquet`, hacer merge, limpiar y guardar `silver/dataset_modelo.parquet`.

**Fuente de referencia:** `notebooks/01_data_engineering.ipynb`, celdas 21-26 (merge, filtro de fechas, forward-fill).

**Código clave del notebook 01 a adaptar:**
```python
# Merge de todas las series
df_final = df_fred.merge(df_gold, on='date', how='outer')
df_final = df_final.sort_values('date').reset_index(drop=True)

# Filtrar rango con cobertura completa
fecha_min = pd.Timestamp('1992-01-01')
fecha_max = df_gold['date'].max()  # último dato del World Bank
df_modelo = df_final[(df_final['date'] >= fecha_min) & (df_final['date'] <= fecha_max)].copy()

# Forward-fill para huecos internos (ej. CPI de oct-2025 no publicado)
df_modelo = df_modelo.sort_values('date').ffill().dropna().reset_index(drop=True)
```

**Output:** `s3://poc-inflation-predictor/silver/dataset_modelo.parquet`
(primera aparición de parquet — aquí es donde tiene sentido optimizar el formato)

---

## Tarea 3 — Crear Lambda Features (`fn-poc-features`)

**Responsabilidad:** Leer `silver/dataset_modelo.parquet`, ejecutar feature engineering y guardar `gold/features.parquet`.

**Fuente de referencia:** `notebooks/03_feature_engineering.ipynb` — contiene las funciones exactas.

**Código clave del notebook 03 a adaptar (copiar estas funciones tal cual):**

```python
import numpy as np
import pandas as pd

LAGS = [1, 3, 6, 12]
MOVING_AVG_WINDOWS = [3, 6, 12]

def add_lags(df_in, lags):
    out = {}
    for col in df_in.columns:
        for k in lags:
            out[f'{col}_lag{k}'] = df_in[col].shift(k)
    return pd.DataFrame(out, index=df_in.index)

def add_moving_averages(df_in, windows):
    out = {}
    for col in df_in.columns:
        shifted = df_in[col].shift(1)
        for w in windows:
            out[f'{col}_ma{w}'] = shifted.rolling(window=w, min_periods=w).mean()
    return pd.DataFrame(out, index=df_in.index)

def add_pct_changes(df_in, exclude=None):
    exclude = set(exclude or [])
    out = {}
    for col in df_in.columns:
        if col in exclude:
            continue
        shifted = df_in[col].shift(1)
        out[f'{col}_mom'] = shifted.pct_change(periods=1) * 100
        out[f'{col}_yoy'] = shifted.pct_change(periods=12) * 100
    return pd.DataFrame(out, index=df_in.index)

def build_features(df):
    df = df.set_index('date') if 'date' in df.columns else df
    
    target = df['cpi'].pct_change() * 100
    target.name = 'inflation_mom'
    
    # Features especiales del oro
    gold_log = np.log(df['gold_price'])
    df_gold = pd.DataFrame({
        'gold_price_log_lag1':   gold_log.shift(1),
        'gold_price_log_diff1':  gold_log.diff(1).shift(1),
        'gold_price_log_diff12': gold_log.diff(12).shift(1),
    }, index=df.index)
    
    # Features temporales
    month = df.index.month
    quarter = df.index.quarter
    df_time = pd.DataFrame({
        'month_sin': np.sin(2 * np.pi * month / 12),
        'month_cos': np.cos(2 * np.pi * month / 12),
    }, index=df.index)
    for q in [1, 2, 3, 4]:
        df_time[f'quarter_{q}'] = (quarter == q).astype(int)
    
    # Features autorregresivos del target
    autoreg = {}
    for k in [1, 3, 6, 12]:
        autoreg[f'inflation_mom_lag{k}'] = target.shift(k)
    target_shifted1 = target.shift(1)
    for w in [3, 6, 12]:
        autoreg[f'inflation_mom_ma{w}'] = target_shifted1.rolling(window=w, min_periods=w).mean()
    df_autoreg = pd.DataFrame(autoreg, index=df.index)
    
    # Ensamblar todo
    df_lags = add_lags(df, LAGS)
    df_ma   = add_moving_averages(df, MOVING_AVG_WINDOWS)
    df_pct  = add_pct_changes(df, exclude=['cpi'])
    
    features = pd.concat([df_lags, df_ma, df_pct, df_gold, df_time, df_autoreg], axis=1)
    dataset = features.copy()
    dataset['inflation_mom'] = target
    dataset = dataset.dropna()
    
    return dataset.reset_index()  # date vuelve a ser columna
```

**Output:** `s3://poc-inflation-predictor/gold/features.parquet`

---

## Tarea 4 — Actualizar `poc_inflation_endpoint.ipynb`

### Celda 2 — Cambiar fuente de datos de Silver CSV a Gold Parquet

Reemplazar la línea:
```python
data_obj = s3.get_object(Bucket=BUCKET, Key='silver/features.csv')
df = pd.read_csv(io.BytesIO(data_obj['Body'].read()))
```

Por:
```python
data_obj = s3.get_object(Bucket=BUCKET, Key='gold/features.parquet')
df = pd.read_parquet(io.BytesIO(data_obj['Body'].read()))
```

También instalar pyarrow en la Celda 1:
```python
subprocess.run(['pip', 'install', 'scikit-learn', 'pyarrow', '-q'])
```

### Celda 4 — Reemplazar Bedrock por Anthropic API (Plan B)

El problema actual: `ThrottlingException` — la cuenta nueva de AWS no tiene quota aprobada para Bedrock. La solución es usar la API de Anthropic directamente.

**Reemplazar toda la celda 4 por este código:**

```python
# ============================================================
# Celda 4: Narrativa ejecutiva — Anthropic API (Plan B)
# Bedrock bloqueado por quota en cuenta nueva (caso #177951229800224)
# ============================================================

import subprocess
subprocess.run(['pip', 'install', 'anthropic', '-q'], capture_output=True)
import anthropic

# ANTHROPIC_API_KEY debe estar configurada como variable de entorno
# En SageMaker: Kernel → Environment Variables, o:
# import os; os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-...'

client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno

prompt = f"""Eres un analista macroeconómico senior.
El modelo de Machine Learning predice una inflación mensual (CPI MoM) de {pred:.4f}% para enero 2026.
Contexto: Fed Rate actual ~3.88%, precio del petróleo ~$60 USD, tendencia reciente de desaceleración.
En máximo 3 oraciones, genera una narrativa ejecutiva para un Portfolio Manager."""

t0 = time.time()

message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=300,
    messages=[{"role": "user", "content": prompt}]
)

latencia_llm = (time.time() - t0) * 1000
narrativa = message.content[0].text

latencia_e2e = p95 + latencia_llm

print(f"Latencia LLM (Anthropic): {latencia_llm:.0f} ms")
print(f"Latencia e2e total (ML p95 + LLM): {latencia_e2e:.0f} ms")
print(f"Criterio e2e < 5000ms: {'CUMPLE' if latencia_e2e < 5000 else 'NO CUMPLE'}")
print(f"\n--- Narrativa ejecutiva ---\n{narrativa}")
```

---

## Tarea 5 — Empaquetado y despliegue de las Lambdas

### Opción de packaging recomendada
Usar el **managed layer de AWS SDK for Pandas** (incluye pandas, numpy, pyarrow) + deployment package pequeño con fredapi y requests.

Layer ARN (us-east-1, Python 3.11):
```
arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:20
```
Verificar la versión más reciente en: https://aws-sdk-pandas.readthedocs.io/en/stable/install.html#aws-lambda-layer

### Estructura de carpetas a crear
```
lambdas/
  collector/
    handler.py          ← código del Lambda 1
    requirements.txt    ← fredapi, requests (pandas ya viene del layer)
  etl/
    handler.py          ← código del Lambda 2
    requirements.txt    ← vacío o solo pyarrow si no viene del layer
  features/
    handler.py          ← código del Lambda 3
    requirements.txt    ← vacío
scripts/
  deploy_lambdas.sh     ← comandos AWS CLI para crear/actualizar las 3 funciones
  upload_bronze_seed.sh ← sube gold_price_raw.parquet al bucket (dato semilla)
```

### Parámetros comunes de las Lambdas
- Runtime: `python3.11`
- Timeout: `300` segundos (5 minutos) — suficiente para descargar FRED
- Memory: `512 MB`
- Layer: AWSSDKPandas-Python311 (ver ARN arriba)
- Rol IAM: crear uno nuevo `poc-inflation-lambda-role` con políticas:
  - `AmazonS3FullAccess` (o política específica solo para `poc-inflation-predictor`)
  - `AWSLambdaBasicExecutionRole`

### Variables de entorno de cada Lambda
- `fn-poc-collector`: `FRED_API_KEY=<key>`, `S3_BUCKET=poc-inflation-predictor`
- `fn-poc-etl`: `S3_BUCKET=poc-inflation-predictor`
- `fn-poc-features`: `S3_BUCKET=poc-inflation-predictor`

---

## Tarea 6 — Script de prueba end-to-end (opcional pero recomendado para el video)

Crear `scripts/run_pipeline.sh` que:
1. Invoque Lambda Collector vía AWS CLI
2. Espere 30 segundos
3. Invoque Lambda ETL
4. Espere 30 segundos
5. Invoque Lambda Features
6. Imprima los archivos resultantes en S3

```bash
#!/bin/bash
echo "=== Ejecutando pipeline PoC ==="

echo "1. Collector..."
aws lambda invoke --function-name fn-poc-collector \
  --payload '{}' --cli-binary-format raw-in-base64-out \
  /tmp/collector_out.json
cat /tmp/collector_out.json

sleep 5

echo "2. ETL..."
aws lambda invoke --function-name fn-poc-etl \
  --payload '{}' --cli-binary-format raw-in-base64-out \
  /tmp/etl_out.json
cat /tmp/etl_out.json

sleep 5

echo "3. Features..."
aws lambda invoke --function-name fn-poc-features \
  --payload '{}' --cli-binary-format raw-in-base64-out \
  /tmp/features_out.json
cat /tmp/features_out.json

echo ""
echo "=== Archivos en S3 ==="
aws s3 ls s3://poc-inflation-predictor/ --recursive | grep -E "bronze|silver|gold"
```

---

## Notas importantes

1. **FRED API Key**: Gratuita en https://fred.stlouisfed.org/docs/api/api_key.html — necesaria para el Lambda Collector.

2. **Gold price (World Bank)**: El archivo Excel del Banco Mundial no se puede descargar automáticamente (lo reciben por correo según la propuesta). Ya existe `data/raw/gold_price_raw.csv` en el repo local. El script de deploy debe subirlo a `s3://poc-inflation-predictor/bronze/gold_price_raw.parquet` como dato semilla.

3. **Anthropic API Key**: Necesaria para la Celda 4. Obtenerla en https://console.anthropic.com — configurarla como variable de entorno en SageMaker antes de ejecutar el notebook.

4. **Modelo h1**: El modelo `best_RandomForest_h1.joblib` ya está en `s3://poc-inflation-predictor/models/` y no necesita ser re-entrenado.

5. **La Celda 3 del notebook ya usa `FEATURE_COLS = [c for c in df.columns if c not in ['date', 'inflation_mom']]`** — funciona con cualquier DataFrame que tenga esas columnas, por lo que leer de `gold/features.parquet` es compatible sin cambios en esa celda.

6. **Compatibilidad de columnas**: El parquet de Gold debe tener exactamente las mismas columnas que el `silver/features.csv` actual (122 features + `date` + `inflation_mom`). La función `build_features` del notebook 03 produce exactamente eso.

---

## Orden de ejecución sugerido para Claude Code

1. Crear `lambdas/collector/handler.py` — Lambda Collector
2. Crear `lambdas/etl/handler.py` — Lambda ETL  
3. Crear `lambdas/features/handler.py` — Lambda Features
4. Crear `requirements.txt` de cada Lambda
5. Crear `scripts/deploy_lambdas.sh` con comandos AWS CLI
6. Crear `scripts/upload_bronze_seed.sh` para subir gold_price_raw.parquet
7. Actualizar `poc_inflation_endpoint.ipynb` — Celda 1 (pyarrow), Celda 2 (leer parquet), Celda 4 (Anthropic API)
8. Crear `scripts/run_pipeline.sh` para prueba end-to-end
