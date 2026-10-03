# -*- coding: utf-8 -*-
"""Asistente explicativo con patrón RAG sencillo.

    pregunta -> recuperar de MongoDB -> construir contexto -> LLM responde
    SOLO con lo recuperado, citando los registros de origen. Si no hay
    datos, responde "No tengo información" (sin inventar). Si el LLM no
    está disponible, responde con una plantilla determinista.
"""
import re

from . import llm
from .db import ahora_iso

MAX_DOCS_CONTEXTO = 8


def _buscar_referencias(pregunta: str, store) -> list:
    """Recupera los documentos relevantes de MongoDB para la pregunta.

    Devuelve lista de {"coleccion", "id", "resumen", "doc"}.
    """
    hallados = []
    texto = pregunta.upper()

    ids_camion = set(re.findall(r"\bCAM-?\s?(\d+)\b", texto))
    ids_camion = {f"CAM-{n}" for n in ids_camion}
    placas = set(re.findall(r"\b[A-Z0-9]{2,3}-\d{2,3}-[A-Z0-9]{1,2}\b", texto))

    # --- búsqueda por camión / placa ----------------------------------------
    if ids_camion or placas:
        camiones = store.col("camiones").buscar()
        objetivos = [c for c in camiones
                     if c.get("camion_id") in ids_camion or c.get("placa") in placas]
        for cam in objetivos:
            cid = cam.get("camion_id")
            hallados.append({"coleccion": "camiones", "id": str(cam.get("_id")),
                             "resumen": f"{cid} placa {cam.get('placa')} empresa {cam.get('empresa')}",
                             "doc": cam})
            accesos_camion = (store.col("accesos").buscar({"camion_id": cid},
                              orden=[("timestamp", -1)], limite=3) +
                              store.col("accesos").buscar({"placa": cam.get("placa")},
                              orden=[("timestamp", -1)], limite=3))
            for acc in accesos_camion[:3]:
                hallados.append({"coleccion": "accesos", "id": str(acc.get("_id")),
                                 "resumen": f"acceso {acc.get('timestamp','?')[:16]}: {acc.get('decision')}",
                                 "doc": acc})
            for inc in store.col("incidentes").buscar(limite=400):
                datos = inc.get("datos_extraidos", {}) or {}
                if datos.get("camion_id") == cid or datos.get("placa") == cam.get("placa"):
                    hallados.append({"coleccion": "incidentes", "id": str(inc.get("_id")),
                                     "resumen": f"incidente {inc.get('clasificacion',{}).get('categoria')} "
                                                f"estado {inc.get('estado')}",
                                     "doc": inc})

    # --- intenciones generales ------------------------------------------------
    if re.search(r"incidente|correo|reporte", pregunta, re.IGNORECASE):
        if re.search(r"abierto|pendiente|nuevo|en_atencion|en atencion", pregunta, re.IGNORECASE):
            docs = store.col("incidentes").buscar(
                {"estado": {"$in": ["nuevo", "en_atencion"]}},
                orden=[("timestamp", -1)], limite=MAX_DOCS_CONTEXTO)
        else:
            docs = store.col("incidentes").buscar(
                orden=[("timestamp", -1)], limite=MAX_DOCS_CONTEXTO)
        for d in docs:
            hallados.append({"coleccion": "incidentes", "id": str(d.get("_id")),
                             "resumen": f"{d.get('clasificacion',{}).get('categoria')} "
                                        f"({d.get('clasificacion',{}).get('prioridad')}) "
                                        f"estado {d.get('estado')} - {d.get('asunto','')[:60]}",
                             "doc": d})

    if re.search(r"acceso|camion|camiones|entr[oó]|ingres", pregunta, re.IGNORECASE) and not ids_camion:
        for d in store.col("accesos").buscar(orden=[("timestamp", -1)], limite=5):
            hallados.append({"coleccion": "accesos", "id": str(d.get("_id")),
                             "resumen": f"{d.get('camion_id') or d.get('placa')} -> "
                                        f"{d.get('decision')} ({d.get('timestamp','')[:16]})",
                             "doc": d})
        for d in store.col("camiones").buscar(limite=20):
            if re.search(r"cu[aá]ntos|lista|todos", pregunta, re.IGNORECASE):
                hallados.append({"coleccion": "camiones", "id": str(d.get("_id")),
                                 "resumen": f"{d.get('camion_id')} {d.get('placa')} {d.get('empresa')}",
                                 "doc": d})
                break  # basta el conteo

    if re.search(r"riesgo|[ée]tic", pregunta, re.IGNORECASE):
        docs = store.col("riesgos_eticos").buscar()
        docs.sort(key=lambda d: d.get("probabilidad", 1) * d.get("impacto", 1), reverse=True)
        for d in docs[:MAX_DOCS_CONTEXTO]:
            hallados.append({"coleccion": "riesgos_eticos", "id": str(d.get("_id")),
                             "resumen": f"[{d.get('categoria')}] {d.get('descripcion','')[:70]} "
                                        f"P{d.get('probabilidad')}xI{d.get('impacto')}",
                             "doc": d})

    # deduplicar por (coleccion, id)
    vistos, unicos = set(), []
    for h in hallados:
        clave = (h["coleccion"], h["id"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(h)
    return unicos[:MAX_DOCS_CONTEXTO]


def _contexto(hallados: list) -> str:
    """Serializa los documentos recuperados como contexto para el LLM."""
    lineas = []
    for h in hallados:
        d = h["doc"]
        partes = [f"[{h['coleccion']}#{h['id']}]"]
        if h["coleccion"] == "accesos":
            partes.append(f"camion={d.get('camion_id')} placa={d.get('placa')} "
                          f"P={d.get('P')} Q={d.get('Q')} R={d.get('R')} S={d.get('S')} "
                          f"T={d.get('T')} V={d.get('V')} "
                          f"decision={d.get('decision')} fecha={d.get('timestamp','')[:16]}")
            pasos = d.get("explicacion") or []
            if pasos:
                partes.append("razonamiento: " + " | ".join(pasos[-4:]))
        elif h["coleccion"] == "incidentes":
            c = d.get("clasificacion", {})
            partes.append(f"asunto={d.get('asunto','')} categoria={c.get('categoria')} "
                          f"prioridad={c.get('prioridad')} estado={d.get('estado')} "
                          f"fecha={d.get('timestamp','')[:16]}")
        elif h["coleccion"] == "camiones":
            partes.append(f"camion_id={d.get('camion_id')} placa={d.get('placa')} "
                          f"empresa={d.get('empresa')} autorizacion={d.get('autorizacion')} "
                          f"certificacion_vigente={d.get('certificacion_vigente')} "
                          f"dias_cert={d.get('certificacion_dias_restantes')}")
        else:
            partes.append(f"modulo={d.get('modulo')} categoria={d.get('categoria')} "
                          f"descripcion={d.get('descripcion')} "
                          f"probabilidad={d.get('probabilidad')} impacto={d.get('impacto')} "
                          f"mitigacion={d.get('mitigacion','')}")
        lineas.append(" ".join(partes))
    return "\n".join(lineas)


PROMPT_ASISTENTE = """Eres el asistente del centro de control LogiSmart.
Responde la pregunta del operador usando EXCLUSIVAMENTE la información del
CONTEXTO (registros reales de la base de datos).

Reglas estrictas:
1. Cita siempre el registro de origen con su etiqueta, p. ej. [accesos#abc123].
2. Si el contexto NO contiene la respuesta, di exactamente:
   "No tengo información registrada sobre eso." No inventes datos.
3. Responde en español, claro y breve (máximo 3 párrafos cortos o viñetas).
4. Cuando expliques una decisión de acceso, menciona las premisas (P,Q,R,S,T,V)
   que la causaron según el razonamiento registrado.
"""


def responder(pregunta: str, store, modelo: str, sid: str = "") -> dict:
    hallados = _buscar_referencias(pregunta, store)
    fuentes = [{"coleccion": h["coleccion"], "id": h["id"], "resumen": h["resumen"]}
               for h in hallados]

    if not hallados:
        respuesta = ("No tengo información registrada sobre eso. "
                     "Puedo consultar camiones por placa o ID (CAM-###), "
                     "accesos recientes, incidentes y la matriz de riesgos.")
        modo = "sin_datos"
    else:
        contexto = _contexto(hallados)
        res = llm.chat(modelo, [
            {"role": "system", "content": PROMPT_ASISTENTE},
            {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPREGUNTA: {pregunta}"},
        ])
        if res["ok"]:
            respuesta = res["contenido"]
            modo = "llm"
        else:
            # Respaldo determinista cuando Ollama no está disponible
            respuesta = ("(LLM no disponible; respuesta generada solo con datos "
                         "recuperados)\n\n" +
                         "\n".join(f"- {h['resumen']}  [{h['coleccion']}#{h['id']}]"
                                   for h in hallados))
            modo = "reglas"

    store.col("conversaciones").insertar(
        {"sid": sid, "pregunta": pregunta, "respuesta": respuesta,
         "fuentes": fuentes, "modo": modo, "timestamp": ahora_iso()})
    return {"respuesta": respuesta, "fuentes": fuentes, "modo": modo}
