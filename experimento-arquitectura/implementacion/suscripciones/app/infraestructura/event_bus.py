from app.dominio.eventos import CargoRegistrado

def despachar(evento):
    if isinstance(evento, CargoRegistrado):
        print(f"[EVENTO INTRA-SERVICIO] Se ha registrado el cargo {evento.id_cargo} por un monto de {evento.monto} en la suscripción {evento.id_suscripcion}")
