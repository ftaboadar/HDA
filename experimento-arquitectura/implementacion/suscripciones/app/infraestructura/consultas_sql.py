import sqlite3
from app.aplicacion.consultas import ConsultaEstadoSuscripcion, EstadoSuscripcionDTO

class ConsultaEstadoSuscripcionSQLite(ConsultaEstadoSuscripcion):
    def __init__(self, db_path="suscripciones.db"):
        self.db_path = db_path

    def obtener_estado(self, id_cliente: str) -> EstadoSuscripcionDTO:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT saldo FROM suscripciones WHERE id_cliente = ?", (id_cliente,))
            row = cursor.fetchone()
            if not row:
                return EstadoSuscripcionDTO(id_cliente=id_cliente, saldo_total=0.0, cantidad_cargos=0)
            
            saldo = row[0]
            cursor.execute("SELECT COUNT(*) FROM cargos c JOIN suscripciones s ON c.id_suscripcion = s.id_suscripcion WHERE s.id_cliente = ?", (id_cliente,))
            count = cursor.fetchone()[0]
            
            return EstadoSuscripcionDTO(id_cliente=id_cliente, saldo_total=saldo, cantidad_cargos=count)
