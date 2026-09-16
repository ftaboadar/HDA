# Resultados del experimento MOD-02 (extensión regional sin tocar Colombia/Stripe)

Hogar de los Alpes (HdA) — Entrega 4, MISO 2026-14
Microservicio `pagos` — Strategy `ReglaRegional` + Adapter `IPasarelaDePago`

| | |
|---|---|
| **Ejecutado** | 2026-09-15 (sesión de esta tarea) |
| **Escenario fuente** | `experimento-arquitectura/contexto/escenarios_calidad.md`, tabla "Modificabilidad", columna **MOD-02** |
| **Entorno** | Local — pruebas unitarias de dominio/aplicación (`.venv` propio de `pagos/`), sin infraestructura real (Postgres/HTTP mockeados o no requeridos) |
| **Código bajo prueba** | `pagos/app/application/commands/pagar_trabajo.py`, `pagos/app/domain/pagos/regla_regional.py`, `pagos/app/infrastructure/adapters/regla_colombia.py`, `regla_brasil.py`, `pasarela_stripe.py`, `pasarela_mercadopago.py` |
| **Prueba nueva** | `pagos/tests/unit/aplicacion/test_pagar_trabajo_modificabilidad.py` (3 casos) |
| **Resultado de la suite completa** | **17/17 passed** (14 preexistentes + 3 nuevas) |

## Qué se está validando

Fila **MOD-02** de `escenarios_calidad.md` (texto citado, sin editar):

> **Estímulo**: Se requiere adaptar reglas fiscales, de moneda y regulatorias para el lanzamiento en
> Brasil (2027) sin afectar México ni Argentina.
>
> **Artefacto**: Módulo de reglas regionales (patrón Strategy) dentro de Gestión de Trabajos; para el
> componente de moneda/pasarela específicamente, el patrón Adapter en Pasarelas (submódulo de Pagos —
> ver TP3 en Vista de Módulos: Stripe → MercadoPago sin tocar Liberación y Compensación).
>
> **Respuesta**: *(Prerrequisito de modelo, una sola vez)* Se extiende el ObjetoValor `Monto` con un
> atributo `Moneda` (y `Partner`/`Trabajo` con `Pais`) en la Vista de Información — hoy el modelo no
> distingue moneda ni país. Una vez hecha esa extensión, un desarrollador agrega el nuevo conjunto de
> reglas del país mediante configuración/estrategia, sin recompilar ni redesplegar los demás países ni
> el core.
>
> **Medida de la respuesta**: Extensión de modelo (`Moneda`/`Pais`) completada una única vez, antes del
> primer país adicional; a partir de ahí, cambio implementado y desplegado en < 5 días-persona; 0
> regresiones detectadas por la suite automatizada (gate de release); 0 pipelines de CI/CD disparados
> para módulos de otros países o del core.

