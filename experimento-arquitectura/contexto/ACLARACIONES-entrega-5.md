# Aclaraciones del profesor — Entrega 5 (texto 1, transcrito tal cual)

> Complementa `REGLAS-DURAS-rubrica-entrega-5.md`. Recibido el 2026-09-21. No se reinterpreta.

A continuación se brindan unas aclaraciones sobre el proyecto:

Siguen aplicando las indicaciones de la entrega 4.

NO DEBEN usar todo lo visto en el curso, no se sientan forzados de aplicar cada patrón o táctica. Aplique lo que tenga sentido para su arquitectura de solución y lo que en el enunciado sea explícito su uso.

Con base al punto anterior, es OBLIGATORIO:

- Implementar un patrón de sagas que abarca al menos 3 de los servicios en formato de coreografía u orquestación. Se debe mostrar claramente su funcionamiento, desde una transacción exitosa hasta una con fallos que involucren compensación. Usted como arquitecto debe definir si usar coreografía y orquestación. Su justificación debe ser clara y coherente con las necesidades del negocio.
- Se DEBE mostrar la implementación de un Saga Log y el uso del mismo para monitorear el estado de las transacciones. Haga uso de clientes de bases de datos y trate de ser lo más expresivo posible. Por ejemplo, puede incluir consultas SQL para validar el workflow de las transacciones. En el video debe ser claro el funcionamiento de la Saga. Puede usar el Saga Log para demostrar como se ejecutan los pasos durante la transacción larga, así como las compensaciones.
- Desarrolló un BFF que sirve como base para el API de CSaaS y todos los servicios fueron desplegados en una plataforma de preferencia. Usted acá decide como implementar su BFF. Lo importante es que este debe exponer una interface HTTP REST o GraphQL para que por medio de llamados síncronos se pueda acceder a las capacidades de negocio. Para lograr lo anterior, usted DEBE proveer un link, documentación y collection de POSTMAN. Si la interacción con el BFF no funciona, el tutor está en la potestad de pedir una sesión donde se demuestre el correcto funcionamiento.
- Documento con resultados cuantitativos y cualitativos sobre la experimentación realizada (basado en los escenarios de calidad escogidos). Este debe incluir conclusiones sobre si cumplió o no la hipótesis del experimento. Recuerde que los escenarios DEBEN SER RELEVANTES para el negocio.
- El Documento incluye o anexa otro documento con un refinamiento del diagrama de mapas de contexto TO-BE presentado en la primera entrega, con base a los resultados y conclusiones de la experimentación. Recuerde justificar los cambios e indicar los cambios en el mismo. Así mismo, dicho documento debe incluir un refinamiento de los diagramas de los diferentes puntos de vista presentados en la segunda entrega, con base a los resultados y conclusiones de la experimentación.
- Recuerde que este es un curso donde DDD es la filosofía central de diseño. Por tal motivo, usted DEBE usar los patrones, tácticas y métodos aprendidos durante el curso. Deben ser claros los principios de DDD en el diseño: agregaciones, contextos acotados, inversión de dependencias, capas, arquitectura cebolla, etc. No es una carrera acerca de usar todo lo visto en términos de DDD, pero conceptos como las entidades, objetos valor, agregaciones y modelo de dominio son claves para tener micro-servicios realmente desacoplados y por ende DEBEN ser parte de su solución.
- Cualquier otro detalle que se mencione en el enunciado o rúbrica.

---

# Texto 2 (transcrito tal cual)

Finalmente, los ingenieros quieren ver una prueba de concepto (POC) de la arquitectura de solución que su grupo está proponiendo. Dado que su arquitectura debe satisfacer la visión del negocio, no olvidé que su experimentación debe probar que la arquitectura propuesta nos va a ayudar a escalar el negocio de manera global, Su experimentación debe validar un escenario de calidad por cada atributo de calidad definido en las entregas anteriores. Es decir, su experimentación debe validar 3 escenarios de calidad.

El código debe encontrarse en un software de control de versionamiento como Github, Gitlab, Bitbucket, etc. Lo importante es que los tutores puedan acceder al código en caso de ser necesario.

Deben ser claros los principios de DDD en el diseño: agregaciones, contextos acotados, inversión de dependencias, capas, etc.

Criterios de revisión:

- Implementó un patrón de sagas que abarca al menos 3 de los servicios en formato de coreografía u orquestación. Se debe mostrar claramente su funcionamiento, desde una transacción exitosa hasta una con fallos que involucren compensación.
- Desarrolló un BFF que sirve como base para el API y todos los servicios fueron desplegados en una plataforma de preferencia.
- El diseño, arquitectura y desarrollo de los microservicios es coherente con los 3 escenarios de calidad seleccionados y el video demuestra el cumplimiento de los mismos. Este incluye conclusiones sobre si cumplió o no la hipótesis del experimento. Debe incluir resultados cuantitativos y cualitativos.

---

# Observaciones del profesor sobre la Entrega 4 (notas del equipo, 2026-09-21)

Tomadas por el equipo en la retroalimentación. Cada una debe quedar respondida de forma explícita en la
Entrega 5 (documento + sustentación).

1. **Evento de integración o con carga de estado**: definirlo por evento y justificarlo.
2. **Versionamiento de esquemas o de APIs**: cómo evolucionan los eventos (y las APIs).
3. **Almacenamiento descentralizado, híbrido o centralizado**: definirlo. **Cada microservicio debe tener su BD.**
4. **Patrón de almacenamiento de cada microservicio**: relacional o documental (ej. Mongo), CRUD o Event Sourcing; definirlo por servicio.
5. **Sagas**: modelo de coreografía u orquestación.
6. **BFF** como base del API, y cuenta como uno de los 4 servicios.
7. **Pub/Sub se usa solo en DISP-03; el resto usa Pulsar** (observado por el profesor).
8. **Comunicación entre módulos y entre microservicios**: tener claro cómo se comunican y **dónde está en el código**.
9. **Qué es síncrono y qué es asíncrono** en la comunicación.

## Calificación de la Entrega 4 en los ítems relacionados (transcrito)

| Ítem | Puntaje | Comentario del tutor en la sustentación |
|---|---|---|
| Se justifica correctamente los tipos de eventos a utilizar (integración o carga de estado). Ello incluye la definición de los esquemas y evolución de los mismos | **2,5 / 5** | "No esquemas. Si hay consumidores para trabajo Finalizado." |
| Definió, justificó e implementó alguna de las topologías para la administración de datos | **2,9 / 5** | "No conocemos las topologías de datos (centralizada), simplicidad en centralizada." |

Lectura del equipo: faltó (1) **definir esquemas reales** de los eventos y cómo evolucionan (se publicaba JSON
sin esquema), y (2) **conocer y justificar la topología de datos** frente a las alternativas (centralizada,
descentralizada, híbrida). Ambos se deben responder explícitamente en la Entrega 5.

## Notas del profesor para tener en cuenta en la Entrega 5 (transcrito)

- Topología de datos, qué y para qué
- Evolución y versionamiento de mensajes
- AsyncAPI: documentación de las APIs asíncronas
- Modelo de datos, qué y por qué
- Video con un ejemplo de cada escenario, los tipos de eventos que tenemos y por qué
