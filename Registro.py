'''Código funcional para ingresar resultados por múltiples analitos 
==================================================IMAGEN=====================================================================.
'''

import os
import sys
import time
import re
import pandas as pd
from datetime import date, datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
# ----------------------------------------
# CONFIGURACIÓN DE ANALITOS A PROCESAR
# ----------------------------------------
# Lista de analitos a procesar - MODIFICA SEGÚN NECESITES
TARGET_ANALITOS = [
'ALT/TGP (Alanino aminotransferasa)',
'AST/TGO (Aspartato aminotransferasa)',
'Acido Urico',
'Albúmina',
'Amilasa',
'Bilirrubina Directa (DBIL)',
'Bilirrubina Total/TBIL',
'Calcio',
'Cloro (CL)',
'Colesterol HDL (HDL-C)'
'Colesterol LDL (LDL-C)',
'Colesterol Total (CHOL)',
'Creatin cinasa (CK)',
'Creatinina',
'Deshidrogenasa Láctica (LDH)',
'Fosfatasa Alcalina',
'Fósforo',
'GGT (Gamma Glutamiltransferasa)',
'Glucosa',
'Hierro',
'Lipasa',
'Magnesio',
'Potasio',
'Proteínas Totales (TP)',
'Sodio',
'Triglicéridos',
'Urea nitrogenada (BUN)',
# Agrega o quita analitos según necesites
]

# Mapeo opcional para casos donde el nombre en CSV difiere del nombre en UI
ANALITO_MAPPING = {
    'Acido Urico': 'Acido Urico'
    # Ejemplo: 'Nombre_en_CSV': 'Nombre_en_UI'
}

# ----------------------------------------
# 1) PREPROCESAMIENTO DE CSVs
# ----------------------------------------

csv_folder = './Plantillas/'  # Ajusta según corresponda

if not os.path.isdir(csv_folder):
    print(f"ERROR: La ruta '{csv_folder}' no existe o no es una carpeta válida.", file=sys.stderr)
    sys.exit(1)

# Patrón para extraer fecha (MM_DD_YYYY) de los nombres de archivo
fname_pattern = re.compile(r'(\d{2})_(\d{2})_(\d{4})(?:_(\d{4}))?\.csv')
all_records = []

for fname in os.listdir(csv_folder):
    if not fname.lower().endswith('.csv'):
        continue
    m = fname_pattern.match(fname)
    if not m:
        continue
    mm, dd, yyyy, time_part = m.groups()
    dt = date(int(yyyy), int(mm), int(dd))
    df = pd.read_csv(os.path.join(csv_folder, fname), encoding='utf-8')
    for _, row in df.iterrows():
        analito = row['ANALITO']
        for n in (1, 2, 3):
            valor = row.get(f'NIVEL {n}', 0)
            try:
                valor = float(valor)
            except:
                continue
            if valor == 0:
                continue
            all_records.append((dt, n, analito, valor))

records_df = pd.DataFrame(all_records, columns=['Fecha', 'Nivel', 'Analito', 'Valor'])
# Filtrar solo los analitos que queremos procesar
records_df = records_df[records_df['Analito'].isin(TARGET_ANALITOS)]

# Ordenar por Nivel ascendente, luego Analito y luego Fecha descendente
records_df.sort_values(['Nivel', 'Analito', 'Fecha'], ascending=[True, True, False], inplace=True)

print(f"📊 Analitos encontrados en los datos: {records_df['Analito'].unique().tolist()}")
print(f"📊 Total de registros a procesar: {len(records_df)}")

# ----------------------------------------
# 2) FUNCIONES AUXILIARES
# ----------------------------------------

