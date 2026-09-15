# Despliegue integral en GCP — DISP-03 + Gestión de Trabajos + Reputación + Mocks de Pagos + Pulsar + Observabilidad

Rol: `experto-gcp`. Este documento mapea cada componente construido en `implementacion/` a Terraform
real contra el proyecto `hda-projectt` (`southamerica-east1`), en el mismo estilo que ya usa
`DISP-03/infra/` (prefijo `${entorno}` por stack, Service Account propia por servicio, IP pública +
red autorizada abierta en Cloud SQL "solo para PoC", `allUsers` como invoker público).

**Nada de esto se corrió contra GCP real desde esta sesión.** Se validó únicamente con
`terraform fmt` + `terraform init -backend=false` + `terraform validate` (sintaxis/tipos, sin tocar
la API de GCP) y con `docker build` local del Dockerfile nuevo — ver el resumen de verificación al
final. El `terraform apply` real lo corre el equipo, explícitamente, cuando decida encender esto (son
recursos facturables).

**Incidente durante esta sesión, reportado con honestidad:** en un punto se invocó por error
`terraform plan` sobre `pulsar-infra/gcp` (violando la restricción de "nada de plan/apply contra GCP
real" de esta tarea). El proceso se mató de inmediato al notarlo. Su único efecto fue quedarse
esperando el valor interactivo de `var.project_id` (nunca se pasó `-var`) y salir con error — no llegó
a autenticar ni a leer ningún recurso real de `hda-projectt` (confirmado revisando el log de salida
del proceso). Se limpiaron los artefactos locales que dejó (`terraform.tfstate` vacío,
`.terraform.tfstate.lock.info`, un archivo `.tf` de prueba). No se repitió.

## Stacks nuevos y su relación

```
infra-modules/cloud-run-service/   módulo reusable: 1 Cloud Run v2 + su SA + (opcional) Cloud SQL +
                                    (opcional) Direct VPC egress — usado por gestion-de-trabajos,
                                    reputacion y mocks-pagos (NO por observabilidad/grafana.tf, ver
                                    justificación allá)

pulsar-infra/gcp/                  1 VM de Compute Engine con el docker-compose.yml REAL de
                                    pulsar-infra/ (sin modificar) + un override propio de este stack
gestion-de-trabajos/infra/         Cloud SQL + Cloud Run (API) — vía el módulo, con Direct VPC egress
reputacion/infra/                  Cloud SQL + Cloud Run (SOLO la API — ver limitación abajo)
mocks-pagos/infra/                 2x Cloud Run (mock-stripe, mock-mercadopago) — vía el módulo, sin Cloud SQL
observabilidad/                    Grafana en Cloud Run + APIs de Monitoring/Trace + dashboard.json
DISP-03/infra/                     YA EXISTÍA — solo se le agregó var.pulsar_service_url (plumbing,
                                    sin cambiar su comportamiento actual con Pub/Sub)
```

## Orden de apply

Cada stack es su propio state local (`terraform init` sin backend remoto configurado — igual que
`DISP-03/infra/` hoy). Ejecutar desde el directorio de cada stack.

### 1. `pulsar-infra/gcp` — primero, para obtener la IP de Pulsar

```bash
cd experimento-arquitectura/implementacion/pulsar-infra/gcp
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
terraform output ip_privada   # <- usar este valor en el paso 2, NO ip_publica (ver justificación abajo)
terraform output ip_publica   # solo para debug manual (ssh -tunnel-through-iap, curl :8080)
```

Esperar 2-3 minutos tras el apply antes de dar por sano el cluster (Zookeeper -> pulsar-init ->
bookie -> broker, igual que en local, ver `../README.md`) — verificar con:

```bash
gcloud compute ssh <entorno>-vm --zone <zona-del-output-vm_zone> --tunnel-through-iap \
  --command "curl -sf http://localhost:8080/admin/v2/brokers/health && echo OK"
```

### 2. Los 3 microservicios propios + mocks + DISP-03 (orden entre ellos no importa, salvo que
   `gestion-de-trabajos` necesita las URLs de `mocks-pagos` para su ACL de Pagos)

