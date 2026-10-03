import sys

from nucleo import get_store
from ui.app_tk import TransGuardApp
import config

if __name__ == "__main__":
    store = get_store()
    print("=" * 60)
    print(f"  {config.APP_NOMBRE} - {config.APP_SUBTITULO}")
    print(f"  Persistencia: {store.motor.upper()}"
          + ("" if store.motor == "mongodb" else "  (MongoDB no responde: modo local)"))
    print("  Cierra la ventana para terminar.")
    print("=" * 60)
    sys.exit(TransGuardApp().mainloop() or 0)
