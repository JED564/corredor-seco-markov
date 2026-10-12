import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import unicodedata

# Función para quitar tildes y estandarizar nombres
def normalizar_texto(val):
    if isinstance(val, str):
        nfkd = unicodedata.normalize('NFKD', str(val))
        return "".join([c for c in nfkd if not unicodedata.combining(c)]).strip().upper()
    elif isinstance(val, pd.Series):
        reemplazos = {
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 
            'Ä': 'A', 'Ë': 'E', 'Ï': 'I', 'Ö': 'O', 'Ü': 'U'
        }
        return val.astype(str).str.upper().str.strip().replace(reemplazos, regex=True)
    return val

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Análisis Corredor Seco", layout="wide")
st.title("Modelación de Degradación - Corredor Seco de Guatemala")

# 2. CARGA Y FILTRADO DE DATOS
@st.cache_data
def cargar_datos():
    df = pd.read_excel("BD_Markov_CorredorSeco_Actualizada.xlsx", sheet_name="Datos_Forestales_CS")
    gdf = gpd.read_file("municipios_guatemala.geojson")
    
    # Compatibilidad con columnas de GeoJSON y Excel
    if 'departamento' not in gdf.columns and 'depto_1' in gdf.columns:
        gdf['departamento'] = gdf['depto_1']
    if 'municipio' not in gdf.columns and 'nombre_1' in gdf.columns:
        gdf['municipio'] = gdf['nombre_1']
    if 'municipio' not in df.columns:
        df['municipio'] = ""

    # Normalizamos textos para asegurar el cruce exacto
    df['departamento'] = normalizar_texto(df['departamento'])
    df['municipio'] = normalizar_texto(df['municipio'])
    gdf['departamento'] = normalizar_texto(gdf['departamento'])
    gdf['municipio'] = normalizar_texto(gdf['municipio'])
    
    # -------- CORRECCIÓN: FILTRO EXACTO DE LOS 46 MUNICIPIOS --------
    municipios_corredor_seco = [
        # Baja Verapaz (8)
        "CUBULCO", "SANTA CRUZ EL CHOL", "EL CHOL", "SALAMA", "SAN JERONIMO", "SAN MIGUEL CHICAJ", "RABINAL", "GRANADOS", "PURULHA",
        # El Progreso (8)
        "GUASTATOYA", "MORAZAN", "SAN AGUSTIN ACASAGUASTLAN", "SAN CRISTOBAL ACASAGUASTLAN", "EL JICARO", "SANSARE", "SANARATE", "SAN ANTONIO LA PAZ",
        # Zacapa (8)
        "ZACAPA", "CABANAS", "ESTANZUELA", "GUALAN", "RIO HONDO", "TECULUTAN", "USUMATLAN", "SAN DIEGO",
        # Chiquimula (7)
        "CHIQUIMULA", "SAN JOSE LA ARADA", "SAN JUAN ERMITA", "JOCOTAN", "CAMOTAN", "OLOPA", "SAN JACINTO", "QUEZALTEPEQUE",
        # Jalapa (3)
        "JALAPA", "SAN LUIS JILOTEPEQUE", "SAN MANUEL CHAPARRON", "SAN PEDRO PINULA",
        # Jutiapa (3)
        "ASUNCION MITA", "AGUA BLANCA", "SANTA CATARINA MITA",
        # Quiché (6)
        "SACAPULAS", "ZACUALPA", "SAN ANDRES SAJCABAJA", "JOYABAJ", "CANILLA", "SAN BARTOLOME JOCOTENANGO",
        # Guatemala (3)
        "SAN JOSE DEL GOLFO", "SAN PEDRO AYAMPUC", "CHUARRANCHO"
    ]
    
    # Filtramos por municipios y departamentos para evitar duplicados homónimos
    departamentos_cs = ['BAJA VERAPAZ', 'EL PROGRESO', 'ZACAPA', 'CHIQUIMULA', 'JALAPA', 'JUTIAPA', 'QUICHE', 'GUATEMALA']
    gdf = gdf[gdf['municipio'].isin(municipios_corredor_seco) & gdf['departamento'].isin(departamentos_cs)].copy()
    # ----------------------------------------------------------------
    
    return df, gdf

df, gdf = cargar_datos()

# 3. DISEÑO DE LA INTERFAZ
col_mapa, col_datos = st.columns([2, 1])

