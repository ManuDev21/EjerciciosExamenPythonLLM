import tkinter as tk
from tkinter import messagebox, ttk

from nucleo import get_store
from nucleo.db import ahora_iso
from nucleo.reglas import PREMISAS, evaluar_camion
from .widgets import Semaforo, arbol, fmt_fecha, llenar, mk, modal

PREMISAS_ORDEN = ["P", "Q", "R", "S", "D"]


class PestAcceso(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.vars = {v: tk.BooleanVar(value=False) for v in PREMISAS_ORDEN}
        self.vars["D"].set(True)
        self.camion = None
        self._build()
        self.refrescar()

    def _build(self):
        izq = ttk.Frame(self, width=400)
        izq.pack(side="left", fill="y", padx=(0, 10))
        izq.pack_propagate(False)

        busq = ttk.Labelframe(izq, text=" 1. Localizar unidad ", padding=8)
        busq.pack(fill="x", pady=(0, 8))
        fila = ttk.Frame(busq)
        fila.pack(fill="x")
        self.e_buscar = ttk.Entry(fila, width=22)
        self.e_buscar.pack(side="left", fill="x", expand=True)
        self.e_buscar.insert(0, "TRK-201")
        mk(ttk.Button, fila, text="Buscar", width=7, bootstyle="info",
           command=self._buscar).pack(side="left", padx=4)
        self.lbl_camion = ttk.Label(busq, text="Escribe placa (ABC-123-D) o unidad (TRK-###)",
                                    wraplength=360, font=("Segoe UI", 8))
        self.lbl_camion.pack(anchor="w", pady=(6, 0))

        prem = ttk.Labelframe(izq, text=" 2. Premisas de la unidad ", padding=8)
        prem.pack(fill="x")
        for v in PREMISAS_ORDEN:
            ttk.Checkbutton(prem, text=f"{v} — {PREMISAS[v]}",
                            variable=self.vars[v]).pack(anchor="w", pady=2)

        datos = ttk.Frame(izq)
        datos.pack(fill="x", pady=8)
        self.e_camion = self._campo(datos, "Unidad", 0)
        self.e_placa = self._campo(datos, "Placa", 1)
        self.e_operador = self._campo(datos, "Vigilante", 2)
        self.e_operador.insert(0, "vigilante")
        self.v_guardar = tk.BooleanVar(value=True)
        ttk.Checkbutton(izq, text="Registrar decisión en la bitácora",
                        variable=self.v_guardar).pack(anchor="w")
        mk(ttk.Button, izq, text="EVALUAR INGRESO", bootstyle="success",
           command=self._evaluar).pack(fill="x", pady=8)

        der = ttk.Frame(self)
        der.pack(side="left", fill="both", expand=True)
        res = ttk.Labelframe(der, text=" Resultado ", padding=8)
        res.pack(fill="x")
        fila_r = ttk.Frame(res)
        fila_r.pack(fill="x")
        self.sem = Semaforo(fila_r, r=22, bg="#1c2733")
        self.sem.pack(side="left", padx=10)
        col = ttk.Frame(fila_r)
        col.pack(side="left", fill="x", expand=True)
        self.lbl_decision = mk(ttk.Label, col, text="Evalúa una unidad…",
                               font=("Segoe UI", 13, "bold"))
        self.lbl_decision.pack(anchor="w", pady=(8, 2))
        self.lbl_reglas = ttk.Label(col, text="", font=("Consolas", 9))
        self.lbl_reglas.pack(anchor="w")
        self.txt_exp = tk.Text(res, height=7, wrap="word", font=("Consolas", 8),
                               relief="flat", state="disabled")
        self.txt_exp.pack(fill="x", pady=(8, 0))

        marco = ttk.Labelframe(der, text=" Bitácora de movimientos ", padding=6)
        marco.pack(fill="both", expand=True, pady=(8, 0))
        barra = ttk.Frame(marco)
        barra.pack(fill="x")
        self.e_filtro = ttk.Entry(barra, width=14)
        self.e_filtro.pack(side="right", padx=2)
        mk(ttk.Button, barra, text="Filtrar placa", bootstyle="secondary",
           command=self._cargar_bitacora).pack(side="right")
        mk(ttk.Button, barra, text="↺", width=3, bootstyle="secondary",
           command=self._cargar_bitacora).pack(side="right", padx=2)
        tv = arbol(marco, ("Fecha", "Unidad", "Decisión", "Semáforo", "Vigilante"),
                   (140, 90, 160, 80, 90), alto=8)
        tv.pack(fill="both", expand=True)
        self.tv = tv.tree
        self.tv.bind("<Double-1>", self._ver_explicacion)
        self._accesos = []

    def _campo(self, parent, etiqueta, fila):
        mk(ttk.Label, parent, text=etiqueta, font=("Segoe UI", 8)).grid(
            row=fila, column=0, sticky="w")
        e = ttk.Entry(parent, width=16)
        e.grid(row=fila, column=1, sticky="w", padx=4, pady=1)
        return e

    def _buscar(self):
        q = self.e_buscar.get().strip().upper()
        if not q:
            return
        store = get_store()
        docs = store.col("camiones").buscar({"camion_id": q})
        if not docs:
            docs = store.col("camiones").buscar({"placa": {"$regex": q}})
        if not docs:
            self.camion = None
            self.lbl_camion.configure(text="No se encontró esa unidad en el padrón.")
            return
        c = docs[0]
        self.camion = c
        self.vars["P"].set(bool(c.get("autorizacion")))
        self.vars["S"].set(bool(c.get("certificacion_vigente")))
        self.e_camion.delete(0, "end")
        self.e_camion.insert(0, c.get("camion_id", ""))
        self.e_placa.delete(0, "end")
        self.e_placa.insert(0, c.get("placa", ""))
        self.lbl_camion.configure(
            text=f"{c.get('camion_id')} · {c.get('placa')} · {c.get('empresa')} · "
                 f"autorización: {'sí' if c.get('autorizacion') else 'NO'} · "
                 f"licencia: {'vigente' if c.get('certificacion_vigente') else 'VENCIDA'}")

    def _evaluar(self):
        try:
            res = evaluar_camion(*[self.vars[v].get() for v in PREMISAS_ORDEN])
        except TypeError as exc:
            messagebox.showerror("Premisas", str(exc))
            return
        self.sem.fijar(res["semaforo"])
        self.lbl_decision.configure(text=res["texto_decision"])
        self.lbl_reglas.configure(
            text="   ".join(f"{r}={'V' if res[r] else 'F'}" for r in "AEZY"))
        self.txt_exp.configure(state="normal")
        self.txt_exp.delete("1.0", "end")
        self.txt_exp.insert("end", "\n".join("• " + p for p in res["explicacion"]))
        self.txt_exp.configure(state="disabled")

        if self.v_guardar.get():
            get_store().col("accesos").insertar(
                {"camion_id": self.e_camion.get() or None,
                 "placa": self.e_placa.get() or None,
                 **{v: self.vars[v].get() for v in PREMISAS_ORDEN},
                 "A": res["A"], "E": res["E"], "Z": res["Z"], "Y": res["Y"],
                 "decision": res["decision"], "semaforo": res["semaforo"],
                 "explicacion": res["explicacion"],
                 "operador": self.e_operador.get() or "vigilante",
                 "timestamp": ahora_iso()})
            self._cargar_bitacora()

    def _cargar_bitacora(self):
        filtro = {}
        if self.e_filtro.get().strip():
            filtro["placa"] = {"$regex": self.e_filtro.get().strip().upper()}
        self._accesos = get_store().col("accesos").buscar(
            filtro, orden=[("timestamp", -1)], limite=50)
        llenar(self.tv, [
            (fmt_fecha(a.get("timestamp")), a.get("camion_id") or a.get("placa") or "—",
             a.get("decision", "—"), a.get("semaforo", "—"), a.get("operador") or "—")
            for a in self._accesos])

    def _ver_explicacion(self, _e):
        sel = self.tv.selection()
        if not sel:
            return
        a = self._accesos[int(sel[0])]
        top = modal(self, f"Trazabilidad — {a.get('camion_id') or a.get('placa')}", 560)
        txt = tk.Text(top, wrap="word", font=("Consolas", 9), padx=10, pady=10)
        txt.pack(fill="both", expand=True)
        txt.insert("end", "\n".join(f"{i+1}. {p}" for i, p in
                                   enumerate(a.get("explicacion", []))))
        txt.configure(state="disabled")

    def refrescar(self):
        self._cargar_bitacora()
