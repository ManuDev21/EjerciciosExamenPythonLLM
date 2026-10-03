#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada de LogiSmart Web.

    python run.py            -> http://127.0.0.1:5000
    python run.py --seed     -> fuerza el resembrado de datos demo
"""
import sys

from app import create_app

if __name__ == "__main__":
    app = create_app(sembrar_datos=True)
    store = app.extensions["store"]
    print("=" * 60)
    print("  LogiSmart Web - centro de control inteligente")
    print(f"  Persistencia: {store.motor.upper()}"
          + ("" if store.motor == "mongodb" else "  (MongoDB no responde: modo local)"))
    print("  Abrir:  http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
