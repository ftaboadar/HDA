import sqlite3

class VistasSolicitudes:
    def __init__(self, db_path="vistas_solicitudes.db"):
        self.db_path = db_path
        self._crear_tabla()

    def _crear_tabla(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS solicitudes_leidas (
                    id TEXT PRIMARY KEY,
                    cliente_id TEXT,
                    detalles TEXT,
                    estado TEXT,
                    progreso INTEGER
                )
            ''')

    def actualizar(self, solicitud_id: str, cliente_id: str, detalles: str, estado: str, progreso: int = 0):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM solicitudes_leidas WHERE id = ?", (solicitud_id,))
            if cursor.fetchone():
                conn.execute("UPDATE solicitudes_leidas SET estado=?, progreso=? WHERE id=?", (estado, progreso, solicitud_id))
            else:
                conn.execute("INSERT INTO solicitudes_leidas (id, cliente_id, detalles, estado, progreso) VALUES (?, ?, ?, ?, ?)", (solicitud_id, cliente_id, detalles, estado, progreso))

    def obtener(self, solicitud_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id, cliente_id, detalles, estado, progreso FROM solicitudes_leidas WHERE id = ?", (solicitud_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "cliente_id": row[1],
                    "detalles": row[2],
                    "estado": row[3],
                    "progreso": row[4]
                }
            return None
