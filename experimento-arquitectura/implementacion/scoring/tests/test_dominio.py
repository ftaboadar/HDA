import unittest
from uuid import uuid4

from app.domain.models import FotografoScoring
from app.domain.events import ScoringActualizadoEvent


class TestFotografoScoring(unittest.TestCase):
    def test_registrar_trabajo_finalizado_actualiza_promedio_y_contador(self):
        scoring = FotografoScoring(fotografo_id=uuid4())

        scoring.registrar_trabajo_finalizado(calificacion_trabajo=8.0)

        self.assertEqual(scoring.puntuacion_actual, 8.0)
        self.assertEqual(scoring.trabajos_completados, 1)

    def test_registrar_varios_trabajos_promedia_la_puntuacion(self):
        scoring = FotografoScoring(fotografo_id=uuid4())

        scoring.registrar_trabajo_finalizado(calificacion_trabajo=10.0)
        scoring.registrar_trabajo_finalizado(calificacion_trabajo=6.0)

        self.assertEqual(scoring.puntuacion_actual, 8.0)
        self.assertEqual(scoring.trabajos_completados, 2)

    def test_registrar_trabajo_finalizado_genera_evento_de_dominio(self):
        scoring = FotografoScoring(fotografo_id=uuid4())

        scoring.registrar_trabajo_finalizado(calificacion_trabajo=9.0)

        self.assertEqual(len(scoring._events), 1)
        evento = scoring._events[0]
        self.assertIsInstance(evento, ScoringActualizadoEvent)
        self.assertEqual(evento.fotografo_id, scoring.fotografo_id)
        self.assertEqual(evento.nueva_puntuacion, 9.0)

    def test_clear_events_vacia_el_buffer(self):
        scoring = FotografoScoring(fotografo_id=uuid4())
        scoring.registrar_trabajo_finalizado(calificacion_trabajo=7.0)

        scoring.clear_events()

        self.assertEqual(len(scoring._events), 0)


if __name__ == "__main__":
    unittest.main()
