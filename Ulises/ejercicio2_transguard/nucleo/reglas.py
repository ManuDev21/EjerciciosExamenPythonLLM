import itertools

PREMISAS = {
    "P": "Unidad con autorización previa de ingreso",
    "Q": "El peso rebasa el límite de la terminal",
    "R": "Mercancía catalogada como peligrosa",
    "S": "Operador con licencia/certificado vigente",
    "D": "Documentación portuaria completa (BL, manifiesto)",
}

REGLAS = {
    "A": "P ∧ S ∧ ¬Q     (ingreso libre)",
    "E": "P ∧ (R ∨ Q)   (canal de inspección)",
    "Z": "P ∧ ¬D        (retención documental)",
    "Y": "P ∧ Q ∧ R     (protocolo de emergencia)",
}

JUSTIFICACIONES = {
    "Z": ("Un camión autorizado que llega sin la documentación completa no puede "
          "desconsolidar: se retiene en el andén de revisión documental hasta "
          "regularizar el BL o el manifiesto, aunque las demás reglas lo dejaran pasar."),
    "Y": ("Sobrepeso y mercancía peligrosa juntos multiplican el riesgo (falla "
          "estructural + posible derrame). La combinación activa el protocolo de "
          "emergencia y el acceso queda bloqueado hasta el permiso especial."),
}

DECISIONES = {
    "ingreso_libre": {"semaforo": "verde", "texto": "Ingreso libre a la terminal"},
    "inspeccion": {"semaforo": "amarillo", "texto": "Canal de inspección física"},
    "retencion_documental": {"semaforo": "amarillo", "texto": "Retenido en revisión documental"},
    "emergencia": {"semaforo": "rojo", "texto": "Protocolo de emergencia activado"},
    "denegado": {"semaforo": "rojo", "texto": "Ingreso denegado"},
}


def _v(b: bool) -> str:
    return "V" if b else "F"


def evaluar_camion(P: bool, Q: bool, R: bool, S: bool, D: bool = True) -> dict:
    for nombre, valor in (("P", P), ("Q", Q), ("R", R), ("S", S), ("D", D)):
        if not isinstance(valor, bool):
            raise TypeError(f"La premisa {nombre} debe ser bool, se recibió {type(valor).__name__}")

    A = P and S and (not Q)
    E = P and (R or Q)
    Z = P and (not D)
    Y = P and Q and R

    if not P:
        decision = "denegado"
    elif Y:
        decision = "emergencia"
    elif Z:
        decision = "retencion_documental"
    elif E:
        decision = "inspeccion"
    elif A:
        decision = "ingreso_libre"
    else:
        decision = "denegado"

    explicacion = [
        f"P={_v(P)} ({PREMISAS['P']})",
        f"Q={_v(Q)} ({PREMISAS['Q']})",
        f"R={_v(R)} ({PREMISAS['R']})",
        f"S={_v(S)} ({PREMISAS['S']})",
        f"D={_v(D)} ({PREMISAS['D']})",
        f"A = P∧S∧¬Q = {_v(P)}∧{_v(S)}∧{_v(not Q)} = {_v(A)}",
        f"E = P∧(R∨Q) = {_v(P)}∧({_v(R)}∨{_v(Q)}) = {_v(E)}",
        f"Z = P∧¬D = {_v(P)}∧{_v(not D)} = {_v(Z)}",
        f"Y = P∧Q∧R = {_v(P)}∧{_v(Q)}∧{_v(R)} = {_v(Y)}",
    ]
    if not P:
        explicacion.append("¬P: sin autorización no existe vía de ingreso -> DENEGADO")
    elif Y:
        explicacion.append("Y tiene la máxima prioridad: sobrepeso + mercancía "
                           "peligrosa -> PROTOCOLO DE EMERGENCIA")
    elif Z:
        explicacion.append("Z se cumple: autorizado pero sin documentación completa "
                           "-> RETENCIÓN DOCUMENTAL (regularizar papeles)")
    elif E:
        explicacion.append(f"E se cumple -> CANAL DE INSPECCIÓN"
                           + (" (A también valía; la inspección domina)" if A else ""))
    elif A:
        explicacion.append("A se cumple -> INGRESO LIBRE")
    else:
        explicacion.append("Ninguna regla de ingreso se cumplió (P sin S ni causal "
                           "de inspección) -> DENEGADO")

    return {"premisas": {"P": P, "Q": Q, "R": R, "S": S, "D": D},
            "A": A, "E": E, "Z": Z, "Y": Y,
            "decision": decision, "semaforo": DECISIONES[decision]["semaforo"],
            "texto_decision": DECISIONES[decision]["texto"],
            "explicacion": explicacion}


