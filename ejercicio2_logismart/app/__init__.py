# -*- coding: utf-8 -*-
"""Fábrica de la aplicación Flask de LogiSmart."""
import json
import os
import sys

from flask import Flask, current_app

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .db import Store


def get_store() -> Store:
    return current_app.extensions["store"]


def cargar_dataset() -> list:
    if os.path.exists(config.ARCHIVO_CORREOS):
        with open(config.ARCHIVO_CORREOS, encoding="utf-8") as f:
            return json.load(f)
    return []


def create_app(sembrar_datos: bool = True) -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config["JSON_AS_ASCII"] = False
    app.json.ensure_ascii = False

    store = Store(config.MONGO_URI, config.MONGO_DB, config.MONGO_TIMEOUT_MS,
                  config.ARCHIVO_FALLBACK)
    app.extensions["store"] = store

    from .rutas import registrar_blueprints
    registrar_blueprints(app)

    if sembrar_datos:
        try:
            from .seed import sembrar
            sembrar(store, cargar_dataset())
        except Exception as exc:  # la app arranca aunque falle la semilla
            app.logger.warning("No se pudieron sembrar los datos demo: %s", exc)

    return app
