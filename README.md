# Examen — Ejercicios con LLM local (Ollama)

Dos ejercicios desarrollados a partir de los scripts base `p02primertutor_llm.py`
y `logiuncodigo.py`, ahora como **aplicaciones web Flask + HTML + CSS + JS + Bootstrap**.

| Carpeta | Ejercicio | Puerto |
|---|---|---|
| `ejercicio1_tutor/` | Tutor inteligente con LLM (NutriChef) | 5001 |
| `ejercicio2_logismart/` | LogiSmart: app modular con MongoDB + LLM | 5000 |

## Requisitos

```bash
pip install -r requirements.txt
```

- **Ollama** ejecutándose (`ollama serve`) con algún modelo (p. ej. `ollama pull llama3`).
- **MongoDB** local (`mongodb://localhost:27017`) o Atlas vía `MONGO_URI`.
  Si MongoDB no responde, LogiSmart degrada a un almacén JSON local y lo indica en la GUI.

## Ejecución

```bash
# Ejercicio 1 — tutor con GUI web
cd ejercicio1_tutor
python app.py          # http://127.0.0.1:5001

# Ejercicio 2 — LogiSmart
cd ejercicio2_logismart
python run.py          # http://127.0.0.1:5000

# Pruebas del ejercicio 2
cd ejercicio2_logismart
python -m unittest discover -s tests -v
```

## Ejercicio 1 — qué se cambió

1. **Configuración del sistema distinta**: el `system` ya no es un profesor de IA,
   es **NutriChef**, asistente de cocina saludable y nutrición básica.
2. **Interfaz gráfica**: chat web con burbujas, indicador de escritura y avisos
   de error amigables (Flask + Bootstrap).
3. **Resumen del historial**: el botón *Resumen del historial* pide al LLM una
   síntesis de la conversación del usuario.

## Ejercicio 2 — resumen

Transformación del script monolítico `logiuncodigo.py` en arquitectura por capas:

- **Persistencia**: MongoDB (colecciones `camiones`, `accesos`, `incidentes`,
  `riesgos_eticos`, `evaluaciones_llm`, `conversaciones`, `configuracion`) con CRUD
  desde la GUI y agregación real (incidentes por categoría y semana ISO).
- **Motor de reglas**: conserva `A = P∧S∧¬Q` y `E = P∧(R∨Q)` y agrega dos reglas
  nuevas justificadas con su tabla de verdad (`H = R∧T`, `W = S∧V`), explicación
  paso a paso y análisis de redundancia/conflictos.
- **Clasificador híbrido**: LLM con salida JSON validada por pydantic, reintentos,
  plan de respaldo por reglas y fusión "prioridad más alta + revisión humana".
- **Asistente RAG**: consulta MongoDB primero y responde solo con datos citados.
- **Riesgos éticos**: matriz 5×5 con gráfica inherente vs residual y CRUD.

Ver `ejercicio2_logismart/INFORME.md` para el informe técnico completo.