```bash
cd ../../mocks-pagos/infra
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
terraform output mock_stripe_url
terraform output mock_mercadopago_url

cd ../../gestion-de-trabajos/infra
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1 \
  -var "pulsar_service_url=pulsar://<ip_privada_del_paso_1>:6650" \
  -var "stripe_mock_url=<mock_stripe_url_de_arriba>" \
  -var "mercadopago_mock_url=<mock_mercadopago_url_de_arriba>"
# Nota: gcloud builds submit / docker push de la imagen de este servicio queda
# fuera de este Terraform (mismo criterio que DISP-03: infra/ solo aprovisiona,
# la imagen se construye/sube aparte, ver README.md de DISP-03 sección
# "Correr en GCP" — aquí no hay CLI equivalente a hda-gcp todavía, sería:
#   gcloud builds submit --tag <output.imagen_app> experimento-arquitectura/implementacion/gestion-de-trabajos
# y volver a aplicar para que Cloud Run tome la imagen nueva).

cd ../../reputacion/infra
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
# (ver limitación abajo: esto SOLO despliega la API, no el consumidor de Pulsar)

cd ../../DISP-03/infra
terraform init   # ya existía, re-inicializar solo si cambió el lock de providers
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
# pulsar_service_url por defecto es "" — no hace falta pasarla salvo que
# el equipo quiera dejarla plumbeada con un valor real por adelantado.
```

### 3. `observabilidad` — al final, para que el dashboard de ejemplo tenga servicios reales que graficar

```bash
cd ../../observabilidad
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
terraform output grafana_url
# usuario: admin — contraseña: en Secret Manager, secreto = terraform output grafana_admin_password_secret
gcloud secrets versions access latest --secret "$(terraform output -raw grafana_admin_password_secret)"
```

## Comandos de `terraform destroy` (apagar todo, en orden inverso)

```bash
cd experimento-arquitectura/implementacion/observabilidad            && terraform destroy -var project_id=hda-projectt
cd ../DISP-03/infra                                                   && terraform destroy -var project_id=hda-projectt
cd ../../reputacion/infra                                              && terraform destroy -var project_id=hda-projectt
cd ../../gestion-de-trabajos/infra                                     && terraform destroy -var project_id=hda-projectt
cd ../../mocks-pagos/infra                                             && terraform destroy -var project_id=hda-projectt
cd ../../pulsar-infra/gcp                                              && terraform destroy -var project_id=hda-projectt
```

(`gestion-de-trabajos` antes que `pulsar-infra/gcp` porque depende de su IP; el resto no tiene
dependencias cruzadas de infraestructura entre sí, solo de configuración por variable.)

## Decisiones de diseño no 100% especificadas en el encargo original

### 1. Direct VPC egress para llegar a Pulsar — y por qué "el rango de IPs de Cloud Run" no es una cosa real

El encargo pedía restringir el firewall de la VM de Pulsar "a los rangos de IP de Cloud Run/el resto
de la VPC del proyecto (no 0.0.0.0/0 si es evitable)". **Hallazgo:** Cloud Run, en su configuración de
red por defecto, origina su tráfico saliente desde IPs administradas por Google, NO desde ningún rango
de la VPC del proyecto — no existe un "rango de IPs de Cloud Run" filtrable en un firewall de VPC. Una
regla de firewall restringida al CIDR de la subred `default` (que sí implementé, ver
`pulsar-infra/gcp/network.tf`) bloquearía a Cloud Run exactamente igual que a cualquier otro tráfico de
internet, salvo que el propio servicio de Cloud Run tenga **Direct VPC egress** habilitado (GA en
Cloud Run v2, sin costo de conector adicional) apuntando a esa misma subred.

Por eso:
- El módulo `infra-modules/cloud-run-service` expone `vpc_network`/`vpc_subnetwork`/`vpc_egress`
  (default `PRIVATE_RANGES_ONLY` — solo el tráfico a destinos RFC1918 se enruta por la VPC; las
  llamadas de `gestion-de-trabajos` a los mocks de pagos, que son Cloud Run público, NO pagan ese
  camino).
- `gestion-de-trabajos/infra/service.tf` habilita esto (es el único de los 3 microservicios que
  necesita hablar con Pulsar hoy).