En el proyecto real, la separación del microservicio `pagos` (commit `567604e`, "refactor: separa
Pagos en microservicio independiente") ya había extraído `ReglaColombia`/`PasarelaStripe` en su
propio adaptador, y sesiones posteriores agregaron `ReglaBrasil`/`PasarelaMercadoPago` sin volver a
tocar esos dos archivos. Esta tarea existía para **verificar con código y control de versiones real**
que esa afirmación es cierta, no solo de diseño en papel.

## Nota honesta sobre el prerrequisito de modelo (MOD-02)

El propio `escenarios_calidad.md` marca la extensión de `Monto`/`Trabajo` con `Moneda`/`Pais` en la
Vista de Información como un *prerrequisito de modelo* pendiente al momento de redactar el escenario
(ver notas de sesión en ese mismo archivo, líneas ~90 y ~99). Verifiqué el estado actual de
`experimento-arquitectura/contexto/07-vista-informacion.puml`: **sigue sin tener ningún ObjetoValor
`Moneda` ni `Pais` explícito** — la búsqueda de esos términos en el `.puml` no arrojó resultados.

A nivel de **código** (no del diagrama), el prerrequisito ya está resuelto de facto en `pagos/`:
`Dinero` (`app/domain/pagos/value_objects.py`) ya tiene un campo `moneda: str`, y `Region` ya es un
Value Object tipo enum (`COLOMBIA = "CO"`, `BRASIL = "BR"`) que cumple el mismo rol que el `Pais`
pedido por el escenario. Es decir: el código va adelante del diagrama de Vista de Información en este
punto — dejo esto explícito en vez de editar el `.puml` sin mandato claro de esta tarea (que era
validar el código de `pagos/`, no actualizar la Vista de Información). Queda como hallazgo para quien
sí tenga ese mandato.

## Prueba de la Tarea 1 (resumen)

`test_pagar_trabajo_modificabilidad.py` agrega 3 casos:

1. **`test_pagar_trabajo_resuelve_colombia_y_brasil_por_diccionario`**: construye UNA sola instancia
   de `PagarTrabajo` con los diccionarios `reglas_regionales={Region.COLOMBIA: ReglaColombia(),
   Region.BRASIL: ReglaBrasil()}` y `pasarelas={"stripe": PasarelaStripe(), "mercadopago":
   PasarelaMercadoPago()}` inyectados en el constructor, y llama `ejecutar(...)` dos veces:
   - Una vez con un `RegistroTrabajoElegible` de región Colombia (moneda COP) y pasarela `"stripe"` →
     confirma (vía espías delgados sobre las clases reales) que se invocó `ReglaColombia.validar` y
     `PasarelaStripe.cobrar`, y que el `Pago` resultante quedó `EXITOSO` en `Region.COLOMBIA` /
     `Pasarela.STRIPE`.
   - Otra vez con un `RegistroTrabajoElegible` de región Brasil (moneda BRL) y pasarela
     `"mercadopago"`, con los MISMOS diccionarios y la MISMA instancia del comando → confirma que se
     invocó `ReglaBrasil.validar` y `PasarelaMercadoPago.cobrar`, y que el `Pago` resultante quedó
     `EXITOSO` en `Region.BRASIL` / `Pasarela.MERCADOPAGO`.
   - Los repositorios (`IPagoRepository`, `IRegistroTrabajosRepository`) son fakes en memoria propios
     (mismo estilo que `test_compensar.py`/`test_dispatcher_eventos_dominio.py` — no
     `unittest.mock` para ellos). `httpx.AsyncClient` se reemplaza por un fake vía `monkeypatch` para
     no hacer red real, pero la lógica de `PasarelaStripe`/`PasarelaMercadoPago` (construcción del
     payload, manejo de la respuesta) sí es la real.
2. **`test_pagar_trabajo_trabajo_no_encontrado`**: caso de error ya cubierto (no es nuevo en esencia,
   pero valida que el comando sigue funcionando con diccionarios vacíos, sin condicionales
   escondidos).
3. **`test_pagar_trabajo_no_tiene_condicionales_por_pais`**: parsea `pagar_trabajo.py` con `ast` y
   confirma que ningún `If`/`Match` del archivo compara contra los literales `"BR"`, `"CO"`,
   `Region.BRASIL` o `Region.COLOMBIA` (recorre `ast.Constant` y `ast.Attribute` dentro de cada
   condicional), más una verificación textual redundante sobre el código fuente completo. **Resultado:
   no se encontró ningún condicional de ese tipo** — el despacho en `pagar_trabajo.py` es
   exclusivamente `self._reglas_regionales.get(registro.region)` y
   `self._pasarelas.get(pasarela)` (líneas 69 y 75 del archivo), es decir, por diccionario/puerto
   inyectado, tal como exige MOD-02.

### Resultado real de correr `pytest tests/unit -v` en `pagos/`

```
collecting ... collected 17 items

tests/unit/aplicacion/test_compensar.py::test_compensar_despacha_el_evento_pago_compensado PASSED [  5%]
tests/unit/aplicacion/test_compensar.py::test_compensar_pago_inexistente_lanza_error PASSED [ 11%]
tests/unit/aplicacion/test_compensar.py::test_compensar_transiciona_el_estado PASSED [ 17%]
tests/unit/aplicacion/test_pagar_trabajo_modificabilidad.py::test_pagar_trabajo_resuelve_colombia_y_brasil_por_diccionario PASSED [ 23%]
tests/unit/aplicacion/test_pagar_trabajo_modificabilidad.py::test_pagar_trabajo_trabajo_no_encontrado PASSED [ 29%]
tests/unit/aplicacion/test_pagar_trabajo_modificabilidad.py::test_pagar_trabajo_no_tiene_condicionales_por_pais PASSED [ 35%]
tests/unit/dominio/test_pago_aggregate.py::test_fabrica_crea_pago_pendiente PASSED [ 41%]
tests/unit/dominio/test_pago_aggregate.py::test_marcar_exitoso_transiciona_y_guarda_referencia PASSED [ 47%]
tests/unit/dominio/test_pago_aggregate.py::test_marcar_exitoso_registra_evento_de_dominio PASSED [ 52%]
tests/unit/dominio/test_pago_aggregate.py::test_marcar_fallido_transiciona_y_guarda_motivo PASSED [ 58%]
tests/unit/dominio/test_pago_aggregate.py::test_marcar_fallido_registra_evento_de_dominio PASSED [ 64%]
tests/unit/dominio/test_pago_aggregate.py::test_no_se_puede_marcar_exitoso_dos_veces PASSED [ 70%]
tests/unit/dominio/test_pago_aggregate.py::test_compensar_requiere_pago_exitoso PASSED [ 76%]
tests/unit/dominio/test_regla_regional.py::test_regla_colombia_calcula_comision_2_9_por_ciento PASSED [ 82%]
tests/unit/dominio/test_regla_regional.py::test_regla_colombia_rechaza_moneda_distinta_de_cop PASSED [ 88%]
tests/unit/dominio/test_regla_regional.py::test_regla_brasil_calcula_comision_3_9_por_ciento PASSED [ 94%]
tests/unit/dominio/test_regla_regional.py::test_regla_brasil_y_colombia_dan_comisiones_distintas_para_el_mismo_monto PASSED [100%]

============================= 17 passed in 0.19s ==============================
```

## Control de versiones: ¿se tocó `ReglaColombia`/`PasarelaStripe` al agregar Brasil/MercadoPago?

Salida real de:

```
git log --follow --oneline -- experimento-arquitectura/implementacion/pagos/app/infrastructure/adapters/regla_colombia.py
```

```
567604e refactor: separa Pagos en microservicio independiente (pagos/)
a5ab6e8 feat: microservicio Gestión de Trabajos (+ módulo ACL de Pagos)
```

Salida real de:

```
git log --follow --oneline -- experimento-arquitectura/implementacion/pagos/app/infrastructure/adapters/pasarela_stripe.py
```

```
567604e refactor: separa Pagos en microservicio independiente (pagos/)
a5ab6e8 feat: microservicio Gestión de Trabajos (+ módulo ACL de Pagos)
```

**Confirmación explícita**: en ambos casos el commit más reciente que toca el archivo es `567604e`
("refactor: separa Pagos en microservicio independiente"), y verifiqué con
`git show --stat 567604e -- '*regla_colombia.py' '*pasarela_stripe.py'` que ese commit reporta
**`0 insertions(+), 0 deletions(-)`** para ambos archivos — es decir, es un `git mv` puro (rename con
100% de similaridad desde `gestion-de-trabajos/` hacia `pagos/`), no una edición de contenido. Ningún
commit posterior (por ejemplo, el que agregó `ReglaBrasil`/`PasarelaMercadoPago`) aparece en el
`git log --follow` de estos dos archivos. Esto confirma, con evidencia de control de versiones y no
solo de lectura de código, que agregar Brasil no requirió tocar Colombia ni Stripe.

## ¿Hay algún `if`/`match` por país dentro de `pagar_trabajo.py`?

**No.** La inspección con `ast` (parte de la prueba nueva) y una revisión manual del archivo confirman
que el único despacho relevante es:

```python
regla = self._reglas_regionales.get(registro.region)
...
pasarela_impl = self._pasarelas.get(pasarela)
```

Los `if` que sí existen en el comando (`if registro is None`, `if regla is None`, `if pasarela_impl is
None`, `if resultado.exitoso`) son manejo de casos borde/errores y de la respuesta de la pasarela, no
comparaciones contra un literal de país — no violan el patrón Strategy/Adapter que exige MOD-02.

## Veredicto

**MOD-02 se considera demostrado a nivel de código real** (no solo de diseño en papel), con dos
matices honestos:

1. La prueba automatizada pasa (17/17) y `git log --follow` + `git show --stat` confirman que
   `ReglaColombia`/`PasarelaStripe` no tuvieron ningún cambio de contenido posterior a la extracción
   del microservicio — el commit que las movió tiene 0 líneas modificadas, y agregar
   `ReglaBrasil`/`PasarelaMercadoPago` no generó ningún commit adicional sobre esos dos archivos.
2. El "prerrequisito de modelo" que el propio escenario exige (`Moneda`/`Pais` en la Vista de
   Información) sigue sin reflejarse en `07-vista-informacion.puml`, aunque el código de `pagos/` ya
   lo resolvió de facto (`Dinero.moneda`, `Region`). Esto es una inconsistencia entre diagrama y
   código que dejo reportada explícitamente, no oculta — no es responsabilidad de esta tarea corregir
   el `.puml`, pero si `rubrica-auditor` u otra sesión revisa MOD-02 contra la Vista de Información
   literal, debe saber que ese diagrama todavía no tiene los VOs mencionados.

## Referencias

- `experimento-arquitectura/contexto/escenarios_calidad.md` — fila MOD-02 (tabla Modificabilidad).
- `experimento-arquitectura/implementacion/pagos/tests/unit/aplicacion/test_pagar_trabajo_modificabilidad.py`
  — prueba nueva de esta tarea.
- `experimento-arquitectura/implementacion/pagos/app/application/commands/pagar_trabajo.py` — comando
  bajo prueba.
- `experimento-arquitectura/implementacion/pagos/app/infrastructure/adapters/regla_colombia.py`,
  `regla_brasil.py`, `pasarela_stripe.py`, `pasarela_mercadopago.py` — Strategy/Adapter concretos.
- Commit `567604e` — "refactor: separa Pagos en microservicio independiente (pagos/)" (extracción del
  servicio, `git mv` puro para los archivos de Colombia/Stripe).
- `experimento-arquitectura/contexto/07-vista-informacion.puml` — inconsistencia reportada (sin
  `Moneda`/`Pais` explícitos, ver "Nota honesta" arriba).
