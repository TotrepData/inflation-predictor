#!/bin/bash
# Crea o actualiza las 3 funciones Lambda en AWS.
# Requiere: aws CLI configurado con credenciales del IAM user poc-inflation.
# Uso: bash scripts/deploy_lambdas.sh <FRED_API_KEY>

set -e

if [ -z "$1" ]; then
  echo "Uso: bash scripts/deploy_lambdas.sh <FRED_API_KEY>"
  exit 1
fi

FRED_API_KEY="$1"
BUCKET="poc-inflation-predictor"
REGION="us-east-1"
ACCOUNT_ID="793239448746"
ROLE_NAME="poc-inflation-lambda-role"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
# Layer AWSSDKPandas-Python311 — verificar ultima version en:
# https://aws-sdk-pandas.readthedocs.io/en/stable/install.html#aws-lambda-layer
LAYER_ARN="arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:20"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TMP_DIR="$(mktemp -d)"

echo "=== Deploy Lambdas PoC Inflation Predictor ==="
echo "Repo: $REPO_ROOT"
echo "Tmp:  $TMP_DIR"
echo ""

# ── IAM Role ──────────────────────────────────────────────────────────────────
echo "1. Verificando rol IAM $ROLE_NAME..."
if ! aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
  echo "   Creando rol $ROLE_NAME..."
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version":"2012-10-17",
      "Statement":[{
        "Effect":"Allow",
        "Principal":{"Service":"lambda.amazonaws.com"},
        "Action":"sts:AssumeRole"
      }]
    }' > /dev/null
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "   Esperando 15s para que el rol se propague..."
  sleep 15
  echo "   OK rol creado"
else
  echo "   OK rol ya existe"
fi

# ── Función auxiliar para crear/actualizar una Lambda ─────────────────────────
deploy_lambda() {
  local FUNC_NAME="$1"
  local HANDLER_DIR="$2"
  local ENV_VARS="$3"

  echo ""
  echo "Empaquetando $FUNC_NAME..."
  local PKG_DIR="$TMP_DIR/$FUNC_NAME"
  mkdir -p "$PKG_DIR"

  cp "$REPO_ROOT/lambdas/$HANDLER_DIR/handler.py" "$PKG_DIR/"

  # Instalar dependencias propias si las hay
  local REQS="$REPO_ROOT/lambdas/$HANDLER_DIR/requirements.txt"
  if grep -qv "^#" "$REQS" 2>/dev/null; then
    pip install -q -r "$REQS" -t "$PKG_DIR/"
  fi

  local ZIP_FILE="$TMP_DIR/${FUNC_NAME}.zip"
  (cd "$PKG_DIR" && zip -qr "$ZIP_FILE" .)

  if aws lambda get-function --function-name "$FUNC_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo "   Actualizando codigo de $FUNC_NAME..."
    aws lambda update-function-code \
      --function-name "$FUNC_NAME" \
      --zip-file "fileb://$ZIP_FILE" \
      --region "$REGION" > /dev/null
    aws lambda wait function-updated --function-name "$FUNC_NAME" --region "$REGION"
    aws lambda update-function-configuration \
      --function-name "$FUNC_NAME" \
      --environment "Variables={$ENV_VARS}" \
      --region "$REGION" > /dev/null
  else
    echo "   Creando $FUNC_NAME..."
    aws lambda create-function \
      --function-name "$FUNC_NAME" \
      --runtime python3.11 \
      --role "$ROLE_ARN" \
      --handler handler.handler \
      --zip-file "fileb://$ZIP_FILE" \
      --timeout 300 \
      --memory-size 512 \
      --layers "$LAYER_ARN" \
      --environment "Variables={$ENV_VARS}" \
      --region "$REGION" > /dev/null
  fi

  echo "   OK $FUNC_NAME desplegado"
}

# ── Deploy de las 3 Lambdas ───────────────────────────────────────────────────
deploy_lambda \
  "fn-poc-collector" \
  "collector" \
  "FRED_API_KEY=${FRED_API_KEY},S3_BUCKET=${BUCKET}"

deploy_lambda \
  "fn-poc-etl" \
  "etl" \
  "S3_BUCKET=${BUCKET}"

deploy_lambda \
  "fn-poc-features" \
  "features" \
  "S3_BUCKET=${BUCKET}"

# ── Limpieza ──────────────────────────────────────────────────────────────────
rm -rf "$TMP_DIR"

echo ""
echo "=== Deploy completado ==="
echo "Lambdas disponibles:"
echo "  fn-poc-collector"
echo "  fn-poc-etl"
echo "  fn-poc-features"
echo ""
echo "Siguiente paso: bash scripts/upload_bronze_seed.sh"
