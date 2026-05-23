# Vessel Traffic Depth Monitoring

> **Pipeline de Big Data para monitorear profundidades oceanográficas e identificar zonas de riesgo marítimo.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Databricks](https://img.shields.io/badge/Databricks-Workspace-red.svg)](https://databricks.com/)

---

## 📋 Descripción del Proyecto

Este proyecto implementa una **arquitectura Medallion** completa que integra datos de tráfico marítimo (AIS de Marine Cadastre) con mediciones oceanográficas (NOAA Bathymetry) para:

- 🗺️ **Monitorear profundidades** en rutas de navegación
- ⚠️ **Identificar zonas de riesgo** (aguas someras con tráfico alto)
- 📊 **Visualizar patrones** de tráfico marítimo global
- 🔍 **Análisis geoespacial** usando indexación H3 hexagonal

**Resultado**: Dashboard interactivo que mapea 9,805 zonas oceanográficas con métricas de profundidad y tráfico.

---

## 🏗️ Arquitectura

### Medallion Architecture (Bronze → Silver → Gold)

```
┌─────────────────────────────────────────────────────────────┐
│                    DATOS CRUDOS (BRONZE)                      │
├─────────────────────────────────────────────────────────────┤
│  bronze_ais (7.3M)     │     bronze_noaa (1.1M)              │
│  Marine Cadastre       │     NOAA Bathymetry                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              DATOS LIMPIOS + ENRIQUECIDOS (SILVER)            │
├─────────────────────────────────────────────────────────────┤
│  silver_ais            │  silver_noaa  │  silver_enriched    │
│  Validado + H3         │  Validado     │  AIS + NOAA + H3    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           DATOS AGREGADOS + OPTIMIZADOS (GOLD)               │
├─────────────────────────────────────────────────────────────┤
│       gold_analytics (9,805 zonas H3)                        │
│   Métricas por zona: profundidad avg/min/max, tráfico       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              DASHBOARD INTERACTIVO                            │
├─────────────────────────────────────────────────────────────┤
│  • Mapa geográfico con puntos de profundidad                 │
│  • Gráficos de distribución (tipo barco, carga)              │
│  • KPIs principales (total barcos, profundidad, zonas)       │
│  • Tabla de zonas de riesgo (CRÍTICO/ALTO/MEDIO/BAJO)        │
└─────────────────────────────────────────────────────────────┘
```

### Tecnologías Utilizadas

| Capa | Tecnología | Propósito |
|------|-----------|----------|
| **Datos** | Databricks Workspace | Plataforma unificada |
| **Procesamiento** | Apache Spark 3.x | ETL distribuido |
| **Almacenamiento** | Delta Lake | ACID + Versionado |
| **Geoespacial** | H3 Uber | Indexación hexagonal |
| **Visualización** | Databricks Dashboard | BI interactivo |
| **Cloud** | CloudLabs (AWS) | Infraestructura compartida |

---

## 📊 Datasets

### Fuente 1: Marine Cadastre AIS

- **Proveedor**: NOAA Marine Cadastre
- **Período**: 2025-01-01
- **Registros**: 7,337,208 posiciones de barcos
- **Campos principales**:
  - `mmsi`: ID único del barco
  - `latitude`, `longitude`: Posición geográfica
  - `vessel_type`: Tipo de embarcación (buque, pesquero, etc.)
  - `cargo`: Tipo de carga transportada
  - `base_date_time`: Timestamp del registro

### Fuente 2: NOAA Crowdsourced Bathymetry

- **Proveedor**: NOAA Crowdsourced Bathymetry Program
- **Período**: 2025-01-01 (252 archivos)
- **Registros**: 1,133,563 mediciones de profundidad
- **Tamaño**: ~381 MB
- **Campos principales**:
  - `LAT`, `LON`: Coordenadas
  - `DEPTH`: Profundidad en metros (0.3m - 157.1m)
  - `TIME`: Timestamp de medición
  - `PLATFORM_NAME`: Dispositivo que realizó la medición

---

## 🔄 Pipeline ETL

### FASE 1: Ingesta de Datos

#### 1.1 Descargar NOAA desde S3

```bash
# Requisitos: AWS CLI instalado
brew install awscli

# Descargar archivos NOAA (acceso público)
aws s3 cp s3://noaa-dcdb-bathymetry-pds/csb/csv/2025/01/01/ \
  ~/noaa_data/ --recursive --no-sign-request
```

#### 1.2 Crear infraestructura en Databricks

```sql
-- Schema para organizar todo el proyecto
CREATE SCHEMA IF NOT EXISTS labs_56754_cs713b.vessel_traffic_monitoring;

-- Volumen para almacenar datos NOAA
CREATE VOLUME IF NOT EXISTS 
  labs_56754_cs713b.vessel_traffic_monitoring.noaa_raw_data;
```

### FASE 2: Bronze (Datos Crudos)

Guardar datos originales sin transformación:
- `bronze_ais`: 7.3M registros sin procesar
- `bronze_noaa`: 1.1M mediciones sin procesar

**Ventajas**:
- Auditoría completa
- Reproducibilidad
- Reversibilidad en caso de errores

### FASE 3: Silver (Datos Limpios)

**Operaciones realizadas**:

1. **Validación AIS**
   - Filtrar registros sin `mmsi`, `latitude`, `longitude`
   - Validar rangos: lat [-90, 90], lon [-180, 180]
   - Rellenar nulos: `vessel_type` y `cargo` → "UNKNOWN"

2. **Validación NOAA**
   - Validar profundidad > 0
   - Validar rangos de coordenadas
   - Sin nulos críticos ✓

3. **Enriquecimiento con H3**
   - Convertir lat/lon a celdas hexagonales H3 (nivel 5)
   - Agrupación geográfica uniforme (~1200 km² por celda)
   - Permite joins eficientes

4. **Cruce AIS-NOAA**
   - JOIN por H3 cell + ventana temporal (30 min)
   - LEFT JOIN: mantener todos los barcos
   - Agregar profundidad promedio cercana

### FASE 4: Gold (Datos Agregados)

**Agregación por**:
- `h3_cell`: Zona geográfica hexagonal
- `vessel_type`: Tipo de embarcación
- `cargo`: Tipo de carga

**Métricas calculadas**:
- `vessel_count`: Total de barcos en zona
- `avg_depth_m`: Profundidad promedio
- `min_depth_m`: Profundidad mínima
- `max_depth_m`: Profundidad máxima
- `avg_samples`: Promedio de muestras de profundidad

**Resultado**: 9,805 zonas H3 listas para análisis

---

## 📈 Dashboard

### KPIs Principales

| Métrica | Valor | Descripción |
|---------|-------|-------------|
| **Total de Barcos** | 8.29M | Embarcaciones registradas en el período |
| **Profundidad Promedio** | 5.93 m | Promedio oceanográfico global |
| **Zonas Navegadas** | 9.81K | Celdas H3 con tráfico detectado |

### Visualizaciones

1. **Mapa Geográfico** (Point Map)
   - Puntos azules = zonas con mediciones de profundidad
   - Azul oscuro = aguas profundas (>30m, seguras)
   - Azul claro = aguas someras (<10m, riesgosas)
   - Tooltip: barcos totales, profundidad avg/min/max

2. **Top 15 Tipos de Embarcación** (Bar Chart)
   - Tipo 37: 2.04M barcos (53.2%)
   - Tipo 31: 1.56M barcos (40.6%)
   - Tipo 52: 1.48M barcos (38.6%)
   - Color indica profundidad promedio de navegación

3. **Top 15 Tipos de Carga** (Bar Chart)
   - UNKNOWN: 3.05M barcos (mayoría sin datos)
   - Distribución por tipo de carga transportada
   - Análisis de correlación carga-profundidad

4. **Zonas de Riesgo** (Table)
   - Identifica aguas someras con tráfico alto
   - Clasificación: CRÍTICO/ALTO/MEDIO/BAJO
   - Criterios:
     - **CRÍTICO**: profundidad < 5m Y tráfico > 100 barcos
     - **ALTO**: profundidad < 10m Y tráfico > 50 barcos
     - **MEDIO**: profundidad < 15m Y tráfico > 25 barcos

### Filtros Globales

- Tipo de embarcación
- Tipo de carga
- Rango de profundidad
- Nivel de riesgo

---

## 🚀 Optimizaciones Implementadas

### Delta Lake ✅

```python
.write.format("delta").mode("overwrite").saveAsTable(...)
```

**Beneficios**:
- Transacciones ACID garantizadas
- Versionado automático de datos
- Time-travel para auditoría
- Schema enforcement

### H3 Indexing ✅

```python
from h3 import latlng_to_cell
h3_cell = latlng_to_cell(lat, lon, 5)
```

**Ventajas**:
- Reduce 8 billones comparaciones → 10 millones
- Celdas hexagonales uniformes
- Agrupación geográfica eficiente
- Join por string (muy rápido)

### Agregación en Gold ✅

```python
gold.groupBy("h3_cell", "vessel_type", "cargo").agg(
    count("mmsi"),
    avg("depth")
)
```

**Resultado**:
- Escala: 7.3M registros → 9,805 zonas
- Performance: Queries < 1 segundo
- Dashboard-ready

---

## 📋 Requisitos

### Software
- Python 3.8+
- Databricks Workspace
- AWS CLI (para descargar NOAA)
- Git

### Librerías Python
```
pyspark>=3.0
h3>=3.7.0
```

### Acceso
- Databricks Workspace (CloudLabs)
- AWS S3 (público, sin credenciales)

---

## 🛠️ Instalación y Ejecución

### 1. Clonar este repositorio

```bash
git clone https://github.com/TotrepData/vessel-traffic-depth-monitoring.git
cd vessel-traffic-depth-monitoring
```

### 2. Descargar datos NOAA (local)

```bash
# Instalar AWS CLI
brew install awscli

# Descargar archivos
aws s3 cp s3://noaa-dcdb-bathymetry-pds/csb/csv/2025/01/01/ \
  ~/noaa_data/ --recursive --no-sign-request
```

### 3. En Databricks

1. Crear schema: `vessel_traffic_monitoring`
2. Crear volumen: `noaa_raw_data`
3. Subir 252 archivos CSV del paso 2
4. Ejecutar notebook en orden: 1 → 2 → 3 → 4 → 5 → 6

### 4. Dashboard

- Ir a Dashboards → Crear nuevo
- Conectar a `gold_analytics`
- Crear visualizaciones (ver sección Dashboard)

---

## 📁 Estructura del Repositorio

```
vessel-traffic-depth-monitoring/
├── README.md                                 # Este archivo
├── LICENSE                                   # MIT License
├── .gitignore                                # Archivos ignorados
├── vessel-traffic-depth-monitoring.ipynb     # Notebook principal
│   ├── 1. Importar librerías
│   ├── 2. Leer datos AIS
│   ├── 3. Leer datos NOAA
│   ├── 4. Crear tablas Bronze
│   ├── 5. Crear tablas Silver
│   ├── 6. Crear tabla Gold
│   ├── 7. Consultas para Dashboard (documentación)
│   └── Resumen y conclusiones
└── docs/
    ├── ARCHITECTURE.md                       # Diagrama detallado
    ├── H3_EXPLANATION.md                     # Guía de H3
    └── DASHBOARD_GUIDE.md                    # Uso del dashboard
```

---

## 📊 Resultados Clave

### Volumen de Datos Procesado

| Capa | Registros | Tamaño | Observaciones |
|------|-----------|--------|---------------|
| Bronze AIS | 7.3M | ~2 GB | Datos crudos |
| Bronze NOAA | 1.1M | ~381 MB | 252 archivos |
| Silver AIS | 7.3M | ~2 GB | Validado |
| Silver NOAA | 1.1M | ~381 MB | Validado |
| Silver Enriched | 7.3M | ~2.5 GB | Con H3 + JOIN |
| **Gold** | **9,805** | **~5 MB** | **Agregado** |

### Reducción de Escala

- **Entrada**: 7.3M posiciones de barcos
- **Salida**: 9,805 zonas H3 agregadas
- **Factor**: 744x más pequeño
- **Performance**: Queries < 1 segundo

---

## 🔮 Casos de Uso

1. **Navegación Segura**
   - Alertas en aguas someras
   - Rutas optimizadas por profundidad

2. **Monitoreo Ambiental**
   - Análisis de ecosistemas marinos
   - Impacto del tráfico en biodiversidad

3. **Planificación Logística**
   - Optimización de rutas comerciales
   - Análisis de accesibilidad portuaria

4. **Investigación Oceanográfica**
   - Validación de modelos batimétricos
   - Análisis de variabilidad espacial

---

## 📚 Próximos Pasos (Backlog)

- [ ] Implementar Workflow incremental (procesamiento diario)
- [ ] Agregar alertas en tiempo real para zonas críticas
- [ ] Expandir a múltiples fechas (series temporales)
- [ ] API REST para integración externa
- [ ] Modelo ML para predicción de rutas óptimas
- [ ] Análisis de anomalías en profundidades

---

## 👨‍💻 Autor

**TotrépData**  
Data Engineering | Big Data | Databricks

---

## 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver archivo [LICENSE](LICENSE) para más detalles.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📧 Contacto

- GitHub: [@TotrepData](https://github.com/TotrepData)
- Email: data@example.com

---

## 🎓 Agradecimientos

- NOAA por Crowdsourced Bathymetry data
- Marine Cadastre por datos AIS públicos
- Uber H3 por indexación geográfica
- Databricks por infraestructura

---

**Última actualización**: Noviembre 2025  
**Versión**: 1.0.0  
**Estado**: ✅ Production Ready
