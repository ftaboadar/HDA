import unittest
from src.scoring.dominio.entidades.perfil_crediticio import PerfilCrediticio

class TestPerfilCrediticio(unittest.TestCase):
    def test_registrar_trabajo_exitoso(self):
        perfil = PerfilCrediticio(id="1", cliente_id="c1", puntaje=50, historial_trabajos=0)
        perfil.registrar_trabajo_finalizado(exito=True)
        self.assertEqual(perfil.puntaje, 60)
        self.assertEqual(perfil.historial_trabajos, 1)
        self.assertEqual(len(perfil.eventos), 1)
        self.assertEqual(perfil.eventos[0].tipo, "ScoringActualizado")

    def test_registrar_trabajo_fallido(self):
        perfil = PerfilCrediticio(id="1", cliente_id="c1", puntaje=50, historial_trabajos=0)
        perfil.registrar_trabajo_finalizado(exito=False)
        self.assertEqual(perfil.puntaje, 45)
        self.assertEqual(perfil.historial_trabajos, 1)
        self.assertEqual(len(perfil.eventos), 1)
        self.assertEqual(perfil.eventos[0].tipo, "ScoringActualizado")

if __name__ == "__main__":
    unittest.main()
