import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nucleo.reglas import (analisis_reglas, evaluar_camion, tabla_verdad,
                           tablas_para_ui)
from nucleo.clasificador import (clasificar_por_reglas, extraer_datos,
                                 clasificar)
from nucleo.esquemas import CamionIn, RiesgoIn, ClasificacionLLM, enriquecer_riesgo
from pydantic import ValidationError


class TestReglas(unittest.TestCase):
    def test_ingreso_libre(self):
        r = evaluar_camion(True, False, False, True, True)
        self.assertTrue(r["A"])
        self.assertFalse(r["E"])
        self.assertEqual(r["decision"], "ingreso_libre")
        self.assertEqual(r["semaforo"], "verde")

    def test_inspeccion_por_peso(self):
        r = evaluar_camion(True, True, False, True, True)
        self.assertTrue(r["E"])
        self.assertEqual(r["decision"], "inspeccion")

    def test_inspeccion_por_peligrosa(self):
        r = evaluar_camion(True, False, True, True, True)
        self.assertTrue(r["E"])
        self.assertEqual(r["decision"], "inspeccion")

    def test_denegado_sin_autorizacion(self):
        r = evaluar_camion(False, False, False, True, True)
        self.assertFalse(r["A"])
        self.assertFalse(r["E"])
        self.assertEqual(r["decision"], "denegado")

    def test_retencion_documental(self):
        r = evaluar_camion(True, False, False, True, False)
        self.assertTrue(r["Z"])
        self.assertEqual(r["decision"], "retencion_documental")

    def test_emergencia_domina_todo(self):
        r = evaluar_camion(True, True, True, True, False)
        self.assertTrue(r["Y"])
        self.assertTrue(r["Z"])
        self.assertEqual(r["decision"], "emergencia")

    def test_emergencia_vs_inspeccion(self):
        r = evaluar_camion(True, True, True, True, True)
        self.assertTrue(r["Y"])
        self.assertTrue(r["E"])
        self.assertEqual(r["decision"], "emergencia")

    def test_denegado_sin_licencia(self):
        r = evaluar_camion(True, False, False, False, True)
        self.assertEqual(r["decision"], "denegado")

    def test_explicacion_paso_a_paso(self):
        r = evaluar_camion(True, False, False, True, True)
        self.assertTrue(any("P=V" in p for p in r["explicacion"]))
        self.assertTrue(any("A = P" in p for p in r["explicacion"]))
        self.assertTrue(any("INGRESO LIBRE" in p for p in r["explicacion"]))

    def test_tipo_invalido(self):
        with self.assertRaises(TypeError):
            evaluar_camion("si", False, False, True)

    def test_tabla_original_16(self):
        t = tabla_verdad(("P", "Q", "R", "S"))
        self.assertEqual(len(t), 16)
        for f in t:
            self.assertIn("A", f)
            self.assertIn("E", f)
            self.assertIn("decision", f)

    def test_tabla_z(self):
        t = tablas_para_ui()["Z"]
        self.assertEqual(len(t), 4)
        zs = [f["Z"] for f in t]
        self.assertEqual(zs.count(True), 1)

    def test_tabla_y(self):
        t = tablas_para_ui()["Y"]
        self.assertEqual(len(t), 8)
        self.assertEqual(sum(f["Y"] for f in t), 1)

    def test_analisis_sin_contradiccion(self):
        a = analisis_reglas()
        self.assertEqual(a["total_combinaciones"], 32)
        self.assertFalse(a["hay_contradiccion_logica"])
        self.assertEqual(a["redundantes"], [])
        conf = {tuple(c["reglas"]): c["casos"] for c in a["conflictos"]}
        self.assertEqual(conf[("Y", "E")], 4)
        self.assertEqual(conf[("Z", "E")], 6)
        self.assertEqual(conf[("Z", "A")], 2)
        self.assertEqual(conf[("Z", "Y")], 2)


class TestClasificador(unittest.TestCase):
    def test_derrame_critico(self):
        r = clasificar_por_reglas("urgente derrame",
                                  "emergencia fuga de ácido en el muelle")
        self.assertEqual(r["categoria"], "carga_peligrosa")
        self.assertEqual(r["prioridad"], "critica")

    def test_sobrepeso(self):
        r = clasificar_por_reglas("unidad con sobrepeso",
                                  "la báscula marcó exceso de carga")
        self.assertEqual(r["categoria"], "peso_excedido")

    def test_intruso(self):
        r = clasificar_por_reglas("persona intrusa",
                                  "entró sin autorización por la valla")
        self.assertEqual(r["categoria"], "acceso_indebido")

    def test_grua(self):
        r = clasificar_por_reglas("grúa apagada",
                                  "la grúa pórtico no enciende, suena corto")
        self.assertEqual(r["categoria"], "falla_equipo")

    def test_tos(self):
        r = clasificar_por_reglas("sistema caído",
                                  "el tos no carga la pantalla, error")
        self.assertEqual(r["categoria"], "falla_sistema")

    def test_fatiga(self):
        r = clasificar_por_reglas("chofer cansado",
                                  "el operador reporta fatiga y sueño")
        self.assertEqual(r["categoria"], "estado_conductor")

    def test_sin_coincidencia_otro(self):
        r = clasificar_por_reglas("felicidades",
                                  "gracias por la excelente atención")
        self.assertEqual(r["categoria"], "otro")

    def test_extraer_trk_y_placa(self):
        e = extraer_datos("aviso TRK-205",
                          "la unidad TRK-205 placa GRV-515-N en muelle 3")
        self.assertEqual(e["camion_id"], "TRK-205")
        self.assertEqual(e["placa"], "GRV-515-N")
        self.assertEqual(e["ubicacion"], "muelle 3")

    def test_extraer_peso_toneladas(self):
        e = extraer_datos("peso", "la báscula registró 38.5 toneladas")
        self.assertEqual(e["peso_reportado_kg"], 38500.0)

    def test_modo_reglas_sin_llm(self):
        r = clasificar("fuga de gas", "fuga de gas en contenedor, urgente",
                       modo="reglas")
        self.assertEqual(r["categoria"], "carga_peligrosa")
        self.assertEqual(r["fuente"], "reglas")
        self.assertIn("latencia_ms", r)


class TestEsquemas(unittest.TestCase):
    def test_camion_valido(self):
        c = CamionIn(placa="PTX-104-B", camion_id="TRK-201",
                     empresa="Naviera del Istmo", autorizacion=True,
                     certificacion_vigente=True)
        self.assertEqual(c.placa, "PTX-104-B")

    def test_camion_placa_corta(self):
        with self.assertRaises(ValidationError):
            CamionIn(placa="AB", camion_id="TRK-1", empresa="x",
                     autorizacion=True, certificacion_vigente=True)

    def test_riesgo_enriquecer(self):
        d = enriquecer_riesgo({"probabilidad": 4, "impacto": 5,
                               "probabilidad_residual": 2, "impacto_residual": 3})
        self.assertEqual(d["puntaje"], 20)
        self.assertEqual(d["nivel"], "critico")
        self.assertEqual(d["puntaje_residual"], 6)
        self.assertEqual(d["nivel_residual"], "medio")

    def test_riesgo_probabilidad_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            RiesgoIn(modulo="x", descripcion="descripcion larga",
                     categoria="sesgo", probabilidad=6, impacto=3)

    def test_clasificacion_llm_valida(self):
        c = ClasificacionLLM(categoria="falla_sistema", prioridad="baja",
                             entidades={}, resumen="la pantalla no carga")
        self.assertIsNone(c.entidades.placa)


if __name__ == "__main__":
    unittest.main()