- `pulsar_service_url` debe construirse con la IP **interna** de la VM (`output ip_privada`), no la
  externa — la IP externa (`output ip_publica`) queda solo para administración/debug manual desde
  fuera de la VPC (SSH vía IAP, `curl` al admin REST).

### 2. `advertisedListeners=127.0.0.1` en `pulsar-infra/docker-compose.yml` rompe el acceso externo — parche vía override, sin tocar el archivo original

Hallazgo más serio, y el que más directamente amenaza la validez de "correr el docker-compose.yml tal
cual" en una VM: ese archivo fija
`advertisedListeners=external:pulsar://127.0.0.1:6650` en el servicio `broker`. Ese valor es correcto
SOLO para un cliente que vive en el mismo host Docker (ahí `127.0.0.1` apunta al propio host). Un
cliente Pulsar real hace primero un *lookup* contra el broker, que le devuelve la URL de este
"external listener" para la conexión de datos real — si sigue siendo `127.0.0.1`, cualquier cliente
externo (Cloud Run, o cualquier máquina fuera de esta VM) intentaría conectarse a **su propio
loopback**, no a la VM, y la publicación/consumo de mensajes fallaría después de un handshake TCP
inicial aparentemente exitoso. Esto no se manifiesta en local porque ahí el cliente y el broker sí
comparten host.

Como la tarea pide explícitamente NO modificar `pulsar-infra/docker-compose.yml`, la solución es un
`docker-compose.override.yml` **nuevo**, que vive en `pulsar-infra/gcp/templates/` (fuera de
`pulsar-infra/`) y se aplica encima con `docker compose -f docker-compose.yml -f
docker-compose.override.yml up -d` (ver `pulsar-infra/gcp/templates/startup.sh.tpl`). El placeholder
`__ADVERTISED_IP__` de ese override se sustituye en tiempo de arranque de la VM (vía el servidor de
metadata de GCP, `curl -H "Metadata-Flavor: Google" .../network-interfaces/0/ip`), no en tiempo de
Terraform — la instancia no puede referenciar su propia IP dentro de su propio
`metadata_startup_script` (dependencia circular).

**No validado contra un cluster real** (nada de esto se aplicó) — es la corrección técnicamente
correcta según cómo funciona el protocolo de Pulsar, pero la primera persona que haga
`terraform apply` de este stack debe confirmarlo con un productor/consumidor real desde fuera de la
VM, igual que el propio `pulsar-infra/README.md` ya pide para el compose original.

### 3. El consumidor de Pulsar de Reputación NO se despliega en este PR

`reputacion/app/infrastructure/messaging/consumidor_pulsar.py` es un loop pull bloqueante sin ningún
servidor HTTP. Cloud Run v2 (services) exige que el contenedor escuche en su puerto asignado y pase un
probe de arranque — este consumidor nunca lo haría, así que desplegarlo con el módulo genérico
fallaría en el primer arranque. `reputacion/infra/` solo despliega la API (que si expone HTTP y no
necesita Pulsar). Ver el comentario extenso en `reputacion/infra/service.tf` para las dos rutas de
solución (agregar un health-check HTTP trivial al propio consumidor + Cloud Run con
`cpu_idle = false`, o desplegarlo en una VM de Compute Engine igual que Pulsar) — ninguna implementada
aquí porque ambas exceden el alcance de "Cloud SQL + Cloud Run vía el módulo" pedido para este
servicio y una de ellas requiere tocar código de aplicación.

### 4. Google Managed Service for Prometheus: solo se habilitó la API, no se desplegó un colector

GMP no tiene una API propia distinta de `monitoring.googleapis.com` — su componente adicional es un
colector que hace scraping de endpoints Prometheus nativos. Ninguno de los 3 microservicios nuevos (ni
DISP-03) expone un endpoint `/metrics` de Prometheus hoy; Cloud Run ya envía sus métricas nativas
(`run.googleapis.com/request_count`, `.../request_latencies`, etc.) a Cloud Monitoring sin ningún
agente. Desplegar un colector GMP ahora no tendría nada adicional que recolectar — se documenta como
ruta de mejora futura si algún microservicio agrega instrumentación Prometheus propia.

### 5. Grafana no usa el módulo `cloud-run-service`

