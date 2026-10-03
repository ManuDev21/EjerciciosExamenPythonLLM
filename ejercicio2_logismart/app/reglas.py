# -*- coding: utf-8 -*-
"""Motor de reglas de acceso (lógica proposicional) de LogiSmart.

Premisas:
    P: Vehículo con autorización previa
    Q: El peso excede el límite permitido
    R: Carga con materiales peligrosos
    S: Conductor con certificación vigente
    T: Horario restringido vigente para materiales peligrosos   (NUEVA)
    V: Certificación del conductor vence en menos de 30 días    (NUEVA)

Reglas originales (se conservan intactas):
    A (Acceso estándar)      = P ∧ S ∧ ¬Q
    E (Inspección especial)  = P ∧ (R ∨ Q)

Reglas nuevas (justificación en JUSTIFICACIONES):
    H (Retención por horario)         = R ∧ T
    W (Alerta de certif. por vencer)  = S ∧ V

Decisión final (por precedencia):
    ¬P        -> denegado
    H         -> retenido por horario restringido (domina a A y a E)
    E         -> inspección especial (domina a A cuando ambas valen)
    A         -> acceso estándar
    resto     -> denegado
"""
import itertools

PREMISAS = {
    "P": "Vehículo con autorización previa",
    "Q": "El peso excede el límite permitido",
    "R": "Carga con materiales peligrosos",
    "S": "Conductor con certificación vigente",
    "T": "Horario restringido vigente para materiales peligrosos",
    "V": "Certificación del conductor vence en menos de 30 días",
}

REGLAS = {
    "A": "P ∧ S ∧ ¬Q   (acceso estándar)",
    "E": "P ∧ (R ∨ Q)  (inspección especial)",
    "H": "R ∧ T        (retención por horario restringido)",
    "W": "S ∧ V        (alerta de certificación por vencer)",
}

JUSTIFICACIONES = {
    "H": ("Las normas de transporte de materiales peligrosos restringen su "
          "circulación en horario nocturno (p. ej. 22:00-06:00). Si R y T son "
          "verdaderas el camión se retiene y se reprograma, aunque A o E valgan."),
    "W": ("Una certificación a punto de vencer es un riesgo regulatorio: el "
          "acceso se permite pero se genera una alerta para que el operador "
          "exija la renovación antes de la siguiente visita."),
}

DECISIONES = {
    "acceso_estandar": {"semaforo": "verde", "texto": "Acceso estándar autorizado"},
    "inspeccion_especial": {"semaforo": "amarillo", "texto": "Enviado a inspección especial"},
    "retenido_horario": {"semaforo": "rojo", "texto": "Retenido: horario restringido (mat. peligrosos)"},
    "denegado": {"semaforo": "rojo", "texto": "Acceso denegado"},
}


def _v(b: bool) -> str:
    return "V" if b else "F"


def evaluar_camion(P: bool, Q: bool, R: bool, S: bool,
                   T: bool = False, V: bool = False) -> dict:
    """Evalúa las cuatro reglas y deriva la decisión con su explicación."""
    for nombre, valor in (("P", P), ("Q", Q), ("R", R), ("S", S), ("T", T), ("V", V)):
        if not isinstance(valor, bool):
            raise TypeError(f"La premisa {nombre} debe ser bool, se recibió {type(valor).__name__}")

    A = P and S and (not Q)
    E = P and (R or Q)
    H = R and T
    W = S and V

    if not P:
        decision = "denegado"
    elif H:
        decision = "retenido_horario"
    elif E:
        decision = "inspeccion_especial"
    elif A:
        decision = "acceso_estandar"
    else:
        decision = "denegado"

    semaforo = DECISIONES[decision]["semaforo"]
    if decision == "acceso_estandar" and W:
        semaforo = "amarillo"  # entra, pero el operador debe atender la alerta

    explicacion = [
        f"P={_v(P)} ({PREMISAS['P']})",
        f"Q={_v(Q)} ({PREMISAS['Q']})",
        f"R={_v(R)} ({PREMISAS['R']})",
        f"S={_v(S)} ({PREMISAS['S']})",
        f"T={_v(T)} ({PREMISAS['T']})",
        f"V={_v(V)} ({PREMISAS['V']})",
        f"A = P∧S∧¬Q = {_v(P)}∧{_v(S)}∧{_v(not Q)} = {_v(A)}",
        f"E = P∧(R∨Q) = {_v(P)}∧({_v(R)}∨{_v(Q)}) = {_v(E)}",
        f"H = R∧T = {_v(R)}∧{_v(T)} = {_v(H)}",
        f"W = S∧V = {_v(S)}∧{_v(V)} = {_v(W)}",
    ]
    if not P:
        explicacion.append("¬P: sin autorización previa no hay acceso ni inspección -> DENEGADO")
    elif H:
        explicacion.append("H es verdadera y tiene prioridad: material peligroso en "
                           "horario restringido -> RETENIDO (reprogramar ingreso)")
    elif E:
        explicacion.append(f"E es verdadera -> canal de INSPECCIÓN ESPECIAL"
                           + (" (A también valía; la inspección domina)" if A else ""))
    elif A:
        explicacion.append("A es verdadera -> ACCESO ESTÁNDAR"
                           + (" + ALERTA W: certificación por vencer, avisar al operador" if W else ""))
    else:
        explicacion.append("Ninguna regla de acceso se cumplió (P sin S ni causal de "
                           "inspección) -> DENEGADO")

    return {"premisas": {"P": P, "Q": Q, "R": R, "S": S, "T": T, "V": V},
            "A": A, "E": E, "H": H, "W": W,
            "decision": decision, "semaforo": semaforo,
            "texto_decision": DECISIONES[decision]["texto"],
            "explicacion": explicacion}


