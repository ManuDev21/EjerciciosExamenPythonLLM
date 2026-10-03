import tkinter as tk
from tkinter import messagebox, ttk

from nucleo import get_store
from nucleo.db import ahora_iso
from nucleo.esquemas import CATEGORIAS_RIESGO, RiesgoIn, enriquecer_riesgo
from pydantic import ValidationError
from .widgets import MatrizRiesgo, arbol, llenar, mk, modal, nivel_de


class PestRiesgos(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.riesgos = []
        self._build()
        self.refrescar()

    def _build(self):
        izq = ttk.Frame(self)
        izq.pack(side="left", fill="both", expand=True)
        marco = ttk.Labelframe(izq, text=" Matriz inherente (probabilidad x impacto) ",
                               padding=8)
        marco.pack(fill="both", expand=True)
        self.matriz = MatrizRiesgo(marco, celda=52, bg="#1c2733")
        self.matriz.pack(pady=6)
        self.matriz_res = MatrizRiesgo(marco, celda=52, bg="#1c2733")
        ttk.Label(marco, text="Matriz residual (tras mitigación)",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 0))
        self.matriz_res.pack(pady=6)

        der = ttk.Frame(self)
        der.pack(side="left", fill="both", expand=True, padx=(12, 0))
        barra = ttk.Frame(der)
        barra.pack(fill="x", pady=(0, 4))
        mk(ttk.Label, barra, text="Registro de riesgos éticos",
           font=("Segoe UI", 11, "bold")).pack(side="left")
        mk(ttk.Button, barra, text="+ Nuevo", bootstyle="success",
           command=lambda: self._editor()).pack(side="right")

        tv = arbol(der, ("Módulo", "Categoría", "Inherente", "Residual", "Descripción"),
                   (110, 90, 80, 80, 260), alto=13)
        tv.pack(fill="both", expand=True)
        self.tv = tv.tree
        self.tv.bind("<Double-1>", lambda e: self._editor())

        acc = ttk.Frame(der)
        acc.pack(fill="x", pady=6)
        mk(ttk.Button, acc, text="Editar", bootstyle="info",
           command=self._editor).pack(side="left")
        mk(ttk.Button, acc, text="Eliminar", bootstyle="danger",
           command=self._eliminar).pack(side="left", padx=8)

    def _sel(self):
        sel = self.tv.selection()
        return self.riesgos[int(sel[0])] if sel else None

    def _editor(self, _e=None):
        d = self._sel() or {}
        top = modal(self, "Riesgo ético" + (" — edición" if d else ""), 480)
        campos = {}

        def fila(etq, fila_i, widget):
            ttk.Label(top, text=etq, width=16, font=("Segoe UI", 9)).grid(
                row=fila_i, column=0, sticky="w", padx=10, pady=3)
            widget.grid(row=fila_i, column=1, sticky="we", padx=6, pady=3)
            return widget

        e_mod = fila("Módulo", 0, ttk.Entry(top, width=30))
        e_mod.insert(0, d.get("modulo", ""))
        e_desc = tk.Text(top, width=34, height=3, font=("Segoe UI", 9))
        fila("Descripción", 1, e_desc)
        e_desc.insert("1.0", d.get("descripcion", ""))
        c_cat = fila("Categoría", 2, ttk.Combobox(top, values=CATEGORIAS_RIESGO,
                                                state="readonly", width=20))
        c_cat.set(d.get("categoria", CATEGORIAS_RIESGO[0]))
        s_prob = fila("Probabilidad (1-5)", 3, ttk.Spinbox(top, from_=1, to=5, width=6))
        s_prob.set(d.get("probabilidad", 3))
        s_imp = fila("Impacto (1-5)", 4, ttk.Spinbox(top, from_=1, to=5, width=6))
        s_imp.set(d.get("impacto", 3))
        e_mit = tk.Text(top, width=34, height=3, font=("Segoe UI", 9))
        fila("Mitigación", 5, e_mit)
        e_mit.insert("1.0", d.get("mitigacion", ""))
        s_pr = fila("Prob. residual", 6, ttk.Spinbox(top, from_=0, to=5, width=6))
        s_pr.set(d.get("probabilidad_residual") or 0)
        s_ir = fila("Imp. residual", 7, ttk.Spinbox(top, from_=0, to=5, width=6))
        s_ir.set(d.get("impacto_residual") or 0)
        ttk.Label(top, text="(0 = aún sin evaluar)", font=("Segoe UI", 8)).grid(
            row=8, column=1, sticky="w", padx=6)

        def guardar():
            pr, ir = int(s_pr.get()), int(s_ir.get())
            try:
                datos = RiesgoIn(
                    modulo=e_mod.get().strip(),
                    descripcion=e_desc.get("1.0", "end").strip(),
                    categoria=c_cat.get(),
                    probabilidad=int(s_prob.get()),
                    impacto=int(s_imp.get()),
                    mitigacion=e_mit.get("1.0", "end").strip(),
                    probabilidad_residual=pr if pr > 0 else None,
                    impacto_residual=ir if ir > 0 else None,
                ).model_dump()
            except (ValidationError, ValueError) as exc:
                messagebox.showerror("Riesgo", f"Datos inválidos:\n{exc}", parent=top)
                return
            col = get_store().col("riesgos_eticos")
            if d:
                col.actualizar(d["_id"], datos)
                col.agregar_a_lista(d["_id"], "historico",
                                    {"ts": ahora_iso(), "evento": "edición"})
            else:
                datos["historico"] = [{"ts": ahora_iso(), "evento": "alta"}]
                col.insertar(datos)
            top.destroy()
            self.refrescar()

        mk(ttk.Button, top, text="Guardar", bootstyle="success",
           command=guardar).grid(row=9, column=1, sticky="e", padx=6, pady=8)

    def _eliminar(self):
        d = self._sel()
        if d and messagebox.askyesno("Eliminar", "¿Eliminar este riesgo?"):
            get_store().col("riesgos_eticos").eliminar(d["_id"])
            self.refrescar()

    def refrescar(self):
        col = get_store().col("riesgos_eticos")
        docs = col.buscar()
        for d in docs:
            pr, ir = d.get("probabilidad_residual"), d.get("impacto_residual")
            if pr and ir and "puntaje_residual" not in d:
                col.actualizar(d["_id"], {"puntaje_residual": pr * ir,
                                          "nivel_residual": nivel_de(pr * ir)})
        self.riesgos = [enriquecer_riesgo(dict(d)) for d in docs]
        self.riesgos.sort(key=lambda r: r["puntaje"], reverse=True)
        llenar(self.tv, [
            (r.get("modulo"), r.get("categoria"),
             f"{r['puntaje']} ({r['nivel']})",
             (f"{r['puntaje_residual']} ({r['nivel_residual']})"
              if r.get("puntaje_residual") else "—"),
             r.get("descripcion", "")[:60])
            for r in self.riesgos])
        self.matriz.fijar(self.riesgos)
        residuales = [r for r in self.riesgos
                      if r.get("probabilidad_residual") and r.get("impacto_residual")]
        self.matriz_res.fijar([{"probabilidad": r["probabilidad_residual"],
                                "impacto": r["impacto_residual"]}
                               for r in residuales])