with col_mapa:
    st.subheader("Mapa Interactivo del Corredor Seco")
    m = folium.Map(location=[15.0, -89.8], zoom_start=8)
    
    folium.GeoJson(
        gdf,
        name="Corredor Seco",
        tooltip=folium.GeoJsonTooltip(fields=['departamento', 'municipio']),
        highlight_function=lambda x: {'weight': 3, 'color': 'red'} 
    ).add_to(m)

    mapa_interactivo = st_folium(m, width=800, height=600)

with col_datos:
    st.subheader("Matrices de Transición")
    
    drawing = mapa_interactivo.get("last_active_drawing")
    if not drawing and mapa_interactivo.get("last_object_clicked"):
        drawing = mapa_interactivo.get("last_object_clicked")

    if drawing and isinstance(drawing, dict) and "properties" in drawing:
        propiedades = drawing["properties"]
        depto_clic = propiedades.get("departamento", "")
        muni_clic = propiedades.get("municipio", "")
        
        st.success(f"📍 Seleccionaste: **{muni_clic}, {depto_clic}**")
        
        depto_norm = normalizar_texto(depto_clic)
        muni_norm = normalizar_texto(muni_clic)
        
        datos_muni = df[(df['departamento'] == depto_norm) & (df['municipio'] == muni_norm) & (df['municipio'] != "")]
        
        if datos_muni.empty:
            datos_muni = df[df['departamento'] == depto_norm]
        
        if not datos_muni.empty:
            st.markdown(f"#### Matriz de Transición: {muni_clic} (Bosque vs No Bosque)")
            
            bosque_inicial = datos_muni['bosque 2001 (ha)'].values[0]
            perdida = datos_muni['perdida (ha)'].values[0]
            ganancia = datos_muni['ganancia (ha)'].values[0]
            
            area_total = bosque_inicial * 3 
            no_bosque_inicial = area_total - bosque_inicial
            
            P11 = (bosque_inicial - perdida) / bosque_inicial
            P12 = perdida / bosque_inicial
            P21 = ganancia / no_bosque_inicial
            P22 = (no_bosque_inicial - ganancia) / no_bosque_inicial
            
            matriz_2x2 = pd.DataFrame({
                "Hacia Bosque": [f"{P11:.2%}", f"{P21:.2%}"],
                "Hacia No Bosque": [f"{P12:.2%}", f"{P22:.2%}"]
            }, index=["Desde Bosque", "Desde No Bosque"])
            
            st.table(matriz_2x2)
            
            st.markdown(f"#### Matriz Departamental: {depto_clic}")
            st.caption("Matriz A Priori calculada con flujos nacionales 1990-2022, ponderada por volumen forestal departamental.")
            
            datos_depto = df[df['departamento'] == depto_norm]
            bosque_depto = datos_depto['bosque 2001 (ha)'].sum() if not datos_depto.empty else 0
            
            ajuste = max(0.5, min(1.2, bosque_depto / 100000))
            
            P11_dept = min(100, 36.31 * ajuste)
            P12_dept = min(100 - P11_dept, 10.04 * (1/ajuste))
            P13_dept = min(100 - P11_dept - P12_dept, 52.18 * (1/ajuste))
            P14_dept = 100 - P11_dept - P12_dept - P13_dept
            
            P21_dept = min(100, 33.22 * ajuste)
            P22_dept = 100 - P21_dept
            P23_dept = 0.00
            P24_dept = 0.00
            
            P31_dept = min(100, 41.91 * ajuste)
            P32_dept = min(100 - P31_dept, 53.32)
            P33_dept = 100 - P31_dept - P32_dept
            P34_dept = 0.00
            
            matriz_4x4 = pd.DataFrame({
                "Bosque": [f"{P11_dept:.2f}%", f"{P21_dept:.2f}%", f"{P31_dept:.2f}%", "0.00%"],
                "Cultivo": [f"{P12_dept:.2f}%", f"{P22_dept:.2f}%", f"{P32_dept:.2f}%", "0.00%"],
                "Pastizal": [f"{P13_dept:.2f}%", "0.00%", f"{P33_dept:.2f}%", "0.00%"],
                "Otros": [f"{P14_dept:.2f}%", "0.00%", "0.00%", "100.00%"]
            }, index=["Desde Bosque", "Desde Cultivo", "Desde Pastizal", "Desde Otros"])
            
            st.table(matriz_4x4)
            
        else:
            st.warning("No tenemos datos en el Excel para este municipio.")
    else:
        st.info("👈 Haz clic en un municipio en el mapa para ver sus datos.")
