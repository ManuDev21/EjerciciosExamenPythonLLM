import re

from . import llm
from .db import ahora_iso

MAX_DOCS_CONTEXTO = 8


def _buscar_referencias(pregunta: str, store) -> list:
    hallados = []
    texto = pregunta.upper()

    ids_camion = {f"TRK-{n}" for n in re.findall(r"\bTRK-?\s?(\d+)\b", texto)}
    placas = set(re.findall(r"\b[A-Z]{3}-\d{3}-[A-Z]\b", texto))

    if ids_camion or placas:
        camiones = store.col("camiones").buscar()
        objetivos = [c for c in camiones
                     if c.get("camion_id") in ids_camion or c.get("placa") in placas]
        for cam in objetivos:
            cid = cam.get("camion_id")
            hallados.append({"coleccion": "camiones", "id": str(cam.get("_id")),
                             "resumen": f"{cid} placa {cam.get('placa')} naviera {cam.get('empresa')}",
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

    if re.search(r"incidente|correo|reporte|aviso", pregunta, re.IGNORECASE):
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

    if re.search(r"acceso|unidad|camion|ingres|entr[oó]|muelle", pregunta, re.IGNORECASE) and not ids_camion:
        for d in store.col("accesos").buscar(orden=[("timestamp", -1)], limite=5):
            hallados.append({"coleccion": "accesos", "id": str(d.get("_id")),
                             "resumen": f"{d.get('camion_id') or d.get('placa')} -> "
                                        f"{d.get('decision')} ({d.get('timestamp','')[:16]})",
                             "doc": d})
        if re.search(r"cu[aá]ntos|lista|todas|flota", pregunta, re.IGNORECASE):
            for d in store.col("camiones").buscar(limite=25):
                hallados.append({"coleccion": "camiones", "id": str(d.get("_id")),
                                 "resumen": f"{d.get('camion_id')} {d.get('placa')} {d.get('empresa')}",
                                 "doc": d})

    if re.search(r"riesgo|[ée]tic|peligro del sistema", pregunta, re.IGNORECASE):
        docs = store.col("riesgos_eticos").buscar()
        docs.sort(key=lambda d: d.get("probabilidad", 1) * d.get("impacto", 1), reverse=True)
        for d in docs[:MAX_DOCS_CONTEXTO]:
            hallados.append({"coleccion": "riesgos_eticos", "id": str(d.get("_id")),
                             "resumen": f"[{d.get('categoria')}] {d.get('descripcion','')[:70]} "
                                        f"P{d.get('probabilidad')}xI{d.get('impacto')}",
                             "doc": d})

    vistos, unicos = set(), []
    for h in hallados:
        clave = (h["coleccion"], h["id"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(h)
    return unicos[:MAX_DOCS_CONTEXTO]


def _contexto(hallados: list) -> str:
    lineas = []
    for h in hallados:
        d = h["doc"]
        partes = [f"[{h['coleccion']}#{h['id']}]"]
        if h["coleccion"] == "accesos":
            partes.append(f"camion={d.get('camion_id')} placa={d.get('placa')} "
                          f"P={d.get('P')} Q={d.get('Q')} R={d.get('R')} S={d.get('S')} "
                          f"D={d.get('D')} decision={d.get('decision')} "
                          f"fecha={d.get('timestamp','')[:16]}")
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


PROMPT_ASISTENTE = """Eres el asistente de la terminal portuaria TransGuard.
Contesta la pregunta del operador usando UNICAMENTE la información del
CONTEXTO (registros reales de la base de datos).

Reglas:
1. Cita el registro de origen con su etiqueta, p. ej. [accesos#abc123].
2. Si el contexto NO contiene la respuesta, responde exactamente:
   "No tengo información registrada sobre eso." No inventes nada.
3. Español claro y breve (máximo 3 párrafos cortos o viñetas).
4. Al explicar una decisión de acceso menciona las premisas (P,Q,R,S,D)
   que la provocaron según el razonamiento guardado.
"""


def responder(pregunta: str, store, modelo: str, sid: str = "") -> dict:
    hallados = _buscar_referencias(pregunta, store)
    fuentes = [{"coleccion": h["coleccion"], "id": h["id"], "resumen": h["resumen"]}
               for h in hallados]

    if not hallados:
        respuesta = ("No tengo información registrada sobre eso. "
                     "Puedo consultar unidades por placa o id (TRK-###), "
                     "accesos, incidentes y la matriz de riesgos.")
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
            respuesta = ("(LLM no disponible; se muestran los registros "
                         "recuperados directamente)\n\n" +
                         "\n".join(f"- {h['resumen']}  [{h['coleccion']}#{h['id']}]"
                                   for h in hallados))
            modo = "reglas"

    store.col("conversaciones").insertar(
        {"sid": sid, "pregunta": pregunta, "respuesta": respuesta,
         "fuentes": fuentes, "modo": modo, "timestamp": ahora_iso()})
    return {"respuesta": respuesta, "fuentes": fuentes, "modo": modo}
