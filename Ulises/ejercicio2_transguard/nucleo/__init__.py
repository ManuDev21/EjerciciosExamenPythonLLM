import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .db import Store

_store = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(config.MONGO_URI, config.MONGO_DB,
                       config.MONGO_TIMEOUT_MS, config.ARCHIVO_FALLBACK)
    return _store


def cargar_dataset() -> list:
    if os.path.exists(config.ARCHIVO_CORREOS):
        with open(config.ARCHIVO_CORREOS, encoding="utf-8") as f:
            return json.load(f)
    return []


def sembrar_si_vacio(forzar: bool = False) -> dict:
    from .seed import sembrar
    return sembrar(get_store(), cargar_dataset(), forzar=forzar)


def modelo_actual() -> str:
    return get_store().obtener_config().get("modelo") or config.MODELO_DEFAULT