def tabla_verdad(variables=("P", "Q", "R", "S")) -> list:
    filas = []
    fijas = {v: (v == "D") for v in PREMISAS if v not in variables}
    for valores in itertools.product([True, False], repeat=len(variables)):
        prem = {**fijas, **dict(zip(variables, valores))}
        res = evaluar_camion(**prem)
        filas.append({**{v: prem[v] for v in variables},
                      "A": res["A"], "E": res["E"], "Z": res["Z"], "Y": res["Y"],
                      "decision": res["decision"]})
    return filas


def tablas_para_ui() -> dict:
    return {"original": tabla_verdad(("P", "Q", "R", "S")),
            "Z": tabla_verdad(("P", "D")),
            "Y": tabla_verdad(("P", "Q", "R")),
            "premisas": PREMISAS, "reglas": REGLAS,
            "justificaciones": JUSTIFICACIONES}


def analisis_reglas() -> dict:
    salidas = {"A": [], "E": [], "Z": [], "Y": []}
    conflictos = {"Z_y_E": 0, "Z_y_A": 0, "Y_y_E": 0, "Z_y_Y": 0}
    por_decision = {}
    for valores in itertools.product([True, False], repeat=5):
        prem = dict(zip(("P", "Q", "R", "S", "D"), valores))
        res = evaluar_camion(**prem)
        for r in salidas:
            salidas[r].append(res[r])
        conflictos["Z_y_E"] += res["Z"] and res["E"]
        conflictos["Z_y_A"] += res["Z"] and res["A"]
        conflictos["Y_y_E"] += res["Y"] and res["E"]
        conflictos["Z_y_Y"] += res["Z"] and res["Y"]
        por_decision[res["decision"]] = por_decision.get(res["decision"], 0) + 1

    redundantes = []
    nombres = list(salidas)
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            if salidas[nombres[i]] == salidas[nombres[j]]:
                redundantes.append((nombres[i], nombres[j]))

    return {
        "total_combinaciones": 32,
        "por_decision": por_decision,
        "redundantes": [{"reglas": list(p), "nota": "salida idéntica en las 32 combinaciones"}
                        for p in redundantes],
        "conflictos": [
            {"reglas": ["Z", "E"], "casos": conflictos["Z_y_E"],
             "resolucion": "Z domina: sin documentación no hay inspección, va a revisión documental"},
            {"reglas": ["Z", "A"], "casos": conflictos["Z_y_A"],
             "resolucion": "Z domina: el ingreso libre queda bloqueado por falta de papeles"},
            {"reglas": ["Y", "E"], "casos": conflictos["Y_y_E"],
             "resolucion": "Y tiene precedencia: la emergencia absorbe la inspección"},
            {"reglas": ["Z", "Y"], "casos": conflictos["Z_y_Y"],
             "resolucion": "Y tiene precedencia máxima aunque también falten papeles"},
        ],
        "hay_contradiccion_logica": False,
        "nota": ("No hay contradicciones irresolubles: todo solapamiento se resuelve "
                 "por el orden de precedencia Y > Z > E > A."),
    }
