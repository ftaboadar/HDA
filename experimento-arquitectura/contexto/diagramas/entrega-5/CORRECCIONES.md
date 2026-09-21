# Correcciones pendientes en las imágenes de la Entrega 5

Las 4 vistas del equipo se copiaron aquí el 2026-09-21. Las decisiones que las corrigen están en
[`../../15-arquitectura-entrega-5.md`](../../15-arquitectura-entrega-5.md) §3. Las fuentes
legibles por agentes (`../../0{4,5,6,7}-vista-*.puml`) **ya tienen** todas estas correcciones. Lo
que falta es redibujar las imágenes que se presentan. Marca cada casilla al corregirla y vuelve a
exportar PNG + SVG con el **mismo nombre de archivo**.

| Archivo | Herramienta | Quién la corrige |
|---|---|---|
| `01-vista-contexto.{png,svg}` | draw.io | autor de la vista |
| `02-vista-informacion.{png,svg}` | draw.io | autor de la vista |
| `03-vista-modulos.{png,excalidraw.svg}` | Excalidraw (el `.svg` trae la escena; ábrelo en excalidraw.com → *Open*) | autor de la vista |
| `04-vista-cyc-funcional.drawio` → `.png`/`.svg` | draw.io | el `.drawio` **ya está corregido**; solo falta exportar |

## 01 — Vista de contexto

- [ ] Nada que corregir según las decisiones. Coincide con A1 (Gestión de Pagos interno, Pasarela
      externa). Opcional: marcar IA Asistida como "fuera de alcance E5".

## 02 — Vista de información

- [ ] **A8 (decidido):** mover `Cotización` fuera de "Agregación Trabajo" a
      un agregado de Marketplace (`SolicitudTrabajo` → `Cotizacion`). En Trabajo dejar solo una
      referencia por ID a la cotización aceptada.
- [ ] Agregar una "Agregación Solicitud" (Marketplace): `SolicitudTrabajo` «Raíz», `Diagnostico`
      «ObjetoValor», `Cotizacion` «Entidad». Hoy Marketplace no tiene agregado en la imagen.
- [ ] Sacar `Factura` (y `EstadoFactura`) de la caja "Agregación Siniestro" a una caja propia
      "Agregación Factura" (sigue en el contexto Siniestros, módulo Facturación).
- [ ] **A17:** sacar `Novedad` (y `TipoNovedad`) de la Agregación Trabajo a una **Agregación Novedad** propia, con referencia por ID al Trabajo.
- [ ] **A18:** `EstadoPago`: RETENIDO → LIBERADO / COMPENSADO / FALLIDO.
- [ ] **A14:** en la Agregación Proveedor, agregar `AgendaTecnico` «Raíz» → `Reserva` «Entidad» → `Franja` «ObjetoValor» (fecha + bloque), con referencias por ID a `Trabajo` y `Suscripción`.
- [ ] Revisar las líneas punteadas largas del borde ("deriva de", "genera", "tiene (por ID)"): que
      cada una termine claramente en la caja correcta (ver las referencias en `07-vista-informacion.puml`).

## 03 — Vista de módulos

- [ ] **A2:** "Broker de Eventos (Kafka)" → **"Broker de Eventos (Apache Pulsar) — tópicos por contexto"**.
- [ ] **A16:** Proveedores pasa a tener 4 módulos: agregar **Registro** (Proveedor, técnicos, servicios, zonas) y **Agenda** (AgendaTecnico, franjas) junto a Elegibilidad y Verificación.
- [ ] **A18:** en Pagos · Liberación y Compensación, mostrar **retener · liberar · compensar**; flecha "Agenda confirmada → retener pago".
- [ ] **A19:** Suscripciones: agregar el módulo **Ciclo de Suscripción**.
- [ ] **A7:** agregar **SP4** en **Proveedores · Verificación** (sensibilidad ante externos, DISP-03).
- [ ] **A7:** "MercadoPago (futuro)" → **"MercadoPago"** (ya implementado; es el cambio aplicado de MOD-02).
- [ ] **A7:** dentro de Pagos · Liberación y Compensación, mostrar **"ReglaRegional (Strategy): ReglaColombia · ReglaBrasil"**.
- [ ] **A7:** separar las etiquetas encimadas de GT: `async · EstadoTrabajoCambiado` (Motor → Novedades)
      y `async · NovedadRequiereSaaS` (Novedades → Integraciones Externas).
