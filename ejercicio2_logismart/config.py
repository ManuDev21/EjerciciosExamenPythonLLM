import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "logismart")
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "3000"))

MODELO_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
LLM_TIMEOUT_SEG = int(os.environ.get("LLM_TIMEOUT_SEG", "120"))
LLM_MAX_INTENTOS = int(os.environ.get("LLM_MAX_INTENTOS", "2"))
LLM_KEEP_ALIVE = os.environ.get("LLM_KEEP_ALIVE", "30m")

SECRET_KEY = os.environ.get("FLASK_SECRET", "logismart-dev-secret")

DATOS_DIR = os.path.join(BASE_DIR, "datos")
ARCHIVO_CORREOS = os.path.join(DATOS_DIR, "correos_etiquetados.json")
ARCHIVO_FALLBACK = os.path.join(DATOS_DIR, "local_fallback.json")
