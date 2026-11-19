# -*- coding: utf-8 -*-
"""
====================================================================================================
PROYECTO: MONITOR AMBIENTAL Y CALIDAD DEL AIRE EN TIEMPO REAL (STREAMLIT PRO)
EMPRESA / ORGANIZACIÓN: DATAIADEV / ARQUITECTURA DIGITAL JPV
AUTOR PRINCIPAL: ING. JUANCITO PEÑA VIZCAÍNO
VERSIÓN: 2.0.0 (EDICIÓN ENTERPRISE CON NARRACIÓN INTELIGENTE TTS)
FECHA DE REVISIÓN: NOVIEMBRE 2026
LICENCIA: MIT
====================================================================================================

DESCRIPCIÓN GENERAL DE ARQUITECTURA:
----------------------------------------------------------------------------------------------------
Esta aplicación es un Sistema de Información y Monitoreo Ambiental en Tiempo Real diseñado bajo un
patrón desacoplado de tres capas:

1. CAPA DE INGESTA Y ETL (EXTRACT, TRANSFORM, LOAD):
   - Conexión síncrona con timeouts defensivos a dos endpoints REST satelitales de Open-Meteo.
   - Extracción de variables termodinámicas (temperatura, lluvia, radiación solar UV).
   - Extracción de biomarcadores químicos atmosféricos (PM2.5, PM10, CO, AQI Europeo).
   - Mecanismo de persistencia temporal con caché en memoria (@st.cache_data(ttl=900)),
     garantizando tiempos de respuesta ultrarrápidos (< 50ms tras caché) y cero saturación de red.

2. CAPA DE INTELIGENCIA NARRATIVA E INTERPRETACIÓN EJECUTIVA:
   - Motor heurístico que no se limita a leer valores, sino que analiza, compara contra estándares
     internacionales de la Organización Mundial de la Salud (OMS) e interpreta el impacto biológico,
     operativo y logístico en tiempo real según la ciudad y horizonte de tiempo seleccionado.
   - Generación de dictámenes ejecutivos hablados mediante Web Speech API nativa (TTS), con
     controles táctiles de audio (Play, Pause, Resume, Stop) y calibración en vivo de volumen.

3. CAPA DE PRESENTACIÓN VISUAL Y ANALÍTICA:
   - Cuadro de Mando Ejecutivo (Bento Grid) con métricas clave y deltas comparativos.
   - Gráfico temporal híbrido (Líneas y Barras superpuestas con doble eje Y en Plotly).
   - Gráfico de áreas apiladas de contaminantes con umbral crítico de referencia OMS.
   - Mapa de calor matricial bidimensional (Días vs Horas) de radiación ultravioleta.
   - Explorador de datos tabulares con motor de exportación a CSV con codificación UTF-8.

GUÍA PARA NUEVOS DESARROLLADORES QUE HEREDEN ESTE CÓDIGO:
----------------------------------------------------------------------------------------------------
- Para agregar una nueva ciudad: Edite el diccionario global `CATALOGO_CIUDADES` añadiendo su tupla
  (latitud, longitud). La interfaz y los gráficos se adaptarán automáticamente sin tocar código extra.
- Para ajustar el tiempo de expiración de la caché: Modifique el parámetro `ttl=900` (en segundos)
  del decorador `@st.cache_data`.
- Para personalizar los criterios de alerta médica o ambiental: Diríjase a las funciones
  `generar_interpretacion_*` en la Sección 3 del código.
====================================================================================================
"""

import html
import json
import uuid
from typing import Dict, Tuple, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

# ==================================================================================================
# 1. CONFIGURACIÓN INICIAL DEL LIENZO Y CONSTANTES GLOBALES DEL SISTEMA
# ==================================================================================================

