#!/bin/bash
# Dispara el pipeline completo invocando solo fn-poc-collector.
# El ETL y Features se encadenan automáticamente via triggers S3:
#   Collector → bronze/_ready → ETL → silver/dataset_modelo.parquet → Features → gold/features.parquet

set -e

REGION="us-east-1"
BUCKET="poc-inflation-predictor"
OUT_FILE="$(mktemp)"

echo "=== Pipeline PoC Inflation Predictor ==="
echo ""
echo "Invocando fn-poc-collector..."
aws lambda invoke \
  --function-name fn-poc-collector \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  "$OUT_FILE" > /dev/null

STATUS=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('statusCode', 'error'))")
if [ "$STATUS" = "200" ]; then
  echo "OK Collector completado"
  echo "   $(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(json.loads(d['body']))")"
else
  echo "ERROR en Collector:"
  cat "$OUT_FILE"
  rm -f "$OUT_FILE"
  exit 1
fi

rm -f "$OUT_FILE"

echo ""
echo "ETL y Features se ejecutan automáticamente via triggers S3."
echo "Espera ~60s y verifica los archivos resultantes:"
echo ""
echo "  aws s3 ls s3://$BUCKET/ --recursive | grep -E 'silver|gold'"
