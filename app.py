import streamlit as st
import pandas as pd
from datetime import datetime
import os
from extractor_logic import process_uploaded_files
from registro_logic import run_registration, TARGET_ANALITOS_DEFAULT

from dotenv import load_dotenv
load_dotenv()

USER_EMAIL = os.getenv("USER_EMAIL")
PASSWORD = os.getenv("PASSWORD")

# Configuración de la página
st.set_page_config(page_title="Extractor y Registro QC", layout="wide")

st.title("Extractor y Registro QC")
st.markdown("Herramienta unificada para extraer datos de archivos .txt y registrarlos en CCLabControl.")

# --- Sección 1: Logging de Acceso ---
with st.expander("🔑 Logging de Acceso", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        user_email = st.text_input("Usuario", value="USER_EMAIL")
    with col2:
        user_password = st.text_input("Contraseña", type="password", value="PASSWORD")

# --- Sección 2: Carga y Selección de Archivos ---
st.header("1. Carga y Extracción de Datos")
uploaded_files = st.file_uploader("Sube tus archivos .txt", type=['txt'], accept_multiple_files=True)

if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = {}

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    btn_upload = st.button("Procesar Archivos Subidos", disabled=not uploaded_files)

with col_btn2:
    btn_local = st.button("Cargar desde carpeta ./Datos_txt/")

if btn_upload and uploaded_files:
    with st.spinner("Procesando archivos subidos..."):
        resultados = process_uploaded_files(uploaded_files)
        st.session_state.processed_data = resultados
        st.session_state.selected_files = {}
        for fecha, files_list in resultados.items():
            if len(files_list) == 1:
                st.session_state.selected_files[fecha] = files_list[0]['filename']
            else:
                best_file = min(files_list, key=lambda x: x['num_ceros'])
                st.session_state.selected_files[fecha] = best_file['filename']

if btn_local:
    import os
    from extractor_logic import procesar_archivo_txt
    folder_path = './Datos_txt/'
    if not os.path.isdir(folder_path):
        st.error(f"La ruta '{folder_path}' no existe.")
    else:
        with st.spinner("Procesando archivos de la carpeta local..."):
            resultados = {}
            for filename in os.listdir(folder_path):
                if not filename.lower().endswith('.txt'):
                    continue
                file_path = os.path.join(folder_path, filename)
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        lines = f.readlines()
                    df_res, fecha, num_ceros = procesar_archivo_txt(lines)
                    if df_res is not None:
                        if fecha not in resultados:
                            resultados[fecha] = []
                        resultados[fecha].append({
                            'filename': filename,
                            'df': df_res,
                            'num_ceros': num_ceros
                        })
                except Exception as e:
                    st.error(f"Error al procesar '{filename}': {e}")
            
            st.session_state.processed_data = resultados
            st.session_state.selected_files = {}
            for fecha, files_list in resultados.items():
                if len(files_list) == 1:
                    st.session_state.selected_files[fecha] = files_list[0]['filename']
                else:
                    best_file = min(files_list, key=lambda x: x['num_ceros'])
                    st.session_state.selected_files[fecha] = best_file['filename']


if st.session_state.processed_data:
    st.subheader("Resolución de Duplicados")
    st.markdown("Se han detectado las siguientes fechas en los archivos. Selecciona qué archivo deseas utilizar para cada fecha (recomendado elegir el que tiene menos valores en 0).")
    
    # Mostrar opciones para cada fecha
    for fecha, files_list in st.session_state.processed_data.items():
        if len(files_list) > 1:
            st.warning(f"⚠️ Múltiples archivos encontrados para la fecha **{fecha}**")
            
            options = []
            for f in files_list:
                options.append(f"{f['filename']} (Valores en 0: {f['num_ceros']})")
                
            # Buscar el índice del archivo previamente seleccionado
            selected_idx = 0
            for i, opt in enumerate(options):
                if opt.startswith(st.session_state.selected_files.get(fecha, "")):
                    selected_idx = i
                    break
                    
            choice = st.radio(f"Selecciona para {fecha}:", options, index=selected_idx, key=f"radio_{fecha}")
            # Extraer filename de la elección
            selected_filename = choice.split(" (Valores en 0:")[0]
            st.session_state.selected_files[fecha] = selected_filename
        else:
            st.success(f"✅ Fecha **{fecha}**: Único archivo encontrado ({files_list[0]['filename']} con {files_list[0]['num_ceros']} ceros)")

    # Consolidar datos finales
    all_records = []
    for fecha, files_list in st.session_state.processed_data.items():
        selected_filename = st.session_state.selected_files.get(fecha)
        
        # Encontrar el df correspondiente al archivo seleccionado
        df_to_use = None
        for f in files_list:
            if f['filename'] == selected_filename:
                df_to_use = f['df']
                break
                
        if df_to_use is not None:
            # Convertir la fecha "MM_DD_YYYY" a formato datetime y luego iso
            try:
                dt = datetime.strptime(fecha, "%m_%d_%Y").date()
            except ValueError:
                st.error(f"Error al parsear la fecha {fecha}. Debe estar en formato MM_DD_YYYY.")
                continue

            for _, row in df_to_use.iterrows():
                analito = row['ANALITO']
                for n in (1, 2, 3):
                    valor = row.get(f'NIVEL {n}', 0)
                    try:
                        valor = float(valor)
                    except:
                        continue
                    if valor == 0:
                        continue
                    all_records.append((dt.isoformat(), n, analito, valor))

    records_df = pd.DataFrame(all_records, columns=['Fecha', 'Nivel', 'Analito', 'Valor'])

    if not records_df.empty:
        st.write(f"Total de registros consolidados: {len(records_df)}")
        with st.expander("Ver Datos Consolidados"):
            st.dataframe(records_df)

        # --- Sección 3: Configuración y Registro ---
        st.header("2. Configuración de Registro")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Niveles a Procesar")
            nivel_1 = st.checkbox("Nivel 1", value=True)
            nivel_2 = st.checkbox("Nivel 2", value=True)
            nivel_3 = st.checkbox("Nivel 3", value=True)
            
            selected_levels = []
            if nivel_1: selected_levels.append(1)
            if nivel_2: selected_levels.append(2)
            if nivel_3: selected_levels.append(3)
            
        with col2:
            st.subheader("Analitos a Procesar")
            analitos_disponibles = sorted(records_df['Analito'].unique().tolist())
            
            # Pre-seleccionar los que están en TARGET_ANALITOS_DEFAULT
            default_selection = [a for a in analitos_disponibles if a in TARGET_ANALITOS_DEFAULT]
            
            selected_analytes = st.multiselect(
                "Selecciona los analitos:",
                options=analitos_disponibles,
                default=default_selection
            )

        # Filtrar el dataframe final
        final_df = records_df[
            (records_df['Nivel'].isin(selected_levels)) & 
            (records_df['Analito'].isin(selected_analytes))
        ]
        
        st.write(f"**Registros finales a procesar después del filtro:** {len(final_df)}")

        if st.button("🚀 Iniciar Registro Automático", type="primary"):
            if final_df.empty:
                st.error("No hay datos para procesar con la configuración actual.")
            elif not user_email or not user_password:
                st.error("Por favor ingresa usuario y contraseña.")
            else:
                st.info("Iniciando Selenium... Por favor no cierres el navegador que se abrirá.")
                
                log_container = st.container()
                log_container.markdown("### Registro en Proceso")
                log_text = st.empty()
                
                # Custom callback for logging in Streamlit
                logs = []
                def log_callback(msg):
                    logs.append(msg)
                    # Mostrar los últimos 15 mensajes
                    display_text = "\n".join(logs[-15:])
                    log_text.code(display_text, language="markdown")
                
                # Ejecutar
                try:
                    run_registration(final_df, user_email, user_password, log_callback)
                    st.success("¡Proceso finalizado!")
                except Exception as e:
                    st.error(f"Ocurrió un error: {e}")
