import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from nucleo import get_store, reportes
from .widgets import mk

COLECCIONES = ["accesos", "incidentes", "camiones", "riesgos_eticos",
               "evaluaciones_llm", "conversaciones"]
EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "datos", "exportes")


class PestReportes(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self._build()

    def _build(self):
        mk(ttk.Label, self, text="Exportar colecciones de la terminal",
           font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

        marco = ttk.Labelframe(self, text=" Colección ", padding=10)
        marco.pack(fill="x")
        self.cmb = ttk.Combobox(marco, values=COLECCIONES, state="readonly", width=24)
        self.cmb.set("incidentes")
        self.cmb.pack(side="left")
        self.lbl_n = ttk.Label(marco, text="", font=("Segoe UI", 9))
        self.lbl_n.pack(side="left", padx=10)
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._contar())
        self._contar()

        fila = ttk.Frame(self)
        fila.pack(fill="x", pady=10)
        for texto, ext, estilo in (("Exportar CSV", "csv", "primary"),
                                   ("Exportar JSON", "json", "info"),
                                   ("Exportar PDF", "pdf", "warning")):
            mk(ttk.Button, fila, text=texto, bootstyle=estilo, width=18,
               command=lambda x=ext: self._exportar(x)).pack(side="left", padx=6)

        marco_v = ttk.Labelframe(self, text=" Vista previa ", padding=8)
        marco_v.pack(fill="both", expand=True)
        self.txt = tk.Text(marco_v, wrap="none", font=("Consolas", 9),
                           relief="flat", state="disabled")
        self.txt.pack(fill="both", expand=True)
        self.cmb.bind("<<ComboboxSelected>>", lambda e: (self._contar(), self._vista()))
        self._vista()

    def _contar(self):
        n = get_store().col(self.cmb.get()).contar()
        self.lbl_n.configure(text=f"{n} registros")

    def _docs(self):
        return get_store().col(self.cmb.get()).buscar(
            orden=[("timestamp", -1)], limite=500)

    def _vista(self):
        docs = self._docs()[:12]
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        import json
        self.txt.insert("end", json.dumps(docs, ensure_ascii=False, indent=1, default=str))
        self.txt.configure(state="disabled")

    def _exportar(self, ext):
        docs = self._docs()
        if not docs:
            messagebox.showinfo("Exportar", "No hay registros en esa colección.")
            return
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        sugerido = os.path.join(EXPORTS_DIR, reportes.nombre_archivo(self.cmb.get(), ext))
        ruta = filedialog.asksaveasfilename(initialfile=os.path.basename(sugerido),
                                            initialdir=EXPORTS_DIR,
                                            defaultextension="." + ext)
        if not ruta:
            return
        try:
            if ext == "csv":
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    f.write(reportes.a_csv(docs))
            elif ext == "json":
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(reportes.a_json(docs))
            else:
                if not reportes.a_pdf(docs, f"TransGuard — {self.cmb.get()}", ruta):
                    messagebox.showerror("PDF", "Falta el paquete 'fpdf2' "
                                              "(pip install fpdf2).")
                    return
            messagebox.showinfo("Exportar", f"Guardado en:\n{ruta}")
        except OSError as exc:
            messagebox.showerror("Exportar", str(exc))

    def refrescar(self):
        self._contar()
        self._vista()
