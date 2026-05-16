import sys
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# ----------------------------------------
# CONFIGURACIÓN DE ANALITOS Y NIVELES
# ----------------------------------------
# Lista de analitos por defecto
TARGET_ANALITOS_DEFAULT = [
    'ALT/TGP (Alanino aminotransferasa)',
    'AST/TGO (Aspartato aminotransferasa)',
    'Acido Urico',
    'Albúmina',
    'Amilasa',
    'Bilirrubina Directa (DBIL)',
    'Bilirrubina Total/TBIL',
    'Calcio',
    'Cloro (CL)',
    'Colesterol HDL (HDL-C)',
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
    'Urea nitrogenada (BUN)'
]

ANALITO_MAPPING = {
    'Acido Urico': 'Acido Urico'
}

NIVEL_XPATHS = {
    1: "//span[contains(text(), '[46011] - Lyquicheck Assayed Multiqual Nivel 1')]/preceding::button[1]",
    2: "//span[contains(text(), '[46012] - Lyquicheck Assayed Multiqual Nivel 2')]/preceding::button[1]",
    3: "//span[contains(text(), '[46013] - Liquid Assayed Multiqual Nivel 3')]/preceding::button[1]"
}

ANALITOS_EXCLUIDOS_POR_NIVEL = {
    1: [],
    2: [],
    3: ['Colesterol HDL (HDL-C)']
}

# ----------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------
def wait_for_no_overlay(driver, timeout=5):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "cdk-overlay-backdrop"))
        )
    except:
        pass

def reopen_AU480(driver, wait):
    try:
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//span[contains(text(), 'AU480')]/preceding::button[1]"
        ))).click()
        time.sleep(2)
    except:
        pass

def open_multiqual_level(driver, wait, nivel, log_callback):
    xpath = NIVEL_XPATHS.get(nivel)
    if not xpath:
        log_callback(f"❌ No hay XPath configurado para nivel {nivel}")
        return False
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()
            time.sleep(3)
            return True
        except:
            log_callback(f"⚠️ Intento {attempt + 1}/{max_attempts} falló al abrir nivel {nivel}")
            if attempt < max_attempts - 1:
                reopen_AU480(driver, wait)
                time.sleep(2)
    return False

def find_and_click_analito(driver, wait, analito_name, log_callback):
    ui_name = ANALITO_MAPPING.get(analito_name, analito_name)
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            wait_for_no_overlay(driver, timeout=5)
            node_xpath = (
                f"//span[@class='ng-star-inserted' and normalize-space()='{ui_name}']"
                f"/ancestor::div[contains(@class,'p-tree-node-content')]"
            )
            analito_node = wait.until(EC.element_to_be_clickable((By.XPATH, node_xpath)))
            driver.execute_script("arguments[0].scrollIntoView(true);", analito_node)
            time.sleep(0.3)
            analito_node.click()
            time.sleep(1)
            # log_callback(f"✅ Click en analito: {ui_name}")
            return True
            
        except TimeoutException:
            log_callback(f"⏱️ Intento {attempt + 1}/{max_attempts}: No se encontró '{ui_name}'")
            time.sleep(1)
        except ElementClickInterceptedException:
            log_callback(f"🚫 Intento {attempt + 1}/{max_attempts}: Elemento bloqueado '{ui_name}'")
            time.sleep(1)
        except Exception as e:
            log_callback(f"❌ Intento {attempt + 1}/{max_attempts} error con '{ui_name}': {type(e).__name__}")
            time.sleep(1)
    
    log_callback(f"❌ No se pudo hacer click en '{ui_name}' después de {max_attempts} intentos")
    return False

