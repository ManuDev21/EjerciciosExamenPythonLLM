# -*- coding: utf-8 -*-
"""Cliente del LLM local (Ollama).

Centraliza las llamadas para medir latencia, limitar tiempo de espera y
saber si el servicio está disponible (la GUI lo usa para los avisos).
"""
import time

import ollama


def disponible() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False


def listar_modelos() -> list:
    try:
        return [m.get("model") for m in ollama.list().get("models", []) if m.get("model")]
    except Exception:
        return []


def chat(modelo: str, mensajes: list, json_mode: bool = False,
         timeout: int = 120) -> dict:
    """Llama a ollama.chat midiendo latencia.

    Devuelve {"ok": bool, "contenido": str, "latencia_ms": int, "error": str}
    """
    opciones = {"model": modelo, "messages": mensajes}
    if json_mode:
        opciones["format"] = "json"
    inicio = time.perf_counter()
    try:
        respuesta = ollama.chat(**opciones)
        latencia = int((time.perf_counter() - inicio) * 1000)
        return {"ok": True, "contenido": respuesta["message"]["content"],
                "latencia_ms": latencia, "error": None}
    except Exception as exc:
        latencia = int((time.perf_counter() - inicio) * 1000)
        return {"ok": False, "contenido": "", "latencia_ms": latencia,
                "error": f"{type(exc).__name__}: {exc}"}
