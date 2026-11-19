import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. Configuración de página
st.set_page_config(
    page_title="Monitor Ambiental y Calidad del Aire",
    page_icon="🌍",
    layout="wide"
)

# Catálogo de ciudades (Latitud, Longitud)
CIUDADES = {
    "Santo Domingo, RD": (18.4861, -69.9312),
    "Santiago de los Caballeros, RD": (19.4517, -70.6970),
    "Madrid, España": (40.4168, -3.7038),
    "Ciudad de México, MX": (19.4326, -99.1332),
    "Bogotá, Colombia": (4.7110, -74.0721),
    "Buenos Aires, Argentina": (-34.6037, -58.3816),
}

# 2. Extracción y Transformación (ETL con caché de 15 minutos)
@st.cache_data(ttl=900)
def obtener_datos_ambientales(lat: float, lon: float):
    # API 1: Pronóstico Meteorológico
    url_clima = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,uv_index"
        f"&timezone=auto"
    )
    # API 2: Calidad del Aire
    url_aire = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=pm10,pm2_5,carbon_monoxide,european_aqi"
        f"&timezone=auto"
    )

    res_clima = requests.get(url_clima, timeout=10).json()
    res_aire = requests.get(url_aire, timeout=10).json()

    df_clima = pd.DataFrame(res_clima["hourly"])
    df_aire = pd.DataFrame(res_aire["hourly"])

    # Unir ambos datasets por marca de tiempo
    df = pd.merge(df_clima, df_aire, on="time", how="inner")
    df["time"] = pd.to_datetime(df["time"])
    df["fecha"] = df["time"].dt.date
    df["hora"] = df["time"].dt.hour
    return df

# 3. Barra lateral (Filtros)
st.sidebar.header("⚙️ Configuración del Monitor")
ciudad_seleccionada = st.sidebar.selectbox("Selecciona una ciudad:", list(CIUDADES.keys()))
dias_pronostico = st.sidebar.slider("Horizonte de análisis (días):", min_value=1, max_value=5, value=3)

lat, lon = CIUDADES[ciudad_seleccionada]

with st.spinner("Consultando sensores satelitales y estaciones en tiempo real..."):
    df_raw = obtener_datos_ambientales(lat, lon)

# Filtrar por horizonte de días seleccionado
fecha_inicio = df_raw["time"].min()
fecha_fin = fecha_inicio + pd.Timedelta(days=dias_pronostico)
df = df_raw[(df_raw["time"] >= fecha_inicio) & (df_raw["time"] <= fecha_fin)].copy()

# 4. Encabezado y KPIs Principales (Comparando hoy vs promedio del periodo)
st.title(f"🌍 Monitor Ambiental: {ciudad_seleccionada}")
st.markdown("Análisis en tiempo real de condiciones meteorológicas y calidad del aire mediante **Open-Meteo API**.")

actual = df.iloc[0]
promedio_temp = df["temperature_2m"].mean()
promedio_pm25 = df["pm2_5"].mean()
max_uv = df["uv_index"].max()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🌡️ Temperatura Actual",
        value=f"{actual['temperature_2m']:.1f} °C",
        delta=f"{actual['temperature_2m'] - promedio_temp:.1f} °C vs prom."
    )

with col2:
    st.metric(
        label="💨 Partículas PM2.5",
        value=f"{actual['pm2_5']:.1f} µg/m³",
        delta=f"{actual['pm2_5'] - promedio_pm25:.1f} vs prom.",
        delta_color="inverse"  # Subir PM2.5 es negativo (rojo)
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
        delta="Riesgo Alto" if max_uv >= 6 else "Riesgo Moderado/Bajo",
        delta_color="inverse" if max_uv >= 6 else "normal"
    )

st.divider()

# 5. Visualizaciones Analíticas
c1, c2 = st.columns(2)

with c1:
    st.subheader("📈 Evolución de Temperatura y Probabilidad de Lluvia")
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
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=20, r=20, t=30, b=20),
        height=360
    )
    st.plotly_chart(fig_clima, use_container_width=True)

with c2:
    st.subheader("🌫️ Concentración de Contaminantes (PM2.5 vs PM10)")
    fig_aire = px.area(
        df, x="time", y=["pm2_5", "pm10"],
        labels={"value": "Concentración (µg/m³)", "time": "Fecha y Hora", "variable": "Contaminante"},
        color_discrete_map={"pm2_5": "#E74C3C", "pm10": "#F39C12"}
    )
    # Línea de referencia límite OMS para PM2.5
    fig_aire.add_hline(y=15, line_dash="dash", line_color="green", annotation_text="Límite OMS PM2.5 (15)")
    fig_aire.update_layout(
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=20, r=20, t=30, b=20),
        height=360
    )
    st.plotly_chart(fig_aire, use_container_width=True)

# 6. Mapa de Calor Horario y Tabla Descargable
st.subheader("🔥 Mapa de Calor: Índice UV por Día y Hora (Ventanas de Exposición)")
pivote_uv = df.pivot_table(index="hora", columns="fecha", values="uv_index", aggfunc="mean")
fig_heat = px.imshow(
    pivote_uv,
    labels=dict(x="Fecha", y="Hora del Día", color="Índice UV"),
    color_continuous_scale="YlOrRd",
    aspect="auto"
)
fig_heat.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_heat, use_container_width=True)

with st.expander("📋 Ver y descargar tabla de datos consolidados"):
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar reporte en CSV",
        data=csv,
        file_name=f"reporte_ambiental_{ciudad_seleccionada[:10].strip()}.csv",
        mime="text/csv"
    )
