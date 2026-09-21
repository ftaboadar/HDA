# Reglas duras — Rúbrica Entrega 5 (Prueba de concepto, entrega final)

Fuentes (en el repo): `utils/Entrega-005-EntregaFinal.pdf` (rúbrica), `ACLARACIONES-entrega-5.md` (aclaraciones del profesor) y
`utils/Entrega-004y005-POCArquitecturaEnunciado.pdf` (enunciado de las Entregas 4 y 5, puntos 1-12).
Este archivo transcribe la rúbrica **sin reinterpretarla**. Donde el PDF es ambiguo se dice explícitamente.

## Cómo se califica

- La rúbrica vale el **30 %** de la nota; el **70 %** es la **sustentación con el tutor**. Un ítem de 6 pt =
  1,8 pt por entregarlo y que funcione + 4,2 pt por sustentarlo.
- **No presentar un ítem = cero en ese ítem.**
- **Todos** los integrantes deben poder sustentar, aclarar y defender el diseño y la implementación: el
  tutor sabe que la IA genera soluciones plausibles. Cada decisión debe tener un *por qué*: qué atributo de
  calidad beneficia y qué impacto tiene en el producto y el negocio.
- Del enunciado: **código que no corre = cero**; contribuciones equitativas visibles en commits y PRs; el
  README o un anexo describe las actividades de cada miembro; el tutor puede pedir una demo.

## Ítems (100 pt)

| # | Bloque | Ítem | Pt |
|---|---|---|---|
| 1 | Almacenamiento y transacciones | Los servicios implementados antes siguen funcionando (**sin regresión**) | 5 |
| 2 | Almacenamiento y transacciones | Implementó, **justificó y demuestra** un **patrón de sagas** que abarca **al menos 4 servicios**, en coreografía u orquestación. Debe mostrarse **una transacción exitosa y una con fallos que involucren compensación** | 19 |
| 3 | Almacenamiento y transacciones | Implementó y demostró, **junto con el coordinador de sagas**, un **Saga Log** para monitorear el estado de las transacciones | 8 |
| 4 | Presentación y despliegue | Desarrolló un **BFF** que sirve como base para el API | 15 |
| 5 | Presentación y despliegue | Los servicios fueron **desplegados** en una plataforma de preferencia (justificada, enunciado punto 9) | 5 |
| 6 | Presentación y despliegue | **Link, documentación y colección de Postman** para interactuar con el sistema **usando el BFF**. Si el BFF no funciona, el tutor puede pedir una sesión de demostración | 5 |
| 7 | Resultados y refinamiento | **Resultados cuantitativos y cualitativos** de la experimentación, basados en los escenarios de calidad escogidos | 5 |
| 8 | Resultados y refinamiento | **Conclusiones** sobre si se cumplió o no la **hipótesis** de cada experimento | 5 |
| 9 | Resultados y refinamiento | **Refinó el mapa de contextos TO-BE** (Entrega 1) con base en los resultados, **justificando los cambios** | 4 |
| 10 | Resultados y refinamiento | **Refinó los diagramas de los puntos de vista** (Entrega 2) con base en los resultados, **justificando los cambios** | 4 |
| 11 | Contribuciones | Calificación de pares (evaluación 360) | 12,5 |
| 12 | Contribuciones | **Contribución equitativa en el repositorio** | 12,5 |

Además, el texto de la rúbrica pide que el diseño sea coherente con **los 3 escenarios de calidad
seleccionados** (uno por atributo) y que un **video** demuestre su cumplimiento, con conclusiones y
resultados cuantitativos y cualitativos.

## Condiciones del enunciado que siguen vigentes (puntos 1-12)

1. Microservicios basados en eventos: la comunicación entre servicios es con **comandos y eventos**.
2. Eventos definidos según el escenario: **¿de integración o con carga de estado? ¿por qué?** Diseño del
   esquema, desde la tecnología hasta su evolución: **¿Avro o Protobuf? ¿Event Stream Versioning?**, justificado.
3. Al menos **4 microservicios** (no completos: solo comandos, consultas e infraestructura necesaria).
4. Broker: **Apache Pulsar**.
5. Almacenamiento: **¿descentralizado o híbrido? ¿por qué?**
6. **CRUD o Event Sourcing** por servicio (no todos tienen que usar el mismo).
7. **Sagas** para transacciones largas; coreografía u orquestación a decisión del equipo.
8. **BFF** para externos y UI (puede contar como uno de los 4 servicios).
9. Despliegue en la plataforma de preferencia, **justificado**.
10. Resultados cuantitativos y cualitativos.
11. Refinar el mapa de contextos TO-BE y los puntos de vista.
12. **Python.**

## Ambigüedades del PDF (dichas explícitamente, no resueltas a favor del entregable)

- **3 o 4 servicios en la saga:** el texto de la diapositiva dice "al menos 3"; la tabla de puntaje dice
  "al menos 4". **Se toma 4** (lo más exigente, y es la fila que tiene los 19 pt).
- **Coreografía u orquestación:** la rúbrica deja elegir, pero el ítem 3 habla del **"coordinador de
  sagas"** y el enunciado de la entrega final (Sobre la entrega, punto 3) de *"implementación de un
  coordinador de Sagas"*. Con coreografía pura no hay coordinador que muestre el Saga Log: orquestar es la
  lectura más segura para los ítems 2 y 3.
