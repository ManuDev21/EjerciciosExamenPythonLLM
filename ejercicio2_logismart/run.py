import sys
import threading

import config
from app import create_app, llm

if __name__ == "__main__":
    app = create_app(sembrar_datos=True)
    store = app.extensions["store"]
    modelo = llm.resolver_modelo(
        store.obtener_config().get("modelo") or config.MODELO_DEFAULT)
    print("=" * 60)
    print("  LogiSmart Web - centro de control inteligente")
    print(f"  Persistencia: {store.motor.upper()}"
          + ("" if store.motor == "mongodb" else "  (MongoDB no responde: modo local)"))
    print("  Modelo:", modelo)
    print("  Abrir:  http://127.0.0.1:5000")
    print("=" * 60)
    threading.Thread(target=llm.precalentar, args=(modelo,), daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
