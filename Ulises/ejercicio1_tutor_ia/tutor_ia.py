import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import ollama

try:
    import ttkbootstrap as ttkb
    TTKB = True
except ImportError:
    TTKB = False

MENSAJE_SISTEMA = """
Actúa como docente universitario experto en Inteligencia Artificial.

Tu trabajo es apoyar a alumnos de licenciatura en sus dudas.

Indicaciones:

1. Responde en español y de forma clara.
2. Apóyate en ejemplos cotidianos.
3. Detalla los procedimientos uno por uno.
4. Baja el nivel técnico si el alumno va empezando.
5. Incluye fragmentos en Python cuando ayuden a entender.
6. Si el alumno se equivoca, muéstrale el error y cómo corregirlo.
7. No entregues solo la solución: expón también el porqué.
8. Termina las explicaciones largas con una idea resumen.
"""

MODELO_DEFAULT = "llama3"


def _modelo_inicial():
    try:
        modelos = ollama.list().get("models", [])
        if modelos:
            return modelos[0].get("model", MODELO_DEFAULT)
    except Exception:
        pass
    return MODELO_DEFAULT


class TutorIA(ttkb.Window if TTKB else tk.Tk):
    def __init__(self):
        if TTKB:
            super().__init__(themename="cyborg")
        else:
            super().__init__()
        self.title("Tutor de Inteligencia Artificial - escritorio")
        self.geometry("860x620")
        self.minsize(680, 480)

        self.modelo = tk.StringVar(value=_modelo_inicial())
        self.mensajes = [{"role": "system", "content": MENSAJE_SISTEMA}]
        self.cola = queue.Queue()
        self.ocupado = False

        self._construir()
        self._imprimir("sys", "TUTOR DE INTELIGENCIA ARTIFICIAL",
                       "Pregunta sobre agentes, búsqueda, lógica, redes neuronales, "
                       "aprendizaje…\nModelo: " + self.modelo.get())
        self.after(150, self._revisar_cola)
        self.after(0, self._verificar_ollama)

    def _mk(self, cls, parent, **kw):
        if TTKB:
            cls = getattr(ttkb, cls.__name__, cls)
        else:
            kw.pop("bootstyle", None)
        return cls(parent, **kw)

    def _modelos(self):
        try:
            return [m.get("model") for m in ollama.list().get("models", [])] or [MODELO_DEFAULT]
        except Exception:
            return [MODELO_DEFAULT]

    def _construir(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        self._mk(ttk.Label, top, text="🎓  Tutor de IA",
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        self.lbl_estado = self._mk(ttk.Label, top, text="comprobando Ollama…",
                                   bootstyle="secondary")
        self.lbl_estado.pack(side="right")
        self._mk(ttk.Label, top, text="Modelo:", bootstyle="secondary").pack(side="right", padx=(0, 4))
        self.cmb_modelo = ttk.Combobox(top, textvariable=self.modelo, width=18,
                                       state="readonly", values=self._modelos())
        self.cmb_modelo.pack(side="right")

        marco = ttk.Frame(self, padding=(10, 0, 10, 0))
        marco.pack(fill="both", expand=True)
        self.chat = scrolledtext.ScrolledText(
            marco, wrap="word", state="disabled", font=("Consolas", 10),
            bg="#141b26" if TTKB else "#ffffff",
            fg="#e8edf4" if TTKB else "#1a1a1a",
            insertbackground="#e8edf4", relief="flat", padx=10, pady=10)
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("user", foreground="#6fb3ff" if TTKB else "#0b5394",
                             justify="right", spacing1=8)
        self.chat.tag_config("bot", justify="left", spacing1=8)
        self.chat.tag_config("sys", foreground="#8b98ab", justify="center",
                             font=("Segoe UI", 9, "italic"), spacing1=10)
        self.chat.tag_config("nombre", font=("Segoe UI", 9, "bold"))

        abajo = ttk.Frame(self, padding=10)
        abajo.pack(fill="x")
        self.entrada = ttk.Entry(abajo, font=("Segoe UI", 10))
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entrada.bind("<Return>", lambda e: self.enviar())
        self.btn_enviar = self._mk(ttk.Button, abajo, text="Enviar  ➤",
                                   bootstyle="primary", command=self.enviar)
        self.btn_enviar.pack(side="left")

        acciones = ttk.Frame(self, padding=(10, 0, 10, 10))
        acciones.pack(fill="x")
        self.btn_resumen = self._mk(ttk.Button, acciones, text="📋 Resumen del historial",
                                    bootstyle="info-outline", command=self.resumir)
        self.btn_resumen.pack(side="left")
        self._mk(ttk.Button, acciones, text="↺ Reiniciar",
                 bootstyle="danger-outline", command=self.reiniciar).pack(side="left", padx=8)
        self._mk(ttk.Label, acciones,
                 text="El resumen lo genera el LLM con base en esta sesión",
                 bootstyle="secondary", font=("Segoe UI", 8)).pack(side="right")
        self.entrada.focus_set()

    def _imprimir(self, tag, encabezado, cuerpo=""):
        self.chat.configure(state="normal")
        if encabezado:
            self.chat.insert("end", encabezado + "\n", "nombre" if tag != "sys" else "sys")
        if cuerpo:
            self.chat.insert("end", cuerpo + "\n", tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _verificar_ollama(self):
        try:
            modelos = self._modelos()
            self.cmb_modelo.configure(values=modelos)
            if self.modelo.get() not in modelos:
                self.modelo.set(modelos[0])
            self.lbl_estado.configure(text="● Ollama activo")
        except Exception:
            self.lbl_estado.configure(text="● Ollama no responde (inicia 'ollama serve')")

    def enviar(self):
        texto = self.entrada.get().strip()
        if not texto or self.ocupado:
            return
        self.entrada.delete(0, "end")
        self._imprimir("user", "TÚ", texto)
        self.mensajes.append({"role": "user", "content": texto})
        self._lanzar_llm(list(self.mensajes), "respuesta")

    def resumir(self):
        if self.ocupado:
            return
        turnos = [m for m in self.mensajes if m["role"] in ("user", "assistant")]
        if not turnos:
            self._imprimir("sys", "", "Todavía no hay conversación que resumir.")
            return
        peticion = ("Resume en un máximo de 5 viñetas los temas que preguntó el "
                    "estudiante y las ideas principales explicadas. Usa segunda "
                    "persona ('preguntaste…', 'te mostré…').")
        self._lanzar_llm(self.mensajes + [{"role": "user", "content": peticion}],
                         "resumen")

    def reiniciar(self):
        self.mensajes = [{"role": "system", "content": MENSAJE_SISTEMA}]
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._imprimir("sys", "", "Conversación reiniciada.")

    def _lanzar_llm(self, mensajes, tipo):
        self.ocupado = True
        self.btn_enviar.configure(state="disabled")
        self.btn_resumen.configure(state="disabled")
        self._puntos = 0
        self._animar()
        threading.Thread(target=self._trabajo_llm,
                         args=(mensajes, tipo), daemon=True).start()

    def _trabajo_llm(self, mensajes, tipo):
        try:
            r = ollama.chat(model=self.modelo.get(), messages=mensajes)
            self.cola.put((tipo, r["message"]["content"], None))
        except Exception as exc:
            self.cola.put((tipo, None, exc))

    def _animar(self):
        if self.ocupado:
            self._puntos = (self._puntos + 1) % 4
            self.lbl_estado.configure(text="⏳ El tutor escribe" + "." * self._puntos)
            self.after(400, self._animar)

    def _revisar_cola(self):
        try:
            while True:
                tipo, contenido, error = self.cola.get_nowait()
                self.ocupado = False
                self.btn_enviar.configure(state="normal")
                self.btn_resumen.configure(state="normal")
                self._verificar_ollama()
                if error is not None:
                    if self.mensajes and self.mensajes[-1]["role"] == "user":
                        self.mensajes.pop()
                    self._imprimir("sys", "", "Error al contactar Ollama: " + str(error))
                    messagebox.showwarning("Ollama", "Sin respuesta del modelo.\n"
                                                   "Verifica que 'ollama serve' esté activo.")
                elif tipo == "resumen":
                    self._imprimir("bot", "📋 RESUMEN DE TU HISTORIAL", contenido)
                else:
                    self.mensajes.append({"role": "assistant", "content": contenido})
                    self._imprimir("bot", "TUTOR", contenido)
        except queue.Empty:
            pass
        self.after(150, self._revisar_cola)


if __name__ == "__main__":
    TutorIA().mainloop()
