#!/bin/bash
# Sube gold_price_raw.csv al bucket S3 como dato semilla de bronze.
# Ejecutar una sola vez antes del primer deploy.

set -e

BUCKET="poc-inflation-predictor"
LOCAL_FILE="data/raw/gold_price_raw.csv"
S3_KEY="bronze/gold_price_raw.csv"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Subiendo semilla de gold_price a S3..."
aws s3 cp "$REPO_ROOT/$LOCAL_FILE" "s3://$BUCKET/$S3_KEY"
echo "OK s3://$BUCKET/$S3_KEY"