def ingresar_resultado(driver, wait, fecha_iso, valor, nivel, log_callback):
    try:
        wait_for_no_overlay(driver, timeout=5)
        
        registro_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//button[.//span[@class='p-button-label' and contains(text(),'Alta Resultado Nivel {nivel}')]]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", registro_btn)
        time.sleep(0.3)
        registro_btn.click()

        wait_for_no_overlay(driver, timeout=5)

        fecha_input = wait.until(EC.presence_of_element_located((
            By.XPATH, "//input[@matinput and @name='fecha']"
        )))
        wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@matinput and @name='fecha']")))
        
        fecha_input.clear()
        fecha_input.send_keys(fecha_iso)
        time.sleep(0.3)

        valor_input = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//input[@matinput and @placeholder='Valor Nivel {nivel}']"
        )))
        valor_input.clear()
        valor_input.send_keys(str(valor))
        time.sleep(0.3)

        guardar_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[@type='submit' and contains(normalize-space(), 'Guardar')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", guardar_btn)
        time.sleep(0.3)
        guardar_btn.click()

        wait_for_no_overlay(driver, timeout=3)
        time.sleep(0.5)
        return True
        
    except TimeoutException:
        log_callback(f"⏱️ Timeout al ingresar resultado nivel {nivel}: No se encontró elemento")
        return False
    except ElementClickInterceptedException:
        log_callback(f"🚫 Elemento bloqueado (overlay?) al ingresar resultado nivel {nivel}")
        return False
    except Exception as e:
        log_callback(f"❌ Error inesperado al ingresar resultado nivel {nivel}: {type(e).__name__} - {str(e)}")
        return False

# ----------------------------------------
# FUNCIÓN PRINCIPAL DE REGISTRO
# ----------------------------------------
def run_registration(records_df, user, password, log_callback):
    """
    Ejecuta el proceso de automatización Selenium.
    records_df debe contener las columnas ['Fecha', 'Nivel', 'Analito', 'Valor'] filtradas.
    """
    if records_df.empty:
        log_callback("⚠️ No hay datos para procesar.")
        return

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)
    
    total_processed = 0
    total_errors = 0

    try:
        log_callback("🌐 Iniciando navegador y accediendo al sistema...")
        driver.get("https://app.cclabcontrol.com/#/login")
        time.sleep(10)

        driver.find_element(By.NAME, "username").send_keys(user)
        driver.find_element(By.NAME, "password").send_keys(password)
        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[.//strong[contains(text(), ' Entrar ')]]")
        )).click()

        log_callback("Navegando a AU480...")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//img[@alt='Control de Calidad']"))).click()
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//span[contains(text(), 'Quimica clínica')]/preceding::button[1]"
        ))).click()
        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//span[contains(text(), 'AU480')]/preceding::button[1]"
        ))).click()

        # Obtener los niveles a procesar, ordenados
        niveles_a_procesar = sorted(records_df['Nivel'].unique())

        for nivel in niveles_a_procesar:
            log_callback(f"**🔄 Procesando NIVEL {nivel}**")
            nivel_df = records_df[records_df['Nivel'] == nivel]

            if not open_multiqual_level(driver, wait, nivel, log_callback):
                log_callback(f"❌ No se pudo abrir el nivel {nivel}. Saltando.")
                continue

            analitos_nivel = nivel_df['Analito'].unique()

            for analito in analitos_nivel:
                analito_df = nivel_df[nivel_df['Analito'] == analito]
                
                if not find_and_click_analito(driver, wait, analito, log_callback):
                    if not (analito == "Colesterol HDL (HDL-C)" and nivel == 3):
                        log_callback(f"❌ No se pudo encontrar '{analito}' en la interfaz")
                        total_errors += len(analito_df)
                        continue
                    else:
                        log_callback(f"ℹ️ '{analito}' no está en el nivel {nivel}")
                        continue

                for _, row in analito_df.iterrows():
                    valor = row['Valor']
                    # Assuming row['Fecha'] is a datetime object or string 'YYYY-MM-DD'
                    if isinstance(row['Fecha'], str):
                        fecha_iso = row['Fecha']
                    else:
                        fecha_iso = row['Fecha'].isoformat()[:10]

                    attempts = 0
                    while attempts < 3:
                        if ingresar_resultado(driver, wait, fecha_iso, valor, nivel, log_callback):
                            total_processed += 1
                            log_callback(f"✅ {fecha_iso}: {valor} ({analito} Nivel {nivel})")
                            break
                        else:
                            attempts += 1
                            log_callback(f"⚠️ Reintento {attempts} para {fecha_iso} ({analito})")
                            time.sleep(1)
                    else:
                        log_callback(f"❌ Error {nivel}: {fecha_iso}: {valor} ({analito})")
                        total_errors += 1

            reopen_AU480(driver, wait)
            time.sleep(2)

        log_callback("### 📊 RESUMEN FINAL:")
        log_callback(f"- ✅ Registros procesados exitosamente: {total_processed}")
        log_callback(f"- ❌ Errores encontrados: {total_errors}")
        if (total_processed + total_errors) > 0:
            log_callback(f"- 📈 Tasa de éxito: {(total_processed/(total_processed + total_errors)*100):.1f}%")

    except Exception as e:
        log_callback(f"❌ Error crítico en el flujo principal: {str(e)}")
    finally:
        driver.quit()
        log_callback("🔚 Proceso completado. Navegador cerrado.")
