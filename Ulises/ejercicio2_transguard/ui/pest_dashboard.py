import tkinter as tk
from collections import Counter
from tkinter import ttk

from nucleo import get_store
from .widgets import BarrasH, arbol, fmt_fecha, llenar, mk


class PestDashboard(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self._build()
        self.refrescar()

    def _build(self):
        filtros = ttk.Frame(self)
        filtros.pack(fill="x", pady=(0, 8))
        mk(ttk.Label, filtros, text="Desde (AAAA-MM-DD):").pack(side="left")
        self.e_desde = ttk.Entry(filtros, width=12)
        self.e_desde.pack(side="left", padx=4)
        mk(ttk.Label, filtros, text="Hasta:").pack(side="left")
        self.e_hasta = ttk.Entry(filtros, width=12)
        self.e_hasta.pack(side="left", padx=4)
        mk(ttk.Button, filtros, text="Filtrar", bootstyle="primary",
           command=self.refrescar).pack(side="left", padx=4)
        mk(ttk.Button, filtros, text="Limpiar", bootstyle="secondary",
           command=self._limpiar).pack(side="left")

        fila_kpi = ttk.Frame(self)
        fila_kpi.pack(fill="x", pady=4)
        self.kpis = {}
        for clave, texto in (("unidades_atendidas", "Unidades atendidas"),
                             ("incidentes_abiertos", "Incidentes abiertos"),
                             ("riesgos_criticos", "Riesgos críticos"),
                             ("unidades_padron", "Unidades en padrón")):
            tarjeta = ttk.Labelframe(fila_kpi, text=" " + texto + " ", padding=8)
            tarjeta.pack(side="left", fill="x", expand=True, padx=4)
            lbl = mk(ttk.Label, tarjeta, text="–", font=("Segoe UI", 20, "bold"),
                     bootstyle="info")
            lbl.pack()
            self.kpis[clave] = lbl

        fila_g = ttk.Frame(self)
        fila_g.pack(fill="both", expand=True, pady=6)
        self.g_acc = self._grafica(fila_g, "Movimientos por decisión")
        self.g_cat = self._grafica(fila_g, "Incidentes por categoría")
        self.g_sem = self._grafica(fila_g, "Incidentes por semana")

        marco = ttk.Labelframe(self, text=" Últimos movimientos ", padding=6)
        marco.pack(fill="both", expand=True)
        tv = arbol(marco, ("Fecha", "Unidad", "Placa", "P Q R S D", "Decisión", "Vigilante"),
                   (130, 90, 90, 110, 150, 90), alto=6)
        tv.pack(fill="both", expand=True)
        self.tv = tv.tree

    def _grafica(self, parent, titulo):
        tarj = ttk.Labelframe(parent, text=" " + titulo + " ", padding=6)
        tarj.pack(side="left", fill="both", expand=True, padx=4)
        g = BarrasH(tarj, alto=150, bg="#1c2733")
        g.pack(fill="both", expand=True)
        return g

    def _limpiar(self):
        self.e_desde.delete(0, "end")
        self.e_hasta.delete(0, "end")
        self.refrescar()

    def refrescar(self):
        store = get_store()
        filtro = {}
        if self.e_desde.get().strip():
            filtro["timestamp"] = {"$gte": self.e_desde.get().strip()}
        if self.e_hasta.get().strip():
            filtro.setdefault("timestamp", {})["$lte"] = self.e_hasta.get().strip() + "T23:59:59"

        accesos = store.col("accesos").buscar(filtro, orden=[("timestamp", -1)])
        incidentes = store.col("incidentes").buscar(filtro, orden=[("timestamp", -1)])
        riesgos = store.col("riesgos_eticos").buscar()

        self.kpis["unidades_atendidas"].configure(text=str(len(accesos)))
        self.kpis["incidentes_abiertos"].configure(
            text=str(sum(1 for i in incidentes if i.get("estado") in ("nuevo", "en_atencion"))))
        self.kpis["riesgos_criticos"].configure(
            text=str(sum(1 for r in riesgos
                         if r.get("probabilidad", 1) * r.get("impacto", 1) >= 17)))
        self.kpis["unidades_padron"].configure(text=str(store.col("camiones").contar()))

        self.g_acc.fijar(Counter(a.get("decision", "?") for a in accesos))
        self.g_cat.fijar(Counter(i.get("clasificacion", {}).get("categoria", "otro")
                                for i in incidentes))
        por_semana = Counter()
        for reg in store.incidentes_por_categoria_semana():
            por_semana[f"S{reg['semana']:02d}"] += reg["total"]
        self.g_sem.fijar(dict(sorted(por_semana.items())))

        llenar(self.tv, [
            (fmt_fecha(a.get("timestamp")), a.get("camion_id") or "—",
             a.get("placa") or "—",
             " ".join(k if a.get(k) else "·" for k in "PQRSD"),
             a.get("decision", "—"), a.get("operador") or "—")
            for a in accesos[:10]])
