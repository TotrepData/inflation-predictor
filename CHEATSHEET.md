# Cheat Sheet — PoC Inflation Predictor (MINE4105)

## Conceptos clave SAM / CloudFormation

| Concepto | Qué es |
|---|---|
| **Stack** | Conjunto de recursos AWS gestionados como unidad (`poc-inflation-predictor-stack`) |
| **Changeset** | Diferencia entre lo que existe y lo que describes en `template.yaml` — SAM solo aplica lo que cambió |
| **DeletionPolicy: Retain** | El bucket S3 no se borra aunque hagas `sam delete` |
| **Globals** | Configuración compartida por todas las Lambdas (runtime, timeout, memoria, layer) |
| **Events (S3)** | Trigger automático: cuando aparece un archivo en S3 → Lambda se dispara sola |
| **Secrets Manager** | Almacén seguro de credenciales — las Lambdas leen las keys desde ahí, nunca en texto plano |
| **Layer** | Librería compartida entre Lambdas (pandas, numpy, pyarrow vienen del layer AWSSDKPandas) |

---

## Comandos SAM

```bash
# Construir paquetes de las 3 Lambdas
sam build

# Desplegar (primera vez o actualización)
sam build && sam deploy

# Ver el stack desplegado en consola web
# AWS Console → CloudFormation → poc-inflation-predictor-stack

# Eliminar el stack (el bucket S3 se conserva por DeletionPolicy: Retain)
sam delete --stack-name poc-inflation-predictor-stack
```

---

## Comandos AWS CLI más usados

```bash
# Verificar identidad configurada
aws sts get-caller-identity

# Ejecutar pipeline completo
bash scripts/run_pipeline.sh

# Ver archivos en S3
aws s3 ls s3://poc-inflation-predictor/ --recursive

# Ver solo silver y gold
aws s3 ls s3://poc-inflation-predictor/ --recursive | grep -E "silver|gold"

# Invocar una Lambda manualmente
aws lambda invoke \
  --function-name fn-poc-collector \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/out.json && cat /tmp/out.json

# Ver logs de una Lambda (últimas 2 ejecuciones)
aws logs tail /aws/lambda/fn-poc-collector --since 10m
aws logs tail /aws/lambda/fn-poc-etl --since 10m
aws logs tail /aws/lambda/fn-poc-features --since 10m

# Ver variables de entorno de una Lambda
aws lambda get-function-configuration \
  --function-name fn-poc-collector \
  --query "Environment"

# Ver secretos en Secrets Manager
aws secretsmanager list-secrets --region us-east-1 \
  --query "SecretList[].Name"

# Actualizar el valor de un secreto
aws secretsmanager update-secret \
  --secret-id "poc-inflation/fred-api-key" \
  --secret-string '{"api_key":"nueva-key-aqui"}'

# Subir semilla gold price (si se actualiza el Excel del World Bank)
bash scripts/upload_bronze_seed.sh

# Re-subir modelos a S3
aws s3 cp models/ s3://poc-inflation-predictor/models/ --recursive
```

---

## Cómo agregar una nueva variable macroeconómica

**Ejemplo: agregar ISM Manufacturing (`MANEDINNO`)**

### Paso 1 — Agregar al Collector (`lambdas/collector/handler.py`)
```python
SERIES_FRED = {
    ...
    "MANEDINNO": "ism_manufacturing",  # ← agregar esta línea
}
```

### Paso 2 — Redeplegar
```bash
sam build && sam deploy
```

### Paso 3 — Ejecutar el pipeline
```bash
bash scripts/run_pipeline.sh
# El ETL y Features se encadenan solos
```

El nuevo indicador aparece automáticamente en `silver/dataset_modelo.parquet` y en `gold/features.parquet` — sin tocar el ETL ni Features.

---

## Cómo agregar una variable de entorno a una Lambda

### En `template.yaml` (forma correcta — persiste en el repo)
```yaml
CollectorFunction:
  Properties:
    Environment:
      Variables:
        S3_BUCKET: !Ref S3Bucket
        FRED_API_KEY_SECRET: poc-inflation/fred-api-key
        NUEVA_VARIABLE: valor         # ← agregar aquí
```
Luego: `sam build && sam deploy`

### Desde AWS CLI (temporal — solo para pruebas rápidas)
```bash
aws lambda update-function-configuration \
  --function-name fn-poc-collector \
  --environment "Variables={S3_BUCKET=poc-inflation-predictor,FRED_API_KEY_SECRET=poc-inflation/fred-api-key,NUEVA_VARIABLE=valor}"
```
> ⚠️ Este método sobreescribe TODAS las variables — incluir siempre las existentes.

---

## Cómo agregar un nuevo secreto

```bash
aws secretsmanager create-secret \
  --name "poc-inflation/nuevo-secreto" \
  --secret-string '{"api_key":"valor-secreto"}' \
  --region us-east-1
```

El rol IAM ya tiene permiso para leer cualquier secreto con prefijo `poc-inflation/*`.

---

## Flujo completo del pipeline

```
bash scripts/run_pipeline.sh
    │
    └── fn-poc-collector
          ├── Lee FRED_API_KEY desde Secrets Manager
          ├── Descarga 11 series FRED → bronze/*.parquet
          └── Escribe bronze/_ready
                    │
                    └── trigger S3 → fn-poc-etl
                          ├── Lee 11 series + gold_price desde bronze/
                          ├── Merge + limpieza + forward-fill
                          └── Escribe silver/dataset_modelo.parquet
                                    │
                                    └── trigger S3 → fn-poc-features
                                          ├── Lee silver/dataset_modelo.parquet
                                          ├── Feature engineering (lags, MA, pct)
                                          └── Escribe gold/features.parquet
                                                    │
                                                    └── SageMaker Notebook
                                                          ├── Carga modelo RF h1
                                                          ├── Inferencia (p95 < 2000ms)
                                                          └── Narrativa Gemini 2.5 Flash
```

---

## Consola AWS — dónde ver qué

| Qué verificar | Dónde ir |
|---|---|
| Logs de ejecución | CloudWatch → Log groups → `/aws/lambda/fn-poc-*` |
| Métricas (invocaciones, errores, duración) | Lambda → función → pestaña Monitor |
| Triggers S3 configurados | Lambda → función → pestaña Configuration → Triggers |
| Archivos en S3 | S3 → poc-inflation-predictor |
| Estado del stack | CloudFormation → poc-inflation-predictor-stack |
| Secretos | Secrets Manager → poc-inflation/* |
