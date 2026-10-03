# -*- coding: utf-8 -*-
"""Clasificador híbrido de incidentes: reglas + LLM con fusión segura.

Flujo:
    1. Clasificador por reglas (palabras clave, igual que el script base).
    2. Clasificador LLM (Ollama) que debe devolver un JSON exacto que se
       valida con pydantic; si el JSON es inválido se reintenta y después
       se cae al clasificador por reglas (plan de respaldo).
    3. Fusión: si ambos discrepan, prevalece la prioridad más alta
       (ante la duda, seguridad) y se marca requiere_revision_humana.
"""
import json
import re
import time
import unicodedata

from pydantic import ValidationError

from . import llm
from .esquemas import ClasificacionLLM

# ---------------------------------------------------------------------------
# 1. CLASIFICADOR POR REGLAS (idéntico al script monolítico)
# ---------------------------------------------------------------------------

CATEGORIAS_KW = {
    "materiales_peligrosos": ["peligroso", "derrame", "fuga", "quimico", "inflamable", "toxico", "corrosivo"],
    "sobrepeso": ["sobrepeso", "excede", "bascula", "exceso de peso", "sobrecarga"],
    "acceso_no_autorizado": ["sin autorizacion", "no autorizado", "acceso denegado", "barrera", "intruso"],
    "falla_hardware": ["camara", "sensor", "lector", "rfid", "no enciende", "apagado", "danado", "falla electrica"],
    "falla_software": ["sistema", "error", "pantalla", "caido", "no carga", "lento", "software", "aplicacion"],
    "somnolencia_conductor": ["somnolencia", "dormido", "cansancio", "fatiga", "sueno"],
}
PALABRAS_URGENTES = ["urgente", "emergencia", "accidente", "incendio", "herido", "critico", "inmediato"]
PRIORIDAD_BASE = {
    "materiales_peligrosos": "critica",
    "somnolencia_conductor": "alta",
    "acceso_no_autorizado": "alta",
    "sobrepeso": "media",
    "falla_hardware": "media",
    "falla_software": "baja",
    "otro": "baja",
}
ORDEN_PRIORIDAD = ["baja", "media", "alta", "critica"]


def _normalizar(texto: str) -> str:
    """Minúsculas sin acentos ni ñ para comparar palabras clave."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def clasificar_por_reglas(asunto: str, cuerpo: str) -> dict:
    """Categoría por conteo de palabras clave + escalado por urgencia."""
    texto = _normalizar(f"{asunto} {cuerpo}")
    puntajes = {cat: [kw for kw in kws if kw in texto] for cat, kws in CATEGORIAS_KW.items()}
    mejor_cat = max(puntajes, key=lambda c: len(puntajes[c]))
    coincidencias = puntajes[mejor_cat]
    if not coincidencias:
        mejor_cat = "otro"

    prioridad = PRIORIDAD_BASE[mejor_cat]
    urgentes = [p for p in PALABRAS_URGENTES if p in texto]
    if urgentes:
        idx = min(ORDEN_PRIORIDAD.index(prioridad) + 1, len(ORDEN_PRIORIDAD) - 1)
        prioridad = ORDEN_PRIORIDAD[idx]

    return {"categoria": mejor_cat, "prioridad": prioridad,
            "palabras_clave": coincidencias + urgentes}


def extraer_datos(asunto: str, cuerpo: str) -> dict:
    """Entidades por expresiones regulares (None si no se encuentran)."""
    texto = f"{asunto}\n{cuerpo}"
    m_placa = re.search(r"\b[A-Z0-9]{2,3}-\d{2,3}-[A-Z0-9]{1,2}\b", texto.upper())
    m_camion = re.search(r"\bCAM-\d+\b", texto.upper())
    m_peso = re.search(r"(\d+(?:[.,]\d+)?)\s*(toneladas|tonelada|ton|t|kg)\b", texto.lower())
    peso_kg = None
    if m_peso:
        valor = float(m_peso.group(1).replace(",", "."))
        peso_kg = valor if m_peso.group(2) == "kg" else valor * 1000
    m_ubic = re.search(r"\b(and[eé]n|puerta|muelle|caseta|dock)\s+([A-Za-z0-9]+)", texto, re.IGNORECASE)
    return {
        "placa": m_placa.group(0) if m_placa else None,
        "camion_id": m_camion.group(0) if m_camion else None,
        "peso_reportado_kg": peso_kg,
        "ubicacion": f"{m_ubic.group(1)} {m_ubic.group(2)}".lower() if m_ubic else None,
    }


# ---------------------------------------------------------------------------
# 2. CLASIFICADOR LLM (JSON estricto validado con pydantic + reintentos)
# ---------------------------------------------------------------------------

PROMPT_CLASIFICADOR = """Eres el clasificador de incidentes del centro logístico LogiSmart.
Analiza el correo y responde ÚNICAMENTE con un objeto JSON válido, sin texto
adicional, sin markdown, con EXACTAMENTE esta estructura:

