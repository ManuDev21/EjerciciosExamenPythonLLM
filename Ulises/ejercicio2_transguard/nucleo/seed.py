import random
from datetime import datetime, timedelta, timezone

from .clasificador import clasificar_por_reglas, extraer_datos
from .db import ahora_iso
from .reglas import evaluar_camion

CAMIONES_DEMO = [
    {"placa": "PTX-104-B", "camion_id": "TRK-201", "empresa": "Naviera del Istmo",
     "autorizacion": True, "certificacion_vigente": True, "certificacion_dias_restantes": 200},
    {"placa": "MRN-318-E", "camion_id": "TRK-202", "empresa": "Aduanas y Carga del Pacífico",
     "autorizacion": True, "certificacion_vigente": True, "certificacion_dias_restantes": 21},
    {"placa": "SOL-772-K", "camion_id": "TRK-203", "empresa": "Terminal Intermodal Sur",
     "autorizacion": True, "certificacion_vigente": False, "certificacion_dias_restantes": 0},
    {"placa": "BLQ-090-M", "camion_id": "TRK-204", "empresa": "Naviera del Istmo",
     "autorizacion": False, "certificacion_vigente": True, "certificacion_dias_restantes": 150},
    {"placa": "GRV-515-N", "camion_id": "TRK-205", "empresa": "Grúas y Transporte Pesado",
     "autorizacion": True, "certificacion_vigente": True, "certificacion_dias_restantes": 12},
    {"placa": "KLM-233-Q", "camion_id": "TRK-206", "empresa": "Química Portuaria SA",
     "autorizacion": True, "certificacion_vigente": True, "certificacion_dias_restantes": 280},
    {"placa": "DRS-641-T", "camion_id": "TRK-207", "empresa": "Terminal Intermodal Sur",
     "autorizacion": True, "certificacion_vigente": True, "certificacion_dias_restantes": 45},
    {"placa": "WZX-877-V", "camion_id": "TRK-208", "empresa": "Fletes del Golfo",
     "autorizacion": False, "certificacion_vigente": False, "certificacion_dias_restantes": 0},
]

RIESGOS_DEMO = [
    {"modulo": "Clasificador mixto",
     "descripcion": "El LLM puede fabricar categorías o datos que no existen en "
                    "el correo cuando el texto es ambiguo.",
     "categoria": "transparencia", "probabilidad": 4, "impacto": 4,
     "mitigacion": "JSON validado con pydantic, reintentos y respaldo por reglas; "
                   "bandera de revisión humana ante discrepancias.",
     "probabilidad_residual": 2, "impacto_residual": 3},
    {"modulo": "Motor de palabras",
     "descripcion": "Correos con mala ortografía, abreviaturas portuarias o mezcla "
                    "de idiomas quedan subclasificados por falta de palabra clave.",
     "categoria": "sesgo", "probabilidad": 4, "impacto": 3,
     "mitigacion": "Normalización, dataset con lenguaje informal y revisión humana "
                   "obligada de la categoría 'otro'.",
     "probabilidad_residual": 3, "impacto_residual": 2},
    {"modulo": "Expediente de conductores",
     "descripcion": "Datos personales de los operadores (certificados, eventos de "
                    "fatiga) guardados en la base de datos.",
     "categoria": "privacidad", "probabilidad": 3, "impacto": 5,
     "mitigacion": "Mínimo necesario, acceso por rol, retención limitada y cifrado.",
     "probabilidad_residual": 2, "impacto_residual": 4},
    {"modulo": "Operación asistida",
     "descripcion": "El personal puede dejar de contrastar las decisiones "
                    "automáticas por costumbre o presión de tiempo.",
     "categoria": "responsabilidad", "probabilidad": 3, "impacto": 4,
     "mitigacion": "Explicación visible de cada decisión y auditorías sorpresa.",
     "probabilidad_residual": 2, "impacto_residual": 3},
    {"modulo": "Asistente contextual",
     "descripcion": "Inventa respuestas plausibles cuando no existen registros "
                    "suficientes en la base.",
     "categoria": "transparencia", "probabilidad": 3, "impacto": 4,
     "mitigacion": "RAG estricto con citas obligatorias y frase fija de "
                   "'sin información'.",
     "probabilidad_residual": 2, "impacto_residual": 3},
    {"modulo": "Verificador documental",
     "descripcion": "La regla Z con umbrales incorrectos puede frenar embarques "
                    "legítimos por falsa falta de papeles.",
     "categoria": "seguridad", "probabilidad": 2, "impacto": 4,
     "mitigacion": "Tablas de verdad verificables y simulador previo a cambios.",
     "probabilidad_residual": 1, "impacto_residual": 3},
]


def _hace(dias: int, horas: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=dias, hours=horas)).isoformat(timespec="seconds")


def sembrar(store, correos: list = None, forzar: bool = False) -> dict:
    resumen = {}

    col = store.col("camiones")
    if forzar:
        col.vaciar()
    if col.contar() == 0:
        for c in CAMIONES_DEMO:
            col.insertar(c)
        resumen["camiones"] = len(CAMIONES_DEMO)

    col = store.col("accesos")
    if forzar:
        col.vaciar()
    if col.contar() == 0:
        rng = random.Random(99)
        n = 0
        for cam in CAMIONES_DEMO:
            for _ in range(rng.randint(1, 3)):
                P = cam["autorizacion"]
                Q = rng.random() < 0.2
                R = "Química" in cam["empresa"] or rng.random() < 0.15
                S = cam["certificacion_vigente"]
                D = rng.random() > 0.2
                res = evaluar_camion(P, Q, R, S, D)
                col.insertar({"camion_id": cam["camion_id"], "placa": cam["placa"],
                              "P": P, "Q": Q, "R": R, "S": S, "D": D,
                              "A": res["A"], "E": res["E"], "Z": res["Z"], "Y": res["Y"],
                              "decision": res["decision"], "semaforo": res["semaforo"],
                              "explicacion": res["explicacion"],
                              "operador": "demo", "timestamp": _hace(rng.randint(0, 21), rng.randint(0, 14))})
                n += 1
        resumen["accesos"] = n

    col = store.col("incidentes")
    if forzar:
        col.vaciar()
    if col.contar() == 0 and correos:
        rng = random.Random(13)
        estados = ["nuevo", "en_atencion", "cerrado", "cerrado", "nuevo"]
        n = 0
        for item in rng.sample(correos, min(14, len(correos))):
            c = clasificar_por_reglas(item["asunto"], item["cuerpo"])
            col.insertar({
                "remitente": item.get("remitente", "vigilante@muelle.local"),
                "asunto": item["asunto"], "cuerpo": item["cuerpo"],
                "clasificacion": {**c, "fuente": "reglas (demo)"},
                "datos_extraidos": extraer_datos(item["asunto"], item["cuerpo"]),
                "estado": rng.choice(estados),
                "requiere_revision_humana": False,
                "timestamp": _hace(rng.randint(0, 28), rng.randint(0, 20)),
                "historial": [{"ts": _hace(rng.randint(0, 2)), "evento": "creado por seed"}],
            })
            n += 1
        resumen["incidentes"] = n

    col = store.col("riesgos_eticos")
    if forzar:
        col.vaciar()
    if col.contar() == 0:
        for r in RIESGOS_DEMO:
            col.insertar({**r, "historico": [{"ts": ahora_iso(), "evento": "alta (seed)"}]})
        resumen["riesgos_eticos"] = len(RIESGOS_DEMO)

    store.col("meta").insertar({"_tipo": "seed", "ts": ahora_iso(), "resumen": resumen})
    return resumen
