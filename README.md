# Predictor de Inflación USA

Modelo de machine learning para predecir la inflación mensual de Estados Unidos usando datos de la Federal Reserve (FRED).

## Objetivo

Replicar y extender el paper "The consumer price index prediction using machine learning approaches" (ScienceDirect, 2023), con un pipeline profesional de data engineering y MLOps.

## Datos

Fuente: [FRED API](https://fred.stlouisfed.org/)

| Variable | Código | Descripción |
|----------|--------|-------------|
| CPI | CPIAUCSL | Inflación (target) |
| Fed Rate | FEDFUNDS | Tasa de interés |
| Oil Price | DCOILWTICO | Precio del petróleo |
| Gold Price | NASDAQQGLDI | Precio del oro |

## Estructura
```
inflation-predictor/
├── data/
│   ├── raw/           # Datos crudos de FRED
│   └── processed/     # Datos listos para modelo
├── notebooks/         # Exploración y análisis
├── src/               # Código de producción (pendiente)
├── .env               # API keys (no se sube)
├── .gitignore
├── requirements.txt
└── README.md
```

## Instalación
```bash
# Clonar
git clone https://github.com/TU_USUARIO/inflation-predictor.git
cd inflation-predictor

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar API key
echo "FRED_API_KEY=tu_key_aqui" > .env
```

## Progreso

- [x] Fase 1: Data Engineering (ingesta, limpieza, procesamiento)
- [x] Fase 2: Feature Engineering
- [x] Fase 3: Modelos ML
- [ ] Fase 4: MLflow
- [ ] Fase 5: Validación de datos (Great Expectations)
- [ ] Fase 6: Tests
- [ ] Fase 7: AWS (Terraform)
- [ ] Fase 8: Lambdas
- [ ] Fase 9: CI/CD
- [ ] Fase 10: Monitoreo
- [ ] Fase 11: A/B Testing
- [ ] Fase 12: Dashboard

## Stack

- Python, pandas, requests
- MLflow (pendiente)
- AWS: S3, Lambda, Athena, EventBridge (pendiente)
- Terraform (pendiente)
- GitHub Actions (pendiente)
