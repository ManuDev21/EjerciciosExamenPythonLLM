# -*- coding: utf-8 -*-
"""Configuración global de LogiSmart.

Los valores pueden sobreescribirse con variables de entorno o desde la
página de Configuración de la propia aplicación (colección `configuracion`).
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- MongoDB ---------------------------------------------------------------
# Por defecto se usa el clúster/servicio local; para Atlas:
#   set MONGO_URI=mongodb+srv://usuario:clave@cluster.../logismart
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "logismart")
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "3000"))

# --- Ollama ----------------------------------------------------------------
MODELO_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3")
LLM_TIMEOUT_SEG = int(os.environ.get("LLM_TIMEOUT_SEG", "120"))
LLM_MAX_INTENTOS = int(os.environ.get("LLM_MAX_INTENTOS", "2"))

# --- Flask -----------------------------------------------------------------
SECRET_KEY = os.environ.get("FLASK_SECRET", "logismart-dev-secret")

# --- Archivos ---------------------------------------------------------------
DATOS_DIR = os.path.join(BASE_DIR, "datos")
ARCHIVO_CORREOS = os.path.join(DATOS_DIR, "correos_etiquetados.json")
ARCHIVO_FALLBACK = os.path.join(DATOS_DIR, "local_fallback.json")
