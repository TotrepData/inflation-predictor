import os
import io
import json
import boto3
import requests
import pandas as pd
import numpy as np

S3_BUCKET = os.environ["S3_BUCKET"]
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_api_key():
    secret_name = os.environ["FRED_API_KEY_SECRET"]
    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    secret = client.get_secret_value(SecretId=secret_name)
    return json.loads(secret["SecretString"])["api_key"]


FRED_API_KEY = get_fred_api_key()

SERIES_FRED = {
    "CPIAUCSL": "cpi",
    "FEDFUNDS": "fed_rate",
    "DCOILWTICO": "oil_price",
    "UNRATE": "unemployment",
    "INDPRO": "industrial_production",
    "M2SL": "money_supply_m2",
    "RRSFS": "retail_sales",
    "TCU": "capacity_utilization",
    "GS10": "treasury_10y",
    "PPIACO": "ppi",
    "UMCSENT": "consumer_sentiment",
}


def descargar_serie(codigo):
    params = {
        "series_id": codigo,
        "api_key": FRED_API_KEY,
        "file_type": "json",
    }
    response = requests.get(FRED_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "observations" not in data:
        raise ValueError(f"FRED error para {codigo}: {data.get('error_message', 'respuesta inesperada')}")
    df = pd.DataFrame(data["observations"])[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = df["value"].replace(".", np.nan)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def handler(event, context):
    s3 = boto3.client("s3")
    resultados = {}

    for codigo, nombre in SERIES_FRED.items():
        df = descargar_serie(codigo)
        key = f"bronze/{nombre}_raw.parquet"
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=buf.getvalue(),
            ContentType="application/octet-stream",
        )
        resultados[nombre] = len(df)
        print(f"OK {key} ({len(df)} filas)")

    # Centinela que dispara automáticamente el Lambda ETL vía trigger S3
    s3.put_object(Bucket=S3_BUCKET, Key="bronze/_ready", Body=b"")
    print("OK bronze/_ready → trigger ETL")

    return {
        "statusCode": 200,
        "body": json.dumps({"series_descargadas": resultados}),
    }
