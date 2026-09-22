import unittest
from app.solicitudes.domain.solicitud import Solicitud

class TestSolicitudesDomain(unittest.TestCase):
    def test_crear_solicitud_genera_evento(self):
        solicitud = Solicitud(cliente_id="C-123", detalles="Limpieza")
        self.assertEqual(solicitud.estado, "CREADA")
        
        solicitud.crear()
        
        self.assertEqual(len(solicitud.eventos), 1)
        evento = solicitud.eventos[0]
        self.assertEqual(evento.__class__.__name__, "SolicitudCreada")
        self.assertEqual(evento.solicitud_id, solicitud.id)
        self.assertEqual(evento.cliente_id, "C-123")
        self.assertEqual(evento.detalles, "Limpieza")

if __name__ == '__main__':
    unittest.main()
