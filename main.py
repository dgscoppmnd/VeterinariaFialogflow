from fastapi import FastAPI, Request
import re
import json
import os
import requests
from datetime import datetime

app = FastAPI()

# ============================================================
# CONFIGURACIÓN
# ============================================================
DOCS_PATH = "documentos.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"   # cambia a "llama3.2:1b" si va lento

# Regex obligatoria para DNI español
DNI_REGEX = re.compile(r"^\d{8}[A-Z]$")

# ============================================================
# CARGA DE DOCUMENTOS (generados por script_ocr.py)
# ============================================================
def cargar_documentos() -> dict:
    if os.path.exists(DOCS_PATH):
        with open(DOCS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

DOCUMENTOS = cargar_documentos()

# ============================================================
# LÓGICA DE NEGOCIO
# ============================================================
def validar_dni(dni: str) -> bool:
    """Valida el DNI con regex. Requisito obligatorio del enunciado."""
    if not dni:
        return False
    dni_limpio = re.sub(r"\s+", "", dni).upper()
    return bool(DNI_REGEX.match(dni_limpio.strip().upper()))

def consultar_llm(pregunta: str) -> str:
    """Envía los documentos como contexto al LLM con control de alucinaciones."""
    if not DOCUMENTOS:
        return "No tengo documentos cargados en este momento."

    # Construimos el contexto con el texto OCR de cada documento
    contexto = "\n\n".join(
        f"--- Documento: {nombre} ---\n{datos['texto']}"
        for nombre, datos in DOCUMENTOS.items()
    )

    # ==========================================
    # PRINTS DE DEPURACIÓN AÑADIDOS AQUÍ
    # ==========================================
    print("\n" + "="*50)
    print(f"[DEBUG LLM] PREGUNTA RECIBIDA: '{pregunta}'")
    print(f"[DEBUG LLM] LONGITUD DEL CONTEXTO: {len(contexto)} caracteres")
    print("--- INICIO DEL CONTEXTO ENVIADO A OLLAMA ---")
    print(contexto[:1500]) # Imprime solo los primeros 1500 caracteres para no saturar la consola
    if len(contexto) > 1500:
        print("\n[... RESTO DEL CONTEXTO OCULTO ...]")
    print("--- FIN DEL CONTEXTO ---")
    print("="*50 + "\n")
    # ==========================================

    prompt = f"""Eres el asistente de una clínica veterinaria.
Responde a la pregunta del usuario ÚNICAMENTE usando la información de los DOCUMENTOS.
Nota: El OCR ha leído el símbolo del Euro (€) como la letra 'E'. Si ves algo como "28,50 E", significa "28,50 €".
Si la respuesta no está en los documentos, responde exactamente:
"No encuentro esa información en los documentos de la clínica."
No inventes datos. No uses conocimiento externo.

DOCUMENTOS:
{contexto}

PREGUNTA: {pregunta}

RESPUESTA:"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "num_predict": 150,  # Limita la longitud máxima de la respuesta
                    "temperature": 0.1   # Reduce la aleatoriedad, acelera la selección de tokens
                }
            },
            timeout=4.5,   # margen bajo los 5 s de Dialogflow
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except requests.exceptions.Timeout:
        return "La consulta ha tardado demasiado. Inténtalo de nuevo."
    except Exception as e:
        print(f"[ERROR LLM] {e}")
        return "No he podido consultar los documentos en este momento."

# ============================================================
# ENDPOINT WEBHOOK DIALOGFLOW
# ============================================================
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    query_result = body.get("queryResult", {})
    intent = query_result.get("intent", {}).get("displayName", "")
    params = query_result.get("parameters", {})
    query_text = query_result.get("queryText", "")

    print(f"[WEBHOOK] intent={intent} params={params}")

    # --- Flujo de cita: validación de DNI con regex ---
    if intent == "dar_datos_mascota_v2":
        dni = params.get("dni", "")
        nombre = params.get("nombre_mascota", "")
        if not validar_dni(dni):
            return {
                "fulfillmentText": "El DNI no tiene el formato correcto. "
                                "Debe ser ocho números seguidos de una letra."
            }
        dni_limpio = re.sub(r"\s+", "", dni).upper()
        return {
            "fulfillmentText": f"Perfecto, tomo nota: {nombre}, DNI {dni_limpio}. "
                            f"¿Para qué fecha quieres la cita?"
        }

    # --- Confirmación final ---
    if intent == "confirmar_cita":
        respuesta = str(params.get("si-no", "")).lower()
        if "si" in respuesta or "sí" in respuesta:
            return {
                "fulfillmentText": "¡Genial! Cita confirmada. Te esperamos en la clínica."
            }
        return {
            "fulfillmentText": "De acuerdo, cancelamos la cita. ¿Puedo ayudarte en algo más?"
        }

    # --- Consulta documental con LLM ---
    if intent == "consulta_documentacion":
        respuesta = consultar_llm(query_text)
        return {"fulfillmentText": respuesta}

    # --- Fallback del webhook ---
    return {"fulfillmentText": "No estoy seguro de cómo ayudarte con eso."}


# ============================================================
# ENDPOINT DE SALUD (para probar ngrok sin Dialogflow)
# ============================================================
@app.get("/")
def health():
    return {
        "status": "ok",
        "documentos_cargados": list(DOCUMENTOS.keys()),
        "modelo_llm": OLLAMA_MODEL,
    }