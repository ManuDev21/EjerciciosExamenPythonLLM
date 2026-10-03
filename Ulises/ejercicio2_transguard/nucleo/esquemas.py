from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CATEGORIAS = [
    "carga_peligrosa", "peso_excedido", "acceso_indebido",
    "falla_equipo", "falla_sistema", "estado_conductor", "otro",
]
PRIORIDADES = ["baja", "media", "alta", "critica"]
ESTADOS_INCIDENTE = ["nuevo", "en_atencion", "cerrado"]
CATEGORIAS_RIESGO = ["sesgo", "privacidad", "transparencia", "seguridad",
                     "responsabilidad", "otro"]


class Entidades(BaseModel):
    placa: Optional[str] = None
    camion_id: Optional[str] = None
    peso_reportado_kg: Optional[float] = None
    ubicacion: Optional[str] = None


class ClasificacionLLM(BaseModel):
    categoria: Literal[tuple(CATEGORIAS)]
    prioridad: Literal[tuple(PRIORIDADES)]
    entidades: Entidades = Field(default_factory=Entidades)
    resumen: str = ""


class CamionIn(BaseModel):
    placa: str = Field(min_length=4, max_length=15)
    camion_id: str = Field(min_length=3, max_length=15)
    empresa: str = Field(min_length=1, max_length=80)
    autorizacion: bool
    certificacion_vigente: bool
    certificacion_dias_restantes: int = Field(ge=0, le=3650, default=180)

    @field_validator("placa", "camion_id", "empresa")
    @classmethod
    def _strip(cls, v):
        return v.strip()


def nivel_riesgo(puntaje: int) -> str:
    if puntaje >= 17:
        return "critico"
    if puntaje >= 10:
        return "alto"
    if puntaje >= 5:
        return "medio"
    return "bajo"


def enriquecer_riesgo(doc: dict) -> dict:
    doc["puntaje"] = doc.get("probabilidad", 1) * doc.get("impacto", 1)
    doc["nivel"] = nivel_riesgo(doc["puntaje"])
    pr, ir = doc.get("probabilidad_residual"), doc.get("impacto_residual")
    doc["puntaje_residual"] = pr * ir if pr and ir else None
    doc["nivel_residual"] = nivel_riesgo(doc["puntaje_residual"]) if pr and ir else None
    return doc


class RiesgoIn(BaseModel):
    modulo: str = Field(min_length=2, max_length=80)
    descripcion: str = Field(min_length=5, max_length=400)
    categoria: Literal[tuple(CATEGORIAS_RIESGO)]
    probabilidad: int = Field(ge=1, le=5)
    impacto: int = Field(ge=1, le=5)
    mitigacion: str = Field(default="", max_length=400)
    probabilidad_residual: Optional[int] = Field(default=None, ge=1, le=5)
    impacto_residual: Optional[int] = Field(default=None, ge=1, le=5)
