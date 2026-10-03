import tkinter as tk
import uuid
from tkinter import messagebox, ttk

import config
from nucleo import cargar_dataset, clasificador, get_store, modelo_actual
from nucleo.db import ahora_iso
from .widgets import arbol, fmt_fecha, llenar, mk, run_bg

MODOS = ["reglas", "llm", "hibrido"]


class PestEvaluacion(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.resultado = None
        self.job = {"corriendo": False, "progreso": 0, "total": 0}
        self._build()
        self._historico()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        mk(ttk.Label, top, text="Experimento sobre el dataset etiquetado (32 correos)",
           font=("Segoe UI", 11, "bold")).pack(side="left")
        self.vars = {m: tk.BooleanVar(value=(m != "llm")) for m in MODOS}
        for m in MODOS:
            ttk.Checkbutton(top, text=m, variable=self.vars[m]).pack(side="left", padx=6)
        self.btn = mk(ttk.Button, top, text="Ejecutar", bootstyle="primary",
                      command=self._ejecutar)
        self.btn.pack(side="left", padx=8)
        self.prog = ttk.Progressbar(self, mode="determinate")
        self.prog.pack(fill="x", pady=4)
        self.lbl_prog = ttk.Label(self, text="Selecciona modos y ejecuta. "
                                  "(El modo LLM tarda ~90 s por correo en CPU)",
                                  font=("Segoe UI", 8))
        self.lbl_prog.pack(anchor="w")

        self.marco_res = ttk.Frame(self)
        self.marco_res.pack(fill="both", expand=True, pady=6)

        izq = ttk.Frame(self.marco_res)
        izq.pack(side="left", fill="both", expand=True, padx=(0, 8))
        marco_kpi = ttk.Labelframe(izq, text=" Exactitud por modo ", padding=6)
        marco_kpi.pack(fill="x")
        self.txt_kpi = tk.Text(marco_kpi, height=6, font=("Consolas", 9),
                               relief="flat", state="disabled")
        self.txt_kpi.pack(fill="x")
        marco_mat = ttk.Labelframe(izq, text=" Matriz de confusión (esperada -> obtenida) ", padding=6)
        marco_mat.pack(fill="both", expand=True, pady=6)
        fila = ttk.Frame(marco_mat)
        fila.pack(fill="x")
        self.cmb_modo = ttk.Combobox(fila, values=MODOS, state="readonly", width=10)
        self.cmb_modo.pack(anchor="w")
        self.cmb_modo.bind("<<ComboboxSelected>>", lambda e: self._pintar_matriz())
        self.txt_mat = tk.Text(marco_mat, height=10, font=("Consolas", 9),
                               relief="flat", state="disabled")
        self.txt_mat.pack(fill="both", expand=True)

        der = ttk.Frame(self.marco_res)
        der.pack(side="left", fill="both", expand=True)
        marco_det = ttk.Labelframe(der, text=" Detalle por correo ", padding=4)
        marco_det.pack(fill="both", expand=True)
        tv = arbol(marco_det, ("#", "Esperada", "Obtenida", "Pri esp/obt", "OK"),
                   (40, 160, 160, 110, 40), alto=10)
        tv.pack(fill="both", expand=True)
        self.tv_det = tv.tree

        marco_h = ttk.Labelframe(self, text=" Corridas anteriores (evaluaciones_llm) ", padding=4)
        marco_h.pack(fill="x", pady=6)
        tv2 = arbol(marco_h, ("Fecha", "Modo", "Modelo", "Exact. cat", "Exact. pri", "Latencia"),
                    (140, 80, 120, 90, 90, 90), alto=4)
        tv2.pack(fill="x")
        self.tv_hist = tv2.tree

    def _ejecutar(self):
        if self.job["corriendo"]:
            messagebox.showinfo("Evaluación", "Ya hay una evaluación en curso.")
            return
        modos = [m for m in MODOS if self.vars[m].get()]
        if not modos:
            messagebox.showwarning("Modos", "Selecciona al menos un modo.")
            return
        dataset = cargar_dataset()
        self.job = {"corriendo": True, "progreso": 0,
                    "total": len(dataset) * len(modos)}
        self.btn.configure(state="disabled")

        def trabajo():
            def avance(i, _t):
                self.job["progreso"] = i * len(modos)
            res = clasificador.evaluar_dataset(
                dataset, modos, modelo_actual(),
                config.LLM_MAX_INTENTOS, progreso=avance)
            run_id = uuid.uuid4().hex[:12]
            col = get_store().col("evaluaciones_llm")
            for modo, acc in res["resultados"].items():
                col.insertar({"run_id": run_id, "modo": modo,
                              "modelo": modelo_actual(),
                              "prompt": "dataset correos_etiquetados.json",
                              "respuesta": {"exactitud_categoria": acc["exactitud_categoria"],
                                            "exactitud_prioridad": acc["exactitud_prioridad"],
                                            "matriz_confusion": acc["matriz_confusion"]},
                              "latencia": acc["latencia_promedio_ms"],
                              "coincidio_reglas": acc["exactitud_categoria"],
                              "total_correos": res["total_correos"],
                              "timestamp": ahora_iso()})
            return res

        def ok(res):
            self.job["corriendo"] = False
            self.btn.configure(state="normal")
            self.resultado = res
            self._pintar_resultados()
            self._historico()

        def err(exc):
            self.job["corriendo"] = False
            self.btn.configure(state="normal")
            messagebox.showerror("Evaluación", str(exc))

        self.after(300, self._poll)
        run_bg(self, trabajo, ok, err)

    def _poll(self):
        if not self.job["corriendo"]:
            self.prog.configure(value=100)
            return
        pct = 100 * self.job["progreso"] / max(self.job["total"], 1)
        self.prog.configure(value=pct)
        self.lbl_prog.configure(
            text=f"Procesando… {self.job['progreso']}/{self.job['total']} clasificaciones")
        self.after(300, self._poll)

    def _pintar_resultados(self):
        r = self.resultado
        self.txt_kpi.configure(state="normal")
        self.txt_kpi.delete("1.0", "end")
        lineas = [f"correos evaluados: {r['total_correos']}", ""]
        for m in r["modos"]:
            x = r["resultados"][m]
            lineas.append(f"{m:8} cat: {x['exactitud_categoria']*100:5.1f}%   "
                          f"pri: {x['exactitud_prioridad']*100:5.1f}%   "
                          f"lat: {x['latencia_promedio_ms']} ms")
        self.txt_kpi.insert("end", "\n".join(lineas))
        self.txt_kpi.configure(state="disabled")
        self.cmb_modo.configure(values=r["modos"])
        self.cmb_modo.set(r["modos"][0])
        self._pintar_matriz()
        self.lbl_prog.configure(text="Evaluación terminada")

    def _pintar_matriz(self):
        if not self.resultado:
            return
        modo = self.cmb_modo.get() or self.resultado["modos"][0]
        r = self.resultado["resultados"][modo]
        self.txt_mat.configure(state="normal")
        self.txt_mat.delete("1.0", "end")
        for clave, n in sorted(r["matriz_confusion"].items(), key=lambda x: -x[1]):
            marca = "  " if clave.split(" -> ")[0] == clave.split(" -> ")[1] else "x"
            self.txt_mat.insert("end", f"{marca} {clave:<58} {n}\n")
        self.txt_mat.configure(state="disabled")
        llenar(self.tv_det, [
            (d["id"], d["esperada"], d["obtenida"],
             f"{d['prioridad_esperada']} / {d['prioridad_obtenida']}",
             "ok" if d["correcto"] else "x")
            for d in r["detalle"]])

    def _historico(self):
        docs = get_store().col("evaluaciones_llm").buscar(orden=[("timestamp", -1)], limite=20)
        llenar(self.tv_hist, [
            (fmt_fecha(d.get("timestamp")), d.get("modo"), d.get("modelo"),
             f"{100 * (d.get('respuesta', {}).get('exactitud_categoria', d.get('coincidio_reglas', 0))):.1f}%",
             f"{100 * d.get('respuesta', {}).get('exactitud_prioridad', 0):.1f}%",
             f"{d.get('latencia')} ms") for d in docs])

    def refrescar(self):
        self._historico()
