#!/bin/bash
# Ejecuta el pipeline completo: Collector → ETL → Features.
# Requiere las 3 Lambdas ya desplegadas (ver deploy_lambdas.sh).

set -e

REGION="us-east-1"
BUCKET="poc-inflation-predictor"
OUT_DIR="$(mktemp -d)"

echo "=== Pipeline PoC Inflation Predictor ==="
echo ""

invoke_lambda() {
  local FUNC_NAME="$1"
  local OUT_FILE="$OUT_DIR/${FUNC_NAME}.json"
  echo "Invocando $FUNC_NAME..."
  aws lambda invoke \
    --function-name "$FUNC_NAME" \
    --payload '{}' \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    "$OUT_FILE" > /dev/null
  local STATUS
  STATUS=$(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(d.get('statusCode', 'error'))")
  if [ "$STATUS" = "200" ]; then
    echo "   OK $(python3 -c "import json; d=json.load(open('$OUT_FILE')); print(json.loads(d['body']))")"
  else
    echo "   ERROR: $(cat "$OUT_FILE")"
    exit 1
  fi
}

invoke_lambda "fn-poc-collector"
echo "   Esperando 5s..."
sleep 5

invoke_lambda "fn-poc-etl"
echo "   Esperando 5s..."
sleep 5

invoke_lambda "fn-poc-features"

echo ""
echo "=== Archivos en S3 ==="
aws s3 ls "s3://$BUCKET/" --recursive | grep -E "bronze|silver|gold"

rm -rf "$OUT_DIR"
echo ""
echo "=== Pipeline completado ==="
