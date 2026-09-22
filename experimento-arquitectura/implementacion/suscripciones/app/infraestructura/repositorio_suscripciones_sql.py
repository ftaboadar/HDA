from app.dominio.repositorios import RepositorioSuscripciones
from app.dominio.entidades import Suscripcion, Cargo
import sqlite3

class RepositorioSuscripcionesSQLite(RepositorioSuscripciones):
    def __init__(self, db_path="suscripciones.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS suscripciones (
                    id_suscripcion TEXT PRIMARY KEY,
                    id_cliente TEXT,
                    saldo REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cargos (
                    id_cargo TEXT PRIMARY KEY,
                    id_suscripcion TEXT,
                    id_trabajo TEXT,
                    monto REAL,
                    fecha TEXT
                )
            ''')

    def obtener_por_cliente(self, id_cliente: str) -> Suscripcion:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_suscripcion, id_cliente, saldo FROM suscripciones WHERE id_cliente = ?", (id_cliente,))
            row = cursor.fetchone()
            if not row:
                return None
            
            suscripcion = Suscripcion(id_suscripcion=row[0], id_cliente=row[1], saldo=row[2])
            
            cursor.execute("SELECT id_cargo, id_trabajo, monto, fecha FROM cargos WHERE id_suscripcion = ?", (row[0],))
            for cargo_row in cursor.fetchall():
                suscripcion.cargos.append(Cargo(cargo_row[0], cargo_row[1], cargo_row[2], cargo_row[3]))
            return suscripcion

    def guardar(self, suscripcion: Suscripcion):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO suscripciones (id_suscripcion, id_cliente, saldo) VALUES (?, ?, ?)",
                (suscripcion.id_suscripcion, suscripcion.id_cliente, suscripcion.saldo)
            )
            for cargo in suscripcion.cargos:
                conn.execute(
                    "INSERT OR IGNORE INTO cargos (id_cargo, id_suscripcion, id_trabajo, monto, fecha) VALUES (?, ?, ?, ?, ?)",
                    (cargo.id_cargo, suscripcion.id_suscripcion, cargo.id_trabajo, cargo.monto, str(cargo.fecha))
                )
