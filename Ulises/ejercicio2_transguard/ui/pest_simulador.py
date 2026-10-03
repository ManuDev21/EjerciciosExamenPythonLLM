import tkinter as tk
from tkinter import ttk

from nucleo.reglas import (JUSTIFICACIONES, PREMISAS, analisis_reglas,
                           evaluar_camion, tablas_para_ui)
from .widgets import Semaforo, arbol, llenar, mk

PREMISAS_ORDEN = ["P", "Q", "R", "S", "D"]


def _vf(b):
    return "V" if b else "F"


class PestSimulador(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.vars = {v: tk.BooleanVar(value=False) for v in PREMISAS_ORDEN}
        self.vars["D"].set(True)
        self._build()
        self._vivo()
        self._cargar_tablas()

    def _build(self):
        izq = ttk.Frame(self, width=380)
        izq.pack(side="left", fill="y", padx=(0, 10))
        izq.pack_propagate(False)

        marco = ttk.Labelframe(izq, text=" Interruptores (premisas) ", padding=8)
        marco.pack(fill="x")
        for v in PREMISAS_ORDEN:
            ttk.Checkbutton(marco, text=f"{v} — {PREMISAS[v]}",
                            variable=self.vars[v],
                            command=self._vivo).pack(anchor="w", pady=2)

        res = ttk.Labelframe(izq, text=" Salida en vivo ", padding=8)
        res.pack(fill="x", pady=8)
        fila = ttk.Frame(res)
        fila.pack()
        self.sem = Semaforo(fila, r=18, bg="#1c2733")
        self.sem.pack(side="left")
        col = ttk.Frame(fila)
        col.pack(side="left", padx=10)
        self.lbl_dec = mk(ttk.Label, col, text="—", font=("Segoe UI", 12, "bold"))
        self.lbl_dec.pack(anchor="w")
        self.lbl_reglas = ttk.Label(col, text="", font=("Consolas", 10))
        self.lbl_reglas.pack(anchor="w")

        self.txt = tk.Text(izq, height=9, wrap="word", font=("Consolas", 8),
                           relief="flat", state="disabled")
        self.txt.pack(fill="x")

        der = ttk.Frame(self)
        der.pack(side="left", fill="both", expand=True)

        marco_t = ttk.Labelframe(der, text=" Tabla base — A=P∧S∧¬Q, E=P∧(R∨Q) ", padding=4)
        marco_t.pack(fill="both", expand=True)
        tv = arbol(marco_t, ("P", "Q", "R", "S", "A", "E", "Decisión"),
                   (40, 40, 40, 40, 40, 40, 160), alto=8)
        tv.pack(fill="both", expand=True)
        self.tv_orig = tv.tree

        fila_n = ttk.Frame(der)
        fila_n.pack(fill="x", pady=6)
        for titulo, cols, attr in (("Nueva Z = P∧¬D", ("P", "D", "Z"), "tv_z"),
                                   ("Nueva Y = P∧Q∧R", ("P", "Q", "R", "Y"), "tv_y")):
            tarj = ttk.Labelframe(fila_n, text=f" {titulo} ", padding=4)
            tarj.pack(side="left", fill="both", expand=True, padx=4)
            t2 = arbol(tarj, cols, (50, 50, 50, 60), alto=4)
            t2.pack(fill="x")
            setattr(self, attr, t2.tree)
            lbl = ttk.Label(tarj, text=JUSTIFICACIONES[cols[-1]], wraplength=300,
                            font=("Segoe UI", 8))
            lbl.pack(anchor="w", pady=4)

        marco_a = ttk.Labelframe(der, text=" Análisis de solapamientos y redundancia ", padding=6)
        marco_a.pack(fill="x")
        self.txt_analisis = tk.Text(marco_a, height=7, wrap="word",
                                    font=("Segoe UI", 9), relief="flat", state="disabled")
        self.txt_analisis.pack(fill="x")

    def _vivo(self):
        res = evaluar_camion(*[self.vars[v].get() for v in PREMISAS_ORDEN])
        self.sem.fijar(res["semaforo"])
        self.lbl_dec.configure(text=res["texto_decision"])
        self.lbl_reglas.configure(
            text="  ".join(f"{r}={'V' if res[r] else 'F'}" for r in "AEZY"))
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("end", "\n".join(res["explicacion"]))
        self.txt.configure(state="disabled")

    def _cargar_tablas(self):
        t = tablas_para_ui()
        llenar(self.tv_orig, [(_vf(f["P"]), _vf(f["Q"]), _vf(f["R"]), _vf(f["S"]),
                               _vf(f["A"]), _vf(f["E"]), f["decision"])
                              for f in t["original"]])
        llenar(self.tv_z, [(_vf(f["P"]), _vf(f["D"]), _vf(f["Z"])) for f in t["Z"]])
        llenar(self.tv_y, [(_vf(f["P"]), _vf(f["Q"]), _vf(f["R"]), _vf(f["Y"]))
                           for f in t["Y"]])

        a = analisis_reglas()
        lineas = [f"{a['total_combinaciones']} combinaciones. Decisiones: " +
                  ", ".join(f"{k}={v}" for k, v in a["por_decision"].items()),
                  "Reglas redundantes: " +
                  (", ".join(" = ".join(r["reglas"]) for r in a["redundantes"])
                   if a["redundantes"] else "ninguna"),
                  "Solapamientos resueltos por precedencia:"]
        lineas += [f"  • {' ∧ '.join(c['reglas'])}: {c['casos']} caso(s) — {c['resolucion']}"
                   for c in a["conflictos"]]
        lineas.append(a["nota"])
        self.txt_analisis.configure(state="normal")
        self.txt_analisis.delete("1.0", "end")
        self.txt_analisis.insert("end", "\n".join(lineas))
        self.txt_analisis.configure(state="disabled")

    def refrescar(self):
        pass