def wait_for_no_overlay(driver, timeout=5):
    """Espera a que desaparezcan los overlays de carga"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "cdk-overlay-backdrop"))
        )
    except:
        pass

def reopen_AU480(driver, wait):
    """Función para (re)abrir AU480 nodo principal"""
    try:
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//span[contains(text(), 'AU480')]/preceding::button[1]"
        ))).click()
        time.sleep(2)
    except:
        pass

# Al inicio del script, junto con TARGET_ANALITOS
NIVEL_XPATHS = {
    # 1: "//span[contains(text(), '45981 - Lyquicheck Assayed Multiqual')]/preceding::button[1]",
    1: "//span[contains(text(), '46011 - Lyquicheck Assayed Multiqual Nivel 1')]/preceding::button[1]",
    2: "//span[contains(text(), '46012 - Lyquicheck Assayed Multiqual Nivel 2')]/preceding::button[1]",
    # 2: "//span[contains(text(), '45982 - Lyquicheck Assayed Multiqual')]/preceding::button[1]",
    3: "//span[contains(text(), '46013 - Liquid Assayed Multiqual Nivel 3')]/preceding::button[1]"
    
}
# Definir qué analitos NO existen en cada nivel
ANALITOS_EXCLUIDOS_POR_NIVEL = {
    1: [],  # Nivel 1 tiene todos
    2: [],  # Nivel 2 tiene todos
    3: ['Colesterol HDL (HDL-C)']  # Nivel 3 NO tiene HDL
}


def open_multiqual_level(driver, wait, nivel):
    """Abre un nivel específico de Multiqual"""
    xpath = NIVEL_XPATHS.get(nivel)
    if not xpath:
        print(f"❌ No hay XPath configurado para nivel {nivel}")
        return False
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
            time.sleep(3)
            return True
        except:
            print(f"⚠️ Intento {attempt + 1}/{max_attempts} falló al abrir nivel {nivel}")
            if attempt < max_attempts - 1:
                reopen_AU480(driver, wait)
                time.sleep(2)
    return False

def find_and_click_analito(driver, wait, analito_name):
    """Busca y hace click en el nodo del analito"""
    ui_name = ANALITO_MAPPING.get(analito_name, analito_name)
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            wait_for_no_overlay(driver, timeout=5)
            
            # Opción 1: Buscar directamente el span interno y subir al contenedor clickeable
            node_xpath = (
                f"//span[@class='ng-star-inserted' and normalize-space()='{ui_name}']"
                f"/ancestor::div[contains(@class,'p-tree-node-content')]"
            )
            
            analito_node = wait.until(EC.element_to_be_clickable((By.XPATH, node_xpath)))
            driver.execute_script("arguments[0].scrollIntoView(true);", analito_node)
            time.sleep(0.3)
            analito_node.click()
            time.sleep(1)
            
            print(f"✅ Click en analito: {ui_name}")
            return True
            
        except TimeoutException:
            print(f"⏱️ Intento {attempt + 1}/{max_attempts}: No se encontró '{ui_name}'")
            time.sleep(1)
        except ElementClickInterceptedException:
            print(f"🚫 Intento {attempt + 1}/{max_attempts}: Elemento bloqueado '{ui_name}'")
            time.sleep(1)
        except Exception as e:
            print(f"❌ Intento {attempt + 1}/{max_attempts} error con '{ui_name}': {type(e).__name__}")
            time.sleep(1)
    
    print(f"❌ No se pudo hacer click en '{ui_name}' después de {max_attempts} intentos")
    return False
def should_skip_analito(analito, nivel):
    """    Determina si un analito debe ser saltado para un nivel específico
    Args:
        analito: Nombre del analito
        nivel: Número de nivel (1, 2, 3)
    Returns:
        bool: True si debe saltarse, False si debe procesarse
    """
    excluidos = ANALITOS_EXCLUIDOS_POR_NIVEL.get(nivel, [])
    return analito in excluidos

def ingresar_resultado(driver, wait, fecha_iso, valor, nivel):
    """Ingresa un resultado específico"""
    try:
        wait_for_no_overlay(driver, timeout=5)
        
        # Click "Alta Resultado Nivel X"
        registro_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//button[.//span[@class='p-button-label' and contains(text(),'Alta Resultado Nivel {nivel}')]]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", registro_btn)
        time.sleep(0.3)
        registro_btn.click()

        wait_for_no_overlay(driver, timeout=5)

        # Ingresar fecha - CORREGIDO: usar matinput
        fecha_input = wait.until(EC.presence_of_element_located((
            By.XPATH, "//input[@matinput and @name='fecha']"
        )))
        # Esperar a que sea interactuable
        wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@matinput and @name='fecha']")))
        
        fecha_input.clear()
        fecha_input.send_keys(fecha_iso)
        time.sleep(0.3)

        # Ingresar valor de nivel - CORREGIDO: placeholder exacto
        valor_input = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//input[@matinput and @placeholder='Valor Nivel {nivel}']"
        )))
        valor_input.clear()
        valor_input.send_keys(str(valor))
        time.sleep(0.3)

        # Guardar - CORREGIDO: estructura simple de button
        guardar_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[@type='submit' and contains(normalize-space(), 'Guardar')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", guardar_btn)
        time.sleep(0.3)
        guardar_btn.click()

        wait_for_no_overlay(driver, timeout=3)
        time.sleep(0.5)
        
        # print(f"✅ Resultado ingresado: {valor} (Nivel {nivel}) - {fecha_iso}")
        return True
        
    except TimeoutException as e:
        print(f"⏱️ Timeout al ingresar resultado nivel {nivel}: No se encontró elemento")
        # Opcional: tomar screenshot para debug
        # driver.save_screenshot(f"error_nivel_{nivel}_{int(time.time())}.png")
        return False
        
    except ElementClickInterceptedException as e:
        print(f"🚫 Elemento bloqueado (overlay?) al ingresar resultado nivel {nivel}")
        return False
        
    except Exception as e:
        print(f"❌ Error inesperado al ingresar resultado nivel {nivel}: {type(e).__name__} - {str(e)}")
        return False

# ----------------------------------------
# 3) SESIÓN ÚNICA DE SELENIUM
# ----------------------------------------

driver = webdriver.Chrome()
wait = WebDriverWait(driver, 10)

try:
    # 3.a) Login inicial
    driver.get("https://app.cclabcontrol.com/#/login")
    time.sleep(10)

    driver.find_element(By.NAME, "username").send_keys("example.gmail.com")
    driver.find_element(By.NAME, "password").send_keys("PASSWORD")
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[.//strong[contains(text(), ' Entrar ')]]")
    )).click()

    # Navegar hasta "Control de Calidad → Química clínica → AU480"
    wait.until(EC.element_to_be_clickable((By.XPATH, "//img[@alt='Control de Calidad']"))).click()
    wait.until(EC.element_to_be_clickable((
        By.XPATH, "//span[contains(text(), 'Quimica clínica')]/preceding::button[1]"
    ))).click()
    wait.until(EC.element_to_be_clickable((
        By.XPATH, "//span[contains(text(), 'AU480')]/preceding::button[1]"
    ))).click()

    # ----------------------------------------
    # 4) PROCESAMIENTO POR NIVEL Y ANALITO
    # ----------------------------------------
    
    total_processed = 0
    total_errors = 0
    
    for nivel in (1,2,3):
        print(f"\n🔄 Procesando NIVEL {nivel}")
        
        # Filtrar registros para este nivel
        nivel_df = records_df[records_df['Nivel'] == nivel]
        if nivel_df.empty:
            print(f"ℹ️ No hay datos para el nivel {nivel}")
            continue

        # Abrir nivel de Multiqual
        if not open_multiqual_level(driver, wait, nivel):
            print(f"❌ No se pudo abrir Lyquicheck 4598{nivel}. Saltando nivel.")
            continue

        # Obtener analitos únicos para este nivel
        analitos_nivel = nivel_df['Analito'].unique()
        # print(f"📝 Analitos en nivel {nivel}: {analitos_nivel.tolist()}")

        for analito in analitos_nivel:
        
            # Obtener datos para este analito específico
            analito_df = nivel_df[nivel_df['Analito'] == analito]
            
            # Buscar y abrir nodo del analito
            if not find_and_click_analito(driver, wait, analito):
                if not (analito == "Colesterol HDL (HDL-C)" and nivel == 3): # Reportar error
                    print(f"    ❌ No se pudo encontrar '{analito}' en la interfaz")
                    total_errors += len(analito_df)
                    continue
                else:
                    print(f"'{analito}', Este analito no esta en el nivel {nivel}")

          # Procesar cada registro de este analito
            for _, row in analito_df.iterrows():
                valor = row['Valor']
                fecha_iso = row['Fecha'].isoformat()

                attempts = 0
                while attempts < 3:
                    if ingresar_resultado(driver, wait, fecha_iso, valor, nivel):
                        total_processed += 1
                        # print(f"    ✅ {fecha_iso}: {valor}")
                        break
                    else:
                        attempts += 1
                        print(f"    ⚠️ Reintento {attempts} para {fecha_iso}")
                        time.sleep(1)
                else:
                    # Este else se ejecuta solo si el while terminó sin break (es decir, falló todas las veces)
                    print(f"    ❌ Error {nivel}: {fecha_iso}: {valor}")
                    total_errors += 1


        # Al terminar el nivel, reabrir AU480 para el siguiente
        reopen_AU480(driver, wait)
        time.sleep(2)

    # ----------------------------------------
    # 5) RESUMEN FINAL
    # ----------------------------------------
    
    print(f"\n📊 RESUMEN FINAL:")
    print(f"✅ Registros procesados exitosamente: {total_processed}")
    print(f"❌ Errores encontrados: {total_errors}")
    print(f"📈 Tasa de éxito: {(total_processed/(total_processed + total_errors)*100):.1f}%")

finally:
    # Cerrar navegador
    driver.quit()
    print("\n🔚 Proceso completado. Navegador cerrado.")