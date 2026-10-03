import tkinter as tk
import uuid
from tkinter import ttk

from nucleo import asistente, get_store, modelo_actual
from .widgets import ChatPanel, arbol, fmt_fecha, llenar, mk, run_bg

SUGERENCIAS = [
    "¿Por qué TRK-201 fue enviado a inspección?",
    "¿Qué incidentes siguen abiertos?",
    "¿Qué riesgos éticos tiene la terminal?",
    "¿Qué unidades están en el padrón?",
]


class PestAsistente(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.sid = uuid.uuid4().hex[:8]
        self._build()
        self.chat.agregar("sys", "ASISTENTE DE LA TERMINAL",
                          "Pregunta sobre unidades, movimientos, incidentes o riesgos. "
                          "Solo respondo con datos reales de la base y cito el registro.")

    def _build(self):
        der = ttk.Frame(self)
        der.pack(side="right", fill="y", padx=(10, 0))
        marco_h = ttk.Labelframe(der, text=" Últimas consultas ", padding=6)
        marco_h.pack(fill="both", expand=True)
        tv = arbol(marco_h, ("Hora", "Pregunta"), (60, 190), alto=12)
        tv.pack(fill="both", expand=True)
        self.tv_hist = tv.tree

        izq = ttk.Frame(self)
        izq.pack(side="left", fill="both", expand=True)
        self.chat = ChatPanel(izq)
        self.chat.pack(fill="both", expand=True)

        fila_s = ttk.Frame(izq)
        fila_s.pack(fill="x", pady=(6, 2))
        for sug in SUGERENCIAS:
            b = mk(ttk.Button, fila_s, text=sug, bootstyle="secondary-outline",
                   command=lambda s=sug: self._usar_sugerencia(s))
            b.pack(side="left", padx=2)

        fila = ttk.Frame(izq)
        fila.pack(fill="x", pady=4)
        self.e_pregunta = ttk.Entry(fila, font=("Segoe UI", 10))
        self.e_pregunta.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.e_pregunta.bind("<Return>", lambda e: self._preguntar())
        self.btn = mk(ttk.Button, fila, text="Preguntar", bootstyle="primary",
                      command=self._preguntar)
        self.btn.pack(side="left")

    def _usar_sugerencia(self, texto):
        self.e_pregunta.delete(0, "end")
        self.e_pregunta.insert(0, texto)
        self._preguntar()

    def _preguntar(self):
        pregunta = self.e_pregunta.get().strip()
        if not pregunta:
            return
        self.e_pregunta.delete(0, "end")
        self.chat.agregar("user", "TÚ", pregunta)
        self.btn.configure(state="disabled", text="consultando…")

        def trabajo():
            return asistente.responder(pregunta, get_store(), modelo_actual(), self.sid)

        def ok(res):
            self.btn.configure(state="normal", text="Preguntar")
            marca = "" if res["modo"] == "llm" else "  (modo: " + res["modo"] + ")"
            self.chat.agregar("bot", "ASISTENTE" + marca, res["respuesta"],
                              fuentes=res.get("fuentes"))
            self._cargar_historico()

        def err(exc):
            self.btn.configure(state="normal", text="Preguntar")
            self.chat.agregar("sys", "", "Error: " + str(exc))

        run_bg(self, trabajo, ok, err)

    def _cargar_historico(self):
        docs = get_store().col("conversaciones").buscar(
            {"sid": self.sid}, orden=[("timestamp", -1)], limite=20)
        llenar(self.tv_hist, [(fmt_fecha(d.get("timestamp"))[11:],
                               d.get("pregunta", "")[:26]) for d in docs])

    def refrescar(self):
        self._cargar_historico()
