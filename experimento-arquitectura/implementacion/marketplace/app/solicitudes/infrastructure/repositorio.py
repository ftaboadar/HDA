import sqlite3
from app.solicitudes.domain.solicitud import Solicitud

class RepositorioSolicitudes:
    def __init__(self, db_path="solicitudes.db"):
        self.db_path = db_path
        self._crear_tabla()

    def _crear_tabla(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS solicitudes (
                    id TEXT PRIMARY KEY,
                    cliente_id TEXT,
                    detalles TEXT,
                    estado TEXT
                )
            ''')

    def guardar(self, solicitud: Solicitud):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO solicitudes (id, cliente_id, detalles, estado) VALUES (?, ?, ?, ?)",
                (solicitud.id, solicitud.cliente_id, solicitud.detalles, solicitud.estado)
            )

    def actualizar_estado(self, solicitud_id: str, estado: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE solicitudes SET estado = ? WHERE id = ?",
                (estado, solicitud_id)
            )