Necesita un volumen GCS FUSE (datasource + dashboard provisionados) y variables de entorno muy
específicas de Grafana (`GF_SECURITY_ADMIN_*`, `GF_PATHS_PROVISIONING`) que no valía la pena
generalizar en un módulo pensado para los 3 microservicios propios del proyecto. `observabilidad/grafana.tf`
declara sus propios recursos siguiendo el mismo estilo (SA propia, Secret Manager para la contraseña
de admin, `allUsers` como invoker de Cloud Run — la autenticación real la da el login de Grafana).

**Limitación de persistencia, documentada tal como pide la tarea:** Grafana corre sin Cloud SQL ni
disco propio — su base SQLite interna (usuarios más allá de `admin`, alertas propias, dashboards
creados a mano desde la UI) se pierde en cada cold start / nueva revisión. El datasource de Cloud
Monitoring y el dashboard de ejemplo (`observabilidad/dashboard.json`) SÍ sobreviven, porque se
recargan desde el bucket de GCS montado como volumen de solo lectura en cada arranque.

`observabilidad/dashboard.json` (3 paneles: p95, throughput, tasa de error 5xx, con un textbox para
elegir el `service_name`) **no se importó ni se renderizó contra una instancia real de Grafana ni
contra métricas reales de Cloud Run** — su estructura sigue el schema de Grafana 11.x + el datasource
nativo `stackdriver` (Google Cloud Monitoring), pero debe validarse manualmente la primera vez que se
importe contra un proyecto con servicios reales corriendo.

### 6. `mocks-pagos` despliega DOS servicios Cloud Run desde la misma imagen

Igual que `DISP-03/infra/mocks.tf` hace con policía/RUES/certificadora: un solo `Dockerfile`, dos
módulos FastAPI distintos arrancados por `command`/`args` (`app.stripe_mock:app` vs
`app.mercadopago_mock:app`), puerto 8000 (no el default 8080 del módulo — así lo expone
`mocks-pagos/Dockerfile` y así lo arranca su `docker-compose.yml` local, se respetó ese contrato en
vez de inventar un puerto distinto para GCP).

## Diferencias RabbitMQ/Pub/Sub/Pulsar — amenazas a la validez

Ya documentadas en detalle en `DISP-03/README.md`, sección "Diferencias local (RabbitMQ) vs. GCP
(Pub/Sub) vs. Apache Pulsar" — aplica igual aquí para `gestion-de-trabajos`/`reputacion`, que usan
Pulsar como único transporte de integración (no hay variante Pub/Sub de esos dos servicios). Se agrega
un matiz nuevo, específico de correr Pulsar en una VM propia en vez de local: **el hallazgo #2 de este
documento (`advertisedListeners`) es una amenaza a la validez adicional, específica del despliegue en
GCP, que no existe ni en el docker-compose local ni en ningún experimento ya corrido** — cualquier
corrida de `run-experiment` o prueba de carga contra este entorno de GCP debe confirmar primero que el
override realmente resolvió el problema, no asumirlo.

## Resumen de verificación

| Stack | `terraform fmt` | `terraform init -backend=false` | `terraform validate` |
|---|---|---|---|
| `infra-modules/cloud-run-service` | OK | OK | OK |
| `gestion-de-trabajos/infra` | OK | OK | OK |
| `reputacion/infra` | OK | OK | OK |
| `mocks-pagos/infra` | OK | OK | OK |
| `pulsar-infra/gcp` | OK | OK | OK |
| `observabilidad` | OK | OK | OK |
| `DISP-03/infra` (con `pulsar_service_url` agregado) | OK | ya inicializado previamente | OK |

`docker build` de `gestion-de-trabajos/Dockerfile` (nuevo): **exitoso**, imagen
`hda-gestion-de-trabajos:test` construida localmente sin correrla (no se hizo `docker run`, no se probó
contra una base de datos real — eso es responsabilidad de quien corra las pruebas de integración del
servicio, no de este stack de infraestructura).

**No verificado** (fuera de lo que esta tarea permitía tocar): ningún `terraform plan`/`apply` contra
`hda-projectt` real, ningún build/push de imagen a Artifact Registry, ningún arranque real de la VM de
Pulsar con el override, ninguna consulta real de Grafana contra Cloud Monitoring. Todo lo anterior
queda pendiente para cuando el equipo decida encender esto de verdad.
