import queue
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

try:
    import ttkbootstrap as ttkb
    TEMA = "superhero"
    TTKB = True
except ImportError:
    ttkb = None
    TTKB = False

VentanaBase = ttkb.Window if TTKB else tk.Tk


def mk(cls, parent, **kw):
    if TTKB:
        cls = getattr(ttkb, cls.__name__, cls)
    else:
        kw.pop("bootstyle", None)
    return cls(parent, **kw)


def run_bg(raiz, fn, on_ok=None, on_err=None):
    cola = queue.Queue()

    def trabajo():
        try:
            cola.put((True, fn()))
        except Exception as exc:
            cola.put((False, exc))

    def revisar():
        try:
            ok, valor = cola.get_nowait()
        except queue.Empty:
            raiz.after(120, revisar)
            return
        if ok and on_ok:
            on_ok(valor)
        elif not ok:
            if on_err:
                on_err(valor)
            else:
                from tkinter import messagebox
                messagebox.showerror("Error", str(valor))

    threading.Thread(target=trabajo, daemon=True).start()
    raiz.after(120, revisar)


def arbol(parent, columnas, anchos=None, alto=10):
    marco = ttk.Frame(parent)
    tree = ttk.Treeview(marco, columns=columnas, show="headings", height=alto)
    for i, col in enumerate(columnas):
        tree.heading(col, text=col)
        tree.column(col, width=(anchos[i] if anchos else 110),
                    anchor="w", stretch=True)
    vs = ttk.Scrollbar(marco, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    marco.tree = tree
    return marco


def llenar(tree, filas):
    tree.delete(*tree.get_children())
    for i, fila in enumerate(filas):
        tree.insert("", "end", iid=str(i), values=fila)


def modal(raiz, titulo, ancho=460, alto=None):
    top = tk.Toplevel(raiz)
    top.title(titulo)
    top.transient(raiz)
    top.grab_set()
    top.resizable(False, alto is not None)
    if alto:
        top.geometry(f"{ancho}x{alto}")
    else:
        top.minsize(ancho, 10)
    return top


class Semaforo(tk.Canvas):
    COLORES = {"rojo": ("#ff5252", "#5a1f1f"),
               "amarillo": ("#ffc107", "#5a4700"),
               "verde": ("#28d17c", "#14532d")}

    def __init__(self, parent, r=26, **kw):
        super().__init__(parent, width=r * 2 + 10, height=r * 6 + 30,
                         highlightthickness=0, **kw)
        self.r = r
        self.luces = {}
        for i, nombre in enumerate(("rojo", "amarillo", "verde")):
            y = 15 + r + i * (2 * r + 10)
            self.luces[nombre] = self.create_oval(
                5, y - r, 5 + 2 * r, y + r, fill="#333a45", outline="#222")
        self.fijar(None)

    def fijar(self, nivel):
        for nombre, oid in self.luces.items():
            encendido = nombre == nivel
            color = self.COLORES[nombre][0] if encendido else "#333a45"
            self.itemconfigure(oid, fill=color)


class BarrasH(tk.Canvas):
    def __init__(self, parent, alto=170, **kw):
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, height=alto, **kw)
        self.bind("<Configure>", lambda e: self.redibujar())
        self.datos = {}
        self.colores = ["#6fb3ff", "#ffc107", "#ff5252", "#28d17c",
                        "#b18cff", "#20c997", "#fd7e14", "#adb5bd"]

    def fijar(self, datos: dict, colores=None):
        self.datos = dict(datos or {})
        if colores:
            self.colores = colores
        self.redibujar()

    def redibujar(self):
        self.delete("all")
        if not self.datos:
            self.create_text(10, 10, anchor="nw", text="sin datos",
                             fill="#8b98ab", font=("Segoe UI", 9))
            return
        ancho = max(self.winfo_width(), 260)
        alto = max(self.winfo_height(), 60)
        n = len(self.datos)
        margen_txt = 130
        tope = max(self.datos.values()) or 1
        fila_h = max(18, min(30, alto // n))
        for i, (etiq, val) in enumerate(self.datos.items()):
            y0 = 8 + i * fila_h
            largo = (ancho - margen_txt - 46) * (val / tope)
            color = self.colores[i % len(self.colores)]
            self.create_text(margen_txt - 6, y0 + fila_h / 2, anchor="e",
                             text=str(etiq)[:18], fill="#c9d4e6",
                             font=("Segoe UI", 8))
            self.create_rectangle(margen_txt, y0, margen_txt + max(largo, 2),
                                  y0 + fila_h - 6, fill=color, outline="")
            self.create_text(margen_txt + largo + 6, y0 + fila_h / 2, anchor="w",
                             text=str(val), fill="#c9d4e6", font=("Segoe UI", 8, "bold"))


NIVEL_COLOR = {"critico": "#ff8787", "alto": "#ffd8a8",
               "medio": "#fff3bf", "bajo": "#c8f7d4"}
NIVEL_FG = {"critico": "#7a0000", "alto": "#7a3b00",
            "medio": "#6b5200", "bajo": "#14532d"}


def nivel_de(puntaje: int) -> str:
    if puntaje >= 17:
        return "critico"
    if puntaje >= 10:
        return "alto"
    if puntaje >= 5:
        return "medio"
    return "bajo"


class MatrizRiesgo(tk.Canvas):
    def __init__(self, parent, celda=46, on_hover=None, **kw):
        w, h = celda * 6 + 30, celda * 6 + 30
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, width=w, height=h, **kw)
        self.celda = celda
        self.on_hover = on_hover
        self.datos = []

    def fijar(self, riesgos: list):
        self.datos = riesgos
        self.redibujar()

    def redibujar(self):
        self.delete("all")
        c = self.celda
        self.create_text(30 + c * 2.5, 12, text="Probabilidad",
                         fill="#c9d4e6", font=("Segoe UI", 9, "bold"))
        self.create_text(14, 30 + c * 2.5, text="I\nm\np\na\nc\nt\no",
                         fill="#c9d4e6", font=("Segoe UI", 8, "bold"))
        for p in range(1, 6):
            self.create_text(30 + (p - 0.5) * c, 24, text=str(p),
                             fill="#c9d4e6", font=("Segoe UI", 9, "bold"))
        for i in range(1, 6):
            fila = 5 - i
            self.create_text(24, 30 + (fila + 0.5) * c, text=str(i),
                             fill="#c9d4e6", font=("Segoe UI", 9, "bold"))
            for p in range(1, 6):
                puntaje = p * i
                nivel = nivel_de(puntaje)
                celda_riesgos = [r for r in self.datos
                                 if r.get("probabilidad") == p and r.get("impacto") == i]
                x0, y0 = 30 + (p - 1) * c, 30 + fila * c
                self.create_rectangle(x0, y0, x0 + c, y0 + c,
                                      fill=NIVEL_COLOR[nivel], outline="#ffffff", width=2)
                if celda_riesgos:
                    self.create_text(x0 + c / 2, y0 + c / 2,
                                     text=str(len(celda_riesgos)),
                                     fill=NIVEL_FG[nivel],
                                     font=("Segoe UI", 12, "bold"))


class ChatPanel(ttk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.texto = scrolledtext.ScrolledText(
            self, wrap="word", state="disabled", font=("Segoe UI", 10),
            padx=10, pady=10, relief="flat")
        self.texto.pack(fill="both", expand=True)
        self.texto.tag_config("user", foreground="#6fb3ff", justify="right", spacing1=8)
        self.texto.tag_config("bot", justify="left", spacing1=8)
        self.texto.tag_config("nombre", font=("Segoe UI", 8, "bold"))
        self.texto.tag_config("sys", foreground="#8b98ab", justify="center",
                              font=("Segoe UI", 8, "italic"), spacing1=8)
        self.texto.tag_config("fuentes", foreground="#20c997",
                              font=("Segoe UI", 8), spacing3=10)

    def agregar(self, rol, encabezado, cuerpo, fuentes=None):
        self.texto.configure(state="normal")
        self.texto.insert("end", encabezado + "\n", "nombre" if rol != "sys" else "sys")
        if cuerpo:
            self.texto.insert("end", cuerpo + "\n", rol)
        if fuentes:
            chips = "  ".join(f"[{f['coleccion']}#{str(f['id'])[-6:]}]" for f in fuentes)
            self.texto.insert("end", "fuentes: " + chips + "\n", "fuentes")
        self.texto.configure(state="disabled")
        self.texto.see("end")

    def limpiar(self):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.configure(state="disabled")


def fmt_fecha(iso):
    if not iso:
        return "—"
    return str(iso).replace("T", " ")[:16]


PRIORIDAD_COLOR = {"critica": "#ff5252", "alta": "#ffc107",
                   "media": "#6fb3ff", "baja": "#8b98ab"}
