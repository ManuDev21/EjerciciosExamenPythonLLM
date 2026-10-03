import tkinter as tk
from tkinter import ttk

import config
from nucleo import cargar_dataset, get_store, modelo_actual, sembrar_si_vacio
from nucleo import llm

from .widgets import TEMA, TTKB, VentanaBase, mk
from .pest_dashboard import PestDashboard
from .pest_acceso import PestAcceso
from .pest_simulador import PestSimulador
from .pest_incidentes import PestIncidentes
from .pest_evaluacion import PestEvaluacion
from .pest_asistente import PestAsistente
from .pest_riesgos import PestRiesgos
from .pest_camiones import PestCamiones
from .pest_reportes import PestReportes
from .pest_config import PestConfig


class TransGuardApp(VentanaBase):
    def __init__(self):
        if TTKB:
            super().__init__(themename=TEMA)
        else:
            super().__init__()
        self.title(f"{config.APP_NOMBRE} — {config.APP_SUBTITULO}")
        self.geometry("1180x720")
        self.minsize(980, 600)

        try:
            sembrar_si_vacio()
        except Exception:
            pass

        self._cabecera()
        self._pestanas()
        self._estado_bar()
        self.after(500, self._actualizar_estado)

    def _cabecera(self):
        top = ttk.Frame(self, padding=(12, 8))
        top.pack(fill="x")
        mk(ttk.Label, top, text="⚓ " + config.APP_NOMBRE,
           font=("Segoe UI", 17, "bold")).pack(side="left")
        mk(ttk.Label, top, text=config.APP_SUBTITULO,
           bootstyle="secondary").pack(side="left", padx=10, pady=(4, 0))
        self.lbl_llm = mk(ttk.Label, top, text="LLM …", bootstyle="secondary",
                          font=("Segoe UI", 9, "bold"))
        self.lbl_llm.pack(side="right", padx=4)
        self.lbl_db = mk(ttk.Label, top, text="BD …", bootstyle="secondary",
                         font=("Segoe UI", 9, "bold"))
        self.lbl_db.pack(side="right", padx=4)

    def _pestanas(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.tabs = []
        definicion = [
            ("Panel", PestDashboard), ("Acceso", PestAcceso),
            ("Simulador", PestSimulador), ("Incidentes", PestIncidentes),
            ("Evaluación", PestEvaluacion), ("Asistente", PestAsistente),
            ("Riesgos", PestRiesgos), ("Unidades", PestCamiones),
            ("Reportes", PestReportes), ("Configuración", PestConfig),
        ]
        for titulo, cls in definicion:
            pest = cls(self.nb, self)
            self.nb.add(pest, text=" " + titulo + " ")
            self.tabs.append(pest)
        self.nb.bind("<<NotebookTabChanged>>", self._al_cambiar)

    def _al_cambiar(self, _event):
        pest = self.tabs[self.nb.index("current")]
        if hasattr(pest, "refrescar"):
            pest.refrescar()

    def _estado_bar(self):
        self.barra = mk(ttk.Label, self, text="", bootstyle="secondary",
                        anchor="w", padding=(10, 3), font=("Segoe UI", 8))
        self.barra.pack(fill="x", side="bottom")

    def _actualizar_estado(self):
        store = get_store()
        st = store.estado()
        if st["conectado"]:
            self.lbl_db.configure(text=f"● MongoDB ({config.MONGO_DB})")
        else:
            self.lbl_db.configure(text="● Respaldo local (sin MongoDB)")
        if llm.disponible():
            self.lbl_llm.configure(text=f"● LLM: {modelo_actual()}")
        else:
            self.lbl_llm.configure(text="● LLM no disponible")
        self.barra.configure(
            text=f"  {config.APP_NOMBRE} · persistencia: {st['motor']} · "
                 f"dataset: {len(cargar_dataset())} correos etiquetados")
        self.after(10000, self._actualizar_estado)
