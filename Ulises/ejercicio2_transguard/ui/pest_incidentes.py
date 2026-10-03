import tkinter as tk
from tkinter import messagebox, ttk

import config
from nucleo import clasificador, get_store, modelo_actual
from nucleo.db import ahora_iso
from .widgets import arbol, fmt_fecha, llenar, mk, modal, run_bg

CATEGORIAS = list(clasificador.PRIORIDAD_BASE)
PRIORIDADES = clasificador.ORDEN_PRIORIDAD
ESTADOS = ["nuevo", "en_atencion", "cerrado"]


class PestIncidentes(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.incidentes = []
        self.inc_actual = None
        self._build()
        self.refrescar()

    def _build(self):
        izq = ttk.Frame(self, width=430)
        izq.pack(side="left", fill="y", padx=(0, 10))
        izq.pack_propagate(False)

        form = ttk.Labelframe(izq, text=" Clasificar un correo ", padding=8)
        form.pack(fill="x")
        self.e_rem = self._fila(form, "Remitente", "vigilante@muelle.local")
        self.e_asu = self._fila(form, "Asunto", "")
        mk(ttk.Label, form, text="Cuerpo", font=("Segoe UI", 8)).pack(anchor="w")
        self.txt_cuerpo = tk.Text(form, height=6, wrap="word", font=("Segoe UI", 9))
        self.txt_cuerpo.pack(fill="x", pady=2)
        fila = ttk.Frame(form)
        fila.pack(fill="x", pady=4)
        mk(ttk.Label, fila, text="Modo:", font=("Segoe UI", 8)).pack(side="left")
        self.cmb_modo = ttk.Combobox(fila, values=["hibrido", "reglas", "llm"],
                                     width=9, state="readonly")
        self.cmb_modo.set("hibrido")
        self.cmb_modo.pack(side="left", padx=4)
        self.v_guardar = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila, text="Guardar", variable=self.v_guardar).pack(side="left")
        self.btn_cls = mk(ttk.Button, fila, text="Clasificar", bootstyle="primary",
                          command=self._clasificar)
        self.btn_cls.pack(side="right")

        res = ttk.Labelframe(izq, text=" Resultado ", padding=8)
        res.pack(fill="x", pady=8)
        self.lbl_fuente = ttk.Label(res, text="—", font=("Segoe UI", 8))
        self.lbl_fuente.pack(anchor="w")
        fila2 = ttk.Frame(res)
        fila2.pack(fill="x", pady=4)
        mk(ttk.Label, fila2, text="Categoría:", font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
        self.cmb_cat = ttk.Combobox(fila2, values=CATEGORIAS, width=24, state="readonly")
        self.cmb_cat.grid(row=0, column=1, padx=4)
        mk(ttk.Label, fila2, text="Prioridad:", font=("Segoe UI", 8)).grid(row=1, column=0, sticky="w")
        self.cmb_pri = ttk.Combobox(fila2, values=PRIORIDADES, width=12, state="readonly")
        self.cmb_pri.grid(row=1, column=1, sticky="w", padx=4)
        self.lbl_revision = mk(ttk.Label, res, text="", bootstyle="warning",
                               font=("Segoe UI", 8, "bold"))
        self.lbl_revision.pack(anchor="w")
        self.txt_res = tk.Text(res, height=5, wrap="word", font=("Consolas", 8),
                               relief="flat", state="disabled")
        self.txt_res.pack(fill="x", pady=4)
        self.btn_corregir = mk(ttk.Button, res, text="Guardar corrección",
                               bootstyle="success", command=self._corregir)
        self.btn_corregir.pack(anchor="e")
        self.btn_corregir.configure(state="disabled")

        der = ttk.Frame(self)
        der.pack(side="left", fill="both", expand=True)
        barra = ttk.Frame(der)
        barra.pack(fill="x", pady=(0, 4))
        mk(ttk.Label, barra, text="Bandeja de incidentes",
           font=("Segoe UI", 11, "bold")).pack(side="left")
        mk(ttk.Button, barra, text="↺", width=3, bootstyle="secondary",
           command=self.refrescar).pack(side="right")
        self.v_revision = tk.BooleanVar()
        ttk.Checkbutton(barra, text="Solo revisión humana", variable=self.v_revision,
                        command=self.refrescar).pack(side="right", padx=6)
        self.cmb_festado = ttk.Combobox(barra, values=[""] + ESTADOS, width=12,
                                      state="readonly")
        self.cmb_festado.pack(side="right")
        self.cmb_festado.bind("<<ComboboxSelected>>", lambda e: self.refrescar())

        tv = arbol(der, ("Fecha", "Asunto", "Categoría", "Prioridad", "Estado"),
                   (130, 220, 150, 80, 100), alto=12)
        tv.pack(fill="both", expand=True)
        self.tv = tv.tree
        self.tv.bind("<Double-1>", self._detalle)

        acc = ttk.Frame(der)
        acc.pack(fill="x", pady=6)
        mk(ttk.Button, acc, text="Ver detalle", bootstyle="info",
           command=self._detalle).pack(side="left")
        self.cmb_estado = ttk.Combobox(acc, values=ESTADOS, width=12, state="readonly")
        self.cmb_estado.set("en_atencion")
        self.cmb_estado.pack(side="left", padx=6)
        mk(ttk.Button, acc, text="Cambiar estado", bootstyle="warning",
           command=self._cambiar_estado).pack(side="left")
        mk(ttk.Button, acc, text="Eliminar", bootstyle="danger",
           command=self._eliminar).pack(side="right")

    def _fila(self, parent, etiqueta, valor):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=1)
        mk(ttk.Label, f, text=etiqueta, width=10, font=("Segoe UI", 8)).pack(side="left")
        e = ttk.Entry(f)
        e.pack(side="left", fill="x", expand=True)
        if valor:
            e.insert(0, valor)
        return e

    def _clasificar(self):
        cuerpo = self.txt_cuerpo.get("1.0", "end").strip()
        if len(cuerpo) < 3:
            messagebox.showwarning("Correo", "Escribe el cuerpo del correo.")
            return
        self.btn_cls.configure(state="disabled", text="clasificando…")
        self.lbl_fuente.configure(text="Consultando al clasificador (el LLM puede tardar)…")
        modo = self.cmb_modo.get()

        def trabajo():
            return clasificador.clasificar(self.e_asu.get(), cuerpo, modo=modo,
                                           modelo=modelo_actual(),
                                           max_intentos=config.LLM_MAX_INTENTOS)

        def ok(res):
            self.btn_cls.configure(state="normal", text="Clasificar")
            self._mostrar_resultado(res)
            if self.v_guardar.get():
                doc = {"remitente": self.e_rem.get(), "asunto": self.e_asu.get(),
                       "cuerpo": cuerpo,
                       "clasificacion": {k: res.get(k) for k in
                                         ("categoria", "prioridad", "resumen", "fuente",
                                          "palabras_clave", "detalle", "error_llm")
                                         if res.get(k) is not None},
                       "datos_extraidos": res.get("entidades", {}),
                       "estado": "nuevo",
                       "requiere_revision_humana": res.get("requiere_revision_humana", False),
                       "timestamp": ahora_iso(),
                       "historial": [{"ts": ahora_iso(),
                                      "evento": f"clasificado por {res.get('fuente')}"}]}
                doc["_id"] = get_store().col("incidentes").insertar(doc)
                self.inc_actual = doc
                self.btn_corregir.configure(state="normal")
                self.refrescar()

        def err(exc):
            self.btn_cls.configure(state="normal", text="Clasificar")
            self.lbl_fuente.configure(text=f"Error: {exc}")

        run_bg(self, trabajo, ok, err)

    def _mostrar_resultado(self, res):
        self.cmb_cat.set(res.get("categoria", "otro"))
        self.cmb_pri.set(res.get("prioridad", "baja"))
        det = res.get("detalle") or {}
        extra = ""
        if det.get("reglas") and det.get("llm"):
            l = det["llm"]
            extra = (f" | reglas: {det['reglas']['categoria']}/{det['reglas']['prioridad']}"
                     f" · llm: {l.get('categoria','—')}/{l.get('prioridad','—')}")
        self.lbl_fuente.configure(
            text=f"fuente: {res.get('fuente')} · {res.get('latencia_ms')} ms{extra}")
        self.lbl_revision.configure(
            text="REQUIERE REVISIÓN HUMANA" if res.get("requiere_revision_humana") else "")
        self.txt_res.configure(state="normal")
        self.txt_res.delete("1.0", "end")
        lineas = []
        if res.get("resumen"):
            lineas.append("resumen: " + res["resumen"])
        lineas.append("entidades: " + str(res.get("entidades")))
        if res.get("palabras_clave"):
            lineas.append("palabras clave: " + ", ".join(res["palabras_clave"]))
        if res.get("error_llm"):
            lineas.append("llm: " + str(res["error_llm"]))
        self.txt_res.insert("end", "\n".join(lineas))
        self.txt_res.configure(state="disabled")

    def _corregir(self):
        if not self.inc_actual:
            return
        col = get_store().col("incidentes")
        doc = self.inc_actual
        clasif = dict(doc.get("clasificacion", {}))
        if self.cmb_cat.get() != clasif.get("categoria"):
            clasif["categoria"] = self.cmb_cat.get()
        if self.cmb_pri.get() != clasif.get("prioridad"):
            clasif["prioridad"] = self.cmb_pri.get()
        col.actualizar(doc["_id"], {"clasificacion": clasif})
        col.agregar_a_lista(doc["_id"], "historial",
                            {"ts": ahora_iso(),
                             "evento": f"corrección manual -> {clasif['categoria']}/{clasif['prioridad']}"})
        self.refrescar()

    def _sel(self):
        sel = self.tv.selection()
        return self.incidentes[int(sel[0])] if sel else None

    def _detalle(self, _e=None):
        d = self._sel()
        if not d:
            return
        top = modal(self, "Detalle del incidente", 620, 480)
        txt = tk.Text(top, wrap="word", font=("Consolas", 9), padx=10, pady=10)
        txt.pack(fill="both", expand=True)
        c = d.get("clasificacion", {})
        cuerpo = (f"De: {d.get('remitente')}   Fecha: {fmt_fecha(d.get('timestamp'))}\n"
                  f"Asunto: {d.get('asunto')}\n\n{d.get('cuerpo')}\n\n"
                  f"Clasificación: {c.get('categoria')} / {c.get('prioridad')} "
                  f"({c.get('fuente','?')})\nEntidades: {d.get('datos_extraidos')}\n\n"
                  f"Historial:\n" +
                  "\n".join(f"  {fmt_fecha(h.get('ts'))} — {h.get('evento')}"
                            for h in d.get("historial", [])))
        txt.insert("end", cuerpo)
        txt.configure(state="disabled")

    def _cambiar_estado(self):
        d = self._sel()
        if not d:
            return
        col = get_store().col("incidentes")
        nuevo = self.cmb_estado.get()
        col.actualizar(d["_id"], {"estado": nuevo})
        col.agregar_a_lista(d["_id"], "historial",
                            {"ts": ahora_iso(), "evento": f"estado -> {nuevo}"})
        self.refrescar()

    def _eliminar(self):
        d = self._sel()
        if d and messagebox.askyesno("Eliminar", "¿Eliminar este incidente?"):
            get_store().col("incidentes").eliminar(d["_id"])
            self.refrescar()

    def refrescar(self):
        filtro = {}
        if self.cmb_festado.get():
            filtro["estado"] = self.cmb_festado.get()
        if self.v_revision.get():
            filtro["requiere_revision_humana"] = True
        self.incidentes = get_store().col("incidentes").buscar(
            filtro, orden=[("timestamp", -1)], limite=100)
        llenar(self.tv, [
            (fmt_fecha(d.get("timestamp")),
             ("⚠ " if d.get("requiere_revision_humana") else "") + (d.get("asunto") or "(sin asunto)")[:34],
             d.get("clasificacion", {}).get("categoria", "—"),
             d.get("clasificacion", {}).get("prioridad", "—"),
             d.get("estado", "—"))
            for d in self.incidentes])
