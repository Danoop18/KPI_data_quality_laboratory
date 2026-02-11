''' 
Codigo para procesar archivos de laboratorio y generar CSVs con analitos y niveles. genra CSVs con analitos y niveles.
Este script procesa archivos de texto de laboratorio, extrae analitos y sus niveles, y genera archivos CSV con los datos organizados.
en la carpeta './Plantillas/'.
'''
import os
import sys
import pandas as pd
import re
from datetime import datetime

# 1) Mapeo de códigos a (ID, ANALITO) según la plantilla deseada
code_mapping = {
    'GLU':   (1,  'Glucosa'),
    'CHOL':  (2,  'Colesterol Total (CHOL)'),
    'ALB':   (3,  'Albúmina'),
    'ALT':   (4,  'ALT/TGP (Alanino aminotransferasa)'),
    'GGT':   (7,  'GGT (Gamma Glutamiltransferasa)'),
    'MG':    (9,  'Magnesio'),
    'CALA':  (10, 'Calcio'),
    'BUN':   (11, 'Urea nitrogenada (BUN)'),
    'TRIG':  (13, 'Triglicéridos'),
    'TP':    (14, 'Proteínas Totales (TP)'),
    'AST':   (15, 'AST/TGO (Aspartato aminotransferasa)'),
    'AMY':   (16, 'Amilasa'),
    'NA':    (18, 'Sodio'),
    'CK':    (19, 'Creatin cinasa (CK)'),
    'CRE':   (20, 'Creatinina'),
    'TBILC': (21, 'Bilirrubina Total/TBIL'),
    'ALP':   (22, 'Fosfatasa Alcalina'),
    'LIP':   (23, 'Lipasa'),
    'K':     (24, 'Potasio'),
    'IRON':  (25, 'Hierro'),
    'UA':    (26, 'Acido Urico'),
    'LDL':   (27, 'Colesterol LDL (LDL-C)'),
    'DBILC': (28, 'Bilirrubina Directa (DBIL)'),
    'LDH':   (29, 'Deshidrogenasa Láctica (LDH)'),
    'PHOS':  (31, 'Fósforo'),
    'CL':    (32, 'Cloro (CL)'),
    'HDL':   (33, 'Colesterol HDL (HDL-C)')
}

# 2) Regex para extraer valores “CÓDIGO – {nivel} {valor}:”
pattern_valores = re.compile(r'([A-Z\-]+)\s*-\s*(\d)\s*([0-9]+(?:\.[0-9]+)?):')

# 3) Marcas que detienen la captura (en mayúsculas)
stop_markers = {"QC1 LIQUICHEK URINE", "INMUNOLOGY N1", "HBA1C QC N1"}

# 4) Carpeta donde están los archivos .txt (ajusta según sea necesario)
folder_path = './Datos_txt/'
if not os.path.isdir(folder_path):
    print(f"ERROR: La ruta '{folder_path}' no existe o no es una carpeta válida.", file=sys.stderr)
    sys.exit(1)

# 5) Función para procesar un único archivo .txt
def procesar_archivo_txt(file_path):
    with open(file_path, 'r', encoding='latin-1') as f:
        lines = f.readlines()

    # Inicializar DataFrame base con ceros
    base_rows = []
    for code, (aid, aname) in code_mapping.items():
        base_rows.append({
            'ID':       aid,
            'ANALITO':  aname,
            'NIVEL 1':  0.0,
            'NIVEL 2':  0.0,
            'NIVEL 3':  0.0
        })
    df = pd.DataFrame(base_rows).sort_values('ID').reset_index(drop=True)

    # Extraer la fecha (sin hora ni palabra "Índice")
    fecha_extraida = None
    for raw_line in lines:
        if 'NDICE' in raw_line.upper():
            idx = raw_line.upper().find('NDICE') + len('NDICE')
            resto = raw_line[idx:]
            parte_fecha = resto.strip().split(' ')[0]  # e.g. "05/31/2025"
            fecha_extraida = parte_fecha.replace('/', '_')
            break

    # Variables de control de bloque
    procesando = False

    # Recorrer líneas entre "LYPHOCHEK-ASSAYED" y siguiente stop_marker
    for raw_line in lines:
        line_up = raw_line.upper()

        if 'LYPHOCHEK-ASSAYED' in line_up:
            procesando = True
            continue

        if procesando and any(marker in line_up for marker in stop_markers):
            procesando = False
            continue

        if not procesando:
            continue

        for m in pattern_valores.finditer(line_up):
            raw_code = m.group(1).strip()
            nivel = int(m.group(2))
            valor = float(m.group(3))

            code = raw_code.upper()
            if code.endswith('-C'):
                code = code[:-2]
            code = code.replace('-', '')

            if code not in code_mapping:
                continue

            analyte_id, _ = code_mapping[code]
            fila_idx = df.index[df['ID'] == analyte_id]
            if len(fila_idx) != 1:
                print(f"ATENCIÓN: ID duplicado o no encontrado para '{raw_code}' en '{os.path.basename(file_path)}'.", file=sys.stderr)
                continue

            col_name = f'NIVEL {nivel}'
            df.at[fila_idx[0], col_name] = valor

    # Verificar si al menos un analito cambió de cero
    totales = df[['NIVEL 1','NIVEL 2','NIVEL 3']].sum(axis=1)
    if (totales == 0).all():
        return None, fecha_extraida

    return df, fecha_extraida

# 6) Primer pase: procesar todos los archivos y recolectar fechas
resultados = []  # Lista de tuplas: (filename, DataFrame, fecha_extraida, file_path)
for filename in os.listdir(folder_path):
    if not filename.lower().endswith('.txt'):
        continue
    file_path = os.path.join(folder_path, filename)
    try:
        df_res, fecha = procesar_archivo_txt(file_path)
    except Exception as e:
        print(f"ERROR al procesar '{filename}': {e}", file=sys.stderr)
        continue
    if df_res is None:
        continue
    resultados.append((filename, df_res, fecha, file_path))

# 7) Contar cuántas veces aparece cada fecha
fecha_counts = {}
for _, _, fecha, _ in resultados:
    if fecha:
        fecha_counts[fecha] = fecha_counts.get(fecha, 0) + 1

# 8) Segundo pase: guardar cada DataFrame con nombre ajustado
used_plain_dates = set()
for filename, df_res, fecha, file_path in resultados:
    if fecha:
        count = fecha_counts.get(fecha, 0)
        if count > 1:
            # Si aún no se usó la versión sin hora para esta fecha, emplear solo fecha
            if fecha not in used_plain_dates:
                nuevo_nombre = f"{fecha}.csv"
                used_plain_dates.add(fecha)
            else:
                # Para las demás ocurrencias, agregar hora de creación
                ctime = os.path.getctime(file_path)
                hora = datetime.fromtimestamp(ctime).strftime('%H%M')
                nuevo_nombre = f"{fecha}_{hora}.csv"
        else:
            # Si la fecha es única, basta con usar solo fecha
            nuevo_nombre = f"{fecha}.csv"
    else:
        base_name = os.path.splitext(filename)[0]
        nuevo_nombre = f"{base_name}.csv"

    output_path = os.path.join( "./Plantillas/",nuevo_nombre)
    try:
        df_res.to_csv(output_path, index=False, encoding='utf-8')
        print(f"Se generó '{nuevo_nombre}'.")
    except Exception as e:
        print(f"ERROR al guardar '{nuevo_nombre}': {e}", file=sys.stderr)
        continue

