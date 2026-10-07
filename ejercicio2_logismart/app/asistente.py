import json
import re

from . import llm
from .db import ahora_iso

MAX_DOCS_CONTEXTO = 12


def _ref_incidente(d):
    return {"coleccion": "incidentes", "id": str(d.get("_id")),
            "resumen": f"{d.get('clasificacion',{}).get('categoria')} "
                       f"({d.get('clasificacion',{}).get('prioridad')}) "
                       f"estado {d.get('estado')} - {d.get('asunto','')[:60]}",
            "doc": d}


def _ref_acceso(d):
    return {"coleccion": "accesos", "id": str(d.get("_id")),
            "resumen": f"{d.get('camion_id') or d.get('placa')} -> "
                       f"{d.get('decision')} ({d.get('timestamp','')[:16]})",
            "doc": d}


def _ref_camion(d):
    return {"coleccion": "camiones", "id": str(d.get("_id")),
            "resumen": f"{d.get('camion_id')} {d.get('placa')} {d.get('empresa')}",
            "doc": d}


def _buscar_referencias(pregunta: str, store) -> list:
    hallados = []
    texto = pregunta.upper()
    q = pregunta.lower()

    ids_camion = {f"CAM-{n}" for n in re.findall(r"\bCAM-?\s?(\d+)\b", texto)}
    placas = set(re.findall(r"\b[A-Z0-9]{2,3}-\d{2,3}-[A-Z0-9]{1,2}\b", texto))

    if ids_camion or placas:
        camiones = store.col("camiones").buscar()
        objetivos = [c for c in camiones
                     if c.get("camion_id") in ids_camion or c.get("placa") in placas]
        for cam in objetivos:
            cid = cam.get("camion_id")
            hallados.append(_ref_camion(cam))
            accesos_camion = (store.col("accesos").buscar({"camion_id": cid},
                              orden=[("timestamp", -1)], limite=3) +
                              store.col("accesos").buscar({"placa": cam.get("placa")},
                              orden=[("timestamp", -1)], limite=3))
            for acc in accesos_camion[:3]:
                hallados.append(_ref_acceso(acc))
            for inc in store.col("incidentes").buscar(limite=400):
                datos = inc.get("datos_extraidos", {}) or {}
                if datos.get("camion_id") == cid or datos.get("placa") == cam.get("placa"):
                    hallados.append({**_ref_incidente(inc),
                                     "resumen": f"incidente {inc.get('clasificacion',{}).get('categoria')} "
                                                f"estado {inc.get('estado')}"})

    if re.search(r"incidente|correo|reporte|falla|alerta|derrame|fuga|accidente|problema|revisi[oó]n", q):
        if re.search(r"abierto|pendiente|nuevo|en_atencion|en atencion|urgente|crit", q):
            docs = store.col("incidentes").buscar(
                {"estado": {"$in": ["nuevo", "en_atencion"]}},
                orden=[("timestamp", -1)], limite=MAX_DOCS_CONTEXTO)
        else:
            docs = store.col("incidentes").buscar(
                orden=[("timestamp", -1)], limite=MAX_DOCS_CONTEXTO)
        for d in docs:
            hallados.append(_ref_incidente(d))

    if not ids_camion:
        if re.search(r"acceso|entr[oó]|ingres|salid|inspecci[oó]n|denegad|retenid|decisi[oó]n|sem[aá]foro", q):
            for d in store.col("accesos").buscar(orden=[("timestamp", -1)], limite=5):
                hallados.append(_ref_acceso(d))

        if re.search(r"camion|camiones|placa|tractor|unidad|veh[ií]culo|empresa|flota|registrad", q):
            for d in store.col("camiones").buscar(limite=20):
                hallados.append(_ref_camion(d))

    if re.search(r"riesgo|[ée]tic|matriz|privacidad|sesgo|transparencia", q):
        docs = store.col("riesgos_eticos").buscar()
        docs.sort(key=lambda d: d.get("probabilidad", 1) * d.get("impacto", 1), reverse=True)
        for d in docs[:MAX_DOCS_CONTEXTO]:
            hallados.append({"coleccion": "riesgos_eticos", "id": str(d.get("_id")),
                             "resumen": f"[{d.get('categoria')}] {d.get('descripcion','')[:70]} "
                                        f"P{d.get('probabilidad')}xI{d.get('impacto')}",
                             "doc": d})

    if not hallados and re.search(r"cu[aá]nt|total|hay|estado|resumen|hoy|[úu]ltim|recient|qu[eé]|estad[ií]stic", q):
        for d in store.col("incidentes").buscar(orden=[("timestamp", -1)], limite=4):
            hallados.append(_ref_incidente(d))
        for d in store.col("accesos").buscar(orden=[("timestamp", -1)], limite=4):
            hallados.append(_ref_acceso(d))
        for d in store.col("camiones").buscar(limite=20):
            hallados.append(_ref_camion(d))

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
2. Interpreta preguntas breves o ambiguas ("dame placas", "qué camiones hay",
   "incidentes", "cuántos") como solicitud de LISTAR o resumir los registros
   del contexto relacionados con lo pedido. Los registros [camiones#...]
   incluyen camion_id y placa: si piden placas o IDs, preséntalos como pares
   camion_id -> placa.
3. Solo si el contexto NO contiene nada relacionado con la pregunta, di
   exactamente: "No tengo información registrada sobre eso." No inventes datos.
4. Responde en español, claro y breve (máximo 3 párrafos cortos o viñetas).
5. Cuando expliques una decisión de acceso, menciona las premisas (P,Q,R,S,T,V)
   que la causaron según el razonamiento registrado.
"""

def responder_stream(pregunta: str, store, modelo: str, sid: str = ""):
    hallados = _buscar_referencias(pregunta, store)
    fuentes = [{"coleccion": h["coleccion"], "id": h["id"], "resumen": h["resumen"]}
               for h in hallados]

    if not hallados:
        respuesta = ("No tengo información registrada sobre eso. "
                     "Puedo consultar camiones por placa o ID (CAM-###), "
                     "accesos recientes, incidentes y la matriz de riesgos.")
        modo = "sin_datos"
        yield json.dumps({"chunk": respuesta}, ensure_ascii=False) + "\n"
    else:
        contexto = _contexto(hallados)
        try:
            respuesta = ""
            for trozo in llm.chat_stream(modelo, [
                {"role": "system", "content": PROMPT_ASISTENTE},
                {"role": "user", "content": f"CONTEXTO:\n{contexto}\n\nPREGUNTA: {pregunta}"},
            ]):
                respuesta += trozo
                yield json.dumps({"chunk": trozo}, ensure_ascii=False) + "\n"
            modo = "llm"
        except Exception:
            if respuesta:
                modo = "llm"
            else:
                respuesta = ("(LLM no disponible; respuesta generada solo con datos "
                             "recuperados)\n\n" +
                             "\n".join(f"- {h['resumen']}  [{h['coleccion']}#{h['id']}]"
                                       for h in hallados))
                modo = "reglas"
                yield json.dumps({"chunk": respuesta}, ensure_ascii=False) + "\n"

    store.col("conversaciones").insertar(
        {"sid": sid, "pregunta": pregunta, "respuesta": respuesta,
         "fuentes": fuentes, "modo": modo, "timestamp": ahora_iso()})
    yield json.dumps({"done": True, "fuentes": fuentes, "modo": modo},
                     ensure_ascii=False) + "\n"

def responder(pregunta: str, store, modelo: str, sid: str = "") -> dict:
    texto, meta = "", {}
    for linea in responder_stream(pregunta, store, modelo, sid):
        d = json.loads(linea)
        if "chunk" in d:
            texto += d["chunk"]
        else:
            meta = d
    return {"respuesta": texto,
            "fuentes": meta.get("fuentes", []),
            "modo": meta.get("modo", "")}
