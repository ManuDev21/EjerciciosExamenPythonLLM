import json
import os
import re
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def a_json(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [a_json(d) for d in doc]
    salida = {}
    for clave, valor in doc.items():
        if isinstance(valor, ObjectId):
            salida[clave] = str(valor)
        elif isinstance(valor, datetime):
            salida[clave] = valor.isoformat(timespec="seconds")
        elif isinstance(valor, dict):
            salida[clave] = a_json(valor)
        elif isinstance(valor, list):
            salida[clave] = [a_json(v) if isinstance(v, (dict, list)) else v for v in valor]
        else:
            salida[clave] = valor
    return salida


def _campo(doc, ruta):
    actual = doc
    for parte in ruta.split("."):
        if not isinstance(actual, dict):
            return None
        actual = actual.get(parte)
    return actual


def _coincide(doc, filtro) -> bool:
    for clave, esperado in (filtro or {}).items():
        real = _campo(doc, clave)
        if isinstance(esperado, dict):
            for op, valor in esperado.items():
                if op == "$ne" and real == valor:
                    return False
                if op == "$in" and real not in valor:
                    return False
                if op == "$gte" and (real is None or real < valor):
                    return False
                if op == "$lte" and (real is None or real > valor):
                    return False
                if op == "$regex" and not re.search(valor, str(real or ""), re.IGNORECASE):
                    return False
        elif real != esperado:
            return False
    return True


def _ordenar(docs, orden):
    for campo, direccion in reversed(orden or []):
        docs.sort(key=lambda d: str(_campo(d, campo) or ""), reverse=(direccion == -1))
    return docs


class Coleccion:
    def __init__(self, nombre, store):
        self.nombre = nombre
        self._store = store

    def insertar(self, doc: dict) -> str:
        doc = dict(doc)
        doc.setdefault("creado_en", ahora_iso())
        if self._store.mongo is not None:
            res = self._store.mongo[self.nombre].insert_one(doc)
            return str(res.inserted_id)
        doc.setdefault("_id", uuid.uuid4().hex[:24])
        self._store.local[self.nombre].append(doc)
        self._store.guardar_local()
        return doc["_id"]

    def actualizar(self, doc_id: str, campos: dict) -> bool:
        campos = dict(campos)
        campos["actualizado_en"] = ahora_iso()
        if self._store.mongo is not None:
            res = self._store.mongo[self.nombre].update_one(
                self._store.filtro_id(doc_id), {"$set": campos})
            return res.matched_count > 0
        for doc in self._store.local[self.nombre]:
            if str(doc.get("_id")) == doc_id:
                doc.update(campos)
                self._store.guardar_local()
                return True
        return False

    def eliminar(self, doc_id: str) -> bool:
        if self._store.mongo is not None:
            res = self._store.mongo[self.nombre].delete_one(self._store.filtro_id(doc_id))
            return res.deleted_count > 0
        antes = len(self._store.local[self.nombre])
        self._store.local[self.nombre] = [
            d for d in self._store.local[self.nombre] if str(d.get("_id")) != doc_id
        ]
        self._store.guardar_local()
        return len(self._store.local[self.nombre]) < antes

    def agregar_a_lista(self, doc_id: str, campo: str, item: dict) -> bool:
        if self._store.mongo is not None:
            res = self._store.mongo[self.nombre].update_one(
                self._store.filtro_id(doc_id), {"$push": {campo: item}})
            return res.matched_count > 0
        for doc in self._store.local[self.nombre]:
            if str(doc.get("_id")) == doc_id:
                doc.setdefault(campo, []).append(item)
                self._store.guardar_local()
                return True
        return False

    def buscar(self, filtro=None, orden=None, limite=None) -> list:
        if self._store.mongo is not None:
            cur = self._store.mongo[self.nombre].find(filtro or {})
            if orden:
                cur = cur.sort(orden)
            if limite:
                cur = cur.limit(limite)
            return [a_json(d) for d in cur]
        docs = [d for d in self._store.local[self.nombre] if _coincide(d, filtro)]
        docs = _ordenar([dict(d) for d in docs], orden)
        return [a_json(d) for d in (docs[:limite] if limite else docs)]

    def buscar_uno(self, filtro) -> dict:
        docs = self.buscar(filtro, limite=1)
        return docs[0] if docs else None

    def buscar_por_id(self, doc_id: str) -> dict:
        if self._store.mongo is not None:
            return a_json(self._store.mongo[self.nombre].find_one(self._store.filtro_id(doc_id)))
        for doc in self._store.local[self.nombre]:
            if str(doc.get("_id")) == doc_id:
                return a_json(doc)
        return None

    def contar(self, filtro=None) -> int:
        if self._store.mongo is not None:
            return self._store.mongo[self.nombre].count_documents(filtro or {})
        return sum(1 for d in self._store.local[self.nombre] if _coincide(d, filtro))

    def vaciar(self):
        if self._store.mongo is not None:
            self._store.mongo[self.nombre].delete_many({})
        else:
            self._store.local[self.nombre] = []
            self._store.guardar_local()


class Store:
    COLECCIONES = ["camiones", "accesos", "incidentes", "riesgos_eticos",
                   "evaluaciones_llm", "conversaciones", "configuracion", "meta"]

    def __init__(self, uri: str, nombre_db: str, timeout_ms: int = 3000,
                 archivo_fallback: str = ""):
        self.uri = uri
        self.nombre_db = nombre_db
        self.timeout_ms = timeout_ms
        self.archivo_fallback = archivo_fallback
        self.mongo = None
        self.error = None
        self.local = {c: [] for c in self.COLECCIONES}
        self.reconectar()

    def reconectar(self) -> bool:
        try:
            cliente = MongoClient(self.uri, serverSelectionTimeoutMS=self.timeout_ms)
            cliente.admin.command("ping")
            self.mongo = cliente[self.nombre_db]
            self.error = None
            return True
        except PyMongoError as exc:
            self.mongo = None
            self.error = str(exc)
            self._cargar_local()
            return False

    @property
    def motor(self) -> str:
        return "mongodb" if self.mongo is not None else "local"

    def estado(self) -> dict:
        return {"motor": self.motor, "conectado": self.mongo is not None,
                "uri": self.uri if self.mongo is not None else None,
                "error": self.error}

    def col(self, nombre: str) -> Coleccion:
        return Coleccion(nombre, self)

    def filtro_id(self, doc_id: str):
        try:
            return {"_id": ObjectId(doc_id)}
        except Exception:
            return {"_id": doc_id}

    def _cargar_local(self):
        if self.archivo_fallback and os.path.exists(self.archivo_fallback):
            try:
                with open(self.archivo_fallback, encoding="utf-8") as f:
                    datos = json.load(f)
                for c in self.COLECCIONES:
                    self.local[c] = datos.get(c, [])
            except (json.JSONDecodeError, OSError):
                pass

    def guardar_local(self):
        if not self.archivo_fallback:
            return
        os.makedirs(os.path.dirname(self.archivo_fallback), exist_ok=True)
        tmp = self.archivo_fallback + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.local, f, ensure_ascii=False, default=str)
        os.replace(tmp, self.archivo_fallback)

    def obtener_config(self) -> dict:
        doc = self.col("configuracion").buscar_uno({"_tipo": "app"})
        if not doc:
            doc = {"_tipo": "app", "modelo": None, "umbral_confianza": 0.5,
                   "simulacion_correo": True, "operador": "vigilante"}
            self.col("configuracion").insertar(doc)
        return doc

    def guardar_config(self, campos: dict):
        cfg = self.obtener_config()
        self.col("configuracion").actualizar(cfg["_id"], campos)

    def incidentes_por_categoria_semana(self) -> list:
        if self.mongo is not None:
            pipeline = [
                {"$group": {
                    "_id": {
                        "categoria": "$clasificacion.categoria",
                        "semana": {"$isoWeek": {"$dateFromString": {"dateString": "$timestamp"}}},
                        "anio": {"$isoWeekYear": {"$dateFromString": {"dateString": "$timestamp"}}},
                    },
                    "total": {"$sum": 1},
                }},
                {"$sort": {"_id.anio": 1, "_id.semana": 1}},
            ]
            return [{"categoria": d["_id"]["categoria"] or "otro",
                     "semana": d["_id"]["semana"], "anio": d["_id"]["anio"],
                     "total": d["total"]}
                    for d in self.mongo["incidentes"].aggregate(pipeline)]
        grupos = {}
        for d in self.local["incidentes"]:
            try:
                fecha = datetime.fromisoformat(str(d.get("timestamp", ""))[:26])
                anio, semana, _ = fecha.isocalendar()
            except ValueError:
                anio = semana = 0
            clave = (d.get("clasificacion", {}).get("categoria", "otro"), anio, semana)
            grupos[clave] = grupos.get(clave, 0) + 1
        return [{"categoria": c, "anio": a, "semana": s, "total": t}
                for (c, a, s), t in sorted(grupos.items(), key=lambda x: (x[0][1], x[0][2]))]
