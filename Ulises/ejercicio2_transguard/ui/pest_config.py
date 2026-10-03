import tkinter as tk
from tkinter import messagebox, ttk

import config
from nucleo import get_store, llm, modelo_actual, sembrar_si_vacio
from .widgets import mk, run_bg


class PestConfig(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self._build()
        self.refrescar()

    def _build(self):
        izq = ttk.Frame(self, width=420)
        izq.pack(side="left", fill="y", padx=(0, 12))
        izq.pack_propagate(False)

        marco = ttk.Labelframe(izq, text=" Modelo LLM (Ollama) ", padding=10)
        marco.pack(fill="x")
        self.v_modelo = tk.StringVar()
        self.cmb_mod = ttk.Combobox(marco, textvariable=self.v_modelo, width=20)
        self.cmb_mod.pack(side="left")
        mk(ttk.Button, marco, text="↺", width=3, bootstyle="secondary",
           command=self._cargar_modelos).pack(side="left", padx=6)
        self.lbl_ollama = ttk.Label(marco, text="", font=("Segoe UI", 8))
        self.lbl_ollama.pack(side="left", padx=8)

        marco2 = ttk.Labelframe(izq, text=" Umbrales y operación ", padding=10)
        marco2.pack(fill="x", pady=8)
        ttk.Label(marco2, text="Umbral de confianza (0-1):",
                  font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=3)
        self.s_umbral = ttk.Spinbox(marco2, from_=0.0, to=1.0, increment=0.05,
                                    width=8, format="%.2f")
        self.s_umbral.grid(row=0, column=1, sticky="w", padx=6)
        self.v_sim = tk.BooleanVar()
        ttk.Checkbutton(marco2, text="Modo simulación de correos entrantes",
                        variable=self.v_sim).grid(row=1, column=0, columnspan=2,
                                                  sticky="w", pady=4)
        ttk.Label(marco2, text="Vigilante de turno:",
                  font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=3)
        self.e_op = ttk.Entry(marco2, width=16)
        self.e_op.grid(row=2, column=1, sticky="w", padx=6)
        mk(ttk.Button, marco2, text="Guardar configuración", bootstyle="success",
           command=self._guardar).grid(row=3, column=0, columnspan=2, pady=10)

        marco3 = ttk.Labelframe(izq, text=" Datos de demostración ", padding=10)
        marco3.pack(fill="x")
        mk(ttk.Button, marco3, text="Resembrar demo (borra y recrea)",
           bootstyle="danger-outline", command=self._resembrar).pack(anchor="w")

        der = ttk.Frame(self)
        der.pack(side="left", fill="both", expand=True)
        marco4 = ttk.Labelframe(der, text=" Estado de las conexiones ", padding=10)
        marco4.pack(fill="x")
        self.lbl_mongo = ttk.Label(marco4, text="", font=("Consolas", 9),
                                   wraplength=520, justify="left")
        self.lbl_mongo.pack(anchor="w")
        mk(ttk.Button, marco4, text="Reintentar conexión a MongoDB",
           bootstyle="info", command=self._reconectar).pack(anchor="w", pady=6)

        marco5 = ttk.Labelframe(der, text=" Acerca de ", padding=10)
        marco5.pack(fill="x", pady=8)
        ttk.Label(marco5, font=("Segoe UI", 9), justify="left", wraplength=520,
                  text=f"{config.APP_NOMBRE} — {config.APP_SUBTITULO}.\n"
                       "Escritorio tkinter: MongoDB (con respaldo local), "
                       "Ollama local, motor de reglas A=P∧S∧¬Q / E=P∧(R∨Q) "
                       "ampliado con Z=P∧¬D e Y=P∧Q∧R.").pack(anchor="w")

    def _cargar_modelos(self):
        modelos = llm.listar_modelos()
        self.cmb_mod.configure(values=modelos or [config.MODELO_DEFAULT])
        if modelos and self.v_modelo.get() not in modelos:
            self.v_modelo.set(modelos[0])

    def _guardar(self):
        try:
            umbral = float(self.s_umbral.get())
        except ValueError:
            umbral = 0.5
        get_store().guardar_config({"modelo": self.v_modelo.get() or None,
                                    "umbral_confianza": umbral,
                                    "simulacion_correo": self.v_sim.get(),
                                    "operador": self.e_op.get().strip() or "vigilante"})
        messagebox.showinfo("Configuración", "Guardada.")

    def _resembrar(self):
        if not messagebox.askyesno("Resembrar",
                                   "Se borran camiones, accesos, incidentes y "
                                   "riesgos y se recrean los datos demo. ¿Seguro?"):
            return
        self.btn_res = None

        def trabajo():
            return sembrar_si_vacio(forzar=True)

        def ok(res):
            messagebox.showinfo("Resembrar", "Datos recreados: " + str(res))
            self.refrescar()

        run_bg(self, trabajo, ok)

    def _reconectar(self):
        store = get_store()
        ok = store.reconectar()
        if ok:
            messagebox.showinfo("MongoDB", "Conexión restablecida.")
        else:
            messagebox.showwarning("MongoDB", "Sigue sin responder.\n" +
                                   str(store.error or ""))
        self.refrescar()

    def refrescar(self):
        store = get_store()
        cfg = store.obtener_config()
        self.v_modelo.set(cfg.get("modelo") or modelo_actual())
        self.s_umbral.set(cfg.get("umbral_confianza", 0.5))
        self.v_sim.set(bool(cfg.get("simulacion_correo", True)))
        self.e_op.delete(0, "end")
        self.e_op.insert(0, cfg.get("operador", "vigilante"))
        self._cargar_modelos()

        st = store.estado()
        if st["conectado"]:
            self.lbl_mongo.configure(text=f"MongoDB CONECTADO\n{st['uri']} / "
                                          f"{config.MONGO_DB}")
        else:
            self.lbl_mongo.configure(
                text=f"MongoDB SIN CONEXIÓN — usando respaldo local\n"
                     f"URI intentada: {config.MONGO_URI}\n"
                     f"error: {st['error'] or 'desconocido'}")
        self.lbl_ollama.configure(
            text="Ollama activo" if llm.disponible() else "Ollama no responde")