{
  "categoria": "<una de: materiales_peligrosos | sobrepeso | acceso_no_autorizado | falla_hardware | falla_software | somnolencia_conductor | otro>",
  "prioridad": "<una de: baja | media | alta | critica>",
  "entidades": {
    "placa": "<placa vehicular o null>",
    "camion_id": "<id tipo CAM-### o null>",
    "peso_reportado_kg": <número en kg o null>,
    "ubicacion": "<lugar mencionado o null>"
  },
  "resumen": "<una frase corta describiendo el incidente>"
}

Reglas:
- materiales_peligrosos: derrames, fugas, químicos, inflamables, tóxicos.
- sobrepeso: exceso de peso en báscula, sobrecarga.
- acceso_no_autorizado: ingresos sin autorización, intrusos, barrera forzada.
- falla_hardware: cámaras, sensores, lectores RFID dañados o apagados.
- falla_software: sistema, aplicación, pantallas, errores de software.
- somnolencia_conductor: conductor dormido, fatiga, cansancio.
- prioridad critica: riesgo inmediato a personas o materiales peligrosos;
  alta: seguridad comprometida; media: operación afectada; baja: resto.
- Extrae solo datos presentes en el correo; si falta un dato usa null.
"""


def _parsear_json(texto: str) -> dict:
    """Tolera que el LLM envuelva el JSON en ```json ... ``` o texto extra."""
    limpio = texto.strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(m.group(0))


def clasificar_llm(asunto: str, cuerpo: str, modelo: str,
                   max_intentos: int = 2) -> dict:
    """Devuelve la clasificación del LLM validada con pydantic.

    Retorna {ok, datos, crudo, intentos, latencia_ms, error}.
    """
    if not llm.disponible():
        return {"ok": False, "datos": None, "crudo": None, "intentos": 0,
                "latencia_ms": 0, "error": "Ollama no disponible"}

    correo = f"ASUNTO: {asunto}\n\nCUERPO:\n{cuerpo}"
    mensajes = [{"role": "system", "content": PROMPT_CLASIFICADOR},
                {"role": "user", "content": correo}]
    crudo, ultimo_error, latencia_total, intentos = None, None, 0, 0

    for intento in range(1, max_intentos + 1):
        intentos = intento
        res = llm.chat(modelo, mensajes, json_mode=True)
        latencia_total += res["latencia_ms"]
        if not res["ok"]:
            ultimo_error = res["error"]
            break
        crudo = res["contenido"]
        try:
            datos = ClasificacionLLM.model_validate(_parsear_json(crudo))
            return {"ok": True, "datos": datos.model_dump(), "crudo": crudo,
                    "intentos": intentos, "latencia_ms": latencia_total, "error": None}
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            ultimo_error = f"JSON inválido (intento {intento}): {exc}"
            mensajes.append({"role": "user", "content":
                             "Tu respuesta no fue un JSON válido con el esquema "
                             "requerido. Responde SOLO con el JSON correcto."})

    return {"ok": False, "datos": None, "crudo": crudo, "intentos": intentos,
            "latencia_ms": latencia_total, "error": ultimo_error}


# ---------------------------------------------------------------------------
# 3. FUSIÓN (híbrido)
# ---------------------------------------------------------------------------

def clasificar(asunto: str, cuerpo: str, modo: str = "hibrido",
               modelo: str = "llama3", max_intentos: int = 2) -> dict:
    """Punto único de entrada. modo: reglas | llm | hibrido."""
    inicio = time.perf_counter()
    reglas = clasificar_por_reglas(asunto, cuerpo)
    entidades_regex = extraer_datos(asunto, cuerpo)

    if modo == "reglas":
        return {**reglas, "fuente": "reglas", "entidades": entidades_regex,
                "requiere_revision_humana": False,
                "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                "detalle": {"reglas": reglas}}

    res_llm = clasificar_llm(asunto, cuerpo, modelo, max_intentos)

    if modo == "llm":
        if not res_llm["ok"]:
            # plan de respaldo: el LLM falló -> se entrega el clasificador por reglas
            return {**reglas, "fuente": "reglas (respaldo: LLM falló)",
                    "entidades": entidades_regex, "requiere_revision_humana": True,
                    "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                    "error_llm": res_llm["error"], "detalle": {"reglas": reglas, "llm": res_llm}}
        return {**res_llm["datos"], "fuente": "llm",
                "requiere_revision_humana": False,
                "latencia_ms": res_llm["latencia_ms"],
                "detalle": {"llm": res_llm}}

    # ---- híbrido ----------------------------------------------------------
    if not res_llm["ok"]:
        return {**reglas, "fuente": "reglas (respaldo: LLM no disponible)",
                "entidades": entidades_regex, "requiere_revision_humana": False,
                "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                "error_llm": res_llm["error"], "detalle": {"reglas": reglas, "llm": res_llm}}

    cat_r, pri_r = reglas["categoria"], reglas["prioridad"]
    datos_llm = res_llm["datos"]
    cat_l, pri_l = datos_llm["categoria"], datos_llm["prioridad"]

    # prioridad final = la más alta reportada (ante la duda, seguridad)
    prioridad = pri_r if ORDEN_PRIORIDAD.index(pri_r) >= ORDEN_PRIORIDAD.index(pri_l) else pri_l
    # la categoría se toma del clasificador que reportó la prioridad mayor;
    # en empate se conserva la del LLM (entendió la semántica del correo)
    if ORDEN_PRIORIDAD.index(pri_r) > ORDEN_PRIORIDAD.index(pri_l):
        categoria = cat_r
    else:
        categoria = cat_l
    revision = (cat_r != cat_l) or (pri_r != pri_l)

    entidades = {k: v for k, v in datos_llm["entidades"].items() if v is not None}
    for k, v in entidades_regex.items():  # regex como respaldo de campos nulos
        entidades.setdefault(k, v)

    return {"categoria": categoria, "prioridad": prioridad,
            "resumen": datos_llm.get("resumen", ""),
            "palabras_clave": reglas["palabras_clave"],
            "entidades": entidades,
            "fuente": "hibrido",
            "requiere_revision_humana": revision,
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "detalle": {"reglas": {"categoria": cat_r, "prioridad": pri_r},
                        "llm": {"categoria": cat_l, "prioridad": pri_l,
                                "intentos": res_llm["intentos"]}}}


# ---------------------------------------------------------------------------
# 4. EVALUACIÓN CON DATASET ETIQUETADO
# ---------------------------------------------------------------------------

def evaluar_dataset(dataset: list, modelos_modos: list, modelo: str,
                    max_intentos: int = 2, progreso=None) -> dict:
    """Corre el/los clasificadores sobre el dataset etiquetado.

    modelos_modos: subconjunto de ["reglas", "llm", "hibrido"].
    Devuelve métricas por modo: exactitud (categoría y prioridad), matriz de
    confusión de categorías y latencia promedio.
    """
    resultados = {m: {"aciertos_cat": 0, "aciertos_pri": 0, "latencias": [],
                      "matriz": {}, "detalle": []} for m in modelos_modos}
    total = len(dataset)

    for i, item in enumerate(dataset):
        for modo in modelos_modos:
            r = clasificar(item["asunto"], item["cuerpo"], modo=modo,
                           modelo=modelo, max_intentos=max_intentos)
            acc = resultados[modo]
            ok_cat = r["categoria"] == item["categoria"]
            ok_pri = r["prioridad"] == item["prioridad"]
            acc["aciertos_cat"] += ok_cat
            acc["aciertos_pri"] += ok_pri
            acc["latencias"].append(r["latencia_ms"])
            clave = f'{item["categoria"]} -> {r["categoria"]}'
            acc["matriz"][clave] = acc["matriz"].get(clave, 0) + 1
            acc["detalle"].append({"id": item.get("id", i + 1),
                                   "esperada": item["categoria"],
                                   "obtenida": r["categoria"],
                                   "prioridad_esperada": item["prioridad"],
                                   "prioridad_obtenida": r["prioridad"],
                                   "correcto": ok_cat})
        if progreso:
            progreso(i + 1, total)

    resumen = {}
    for modo, acc in resultados.items():
        resumen[modo] = {
            "exactitud_categoria": round(acc["aciertos_cat"] / total, 4) if total else 0,
            "exactitud_prioridad": round(acc["aciertos_pri"] / total, 4) if total else 0,
            "latencia_promedio_ms": int(sum(acc["latencias"]) / len(acc["latencias"])) if acc["latencias"] else 0,
            "matriz_confusion": acc["matriz"],
            "detalle": acc["detalle"],
        }
    return {"total_correos": total, "modos": modelos_modos, "resultados": resumen}
