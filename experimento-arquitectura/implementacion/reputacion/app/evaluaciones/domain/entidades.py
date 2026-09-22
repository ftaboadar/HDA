class ReputacionPartner:
    def __init__(
        self, partner_id: str, promedio_actual: float, total_evaluaciones: int
    ):
        self.partner_id = partner_id
        self.promedio_actual = promedio_actual
        self.total_evaluaciones = total_evaluaciones

    def actualizar_promedio(self, nueva_calificacion: float) -> "ReputacionPartner":
        nuevo_total = self.total_evaluaciones + 1
        nuevo_promedio = (
            (self.promedio_actual * self.total_evaluaciones) + nueva_calificacion
        ) / nuevo_total
        return ReputacionPartner(self.partner_id, nuevo_promedio, nuevo_total)
