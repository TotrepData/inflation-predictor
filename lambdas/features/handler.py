import os
import io
import json
import boto3
import pandas as pd
import numpy as np

S3_BUCKET = os.environ["S3_BUCKET"]

LAGS = [1, 3, 6, 12]
MOVING_AVG_WINDOWS = [3, 6, 12]


def add_lags(df_in, lags):
    out = {}
    for col in df_in.columns:
        for k in lags:
            out[f"{col}_lag{k}"] = df_in[col].shift(k)
    return pd.DataFrame(out, index=df_in.index)


def add_moving_averages(df_in, windows):
    out = {}
    for col in df_in.columns:
        shifted = df_in[col].shift(1)
        for w in windows:
            out[f"{col}_ma{w}"] = shifted.rolling(window=w, min_periods=w).mean()
    return pd.DataFrame(out, index=df_in.index)


def add_pct_changes(df_in, exclude=None):
    exclude = set(exclude or [])
    out = {}
    for col in df_in.columns:
        if col in exclude:
            continue
        shifted = df_in[col].shift(1)
        out[f"{col}_mom"] = shifted.pct_change(periods=1) * 100
        out[f"{col}_yoy"] = shifted.pct_change(periods=12) * 100
    return pd.DataFrame(out, index=df_in.index)


def build_features(df):
    df = df.set_index("date") if "date" in df.columns else df

    target = df["cpi"].pct_change() * 100
    target.name = "inflation_mom"

    gold_log = np.log(df["gold_price"])
    df_gold = pd.DataFrame(
        {
            "gold_price_log_lag1": gold_log.shift(1),
            "gold_price_log_diff1": gold_log.diff(1).shift(1),
            "gold_price_log_diff12": gold_log.diff(12).shift(1),
        },
        index=df.index,
    )

    month = df.index.month
    quarter = df.index.quarter
    df_time = pd.DataFrame(
        {
            "month_sin": np.sin(2 * np.pi * month / 12),
            "month_cos": np.cos(2 * np.pi * month / 12),
        },
        index=df.index,
    )
    for q in [1, 2, 3, 4]:
        df_time[f"quarter_{q}"] = (quarter == q).astype(int)

    autoreg = {}
    for k in [1, 3, 6, 12]:
        autoreg[f"inflation_mom_lag{k}"] = target.shift(k)
    target_shifted1 = target.shift(1)
    for w in [3, 6, 12]:
        autoreg[f"inflation_mom_ma{w}"] = target_shifted1.rolling(window=w, min_periods=w).mean()
    df_autoreg = pd.DataFrame(autoreg, index=df.index)

    df_lags = add_lags(df, LAGS)
    df_ma = add_moving_averages(df, MOVING_AVG_WINDOWS)
    df_pct = add_pct_changes(df, exclude=["cpi"])

    features = pd.concat([df_lags, df_ma, df_pct, df_gold, df_time, df_autoreg], axis=1)
    dataset = features.copy()
    dataset["inflation_mom"] = target
    dataset = dataset.dropna()

    return dataset.reset_index()


def handler(event, context):
    s3 = boto3.client("s3")

    obj = s3.get_object(Bucket=S3_BUCKET, Key="silver/dataset_modelo.parquet")
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))

    dataset = build_features(df)

    buf = io.BytesIO()
    dataset.to_parquet(buf, index=False)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="gold/features.parquet",
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )

    print(f"OK gold/features.parquet ({len(dataset)} filas, {len(dataset.columns)} columnas)")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "filas": len(dataset),
            "columnas": len(dataset.columns),
        }),
    }
