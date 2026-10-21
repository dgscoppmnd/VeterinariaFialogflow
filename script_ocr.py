import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from PIL import Image
import re
import json
import os

# --- Configuración de Tesseract (solo Windows) ---
# Descomenta y ajusta la ruta si estás en Windows:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- Regex para validar/extraer campos ---
FECHA_REGEX = re.compile(r"\d{2}/\d{2}/\d{4}")
IMPORTE_REGEX = re.compile(r"\d+[.,]\d{2}\s?€")
CODIGO_REGEX = re.compile(r"[A-Z]{2,4}-\d{3,6}")

def extraer_texto(ruta_imagen: str) -> str:
    """OCR con pytesseract, idioma español."""
    img = Image.open(ruta_imagen)
    # --psm 3 = segmentación automática (buena para documentos)
    config = "--psm 3"
    texto = pytesseract.image_to_string(img, lang="spa_old", config=config)
    return texto.strip()

def validar_campos(texto: str) -> dict:
    """Extrae campos validados con regex del texto OCR."""
    return {
        "fechas_encontradas": FECHA_REGEX.findall(texto),
        "importes_encontrados": IMPORTE_REGEX.findall(texto),
        "codigos_encontrados": CODIGO_REGEX.findall(texto),
    }

def procesar_documentos(carpeta: str = "documentos_ocr"):
    """Procesa todas las imágenes de una carpeta y genera documentos.json."""
    resultado = {}
    if not os.path.exists(carpeta):
        print(f"Crea la carpeta '{carpeta}' y mete ahí 3-5 imágenes de documentos.")
        return

    for archivo in sorted(os.listdir(carpeta)):
        if archivo.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp")):
            ruta = os.path.join(carpeta, archivo)
            print(f"Procesando: {archivo}...")
            texto = extraer_texto(ruta)
            campos = validar_campos(texto)
            resultado[archivo] = {
                "texto": texto,
                "campos_validados": campos,
            }
            print(f"  → Fechas: {campos['fechas_encontradas']}")
            print(f"  → Importes: {campos['importes_encontrados']}")
            print(f"  → Códigos: {campos['codigos_encontrados']}\n")

    with open("documentos.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"Guardado documentos.json con {len(resultado)} documentos.")

if __name__ == "__main__":
    procesar_documentos()