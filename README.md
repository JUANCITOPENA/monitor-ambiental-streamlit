# 🌍 Monitor Ambiental y Calidad del Aire (Streamlit Pro)

Sistema analítico e interactivo desarrollado en **Python** con **Streamlit** y **Plotly** para la monitorización en tiempo real y predicción horaria de variables meteorológicas críticas y niveles de polución atmosférica a nivel global, mediante integración en vivo con las APIs abiertas de **Open-Meteo**.

---

## 📌 Tabla de Contenidos
1. [Visión General](#-visión-general)
2. [Arquitectura del Sistema](#-arquitectura-del-sistema)
3. [Fuentes de Datos y APIs](#-fuentes-de-datos-y-apis)
4. [Métricas y Parámetros Analizados](#-métricas-y-parámetros-analizados)
5. [Estructura del Proyecto](#-estructura-del-proyecto)
6. [Instalación y Configuración](#-instalación-y-configuración)
7. [Modo de Uso](#-modo-de-uso)
8. [Detalle de Componentes Visuales](#-detalle-de-componentes-visuales)
9. [Gobernanza y Buenas Prácticas](#-gobernanza-y-buenas-prácticas)
10. [Créditos y Autoría](#-créditos-y-autoría)

---

## 🔬 Visión General

El **Monitor Ambiental y Calidad del Aire** es una estación de control meteorológico y ambiental orientada a la toma de decisiones informadas para salud pública, gestión de operaciones al aire libre y análisis climatológico.

### Capacidades Principales:
- **Cobertura Multiciudad:** Catálogo preconfigurado con ciudades clave (Santo Domingo, Santiago de los Caballeros, Madrid, Ciudad de México, Bogotá, Buenos Aires).
- **Horizonte Dinámico de Análisis:** Exploración horaria configurable de 1 a 5 días continuos.
- **Doble Fuente Satelital:** Fusión en tiempo real de pronóstico numérico meteorológico y estaciones de monitoreo químico atmosférico.
- **Caché Inteligente de Alta Eficiencia:** Mecanismo de persistencia temporal (`@st.cache_data(ttl=900)`) que congela los datos durante 15 minutos, reduciendo drásticamente la latencia y las llamadas a red redundantes.
- **Comparativa Estadística:** Tarjetas KPI con evaluación delta en tiempo real comparando la condición actual contra el promedio histórico del período seleccionado.
- **Exportación de Datos:** Descarga de reportes tabulares consolidados en formato CSV delimitado por comas con codificación UTF-8.

---

## 🏗️ Arquitectura del Sistema

El flujo de procesamiento de datos sigue un patrón clásico **ETL (Extract, Transform, Load)** optimizado en memoria:

```
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│   Open-Meteo Forecast API       │       │    Open-Meteo Air Quality API    │
│  (Temperatura, Lluvia, UV, Hum) │       │   (PM2.5, PM10, CO, AQI Europeo) │
└────────────────┬────────────────┘       └────────────────┬─────────────────┘
                 │                                         │
                 │ JSON (Hourly Payload)                   │ JSON (Hourly Payload)
                 └──────────────────┬──────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────┐
                │  @st.cache_data(ttl=900)             │
                │  Extracción HTTP con requests        │
                │  Timeout controlado (10s)            │
                └──────────────────┬───────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────┐
                │  Transformación en Pandas DataFrame  │
                │  Inner Join sobre columna 'time'     │
                │  Parseo temporal (fecha / hora)      │
                └──────────────────┬───────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────┐
                │        Capa de Presentación          │
                │  Streamlit Metrics + Plotly Charts   │
                │  - Tarjetas Bento de KPIs            │
                │  - Serie temporal mixta Línea/Barra  │
                │  - Área rellena PM2.5 vs PM10        │
                │  - Heatmap horario de Índice UV      │
                │  - Dataframe interactivo descargable │
                └──────────────────────────────────────┘
```

---

## 📡 Fuentes de Datos y APIs

La aplicación consume dos endpoints REST públicos y libres de claves de **Open-Meteo**:

1. **Weather Forecast API (`https://api.open-meteo.com/v1/forecast`):**
   - Variables horarias solicitadas:
     - `temperature_2m`: Temperatura del aire a 2 metros de superficie (°C).
     - `relative_humidity_2m`: Humedad relativa porcentual (%).
     - `precipitation_probability`: Probabilidad de precipitación pluvial (0-100%).
     - `uv_index`: Índice de radiación ultravioleta.

2. **Air Quality API (`https://air-quality-api.open-meteo.com/v1/air-quality`):**
   - Variables horarias solicitadas:
     - `pm10`: Concentración de material particulado $\le 10\ \mu\text{m}$ ($\mu\text{g/m}^3$).
     - `pm2_5`: Concentración de material particulado fino $\le 2.5\ \mu\text{m}$ ($\mu\text{g/m}^3$).
     - `carbon_monoxide`: Monóxido de carbono ($\mu\text{g/m}^3$).
     - `european_aqi`: Índice de Calidad del Aire Europeo (EAQI).

---

## 📊 Métricas y Parámetros Analizados

### 1. Material Particulado (PM2.5 y PM10)
- **PM2.5:** Partículas microscópicas capaces de penetrar profundamente en las vías respiratorias y el torrente sanguíneo.
  - **Umbral de Referencia OMS (2021):** Exposición media en 24 horas no debe superar los **$15\ \mu\text{g/m}^3$** (marcado con línea discontinua verde en el gráfico).
- **PM10:** Partículas inhalables de polvo, polen y residuos de combustión. Límite de referencia OMS de **$45\ \mu\text{g/m}^3$**.

### 2. Índice de Calidad del Aire (European AQI)
- **Bueno (< 40):** Aire limpio, sin riesgo para la población general.
- **Moderado (40 - 59):** Calidad aceptable; personas extraordinariamente sensibles deben vigilar síntomas respiratorios.
- **Deficiente ($\ge$ 60):** Posibles efectos adversos para grupos de riesgo (niños, adultos mayores, asmáticos).

### 3. Índice de Radiación Ultravioleta (UV Index)
- **0 a 2 (Bajo):** Riesgo nulo o mínimo para la piel desprotegida.
- **3 a 5 (Moderado):** Protección recomendada en horas centrales del día.
- **6 a 7 (Alto):** Riesgo elevado; se requiere bloqueador solar FPS 50+, sombrero y gafas de sol.
- **8 a 10 (Muy Alto) y 11+ (Extremo):** Evitar exposición directa entre 10:00 AM y 4:00 PM.

---

## 📁 Estructura del Proyecto

```
monitor_ambiental_streamlit/
│
├── .venv/                      # Entorno virtual seguro de Python (aislado)
├── .gitignore                  # Exclusión de archivos temporales y venv
├── app.py                      # Código fuente principal de la aplicación Streamlit
├── requirements.txt            # Dependencias del proyecto (sin fijación de versiones)
├── README.md                   # Documentación técnica completa (este archivo)
├── STATUS.md                   # Bitácora de estado, requisitos e inventario técnico
└── iniciar_monitor.bat         # Acceso directo para ejecutar la app en Windows
```

---

## ⚙️ Instalación y Configuración

### Prerrequisitos:
- **Python 3.10 o superior** instalado en el sistema operativo Windows.
- Conexión a internet para la descarga inicial de paquetes y la consulta a las APIs de Open-Meteo.

### Paso 1: Clonar o ubicar el directorio del proyecto
```bash
cd "C:\Users\User\Desktop\CARPETA DE TRABAJO DE ANTIGRAVITY CLI-JPV\monitor_ambiental_streamlit"
```

### Paso 2: Crear el Entorno Virtual Seguro (si no estuviese creado)
```bash
python -m venv .venv
```

### Paso 3: Activar el Entorno Virtual
En PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```
En Símbolo del Sistema (CMD):
```cmd
.\.venv\Scripts\activate.bat
```

### Paso 4: Instalar las dependencias requeridas
El archivo `requirements.txt` define las librerías necesarias sin fijación estricta de versiones:
```text
streamlit
requests
pandas
plotly
```
Instalación mediante pip:
```bash
pip install -r requirements.txt
```

---

## 🚀 Modo de Uso

### Opción Rápida (Recomendada en Windows):
Haga doble clic en el archivo ejecutable por lotes:
```
iniciar_monitor.bat
```

### Opción por Línea de Comandos:
Con el entorno virtual activado, ejecute:
```bash
streamlit run app.py
```

La aplicación se iniciará y abrirá automáticamente en su navegador web predeterminado en:
`http://localhost:8501`

---

## 🎨 Detalle de Componentes Visuales

1. **Sidebar de Control:**
   - Selector desplegable de ciudades globales con coordenadas geográficas calibradas.
   - Slider deslizante de horizonte de análisis (1 a 5 días).

2. **Fila Superior de KPIs (4 Cards Bento):**
   - **Temperatura Actual:** Muestra grados Celsius y el delta comparativo contra el promedio del período.
   - **Partículas PM2.5:** Muestra concentración en $\mu\text{g/m}^3$ con delta en color inverso (el incremento de partículas es desfavorable).
   - **Índice Calidad Aire (AQI):** Categorización semántica automática (Bueno, Moderado, Deficiente) y delta informativo de PM10.
   - **Pico Máximo Índice UV:** Detección automática del valor máximo de radiación solar esperado con semáforo de riesgo (Riesgo Alto vs Moderado/Bajo).

3. **Gráfico Mixto de Clima (Plotly):**
   - Línea continua en tono naranja (#FF5733) para la curva de temperatura.
   - Barras semi-transparentes (#3498DB) sobre un segundo eje Y (0 a 100%) para la probabilidad de lluvia.

4. **Gráfico de Contaminantes (Plotly Area):**
   - Áreas rellenas apiladas para contrastar concentraciones de PM2.5 y PM10 con línea de referencia OMS en verde ($15\ \mu\text{g/m}^3$).

5. **Mapa de Calor Horario (Heatmap UV):**
   - Matriz bidimensional (Eje X: Fechas, Eje Y: Horas del día 0 a 23h) con paleta `YlOrRd` (Amarillo a Rojo) para identificar con precisión quirúrgica las horas críticas de exposición solar.

6. **Módulo de Exportación:**
   - Tabla interactiva con búsqueda, ordenación por columnas y botón de descarga directa de un archivo CSV consolidado con nombre dinámico por ciudad.

---

## 🛡️ Gobernanza y Buenas Prácticas

- **Aislamiento en Entorno Virtual (.venv):** Garantiza que las dependencias del proyecto no colisionen con otros paquetes instalados globalmente en la máquina.
- **Gestión de Errores de Red:** Las llamadas HTTP cuentan con un parámetro explícito `timeout=10` para prevenir bloqueos indefinidos si los servicios externos presentan caídas momentáneas.
- **Cero Hardcoding de Credenciales:** La plataforma utiliza APIs públicas sin necesidad de tokens o llaves sensibles, preservando la confidencialidad.
- **Cumplimiento de Estándares JPV:** Estructura modular, código limpio, documentación técnica exhaustiva y visualizaciones de alto impacto con contraste adecuado.

---

## 🏛️ Créditos y Autoría

- **Desarrollador y Arquitecto de Solución:** Ing. Juancito Peña Vizcaíno
- **Ecosistema:** Antigravity CLI / DataIADev Pro
- **Año:** 2026
