import csv
import io
import json
from datetime import datetime


def a_csv(docs: list, campos: list = None) -> str:
    if not docs:
        return ""
    filas = []
    for d in docs:
        fila = {}
        _aplanar(d, "", fila)
        filas.append(fila)
    campos = campos or sorted({k for f in filas for k in f})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, extrasaction="ignore")
    w.writeheader()
    w.writerows(filas)
    return buf.getvalue()


def _aplanar(d, prefijo, salida):
    for k, v in d.items():
        clave = f"{prefijo}{k}" if not prefijo else f"{prefijo}.{k}"
        if isinstance(v, dict):
            _aplanar(v, clave, salida)
        elif isinstance(v, list):
            salida[clave] = json.dumps(v, ensure_ascii=False)
        else:
            salida[clave] = v


def a_json(docs: list) -> str:
    return json.dumps(docs, ensure_ascii=False, indent=2, default=str)


def nombre_archivo(coleccion: str, ext: str) -> str:
    return f"transguard_{coleccion}_{datetime.now():%Y%m%d_%H%M%S}.{ext}"


def _limpio(texto) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in s if ord(c) < 128)


def a_pdf(docs: list, titulo: str, ruta: str) -> bool:
    try:
        from fpdf import FPDF
    except ImportError:
        return False
    pdf = FPDF(orientation="L", unit="mm", format="letter")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 8, _limpio(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    pdf.cell(0, 5, _limpio(f"Generado: {datetime.now():%Y-%m-%d %H:%M}  -  "
                          f"registros: {len(docs)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    campos_omitidos = {"explicacion", "cuerpo", "historial", "historico",
                       "respuesta", "detalle", "datos_extraidos"}
    for i, doc in enumerate(docs, 1):
        lineas = "  |  ".join(
            f"{k}: {_limpio(v) if not isinstance(v, (dict, list)) else _limpio(json.dumps(v, ensure_ascii=False))[:80]}"
            for k, v in doc.items() if k not in campos_omitidos)
        pdf.set_font("courier", "", 7)
        pdf.multi_cell(0, 4, _limpio(f"#{i}  {lineas}"))
        pdf.ln(1)
    pdf.output(ruta)
    return True
