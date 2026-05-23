#!/bin/bash
# Convierte gold_price_raw.csv a parquet y lo sube a S3 bronze.
# Ejecutar una sola vez después del primer sam deploy.

set -e

BUCKET="poc-inflation-predictor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TMP_FILE="$(mktemp).parquet"

echo "Convirtiendo gold_price_raw.csv a parquet..."
python3 - <<PYEOF
import pandas as pd
df = pd.read_csv("$REPO_ROOT/data/raw/gold_price_raw.csv")
df['date'] = pd.to_datetime(df['date'])
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df.to_parquet("$TMP_FILE", index=False)
print(f"  {len(df)} filas, rango {df['date'].min().strftime('%Y-%m')} → {df['date'].max().strftime('%Y-%m')}")
PYEOF

echo "Subiendo a S3..."
aws s3 cp "$TMP_FILE" "s3://$BUCKET/bronze/gold_price_raw.parquet"
echo "OK s3://$BUCKET/bronze/gold_price_raw.parquet"

rm -f "$TMP_FILE"
