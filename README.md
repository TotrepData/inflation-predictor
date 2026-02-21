# 📈 US Inflation Predictor

A machine learning pipeline to predict monthly US inflation using macroeconomic indicators.

![Python](https://img.shields.io/badge/Python-3.10-blue)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3-orange)
![MLflow](https://img.shields.io/badge/MLflow-2.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This project predicts **monthly inflation** (CPI % change) for the United States using:
- Federal Reserve interest rates
- Oil prices (WTI)
- Gold prices

Based on the paper *"The consumer price index prediction using machine learning approaches"* (ScienceDirect, 2023).

## Results

| Model | RMSE | MAE | R² |
|-------|------|-----|-----|
| **Random Forest** | **0.209** | **0.153** | **0.468** |
| Gradient Boosting | 0.263 | 0.178 | 0.157 |
| Lasso | 0.363 | 0.242 | -0.612 |

**Best model:** Random Forest with R² = 0.47 and MAE = 0.15%

## Project Structure

```
inflation-predictor/
├── data/
│   ├── raw/                 # Raw data from APIs
│   └── processed/           # Clean data for modeling
├── figures/                 # EDA and model visualizations
├── models/                  # Trained models (.joblib)
├── notebooks/
│   ├── 01_data_engineering.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_modelo.ipynb
│   └── 04_mlflow.ipynb
├── mlruns/                  # MLflow tracking
├── src/                     # Production code (coming soon)
├── .env                     # API keys (not in repo)
├── requirements.txt
└── README.md
```

## Data Sources

| Variable | Source | Code | Period |
|----------|--------|------|--------|
| CPI | FRED API | CPIAUCSL | 1947-2026 |
| Fed Rate | FRED API | FEDFUNDS | 1954-2026 |
| Oil Price | FRED API | DCOILWTICO | 1986-2026 |
| Gold Price | World Bank | Pink Sheet | 1960-2025 |

## Quick Start

```bash
# Clone
git clone https://github.com/TotrepData/inflation-predictor.git
cd inflation-predictor

# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure API key
echo "FRED_API_KEY=your_key_here" > .env

# Run notebooks in order
jupyter notebook
```

## Features

The model uses 40 features including:
- **Lags:** 1, 3, 6, 12 months for each variable
- **Moving averages:** 3, 6, 12 months
- **Percent changes:** Month-over-month, Year-over-year
- **Temporal:** Year, month, quarter

## Roadmap

- [x] Data Engineering
- [x] Exploratory Data Analysis
- [x] ML Modeling (6 models compared)
- [ ] MLflow Tracking
- [ ] Data Validation (Great Expectations)
- [ ] Unit Tests
- [ ] AWS Deployment (Terraform)
- [ ] CI/CD (GitHub Actions)
- [ ] Dashboard

## Tech Stack

**Data:** pandas, numpy, requests, openpyxl

**ML:** scikit-learn, MLflow

**Visualization:** matplotlib, seaborn

**Infrastructure (planned):** AWS (S3, Lambda, EventBridge), Terraform, GitHub Actions

## License

MIT

## Author

**Javier Mondragón**

---

*Built as a learning project for data engineering and MLOps*
