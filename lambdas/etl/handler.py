import os
import io
import json
import boto3
import pandas as pd

S3_BUCKET = os.environ["S3_BUCKET"]

SERIES_FRED = [
    "cpi",
    "fed_rate",
    "oil_price",
    "unemployment",
    "industrial_production",
    "money_supply_m2",
    "retail_sales",
    "capacity_utilization",
    "treasury_10y",
    "ppi",
    "consumer_sentiment",
]


def leer_bronze_parquet(s3, nombre):
    obj = s3.get_object(Bucket=S3_BUCKET, Key=f"bronze/{nombre}_raw.parquet")
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def handler(event, context):
    s3 = boto3.client("s3")

    series_limpias = {}
    for nombre in SERIES_FRED:
        df = leer_bronze_parquet(s3, nombre)

        # Oil price llega diario desde FRED → agregar a mensual por promedio
        if nombre == "oil_price":
            df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
            df = df.groupby("date")["value"].mean().reset_index()

        df = df.rename(columns={"value": nombre})
        series_limpias[nombre] = df

    # Gold price viene del World Bank (semilla ya en bronze)
    gold_obj = s3.get_object(Bucket=S3_BUCKET, Key="bronze/gold_price_raw.parquet")
    df_gold = pd.read_parquet(io.BytesIO(gold_obj["Body"].read()))
    df_gold = df_gold.rename(columns={"value": "gold_price"})

    # Merge de todas las series
    df_final = series_limpias["cpi"].copy()
    for nombre in SERIES_FRED:
        if nombre != "cpi":
            df_final = df_final.merge(series_limpias[nombre], on="date", how="outer")
    df_final = df_final.merge(df_gold[["date", "gold_price"]], on="date", how="outer")
    df_final = df_final.sort_values("date").reset_index(drop=True)

    # Ventana con cobertura completa: retail_sales (RRSFS) arranca en 1992-01
    # y gold_price (World Bank) define el límite superior
    fecha_min = pd.Timestamp("1992-01-01")
    fecha_max = df_gold["date"].max()
    df_modelo = df_final[
        (df_final["date"] >= fecha_min) & (df_final["date"] <= fecha_max)
    ].copy()

    # Forward-fill para huecos internos (ej. CPI no publicado en oct-2025)
    df_modelo = df_modelo.sort_values("date").ffill().dropna().reset_index(drop=True)

    buf = io.BytesIO()
    df_modelo.to_parquet(buf, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="silver/dataset_modelo.parquet",
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )

    print(f"OK silver/dataset_modelo.parquet ({len(df_modelo)} filas, {len(df_modelo.columns)} columnas)")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "filas": len(df_modelo),
            "columnas": len(df_modelo.columns),
            "periodo": f"{df_modelo['date'].min().strftime('%Y-%m')} -> {df_modelo['date'].max().strftime('%Y-%m')}",
        }),
    }
