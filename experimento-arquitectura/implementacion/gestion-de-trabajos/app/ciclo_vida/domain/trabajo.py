"""Agregado raíz `Trabajo` — raíz de agregado ya establecida en el modelo de
información (07-vista-informacion.puml, paquete "Gestión de Trabajos":
`class Trabajo <<AggregateRoot>>`). Este código NO reproduce el agregado
completo de ese diagrama (Trabajo + SubTrabajo + Cotizacion + Novedad +
Direccion/Urgencia/CategoriaServicio) — es un recorte deliberado de
skeleton (ver 12-plan-entrega-4.md sección 1.5: "no hace falta lógica de
negocio rica, 1-2 tablas bastan"). Ver README.md, sección "Qué falta" y la
nota de inconsistencia con el modelo de información al final de este
docstring.

INCONSISTENCIA EXPLÍCITA con el modelo de información, dejada a propósito
en vez de improvisarse en silencio: 07-vista-informacion.puml no modela
ningún atributo de `Trabajo` (el diagrama solo dibuja entidades/VOs y
relaciones, sin atributos — ver su propio comentario: "No se detallan
atributos/métodos"), así que el estado mínimo elegido aquí (proveedor_id,
estado, monto, region, fecha_creacion) es una interpretación razonable pero
NO derivada literalmente del diagrama. Tampoco existe todavía en ese
diagrama ningún campo de dinero/monto en `Trabajo` ni una entidad `Pago` en
ningún paquete — el submódulo ACL de Pagos (`domain/pagos/`) es enteramente
nuevo respecto a 07-vista-informacion.puml, consistente con que Pagos es un
`GENERIC_SUBDOMAIN` externo (01-dominios-subdominios.cml) y no tiene
representación en la vista de información porque no es un agregado propio
de HdA. Quien complete este servicio debería decidir, con el equipo de
diseño, si vale la pena actualizar 07-vista-informacion.puml para incluir
Direccion/Urgencia/CategoriaServicio del Trabajo real, o si se acepta que
el modelo de información describe el dominio completo (Entrega 5+) y este
código solo cubre el subconjunto necesario para los 3 escenarios de calidad
de la Entrega 4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.seedwork.dominio.aggregate_root import AggregateRoot
from app.ciclo_vida.domain.eventos import TrabajoFinalizado
from app.ciclo_vida.domain.value_objects import (
    Dinero,
    EstadoTrabajo,
    ProveedorId,
    Region,
    TrabajoId,
)


class ErrorTransicionInvalida(Exception):
    """Se lanza cuando se intenta una transición de estado que viola un
    invariante del agregado — nunca un `assert` silencioso (mismo patrón
    que `Verificacion.ErrorTransicionInvalida` en Proveedores, cada servicio
    con su propia excepción, sin compartir código entre contextos)."""


class Trabajo(AggregateRoot):
    def __init__(
        self,
        id: uuid.UUID,
        monto: Dinero,
        region: Region,
        proveedor_id: ProveedorId | None = None,
        estado: EstadoTrabajo = EstadoTrabajo.SOLICITADO,
        fecha_creacion: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self.proveedor_id = proveedor_id
        self.monto = monto
        self.region = region
        self.estado = estado
        self.fecha_creacion = fecha_creacion or datetime.now(timezone.utc)

    def esperar_elegibles(self) -> None:
        if self.estado != EstadoTrabajo.SOLICITADO:
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a ESPERANDO_ELEGIBLES"
            )
        self.estado = EstadoTrabajo.ESPERANDO_ELEGIBLES

    def asignar_proveedor(self, proveedor_id: ProveedorId) -> None:
        if self.estado not in (EstadoTrabajo.ESPERANDO_ELEGIBLES, EstadoTrabajo.SOLICITADO):
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a ASIGNADO"
            )
        self.proveedor_id = proveedor_id
        self.estado = EstadoTrabajo.ASIGNADO

    def iniciar_workflow(self) -> None:
        if self.estado != EstadoTrabajo.ASIGNADO:
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a EN_CURSO"
            )
        self.estado = EstadoTrabajo.EN_CURSO

    def reasignar_proveedor(self) -> None:
        if self.estado not in (EstadoTrabajo.ASIGNADO, EstadoTrabajo.EN_CURSO):
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a ESPERANDO_ELEGIBLES"
            )
        self.proveedor_id = None
        self.estado = EstadoTrabajo.ESPERANDO_ELEGIBLES

    def finalizar(self) -> None:
        """Invariante protegido: un Trabajo ya FINALIZADO no puede
        finalizarse otra vez."""
        if self.estado != EstadoTrabajo.EN_CURSO:
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a FINALIZADO"
            )
        self.estado = EstadoTrabajo.FINALIZADO
        if self.proveedor_id:
            self.registrar_evento(
                TrabajoFinalizado(
                    trabajo_id=TrabajoId(self.id),
                    proveedor_id=self.proveedor_id,
                    monto=self.monto.valor,
                    moneda=self.monto.moneda,
                    region=self.region,
                )
            )

    def pagar(self) -> None:
        if self.estado != EstadoTrabajo.FINALIZADO:
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a PAGADO"
            )
        self.estado = EstadoTrabajo.PAGADO

    def disputar(self) -> None:
        if self.estado not in (EstadoTrabajo.FINALIZADO, EstadoTrabajo.PAGADO):
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a EN_DISPUTA"
            )
        self.estado = EstadoTrabajo.EN_DISPUTA

    def cancelar(self) -> None:
        if self.estado not in (EstadoTrabajo.ASIGNADO, EstadoTrabajo.EN_DISPUTA):
            raise ErrorTransicionInvalida(
                f"Transición inválida de {self.estado} a CANCELADO"
            )
        self.estado = EstadoTrabajo.CANCELADO
