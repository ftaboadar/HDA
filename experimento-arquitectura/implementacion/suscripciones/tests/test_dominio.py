import unittest
from app.dominio.entidades import Suscripcion

class TestSuscripcion(unittest.TestCase):
    def test_registrar_cargo_incrementa_saldo_y_genera_evento(self):
        suscripcion = Suscripcion(id_suscripcion="123", id_cliente="cliente-1")
        suscripcion.registrar_cargo_por_trabajo("trabajo-1", 150.50)
        
        self.assertEqual(suscripcion.saldo, 150.50)
        self.assertEqual(len(suscripcion.cargos), 1)
        self.assertEqual(suscripcion.cargos[0].id_trabajo, "trabajo-1")
        self.assertEqual(suscripcion.cargos[0].monto, 150.50)
        
        self.assertEqual(len(suscripcion.eventos), 1)
        self.assertEqual(suscripcion.eventos[0].id_trabajo, "trabajo-1")

if __name__ == "__main__":
    unittest.main()
