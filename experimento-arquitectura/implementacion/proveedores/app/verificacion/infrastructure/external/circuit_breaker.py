import time
from functools import wraps


class CircuitBreaker:
    def __init__(self, fallos_maximos=3, tiempo_reset=60):
        self.fallos_maximos = fallos_maximos
        self.tiempo_reset = tiempo_reset
        self.fallos = 0
        self.ultimo_fallo = None
        self.estado = "CERRADO"

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.estado == "ABIERTO":
                if time.time() - self.ultimo_fallo > self.tiempo_reset:
                    self.estado = "MEDIO_ABIERTO"
                else:
                    raise Exception("Circuit Breaker Abierto: Servicio externo no disponible")
            try:
                resultado = func(*args, **kwargs)
                self.fallos = 0
                self.estado = "CERRADO"
                return resultado
            except Exception as e:
                self.fallos += 1
                self.ultimo_fallo = time.time()
                if self.fallos >= self.fallos_maximos:
                    self.estado = "ABIERTO"
                raise e

        return wrapper
