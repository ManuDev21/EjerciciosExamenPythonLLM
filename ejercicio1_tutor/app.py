import json
import os
import threading
import uuid

import ollama
from flask import Flask, Response, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "nutrichef-dev-secret")

MODELO_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

OPCIONES_LLM = {
    "num_ctx": 4096,
    "num_predict": 800,
    "temperature": 0.7,
}
KEEP_ALIVE = "30m"  

_MODELO_CACHE = None


def modelo_disponible() -> str:
    global _MODELO_CACHE
    if _MODELO_CACHE:
        return _MODELO_CACHE
    try:
        nombres = [m.get("model") for m in ollama.list().get("models", [])]
        if MODELO_DEFAULT in nombres:
            _MODELO_CACHE = MODELO_DEFAULT
        elif ":" not in MODELO_DEFAULT:
            _MODELO_CACHE = next(
                (n for n in nombres if n.split(":")[0] == MODELO_DEFAULT),
                nombres[0] if nombres else MODELO_DEFAULT,
            )
        else:
            _MODELO_CACHE = nombres[0] if nombres else MODELO_DEFAULT
    except Exception:
        _MODELO_CACHE = MODELO_DEFAULT
    return _MODELO_CACHE

MENSAJE_SISTEMA = """
Eres "NutriChef", un asistente experto en cocina saludable y
nutrición básica para personas sin experiencia culinaria.

Tu función es ayudar al usuario a cocinar mejor y comer más sano.

Debes:

1. Responder siempre en español, con tono amable y motivador.
2. Dar recetas con pasos numerados, tiempos y porciones.
3. Sugerir sustitutos económicos cuando un ingrediente sea
   difícil de conseguir.
4. Explicar brevemente el aporte nutricional de los platos
   (proteínas, fibra, vitaminas) sin usar jerga técnica.
5. Advertir sobre alergias comunes (nueces, gluten, mariscos,
   lácteos) cuando la receta los incluya.
6. Adaptar las propuestas si el usuario indica restricciones
   (vegetariano, diabético, sin horno, poco tiempo, etc.).
7. No inventar datos médicos; si la pregunta es clínica,
   recomendar consultar a un profesional de la salud.
8. Mantener respuestas concisas: máximo 3 secciones cortas.
"""

HISTORIALES = {}
LIMITE_TURNOS = 40 


def historial_de(sid: str) -> list:
    """Obtiene (o crea) el historial de una sesión."""
    if sid not in HISTORIALES:
        HISTORIALES[sid] = [{"role": "system", "content": MENSAJE_SISTEMA}]
    return HISTORIALES[sid]

@app.get("/")
def index():
    session.setdefault("sid", uuid.uuid4().hex)
    return render_template("index.html", modelo=modelo_disponible())


@app.get("/api/estado")
def estado():
    """Permite a la interfaz saber si Ollama responde."""
    try:
        modelos = [m.get("model") for m in ollama.list().get("models", [])]
        return jsonify({"ollama": True, "modelos": modelos,
                        "modelo": modelo_disponible()})
    except Exception as exc:
        return jsonify({"ollama": False, "error": str(exc),
                        "modelo": MODELO_DEFAULT})


@app.post("/api/chat")
def chat():
    """Recibe el mensaje del usuario y devuelve la respuesta del LLM."""
    datos = request.get_json(force=True, silent=True) or {}
    mensaje = (datos.get("mensaje") or "").strip()
    if not mensaje:
        return jsonify({"error": "Escribe un mensaje primero."}), 400
    if len(mensaje) > 4000:
        return jsonify({"error": "El mensaje es demasiado largo (máx. 4000 caracteres)."}), 400

    mensajes = historial_de(session.get("sid", "anon"))
    mensajes.append({"role": "user", "content": mensaje})

    def generar():
        """Transmite la respuesta token a token (NDJSON: {"chunk": ...})."""
        contenido = ""
        try:
            flujo = ollama.chat(model=modelo_disponible(),
                                messages=list(mensajes),
                                stream=True,
                                keep_alive=KEEP_ALIVE,
                                options=OPCIONES_LLM)
            for parte in flujo:
                trozo = parte["message"]["content"]
                if trozo:
                    contenido += trozo
                    yield json.dumps({"chunk": trozo}) + "\n"
        except Exception as exc:
            if not contenido:
                mensajes.pop()  
            yield json.dumps({
                "error": "No fue posible conectar con Ollama. "
                         "Verifica que esté instalado y en ejecución (ollama serve).",
                "detalle": str(exc),
            }) + "\n"
            return

        mensajes.append({"role": "assistant", "content": contenido})

        if len(mensajes) > LIMITE_TURNOS * 2 + 1:
            del mensajes[1:3]
        yield json.dumps({"done": True}) + "\n"

    return Response(generar(), mimetype="application/x-ndjson")


@app.post("/api/resumen")
def resumen():
    """
    PUNTO 3 DEL EJERCICIO:
    genera un resumen breve del historial para el usuario.
    """
    mensajes = historial_de(session.get("sid", "anon"))
    turnos = [m for m in mensajes if m["role"] in ("user", "assistant")]

    if not turnos:
        return jsonify({"resumen": "Todavía no hemos conversado. "
                                   "Envía tu primera pregunta y luego podré resumirla."})

    peticion = (
        "Resume en un máximo de 5 viñetas lo que el usuario ha preguntado "
        "y las recomendaciones principales que le diste en esta conversación. "
        "Habla en segunda persona ('preguntaste...', 'te sugerí...'). "
        "Si solo hubo saludos, dilo claramente."
    )
    try:
        respuesta = ollama.chat(model=modelo_disponible(),
                                messages=mensajes + [{"role": "user", "content": peticion}],
                                keep_alive=KEEP_ALIVE,
                                options=OPCIONES_LLM)
        return jsonify({"resumen": respuesta["message"]["content"]})
    except Exception as exc:
        return jsonify({"error": "Ollama no respondió al generar el resumen.",
                        "detalle": str(exc)}), 502


@app.post("/api/reiniciar")
def reiniciar():
    """Borra el historial de la sesión actual."""
    sid = session.get("sid")
    if sid in HISTORIALES:
        del HISTORIALES[sid]
    return jsonify({"ok": True})


def precalentar_modelo():
    """Carga el modelo en RAM en segundo plano para que la primera
    pregunta no pague el costo de carga desde disco."""
    try:
        ollama.chat(model=modelo_disponible(),
                    messages=[{"role": "user", "content": "ok"}],
                    keep_alive=KEEP_ALIVE,
                    options={"num_predict": 1})
    except Exception:
        pass


if __name__ == "__main__":
    print("=" * 55)
    print("  NUTRICHEF - Tutor inteligente (ejercicio 1)")
    print("  Modelo:", modelo_disponible())
    print("  Abrir:  http://127.0.0.1:5001")
    print("=" * 55)
    threading.Thread(target=precalentar_modelo, daemon=True).start()
    app.run(host="127.0.0.1", port=5001, debug=False)