- [ ] **A4:** agregar flecha **Proveedores → Marketplace "Elegibles publicados (ACL)"** y
      **Marketplace → GT "Proveedor seleccionado (ACL)"**.
- [ ] **A5:** agregar flecha **Pagos → GT "Pago liberado / fallido / compensado (ACL)"** (hoy los
      "eventos de pago" solo llegan al broker).
- [ ] Agregar **Reputación → Proveedores "Reputación publicada (ACL)"** y **Scoring → Reputación
      "Scoring actualizado (ACL)"** (están en C&C).
- [ ] Aclarar la línea roja "publica/consume eventos": todos los servicios propios se conectan al broker.
- [ ] **A9:** "Elegibles publicados" llega también a **Siniestros · Orquestación de Partner** y a
      **Suscripciones**; ambos publican **"Proveedor seleccionado"** hacia GT (el partner aprueba / el cliente elige).
- [ ] **A11:** GT → Siniestros **"Novedad registrada (ACL)"** y Siniestros → GT **"Decisión del partner (ACL)"**.
- [ ] **A10:** GT → Reputación **"Novedad resuelta (no-show, garantía)"** y Marketplace/Siniestros/Suscripciones → Reputación **"Proveedor seleccionado"**.
- [ ] Suscripciones: quitar "(pendiente)"; tiene el módulo **Ciclo de Suscripción** (entra al alcance de E5).

## 04 — C&C funcional (`.drawio` ya corregido, falta exportar)

Cambios aplicados al `.drawio` el 2026-09-21 (el original sin corregir es `Vista Funcional C&C — Arquitectura TO-BE Completa (2).drawio` que compartió el equipo):

- [x] "Bus de eventos particionado" → "… (Apache Pulsar)"; "Bus de Eventos (particiones ↑)" → "Bus de Eventos Pulsar (particiones ↑)" (A2).
- [x] Panel DISP-01: "SaaS externo (pagos / certificadora)" → "(Notificaciones / Gestor Documental)" (A6).
- [x] "Novedades · camino alterno" → "Novedades (módulo de Gestión de Trabajos) · camino alterno" (A3).
- [x] La flecha "Cerrar trabajo → Motor de workflow" ahora va a "réplicas Gestión de trabajos". El
      Motor avisa `sub-trabajos completos` y el cierre lo aplica GT; antes había un ciclo.
- [x] Flecha nueva **Eventos Pagos → ACL de Gestión de Trabajos "Pago liberado / fallido / compensado"** (A5).
      Se agregó sin puntos de quiebre: en draw.io, acomódala para que no cruce otras cajas.
- [ ] **A9 (pendiente en el `.drawio`):** flecha "Elegibles publicados" también hacia el ACL de **Siniestros** y
      de **Suscripciones**; y desde *Aprobar paso (partner)* → "Proveedor seleccionado" → ACL de GT (*Asignar proveedor*).
- [ ] **A11 (pendiente en el `.drawio`):** el camino "si es siniestro · reglas del partner → Aprobar paso" deja de ser
      solo dibujo: agregar la vuelta **Eventos Siniestros → ACL de GT "Decisión del partner (aprobada/rechazada)"**.
- [ ] **A10 (pendiente en el `.drawio`):** "Novedad resuelta (no-show, garantía)" → ACL de **Reputación**.
- [ ] **A14 (pendiente en el `.drawio`):** entre "Proveedor seleccionado" y *Asignar proveedor* va Proveedores: "Reservar franja" → "Agenda confirmada" (a GT) / "Agenda rechazada" (al canal, re-seleccionar).
- [ ] **A18 (pendiente en el `.drawio`):** en Pagos (Marketplace), agregar el comando **Retener pago** disparado por "Agenda confirmada", antes de *Liberar pago*.
- [ ] Exportar `04-vista-cyc-funcional.png` y `.svg` desde draw.io (File → Export as).

## Context Map (`../../03-contextos-acotados-TO-BE.cml`)

- [ ] Validar con Context Mapper (`cm validate -i 03-contextos-acotados-TO-BE.cml`; no había CLI en la
      máquina donde se editó) y generar de nuevo `../03-contextos-acotados-TO-BE_ContextMap.{png,svg}` (la versión anterior, con Pagos externo, quedó en `../../historico/diagramas/`).
