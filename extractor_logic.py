import pandas as pd
import re

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

# 2) Regex para extraer valores "CÓDIGO – {nivel} {valor}:"
pattern_valores = re.compile(r'([A-Z\-]+)\s*-\s*(\d)\s*([0-9]+(?:\.[0-9]+)?):')

# 3) Marcas que detienen la captura (en mayúsculas)
stop_markers = {"QC1 LIQUICHEK URINE", "INMUNOLOGY N1", "HBA1C QC N1"}

def procesar_archivo_txt(lines):
    """
    Procesa las líneas de un archivo de texto de laboratorio y retorna un DataFrame con los resultados.
    """
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

    # Extraer la fecha
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
                continue

            col_name = f'NIVEL {nivel}'
            df.at[fila_idx[0], col_name] = valor

    # Calcular cuántos valores son cero (para que el usuario decida si hay duplicados)
    # Consideramos las columnas de niveles
    niveles_cols = ['NIVEL 1', 'NIVEL 2', 'NIVEL 3']
    num_ceros = (df[niveles_cols] == 0.0).sum().sum()
    
    totales = df[niveles_cols].sum(axis=1)
    if (totales == 0).all():
        return None, fecha_extraida, num_ceros

    return df, fecha_extraida, num_ceros

def process_uploaded_files(uploaded_files):
    """
    Procesa una lista de archivos subidos en Streamlit.
    Devuelve un diccionario donde la clave es la fecha y el valor es una lista de diccionarios con info de cada archivo.
    """
    resultados_por_fecha = {}
    
    for uploaded_file in uploaded_files:
        content = uploaded_file.getvalue().decode('latin-1')
        lines = content.split('\n')
        
        df_res, fecha, num_ceros = procesar_archivo_txt(lines)
        
        if df_res is not None:
            if fecha not in resultados_por_fecha:
                resultados_por_fecha[fecha] = []
            
            resultados_por_fecha[fecha].append({
                'filename': uploaded_file.name,
                'df': df_res,
                'num_ceros': num_ceros
            })
            
    return resultados_por_fecha
