# Ulises — versión de escritorio (Tkinter)

Implementación alternativa del examen, con dominio distinto al resto del
repositorio: **terminal portuaria** en lugar de parque logístico carretero.

## Ejercicio 1 — Tutor de Inteligencia Artificial

`ejercicio1_tutor_ia/tutor_ia.py`

- Chat de escritorio con el modelo local de Ollama.
- System prompt reescrito: docente universitario de IA (dudas de alumnos de
  licenciatura, ejemplos cotidianos, procedimientos paso a paso).
- Botón "Resumen del historial": el propio LLM sintetiza la conversación.
- Manejo de error si Ollama no responde; las llamadas van en un hilo aparte.

Ejecutar:

```
cd ejercicio1_tutor_ia
python tutor_ia.py
```

## Ejercicio 2 — TransGuard (terminal portuaria)

`ejercicio2_transguard/` — aplicación de escritorio con 10 pestañas.

- **Persistencia**: MongoDB (`transguard`) con respaldo local automático en
  `datos/local_fallback.json` si el servidor no responde. Colecciones:
  camiones, accesos, incidentes, riesgos_eticos, evaluaciones_llm,
  conversaciones, configuracion. Agregación: incidentes por categoría y
  semana (panel de control).
- **Motor de reglas** (`nucleo/reglas.py`): conserva `A = P∧S∧¬Q` y
  `E = P∧(R∨Q)`, y añade dos reglas propias con justificación y tabla de
  verdad:
  - `Z = P∧¬D` — retención documental (falta de BL/manifiesto),
  - `Y = P∧Q∧R` — protocolo de emergencia (sobrepeso + mercancía peligrosa).
  Precedencia `Y > Z > E > A`; el simulador muestra solapamientos y
  comprueba que no hay reglas redundantes ni contradicciones.
- **Clasificador híbrido**: LLM con JSON estricto validado por pydantic,
  reintentos, respaldo por palabras clave y fusión con prioridad más alta +
  marca `requiere_revision_humana`. Categorías del dominio portuario:
  carga_peligrosa, peso_excedido, acceso_indebido, falla_equipo,
  falla_sistema, estado_conductor, otro.
- **Dataset**: 32 correos etiquetados a mano en
  `datos/correos_etiquetados.json` (incluye lenguaje informal con faltas de
  ortografía para el análisis de sesgo). Evaluación desde la pestaña
  "Evaluación": exactitud, matriz de confusión y latencia por modo
  (reglas / llm / híbrido).
- **Asistente RAG**: consulta primero la base, responde solo con ese
  contexto citando `[coleccion#id]`, y contesta "No tengo información
  registrada sobre eso." cuando no hay datos.
- **Riesgos éticos**: matriz 5×5 inherente y residual con alta/edición/baja;
  riesgos propios del sistema (fabricación de datos por el LLM, sesgo ante
  ortografía informal, privacidad de los operadores, dependencia de la
  automatización).
- **Reportes**: exportación CSV / JSON / PDF (fpdf2) de cada colección.
- **Unidades**: CRUD del padrón (TRK-###, placas tipo ABC-123-D, navieras).

Ejecutar:

```
cd ejercicio2_transguard
python run.py
```

Variables de entorno opcionales: `MONGO_URI`, `MONGO_DB`, `OLLAMA_MODEL`.

## Pruebas

```
cd ejercicio2_transguard
python -m unittest discover -s tests
```
