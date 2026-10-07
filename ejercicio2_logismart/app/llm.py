import os
import time

import ollama

KEEP_ALIVE = os.environ.get("LLM_KEEP_ALIVE", "30m")

OPCIONES_BASE = {
    "num_ctx": 4096,
    "temperature": 0.4,
}
NUM_PREDICT = 800

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

_RESUELTO = {"preferido": None, "modelo": None, "ts": 0.0}
_RESOLVER_TTL = 30.0

def resolver_modelo(preferido: str = "") -> str:
    ahora = time.time()
    if (_RESUELTO["modelo"] and _RESUELTO["preferido"] == preferido
            and ahora - _RESUELTO["ts"] < _RESOLVER_TTL):
        return _RESUELTO["modelo"]
    nombres = listar_modelos()
    if preferido and preferido in nombres:
        modelo = preferido
    elif preferido and ":" not in preferido:
        modelo = next((n for n in nombres if n.split(":")[0] == preferido),
                      nombres[0] if nombres else preferido)
    else:
        modelo = nombres[0] if nombres else preferido
    _RESUELTO.update(preferido=preferido, modelo=modelo, ts=ahora)
    return modelo

def chat(modelo: str, mensajes: list, json_mode: bool = False,
         timeout: int = 120, num_predict: int = NUM_PREDICT) -> dict:
    opciones = {"model": modelo, "messages": mensajes,
                "keep_alive": KEEP_ALIVE,
                "options": {**OPCIONES_BASE, "num_predict": num_predict}}
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

def chat_stream(modelo: str, mensajes: list, num_predict: int = NUM_PREDICT):
    flujo = ollama.chat(model=modelo, messages=mensajes, stream=True,
                        keep_alive=KEEP_ALIVE,
                        options={**OPCIONES_BASE, "num_predict": num_predict})
    for parte in flujo:
        trozo = parte["message"]["content"]
        if trozo:
            yield trozo

def precalentar(modelo: str):
    try:
        chat(modelo, [{"role": "user", "content": "ok"}], num_predict=1)
    except Exception:
        pass
