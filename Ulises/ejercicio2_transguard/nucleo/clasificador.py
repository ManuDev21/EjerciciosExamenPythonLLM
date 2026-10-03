import json
import re
import time
import unicodedata

from pydantic import ValidationError

from . import llm
from .esquemas import ClasificacionLLM

CATEGORIAS_KW = {
    "carga_peligrosa": ["derrame", "fuga", "quimico", "acido", "inflamable",
                        "toxico", "corrosivo", "solvente", "gas", "peligrosa"],
    "peso_excedido": ["sobrepeso", "bascula", "exceso", "sobrecarga", "excede",
                      "toneladas de mas", "sobre el limite"],
    "acceso_indebido": ["sin autorizacion", "intruso", "colado", "forzada",
                        "no autorizado", "indebido", "valla", "perimetro", "saltaron"],
    "falla_equipo": ["grua", "lector", "camara", "escaner", "apagado", "danado",
                     "no enciende", "rfid", "corto", "quemado", "descompuesto"],
    "falla_sistema": ["tos", "sistema", "pantalla", "caido", "error", "lento",
                      "no carga", "aplicacion", "software", "congelado"],
    "estado_conductor": ["fatiga", "cansancio", "dormido", "somnolencia", "sueno",
                         "borracho", "mareado", "desvelado"],
}
PALABRAS_URGENTES = ["emergencia", "urgente", "accidente", "herido",
                     "incendio", "ahora", "inmediato", "grave"]
PRIORIDAD_BASE = {
    "carga_peligrosa": "critica",
    "estado_conductor": "alta",
    "acceso_indebido": "alta",
    "peso_excedido": "media",
    "falla_equipo": "media",
    "falla_sistema": "baja",
    "otro": "baja",
}
ORDEN_PRIORIDAD = ["baja", "media", "alta", "critica"]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def clasificar_por_reglas(asunto: str, cuerpo: str) -> dict:
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
    texto = f"{asunto}\n{cuerpo}"
    m_placa = re.search(r"\b[A-Z]{3}-\d{3}-[A-Z]\b", texto.upper())
    m_camion = re.search(r"\bTRK-\d+\b", texto.upper())
    m_peso = re.search(r"(\d+(?:[.,]\d+)?)\s*(toneladas|tonelada|ton|kg)\b", texto.lower())
    peso_kg = None
    if m_peso:
        valor = float(m_peso.group(1).replace(",", "."))
        peso_kg = valor if m_peso.group(2) == "kg" else valor * 1000
    m_ubic = re.search(r"\b(muelle|and[eé]n|gr[uú]a|d[aá]rsena|terminal|patio|zona)\s+([A-Za-z0-9]+)",
                       texto, re.IGNORECASE)
    return {
        "placa": m_placa.group(0) if m_placa else None,
        "camion_id": m_camion.group(0) if m_camion else None,
        "peso_reportado_kg": peso_kg,
        "ubicacion": f"{m_ubic.group(1)} {m_ubic.group(2)}".lower() if m_ubic else None,
    }


PROMPT_CLASIFICADOR = """Eres el clasificador de incidentes de la terminal portuaria TransGuard.
Analiza el correo y contesta EXCLUSIVAMENTE con un objeto JSON válido (sin
markdown ni texto extra) con esta estructura exacta:

{
  "categoria": "<carga_peligrosa | peso_excedido | acceso_indebido | falla_equipo | falla_sistema | estado_conductor | otro>",
  "prioridad": "<baja | media | alta | critica>",
  "entidades": {
    "placa": "<placa tipo ABC-123-D o null>",
    "camion_id": "<id tipo TRK-### o null>",
    "peso_reportado_kg": <numero en kg o null>,
    "ubicacion": "<lugar citado o null>"
  },
  "resumen": "<frase corta del incidente>"
}

Guía:
- carga_peligrosa: derrames, fugas, químicos, inflamables, gas, solventes.
- peso_excedido: báscula por encima del límite, sobrecarga.
- acceso_indebido: personas o unidades sin autorización, vallas forzadas.
- falla_equipo: grúas, cámaras, lectores, básculas dañadas o apagadas.
- falla_sistema: TOS, aplicaciones, pantallas, errores de software.
- estado_conductor: fatiga, somnolencia, conductor en mal estado.
- prioridad critica: peligro inmediato; alta: seguridad comprometida;
  media: operación afectada; baja: lo demás.
- Copia solo datos presentes en el correo; si falta un dato usa null.
"""


def _parsear_json(texto: str) -> dict:
    limpio = texto.strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(m.group(0))


def clasificar_llm(asunto: str, cuerpo: str, modelo: str,
                   max_intentos: int = 2) -> dict:
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
                             "La respuesta anterior no fue un JSON válido con el "
                             "esquema pedido. Contesta SOLO con el JSON correcto."})

    return {"ok": False, "datos": None, "crudo": crudo, "intentos": intentos,
            "latencia_ms": latencia_total, "error": ultimo_error}


def clasificar(asunto: str, cuerpo: str, modo: str = "hibrido",
               modelo: str = "llama3", max_intentos: int = 2) -> dict:
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
            return {**reglas, "fuente": "reglas (respaldo: LLM falló)",
                    "entidades": entidades_regex, "requiere_revision_humana": True,
                    "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                    "error_llm": res_llm["error"], "detalle": {"reglas": reglas, "llm": res_llm}}
        return {**res_llm["datos"], "fuente": "llm",
                "requiere_revision_humana": False,
                "latencia_ms": res_llm["latencia_ms"],
                "detalle": {"llm": res_llm}}

    if not res_llm["ok"]:
        return {**reglas, "fuente": "reglas (respaldo: LLM no disponible)",
                "entidades": entidades_regex, "requiere_revision_humana": False,
                "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                "error_llm": res_llm["error"], "detalle": {"reglas": reglas, "llm": res_llm}}

    cat_r, pri_r = reglas["categoria"], reglas["prioridad"]
    datos_llm = res_llm["datos"]
    cat_l, pri_l = datos_llm["categoria"], datos_llm["prioridad"]

    prioridad = pri_r if ORDEN_PRIORIDAD.index(pri_r) >= ORDEN_PRIORIDAD.index(pri_l) else pri_l
    if ORDEN_PRIORIDAD.index(pri_r) > ORDEN_PRIORIDAD.index(pri_l):
        categoria = cat_r
    else:
        categoria = cat_l
    revision = (cat_r != cat_l) or (pri_r != pri_l)

    entidades = {k: v for k, v in datos_llm["entidades"].items() if v is not None}
    for k, v in entidades_regex.items():
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


def evaluar_dataset(dataset: list, modos: list, modelo: str,
                    max_intentos: int = 2, progreso=None) -> dict:
    resultados = {m: {"aciertos_cat": 0, "aciertos_pri": 0, "latencias": [],
                      "matriz": {}, "detalle": []} for m in modos}
    total = len(dataset)

    for i, item in enumerate(dataset):
        for modo in modos:
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
    return {"total_correos": total, "modos": modos, "resultados": resumen}