def tabla_verdad(variables=("P", "Q", "R", "S")) -> list:
    """Tabla de verdad para el subconjunto de variables indicado.

    Las premisas no listadas se fijan en Falso. Con las 4 originales
    produce las 16 filas clásicas.
    """
    filas = []
    fijas = {v: False for v in PREMISAS if v not in variables}
    for valores in itertools.product([True, False], repeat=len(variables)):
        prem = {**fijas, **dict(zip(variables, valores))}
        res = evaluar_camion(**prem)
        filas.append({**{v: prem[v] for v in variables},
                      "A": res["A"], "E": res["E"], "H": res["H"], "W": res["W"],
                      "decision": res["decision"]})
    return filas


def tablas_para_ui() -> dict:
    """Tablas usadas por el simulador: original (16) + una por regla nueva."""
    return {"original": tabla_verdad(("P", "Q", "R", "S")),
            "H": tabla_verdad(("R", "T")),
            "W": tabla_verdad(("S", "V")),
            "premisas": PREMISAS, "reglas": REGLAS,
            "justificaciones": JUSTIFICACIONES}


def analisis_reglas() -> dict:
    """Reto opcional: detecta redundancias y conflictos entre reglas.

    Recorre las 64 combinaciones de (P,Q,R,S,T,V) y compara las salidas.
    - Redundancia: dos reglas con salida idéntica en toda la tabla.
    - Conflicto: combinaciones donde reglas de distinto semáforo valen a
      la vez; el sistema las resuelve por precedencia y aquí se reportan.
    """
    salidas = {"A": [], "E": [], "H": [], "W": []}
    conflictos = {"A_y_H": 0, "E_y_H": 0, "A_y_E": 0}
    por_decision = {}
    for valores in itertools.product([True, False], repeat=6):
        prem = dict(zip(("P", "Q", "R", "S", "T", "V"), valores))
        res = evaluar_camion(**prem)
        for r in salidas:
            salidas[r].append(res[r])
        conflictos["A_y_H"] += res["A"] and res["H"]
        conflictos["E_y_H"] += res["E"] and res["H"]
        conflictos["A_y_E"] += res["A"] and res["E"]
        por_decision[res["decision"]] = por_decision.get(res["decision"], 0) + 1

    redundantes = []
    nombres = list(salidas)
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            if salidas[nombres[i]] == salidas[nombres[j]]:
                redundantes.append((nombres[i], nombres[j]))

    return {
        "total_combinaciones": 64,
        "por_decision": por_decision,
        "redundantes": [{"reglas": list(p), "nota": "producen la misma salida en las 64 combinaciones"}
                        for p in redundantes],
        "conflictos": [
            {"reglas": ["A", "H"], "casos": conflictos["A_y_H"],
             "resolucion": "H tiene precedencia: se retiene aunque el acceso estándar valiera"},
            {"reglas": ["E", "H"], "casos": conflictos["E_y_H"],
             "resolucion": "H tiene precedencia sobre la inspección especial"},
            {"reglas": ["A", "E"], "casos": conflictos["A_y_E"],
             "resolucion": "El camión entra por el carril de inspección (E domina a A)"},
        ],
        "hay_contradiccion_logica": False,
        "nota": ("No existen contradicciones lógicas (ninguna combinación produce "
                 "salidas incompatibles irresolubles); los solapamientos se "
                 "resuelven por orden de precedencia H > E > A."),
    }
