# Veterinaria Dialogflow
## Descripción del caso de uso

Asistente conversacional por voz para una clínica veterinaria que permite
pedir cita para una mascota recogiendo los datos del dueño (nombre de la
mascota y DNI validado con expresión regular) en un flujo multi-turno con
confirmación final. Además, el agente responde preguntas sobre un conjunto
de documentos de la clínica (prospectos, guías de cuidados y horarios)
previamente procesados con OCR, enviando su texto como contexto a un LLM
local con control explícito de alucinaciones: si la respuesta no está en
los documentos, el bot lo dice en lugar de inventarla.


## Arquitectura

![Arquitectura](diagramaAPP.xml)

Flujo: usuario (voz) → Dialogflow ES (STT + agente + TTS) → webhook
FastAPI expuesto con ngrok → validación regex + lógica de cita → LLM
(Ollama) con contexto de `documentos.json` generado offline con Tesseract.


## Intenciones del agente

| Intención | Propósito | Entidades / Contexto |
|---|---|---|
| `Default Welcome Intent` | Saludo inicial | — |
| `Default Fallback Intent` | Fallback estándar | — |
| `pedir_cita_inicio` | Inicia el flujo de cita | Salida: `cita_pendiente` |
| `dar_datos_mascota` | Recoge nombre y DNI | `@dni` (regex, obligatorio) · Entrada: `cita_pendiente` · Salida: `cita_datos` |
| `dar_fecha_hora` | Recoge la fecha | `@sys.date` (obligatorio) · Entrada: `cita_datos` · Salida: `cita_confirmacion` |
| `confirmar_cita` | Confirmación sí/no | `@si_no` (obligatorio) · Entrada: `cita_confirmacion` |
| `consultar_documentacion` | Pregunta sobre documentos OCR | Webhook → LLM |
| `consultar_horario` | Consulta horarios | `@sys.date` |



## Decisiones técnicas

- **Tesseract + pytesseract** para OCR: open source, sin coste, suficiente
  para 3–5 documentos claros. Idioma `spa` para español.
- **Validación regex doble del DNI** (`^\d{8}[A-Z]$`): una en la entidad
  regex de Dialogflow y otra en el webhook (defensa en profundidad, requisito
  del enunciado).
- **Contexto directo en el prompt** en lugar de base vectorial: con 3–5
  documentos no se justifica ChromaDB/FAISS; se incluye el texto completo
  en el prompt.
- **Ollama local con `llama3.2:3b`**: evita API keys y costes, y permite
  cumplir la latencia < 5 s por turno.
- **Control de alucinaciones**: el prompt instruye explícitamente a
  responder solo con los documentos y a decir "No encuentro esa información
  en los documentos de la clínica" si no está.
- **SSML** (`<break>`, `<say-as>`) en las respuestas clave para mejorar la
  naturalidad del TTS nativo.



  ## Cómo ejecutar

### Requisitos
- Python 3.9+
- Tesseract OCR con paquete de idioma `spa`
- Ollama con el modelo `llama3.2:3b`
- ngrok

### Pasos

1. Instalar dependencias:
   ```bash
   pip install -r requirements.txt

2. (Solo Windows) Configurar la ruta de Tesseract en script_ocr.py:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

3. Generar documentos.json (una sola vez):
python script_ocr.py

4. Arrancar Ollama y descargar el modelo:
ollama pull llama3.2:3b

5. Arrancar el webhook:
uvicorn main:app --reload --port 8000

6. Exponer con ngrok:
ngrok http 8000

7. En Dialogflow ES, pegar la URL de ngrok + /webhook en
Fulfillment y activar el webhook en dar_datos_mascota,
confirmar_cita y consultar_documentacion.

8. Probar en el simulador de Dialogflow con el micrófono activado.