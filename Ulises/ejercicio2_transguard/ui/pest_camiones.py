import tkinter as tk
from tkinter import messagebox, ttk

from nucleo import get_store
from nucleo.db import ahora_iso
from nucleo.esquemas import CamionIn
from pydantic import ValidationError
from .widgets import arbol, llenar, mk, modal


class PestCamiones(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.camiones = []
        self._build()
        self.refrescar()

    def _build(self):
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 6))
        mk(ttk.Label, barra, text="Padrón de unidades de la terminal",
           font=("Segoe UI", 12, "bold")).pack(side="left")
        mk(ttk.Button, barra, text="+ Alta de unidad", bootstyle="success",
           command=lambda: self._editor()).pack(side="right")

        tv = arbol(self, ("Unidad", "Placa", "Naviera", "Autorización", "Licencia", "Días restantes"),
                   (90, 110, 220, 100, 100, 100), alto=18)
        tv.pack(fill="both", expand=True)
        self.tv = tv.tree
        self.tv.bind("<Double-1>", lambda e: self._editor())

        acc = ttk.Frame(self)
        acc.pack(fill="x", pady=8)
        mk(ttk.Button, acc, text="Editar selección", bootstyle="info",
           command=self._editor).pack(side="left")
        mk(ttk.Button, acc, text="Dar de baja", bootstyle="danger",
           command=self._eliminar).pack(side="left", padx=8)
        mk(ttk.Button, acc, text="↺ Actualizar", bootstyle="secondary",
           command=self.refrescar).pack(side="right")

    def _sel(self):
        sel = self.tv.selection()
        return self.camiones[int(sel[0])] if sel else None

    def _editor(self, _e=None):
        d = self._sel() or {}
        top = modal(self, "Unidad" + (" — edición" if d else " — alta"), 420)
        e_id = self._fila(top, "Id unidad (TRK-###)", 0, d.get("camion_id", ""))
        e_pl = self._fila(top, "Placa (ABC-123-D)", 1, d.get("placa", ""))
        e_em = self._fila(top, "Naviera / empresa", 2, d.get("empresa", ""))
        v_aut = tk.BooleanVar(value=bool(d.get("autorizacion", True)))
        v_cer = tk.BooleanVar(value=bool(d.get("certificacion_vigente", True)))
        s_dias = ttk.Spinbox(top, from_=0, to=3650, width=8)
        s_dias.set(d.get("certificacion_dias_restantes", 180))
        ttk.Checkbutton(top, text="Autorización de ingreso vigente",
                        variable=v_aut).grid(row=3, column=1, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(top, text="Licencia del operador vigente",
                        variable=v_cer).grid(row=4, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(top, text="Días restantes de licencia", width=20,
                  font=("Segoe UI", 9)).grid(row=5, column=0, sticky="w", padx=10, pady=4)
        s_dias.grid(row=5, column=1, sticky="w", padx=6, pady=4)

        def guardar():
            try:
                datos = CamionIn(
                    camion_id=e_id.get().strip().upper(),
                    placa=e_pl.get().strip().upper(),
                    empresa=e_em.get().strip(),
                    autorizacion=v_aut.get(),
                    certificacion_vigente=v_cer.get(),
                    certificacion_dias_restantes=int(s_dias.get()),
                ).model_dump()
            except (ValidationError, ValueError) as exc:
                messagebox.showerror("Unidad", f"Datos inválidos:\n{exc}", parent=top)
                return
            col = get_store().col("camiones")
            if d:
                col.actualizar(d["_id"], datos)
            else:
                if col.buscar_uno({"camion_id": datos["camion_id"]}):
                    messagebox.showerror("Unidad", "Ese id ya existe en el padrón.",
                                         parent=top)
                    return
                datos["alta_en"] = ahora_iso()
                col.insertar(datos)
            top.destroy()
            self.refrescar()

        mk(ttk.Button, top, text="Guardar", bootstyle="success",
           command=guardar).grid(row=6, column=1, sticky="e", padx=6, pady=10)

    def _fila(self, parent, etq, fila, valor):
        ttk.Label(parent, text=etq, width=20, font=("Segoe UI", 9)).grid(
            row=fila, column=0, sticky="w", padx=10, pady=4)
        e = ttk.Entry(parent, width=26)
        e.grid(row=fila, column=1, sticky="w", padx=6, pady=4)
        e.insert(0, valor)
        return e

    def _eliminar(self):
        d = self._sel()
        if d and messagebox.askyesno("Baja", f"¿Dar de baja {d.get('camion_id')}?"):
            get_store().col("camiones").eliminar(d["_id"])
            self.refrescar()

    def refrescar(self):
        self.camiones = get_store().col("camiones").buscar(orden=[("camion_id", 1)])
        llenar(self.tv, [
            (c.get("camion_id"), c.get("placa"), c.get("empresa"),
             "sí" if c.get("autorizacion") else "NO",
             "vigente" if c.get("certificacion_vigente") else "VENCIDA",
             c.get("certificacion_dias_restantes", "—"))
            for c in self.camiones])
