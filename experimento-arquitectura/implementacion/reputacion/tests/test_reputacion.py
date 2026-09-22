import unittest
from app.evaluaciones.domain.entidades import ReputacionPartner


class TestReputacion(unittest.TestCase):
    def test_actualizar_promedio(self):
        rep = ReputacionPartner("p1", 4.0, 1)
        nueva_rep = rep.actualizar_promedio(5.0)
        self.assertEqual(nueva_rep.promedio_actual, 4.5)
        self.assertEqual(nueva_rep.total_evaluaciones, 2)


if __name__ == "__main__":
    unittest.main()