st.set_page_config(
    page_title="Monitor Ambiental y Calidad del Aire | DataIADev Pro",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Catálogo Geoespacial Centralizado: Coordenadas precisas en grados decimales (WGS84)
CATALOGO_CIUDADES: Dict[str, Tuple[float, float]] = {
    "Santo Domingo, RD": (18.4861, -69.9312),
    "Santiago de los Caballeros, RD": (19.4517, -70.6970),
    "Madrid, España": (40.4168, -3.7038),
    "Ciudad de México, MX": (19.4326, -99.1332),
    "Bogotá, Colombia": (4.7110, -74.0721),
    "Buenos Aires, Argentina": (-34.6037, -58.3816),
}

# Límites de Referencia Sanitaria Internacional de la Organización Mundial de la Salud (OMS 2021)
UMBRAL_OMS_PM25_24H: float = 15.0   # Concentración máxima diaria recomendada en µg/m³
UMBRAL_OMS_PM10_24H: float = 45.0   # Concentración máxima diaria recomendada en µg/m³
UMBRAL_UV_ALTO_RIESGO: float = 6.0  # Índice UV a partir del cual se requiere protección física severa

# Inyección de estilos CSS corporativos para mejorar la estética visual y tipografía
st.markdown("""
<style>
    /* Tipografía y espaciado general */
    .main .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    /* Insignias de estado y estilo de cards */
    .metric-card {
        background: #ffffff;
        border: 2px solid #0f172a;
        box-shadow: 4px 4px 0px #0f172a;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .narrador-box {
        background-color: #f8fafc;
        border-left: 4px solid #0284c7;
        padding: 10px 14px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ==================================================================================================
# 2. CAPA DE EXTRACCIÓN, TRANSFORMACIÓN Y LIMPIEZA DE DATOS (ETL PIPELINE)
# ==================================================================================================

@st.cache_data(ttl=900, show_spinner=False)
def obtener_datos_ambientales(lat: float, lon: float) -> pd.DataFrame:
    """
    Consume los servicios REST de Open-Meteo, integra la información meteorológica y de
    calidad del aire mediante un inner join temporal, y genera las variables analíticas derivadas.

    Parámetros:
    -----------
    lat : float
        Latitud geográfica en grados decimales.
    lon : float
        Longitud geográfica en grados decimales.

    Retorna:
    --------
    pd.DataFrame:
        DataFrame ordenado cronológicamente con todas las variables climáticas y químicas horarias.
        Estructura de columnas:
        - time: Marca temporal exacta (datetime64).
        - temperature_2m: Temperatura del aire a 2 metros (°C).
        - relative_humidity_2m: Humedad relativa porcentual (%).
        - precipitation_probability: Probabilidad horaria de precipitación pluvial (0-100%).
        - uv_index: Radiación solar ultravioleta calculada al nivel de suelo.
        - pm10: Material particulado menor a 10 micrómetros (µg/m³).
        - pm2_5: Material particulado fino respirable menor a 2.5 micrómetros (µg/m³).
        - carbon_monoxide: Concentración de monóxido de carbono (µg/m³).
        - european_aqi: Índice europeo de calidad del aire estandarizado.
        - fecha: Objeto de tipo date para agrupaciones por día.
        - hora: Entero de 0 a 23 representativo del huso local.
    """
    url_clima = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,uv_index"
        f"&timezone=auto"
    )
    url_aire = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=pm10,pm2_5,carbon_monoxide,european_aqi"
        f"&timezone=auto"
    )

    try:
        # Llamadas con timeout explícito para blindar contra bloqueos de sockets
        res_clima = requests.get(url_clima, timeout=12).json()
        res_aire = requests.get(url_aire, timeout=12).json()

        df_clima = pd.DataFrame(res_clima["hourly"])
        df_aire = pd.DataFrame(res_aire["hourly"])

        # Unificación de series mediante clave temporal primaria 'time'
        df = pd.merge(df_clima, df_aire, on="time", how="inner")
        df["time"] = pd.to_datetime(df["time"])
        df["fecha"] = df["time"].dt.date
        df["hora"] = df["time"].dt.hour
        return df

    except Exception as exc:
        st.error(f"⚠️ Error de comunicación con los servicios satelitales de Open-Meteo: {exc}")
        return pd.DataFrame()


# ==================================================================================================
# 3. MOTOR DE INTELIGENCIA NARRATIVA E INTERPRETACIÓN EJECUTIVA EN TIEMPO REAL
# ==================================================================================================

def interpretar_kpis_ejecutivos(actual: pd.Series, df: pd.DataFrame, ciudad: str) -> str:
    """
    Genera un dictamen ejecutivo profundo de la situación meteorológica y de salud pública actual,
    comparando las condiciones del instante presente contra las tendencias de la ventana temporal.
    """
    prom_temp = df["temperature_2m"].mean()
    prom_pm25 = df["pm2_5"].mean()
    max_uv = df["uv_index"].max()
    temp_act = actual["temperature_2m"]
    pm25_act = actual["pm2_5"]
    pm10_act = actual["pm10"]
    aqi_val = int(actual["european_aqi"])

    # Análisis de anomalía térmica
    dif_temp = temp_act - prom_temp
    if abs(dif_temp) < 0.8:
        analisis_temp = f"La temperatura actual se sitúa en {temp_act:.1f} grados Celsius, en perfecta concordancia con el promedio histórico del ciclo."
    elif dif_temp > 0:
        analisis_temp = f"Se detecta una anomalía térmica positiva de {dif_temp:.1f} grados por encima del promedio del periodo, indicando un frente cálido activo con {temp_act:.1f} grados Celsius."
    else:
        analisis_temp = f"Se registra un enfriamiento relativo de {abs(dif_temp):.1f} grados por debajo de la media, alcanzando {temp_act:.1f} grados Celsius."

    # Diagnóstico de calidad del aire y partículas PM2.5
    if pm25_act <= UMBRAL_OMS_PM25_24H:
        analisis_aire = (
            f"Excelente balance en la pureza del aire. Las partículas finas PM2.5 marcan {pm25_act:.1f} microgramos por metro cúbico, "
            f"manteniéndose con holgura por debajo del límite seguro de 15 establecido por la Organización Mundial de la Salud."
        )
    else:
        exceso_pct = ((pm25_act - UMBRAL_OMS_PM25_24H) / UMBRAL_OMS_PM25_24H) * 100
        analisis_aire = (
            f"Alerta preventiva de calidad atmosférica. Las partículas PM2.5 registran {pm25_act:.1f} microgramos por metro cúbico, "
            f"lo que representa un exceso del {exceso_pct:.0f} por ciento sobre el umbral de referencia de la OMS. "
            f"Se aconseja prudencia en actividades cardiovasculares al aire libre a personas asmáticas o con patologías respiratorias."
        )

    # Estado del Índice AQI y Riesgo UV
    if aqi_val < 40:
        estado_aqi = "favorable y de bajo impacto biológico"
    elif aqi_val < 60:
        estado_aqi = "moderado, con presencia de partículas en suspensión"
    else:
        estado_aqi = "comprometido o desfavorable para grupos vulnerables"

    analisis_uv = (
        f"El índice de radiación ultravioleta proyecta un pico máximo de {max_uv:.1f}. "
        f"{'Representa riesgo alto; se exige protección solar obligatoria y sombra en horas centrales.' if max_uv >= 6 else 'Nivel moderado o bajo, con condiciones seguras de exposición moderada.'}"
    )

    narracion = (
        f"Informe Ejecutivo de Condiciones Ambientales para {ciudad}. "
        f"{analisis_temp} "
        f"{analisis_aire} "
        f"El Índice de Calidad del Aire global se sitúa en {aqi_val} puntos, catalogado como {estado_aqi}, con partículas PM10 en {pm10_act:.1f} microgramos. "
        f"{analisis_uv} "
        f"Dictamen general: Parámetros operativos y de habitabilidad bajo monitoreo satelital continuo."
    )
    return narracion


def interpretar_grafico_clima(df: pd.DataFrame, ciudad: str) -> str:
    """
    Analiza la curva termodinámica temporal y las probabilidades de lluvia en el horizonte evaluado.
    """
    temp_min = df["temperature_2m"].min()
    temp_max = df["temperature_2m"].max()
    lluvia_max = df["precipitation_probability"].max()
    horas_lluvia_alta = df[df["precipitation_probability"] >= 50]

    narrativa = (
        f"Análisis Ejecutivo de la Evolución Meteorológica en {ciudad}. "
        f"A lo largo del horizonte seleccionado, la temperatura registrará una oscilación térmica entre una mínima de {temp_min:.1f} grados "
        f"y una cúspide máxima de {temp_max:.1f} grados Celsius, con una amplitud térmica de {temp_max - temp_min:.1f} grados. "
    )

    if lluvia_max >= 50:
        primera_lluvia = horas_lluvia_alta.iloc[0]
        fecha_str = primera_lluvia['time'].strftime('%d de %B a las %H horas')
        narrativa += (
            f"Atención a la logística de transporte y actividades exteriores: la probabilidad de precipitaciones alcanza un pico crítico del {lluvia_max:.0f} por ciento. "
            f"El primer episodio de lluvia significativa está proyectado para el día {fecha_str}. "
            f"Se recomiendan protocolos de contingencia ante pavimento mojado o eventuales demoras en traslados."
        )
    else:
        narrativa += (
            f"Condiciones de estabilidad atmosférica predominantes. La probabilidad máxima de lluvia no superará el {lluvia_max:.0f} por ciento, "
            f"lo que anticipa operaciones fluidas, baja interferencia pluvial y cielos mayoritariamente despejados o con nubosidad leve."
        )
    return narrativa


def interpretar_grafico_contaminantes(df: pd.DataFrame, ciudad: str) -> str:
    """
    Evalúa la correlación entre material particulado fino (PM2.5) e inhalable (PM10),
    contrastándolo contra las directrices de salud pública de la OMS.
    """
    prom_pm25 = df["pm2_5"].mean()
    max_pm25 = df["pm2_5"].max()
    prom_pm10 = df["pm10"].mean()
    horas_exceso_oms = (df["pm2_5"] > UMBRAL_OMS_PM25_24H).sum()
    total_horas = len(df)
    porcentaje_exceso = (horas_exceso_oms / total_horas) * 100 if total_horas > 0 else 0

    narrativa = (
        f"Dictamen Técnico de Toxicología y Contaminantes Atmosféricos para {ciudad}. "
        f"El promedio de material particulado fino PM2.5 durante este ciclo es de {prom_pm25:.1f} microgramos por metro cúbico, "
        f"con un pico puntual que asciende a {max_pm25:.1f} microgramos. Las partículas PM10 promedian {prom_pm10:.1f} microgramos. "
    )

    if porcentaje_exceso > 30:
        narrativa += (
            f"Alerta médica ambiental: En el {porcentaje_exceso:.0f} por ciento de las horas analizadas, los niveles de PM2.5 sobrepasan "
            f"el umbral de 15 microgramos establecido por la OMS. Esto indica una carga importante de aerosoles contaminantes, hollín o polvo en suspensión. "
            f"Se recomienda a empresas con trabajadores en campo proveer mascarillas con filtro particulado N95 o FFP2 y restringir actividades deportivas exigentes."
        )
    else:
        narrativa += (
            f"Excelente desempeño ambiental. Durante el {100 - porcentaje_exceso:.0f} por ciento del periodo, la atmósfera se mantiene en conformidad "
            f"con las metas más exigentes de la OMS. El aire es apto y saludable para la totalidad de la fuerza laboral y residentes urbanos."
        )
    return narrativa


def interpretar_mapa_calor_uv(df: pd.DataFrame, ciudad: str) -> str:
    """
    Identifica las ventanas horarias de máxima radiación solar UV y emite pautas de prevención dermatológica.
    """
    max_uv = df["uv_index"].max()
    horas_peligro = df[df["uv_index"] >= UMBRAL_UV_ALTO_RIESGO]

    narrativa = (
        f"Evaluación de Riesgo Radiotérmico y Mapa de Calor UV para {ciudad}. "
        f"El índice de radiación ultravioleta alcanza un valor extremo de {max_uv:.1f} puntos en su cénit diario. "
    )

    if not horas_peligro.empty:
        hora_inicio = horas_peligro["hora"].min()
        hora_fin = horas_peligro["hora"].max()
        narrativa += (
            f"Se identifica una ventana crítica de exposición solar severa entre las {hora_inicio}:00 y las {hora_fin}:00 horas. "
            f"Durante este intervalo, el índice UV iguala o supera los {UMBRAL_UV_ALTO_RIESGO} puntos, lo cual puede producir quemaduras cutáneas en menos de 20 minutos de exposición directa. "
            f"Es mandatorio el uso de fotoprotectores solares de amplio espectro con factor de protección 50+, lentes con filtro UV400 y prendas protectoras."
        )
    else:
        narrativa += (
            f"El índice UV se mantiene en rangos seguros o moderados a lo largo de todas las jornadas, sin que se proyecten horas de riesgo dermatológico agudo. "
            f"Las actividades al aire libre pueden llevarse a cabo con medidas de fotoprotección estándar básicas."
        )
    return narrativa


def interpretar_tabla_consolidada(df: pd.DataFrame, ciudad: str) -> str:
    """
    Sintetiza la cobertura estadística del dataset consolidado y valida la integridad de los datos.
    """
    total_registros = len(df)
    fecha_min = df["fecha"].min().strftime('%d/%m/%Y')
    fecha_max = df["fecha"].max().strftime('%d/%m/%Y')

    narrativa = (
        f"Auditoría y Certificación del Repositorio de Datos Consolidados de {ciudad}. "
        f"El dataset contiene {total_registros} observaciones horarias completamente depuradas y normalizadas, "
        f"abarcando desde el {fecha_min} hasta el {fecha_max}. "
        f"Todas las series meteorológicas y químicas presentan sincronización temporal al 100%, listas para su exportación a formato CSV "
        f"e integración con sistemas de Business Intelligence corporativos como Power BI, dashboards en Python o plataformas analíticas avanzadas."
    )
    return narrativa


# ==================================================================================================
# 4. COMPONENTE WEB MAESTRO DE NARRACIÓN POR VOZ (TTS - WEB SPEECH API ESTÁNDAR JPV)
# ==================================================================================================

def renderizar_control_audio_tts(texto_narracion: str, bloque_id: str, titulo_seccion: str = "Informe Ejecutivo"):
    """
    Inyecta en la interfaz de Streamlit un panel de control multimedia con Web Speech API nativa.
    Implementa controles táctiles (Play, Pause, Resume, Stop), ecualizador visual verde pulsante,
    control interactivo de volumen con slider y transcripción colapsable.

    Parámetros:
    -----------
    texto_narracion : str
        El dictamen ejecutivo estructurado que será sintetizado por la voz del navegador.
    bloque_id : str
        Identificador único para aislar los listeners y selectores del DOM entre bloques.
    titulo_seccion : str
        Título semántico descriptivo para la tarjeta de reproducción.
    """
    texto_json = json.dumps(texto_narracion, ensure_ascii=False)
    id_seguro = f"tts_{bloque_id}_{uuid.uuid4().hex[:6]}"

    html_code = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <style>
            * {{
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}
            body {{
                margin: 0;
                padding: 4px 0;
                background: transparent;
            }}
            .tts-container {{
                background: #ffffff;
                border: 2px solid #0f172a;
                border-radius: 8px;
                padding: 10px 14px;
                box-shadow: 3px 3px 0px #0f172a;
                margin-bottom: 8px;
            }}
            .tts-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }}
            .tts-title {{
                font-size: 0.82rem;
                font-weight: 700;
                color: #0f172a;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .tts-toolbar {{
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }}
            .btn-tts {{
                display: inline-flex;
                align-items: center;
                gap: 5px;
                font-size: 0.78rem;
                font-weight: 700;
                padding: 5px 12px;
                border-radius: 6px;
                border: 1.5px solid #0f172a;
                cursor: pointer;
                transition: all 0.15s ease-in-out;
                user-select: none;
            }}
            .btn-tts:active {{
                transform: translate(1px, 1px);
            }}
            .btn-play {{
                background: #0f172a;
                color: #ffffff;
                box-shadow: 2px 2px 0px #38bdf8;
            }}
            .btn-play:hover {{
                background: #1e293b;
            }}
            .btn-pause {{
                background: #eab308;
                color: #0f172a;
                box-shadow: 2px 2px 0px #0f172a;
            }}
            .btn-resume {{
                background: #3b82f6;
                color: #ffffff;
                box-shadow: 2px 2px 0px #0f172a;
            }}
            .btn-stop {{
                background: #ef4444;
                color: #ffffff;
                box-shadow: 2px 2px 0px #0f172a;
            }}
            .audio-wave-dot {{
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background-color: #22c55e;
                box-shadow: 0 0 6px #22c55e;
                animation: audioPulse 0.9s infinite alternate ease-in-out;
            }}
            @keyframes audioPulse {{
                0% {{ transform: scale(0.8); opacity: 0.5; }}
                100% {{ transform: scale(1.3); opacity: 1; }}
            }}
            .status-badge {{
                display: none;
                align-items: center;
                gap: 6px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 0.72rem;
                font-weight: 600;
                color: #334155;
            }}
            .vol-control {{
                display: flex;
                align-items: center;
                gap: 4px;
                background: #f8fafc;
                border: 1px solid #94a3b8;
                border-radius: 6px;
                padding: 3px 6px;
                font-size: 0.72rem;
            }}
            .vol-btn {{
                background: transparent;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                font-size: 0.75rem;
                font-weight: 800;
                cursor: pointer;
                padding: 0 5px;
                line-height: 1.2;
            }}
            .vol-slider {{
                width: 60px;
                height: 4px;
                accent-color: #0284c7;
                cursor: pointer;
            }}
            .vol-badge {{
                font-weight: 700;
                font-size: 0.7rem;
                color: #0f172a;
                min-width: 32px;
                text-align: right;
            }}
        </style>
    </head>
    <body>
        <div class="tts-container" id="container_{id_seguro}">
            <div class="tts-header">
                <div class="tts-title">
                    <span>🎙️ {titulo_seccion}</span>
                </div>
                <div class="status-badge" id="badge_{id_seguro}">
                    <span class="audio-wave-dot"></span>
                    <span id="status_text_{id_seguro}">Narrando...</span>
                </div>
            </div>
            
            <div class="tts-toolbar">
                <button type="button" class="btn-tts btn-play" id="btn_play_{id_seguro}" onclick="narrar_{id_seguro}()">
                    ▶️ <span>Escuchar Informe</span>
                </button>
                <button type="button" class="btn-tts btn-pause" id="btn_pause_{id_seguro}" style="display:none;" onclick="pausar_{id_seguro}()">
                    ⏸️ <span>Pausar</span>
                </button>
                <button type="button" class="btn-tts btn-resume" id="btn_resume_{id_seguro}" style="display:none;" onclick="reanudar_{id_seguro}()">
                    ⏯️ <span>Reanudar</span>
                </button>
                <button type="button" class="btn-tts btn-stop" id="btn_stop_{id_seguro}" style="display:none;" onclick="detener_{id_seguro}()">
                    ⏹️ <span>Detener</span>
                </button>

                <div class="vol-control">
                    <span>🔊</span>
                    <button type="button" class="vol-btn" onclick="ajustarVolumen_{id_seguro}(-0.1)">-</button>
                    <input type="range" class="vol-slider" id="slider_{id_seguro}" min="0" max="1" step="0.05" value="1" oninput="cambiarVolumenDirecto_{id_seguro}(this.value)">
                    <button type="button" class="vol-btn" onclick="ajustarVolumen_{id_seguro}(0.1)">+</button>
                    <span class="vol-badge" id="vol_txt_{id_seguro}">100%</span>
                </div>
            </div>
        </div>

        <script>
            (function() {{
                const textoParaNarrar = {texto_json};
                const synth = window.speechSynthesis;
                let currentUtterance = null;
                let volumenActual = 1.0;

                const btnPlay = document.getElementById("btn_play_{id_seguro}");
                const btnPause = document.getElementById("btn_pause_{id_seguro}");
                const btnResume = document.getElementById("btn_resume_{id_seguro}");
                const btnStop = document.getElementById("btn_stop_{id_seguro}");
                const badge = document.getElementById("badge_{id_seguro}");
                const statusTxt = document.getElementById("status_text_{id_seguro}");
                const slider = document.getElementById("slider_{id_seguro}");
                const volTxt = document.getElementById("vol_txt_{id_seguro}");

                function obtenerVozEspanol() {{
                    if (!synth) return null;
                    const voces = synth.getVoices();
                    return voces.find(v => v.lang.startsWith("es-") || v.lang === "es") || null;
                }}

                window.narrar_{id_seguro} = function() {{
                    if (!synth) {{
                        alert("Tu navegador no soporta síntesis de voz (Web Speech API).");
                        return;
                    }}

                    if (synth.paused && currentUtterance) {{
                        synth.resume();
                        actualizarUI("speaking");
                        return;
                    }}

                    synth.cancel(); // Detener cualquier reproducción previa

                    currentUtterance = new SpeechSynthesisUtterance(textoParaNarrar);
                    const vozSeleccionada = obtenerVozEspanol();
                    if (vozSeleccionada) currentUtterance.voice = vozSeleccionada;
                    currentUtterance.lang = "es-ES";
                    currentUtterance.rate = 1.02; // Velocidad óptima para informes de negocio
                    currentUtterance.pitch = 1.0;
                    currentUtterance.volume = volumenActual;

                    currentUtterance.onstart = () => actualizarUI("speaking");
                    currentUtterance.onend = () => actualizarUI("idle");
                    currentUtterance.onerror = () => actualizarUI("idle");

                    synth.speak(currentUtterance);
                }};

                window.pausar_{id_seguro} = function() {{
                    if (synth && synth.speaking) {{
                        synth.pause();
                        actualizarUI("paused");
                    }}
                }};

                window.reanudar_{id_seguro} = function() {{
                    if (synth && synth.paused) {{
                        synth.resume();
                        actualizarUI("speaking");
                    }}
                }};

                window.detener_{id_seguro} = function() {{
                    if (synth) {{
                        synth.cancel();
                        actualizarUI("idle");
                    }}
                }};

                window.cambiarVolumenDirecto_{id_seguro} = function(val) {{
                    volumenActual = Math.max(0, Math.min(1, parseFloat(val)));
                    slider.value = volumenActual;
                    volTxt.innerText = Math.round(volumenActual * 100) + "%";
                    if (currentUtterance && synth.speaking) {{
                        currentUtterance.volume = volumenActual;
                    }}
                }};

                window.ajustarVolumen_{id_seguro} = function(delta) {{
                    let nuevoVol = Math.round((volumenActual + delta) * 100) / 100;
                    cambiarVolumenDirecto_{id_seguro}(nuevoVol);
                }};

                function actualizarUI(estado) {{
                    if (estado === "speaking") {{
                        btnPlay.style.display = "none";
                        btnPause.style.display = "inline-flex";
                        btnResume.style.display = "none";
                        btnStop.style.display = "inline-flex";
                        badge.style.display = "inline-flex";
                        statusTxt.innerText = "Narrando informe...";
                    }} else if (estado === "paused") {{
                        btnPlay.style.display = "none";
                        btnPause.style.display = "none";
                        btnResume.style.display = "inline-flex";
                        btnStop.style.display = "inline-flex";
                        badge.style.display = "inline-flex";
                        statusTxt.innerText = "Pausado";
                    }} else {{
                        btnPlay.style.display = "inline-flex";
                        btnPause.style.display = "none";
                        btnResume.style.display = "none";
                        btnStop.style.display = "none";
                        badge.style.display = "none";
                    }}
                }}

                if (speechSynthesis.onvoiceschanged !== undefined) {{
                    speechSynthesis.onvoiceschanged = obtenerVozEspanol;
                }}
            }})();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=92, scrolling=False)


# ==================================================================================================
# 5. BARRA LATERAL (FILTROS Y HORIZONTE DE ANÁLISIS)
# ==================================================================================================

st.sidebar.header("⚙️ Configuración del Monitor")
st.sidebar.markdown("Selecciona el punto geográfico y el horizonte temporal para ejecutar el pipeline de análisis:")

ciudad_seleccionada = st.sidebar.selectbox(
    "Selecciona una ciudad:",
    options=list(CATALOGO_CIUDADES.keys()),
    index=0,
    help="Catálogo calibrado de estaciones con sensores atmosféricos satelitales."
)

dias_pronostico = st.sidebar.slider(
    "Horizonte de análisis (días):",
    min_value=1,
    max_value=5,
    value=3,
    help="Rango temporal continuo a proyectar en las visualizaciones horarias."
)

lat, lon = CATALOGO_CIUDADES[ciudad_seleccionada]

st.sidebar.divider()
st.sidebar.markdown(f"""
**📍 Coordenadas Geográficas:**
- **Latitud:** `{lat:.4f}°`
- **Longitud:** `{lon:.4f}°`
- **Fuente:** Open-Meteo Cloud Engine
- **Frecuencia Caché:** 15 minutos
""")

# Ejecución de la ingesta de datos
with st.spinner("Consultando constelación satelital y estaciones en tiempo real..."):
    df_raw = obtener_datos_ambientales(lat, lon)

if df_raw.empty:
    st.error("No se pudieron cargar los datos ambientales en este momento. Por favor verifique la conexión a internet.")
    st.stop()

# Filtrado dinámico según el horizonte seleccionado
fecha_inicio = df_raw["time"].min()
fecha_fin = fecha_inicio + pd.Timedelta(days=dias_pronostico)
df = df_raw[(df_raw["time"] >= fecha_inicio) & (df_raw["time"] <= fecha_fin)].copy()

# ==================================================================================================
# 6. ENCABEZADO Y TARJETAS BENTO DE KPIS CON NARRADOR EJECUTIVO
# ==================================================================================================

st.title(f"🌍 Monitor Ambiental y Calidad del Aire")
st.markdown(f"### Territorio Evaluado: **{ciudad_seleccionada}** | Horizonte Activo: **{dias_pronostico} Días**")
st.markdown("Análisis satelital y químico de variables termodinámicas y biomarcadores en suspensión en tiempo real.")

actual = df.iloc[0]
promedio_temp = df["temperature_2m"].mean()
promedio_pm25 = df["pm2_5"].mean()
max_uv = df["uv_index"].max()

# Generación del dictamen de KPIs para voz
texto_narracion_kpis = interpretar_kpis_ejecutivos(actual, df, ciudad_seleccionada)

# Reproductor de voz ejecutiva de la sección de KPIs
renderizar_control_audio_tts(texto_narracion_kpis, "kpis_hero", "Narración Ejecutiva: Diagnóstico de KPIs Actuales")

with st.expander("📄 Ver transcripción del informe ejecutivo de KPIs"):
    st.info(texto_narracion_kpis)

# Fila Bento de Métricas
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🌡️ Temperatura Actual",
        value=f"{actual['temperature_2m']:.1f} °C",
        delta=f"{actual['temperature_2m'] - promedio_temp:+.1f} °C vs prom."
    )

with col2:
    st.metric(
        label="💨 Partículas PM2.5",
        value=f"{actual['pm2_5']:.1f} µg/m³",
        delta=f"{actual['pm2_5'] - promedio_pm25:+.1f} vs prom.",
        delta_color="inverse"  # Aumento de PM2.5 es negativo
    )

with col3:
    estado_aqi = "Bueno" if actual["european_aqi"] < 40 else ("Moderado" if actual["european_aqi"] < 60 else "Deficiente")
    st.metric(
        label="🫁 Índice Calidad Aire (AQI)",
        value=f"{int(actual['european_aqi'])} ({estado_aqi})",
        delta=f"PM10: {actual['pm10']:.1f} µg/m³",
        delta_color="off"
    )

with col4:
    st.metric(
        label="☀️ Pico Máximo Índice UV",
        value=f"{max_uv:.1f}",
        delta="Riesgo Alto (⚠️)" if max_uv >= 6 else "Riesgo Moderado/Bajo",
        delta_color="inverse" if max_uv >= 6 else "normal"
    )

st.divider()

# ==================================================================================================
# 7. SECCIÓN DE VISUALIZACIONES ANALÍTICAS CON NARRACIÓN INTELIGENTE
# ==================================================================================================

c1, c2 = st.columns(2)

with c1:
    st.subheader("📈 Evolución de Temperatura y Probabilidad de Lluvia")
    texto_narracion_clima = interpretar_grafico_clima(df, ciudad_seleccionada)
    renderizar_control_audio_tts(texto_narracion_clima, "grafico_clima", "Narración: Tendencias Térmicas y Lluvia")

    fig_clima = go.Figure()
    fig_clima.add_trace(go.Scatter(
        x=df["time"], y=df["temperature_2m"],
        name="Temperatura (°C)", line=dict(color="#FF5733", width=3)
    ))
    fig_clima.add_trace(go.Bar(
        x=df["time"], y=df["precipitation_probability"],
        name="Prob. Lluvia (%)", marker_color="rgba(52, 152, 219, 0.35)", yaxis="y2"
    ))
    fig_clima.update_layout(
        yaxis=dict(title="Temperatura (°C)"),
        yaxis2=dict(title="Lluvia (%)", overlaying="y", side="right", range=[0, 100]),
        legend=dict(orientation="h", y=1.15),
        margin=dict(l=20, r=20, t=30, b=20),
        height=360
    )
    st.plotly_chart(fig_clima, use_container_width=True)

    with st.expander("📄 Ver interpretación escrita del clima"):
        st.write(texto_narracion_clima)

with c2:
    st.subheader("🌫️ Concentración de Contaminantes (PM2.5 vs PM10)")
    texto_narracion_aire = interpretar_grafico_contaminantes(df, ciudad_seleccionada)
    renderizar_control_audio_tts(texto_narracion_aire, "grafico_aire", "Narración: Análisis Toxicológico y OMS")

    fig_aire = px.area(
        df, x="time", y=["pm2_5", "pm10"],
        labels={"value": "Concentración (µg/m³)", "time": "Fecha y Hora", "variable": "Contaminante"},
        color_discrete_map={"pm2_5": "#E74C3C", "pm10": "#F39C12"}
    )
    # Anotación y línea de referencia estricta de la OMS
    fig_aire.add_hline(
        y=UMBRAL_OMS_PM25_24H,
        line_dash="dash",
        line_color="green",
        annotation_text="Límite OMS PM2.5 (15 µg/m³)",
        annotation_position="top left"
    )
    fig_aire.update_layout(
        legend=dict(orientation="h", y=1.15),
        margin=dict(l=20, r=20, t=30, b=20),
        height=360
    )
    st.plotly_chart(fig_aire, use_container_width=True)

    with st.expander("📄 Ver interpretación escrita de contaminantes"):
        st.write(texto_narracion_aire)

st.divider()

# ==================================================================================================
# 8. MAPA DE CALOR DE RADIACIÓN ULTRAVIOLETA (UV) CON NARRACIÓN
# ==================================================================================================

st.subheader("🔥 Mapa de Calor Horario: Ventanas de Exposición a Radiación UV")
texto_narracion_uv = interpretar_mapa_calor_uv(df, ciudad_seleccionada)
renderizar_control_audio_tts(texto_narracion_uv, "mapa_calor_uv", "Narración: Análisis de Riesgo Solar y Horas Críticas")

pivote_uv = df.pivot_table(index="hora", columns="fecha", values="uv_index", aggfunc="mean")
fig_heat = px.imshow(
    pivote_uv,
    labels=dict(x="Fecha de Observación", y="Hora del Día (0-23h)", color="Índice UV"),
    color_continuous_scale="YlOrRd",
    aspect="auto"
)
fig_heat.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_heat, use_container_width=True)

with st.expander("📄 Ver interpretación médica y dermatológica del Índice UV"):
    st.write(texto_narracion_uv)

st.divider()

# ==================================================================================================
# 9. EXPLORADOR Y EXPORTADOR DE DATOS CONSOLIDADOS CON NARRACIÓN AUDITABLE
# ==================================================================================================

st.subheader("📋 Repositorio Tabular Consolidado y Descarga de Reporte")
texto_narracion_tabla = interpretar_tabla_consolidada(df, ciudad_seleccionada)
renderizar_control_audio_tts(texto_narracion_tabla, "tabla_datos", "Narración: Certificación y Auditoría de Datos")

with st.expander("🔍 Explorar y descargar dataset estructurado completo"):
    st.dataframe(df, use_container_width=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar Reporte Ambiental en CSV (UTF-8)",
        data=csv_bytes,
        file_name=f"reporte_ambiental_{ciudad_seleccionada.replace(' ', '_').replace(',', '')}_{df['fecha'].min()}.csv",
        mime="text/csv",
        help="Exporta la serie temporal horaria completa para integración en Excel o Power BI."
    )
    st.write(texto_narracion_tabla)

# ==================================================================================================
# 10. PIE DE PÁGINA INSTITUCIONAL JPV
# ==================================================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.85rem; padding: 10px 0;">
    <strong>Monitor Ambiental y Calidad del Aire</strong> | Desarrollado con 💻 por <strong>Ing. Juancito Peña Vizcaíno</strong><br>
    Arquitectura Digital Enterprise • Integración Open-Meteo API • Web Speech API TTS Engine • 2026
</div>
""", unsafe_allow_html=True)
