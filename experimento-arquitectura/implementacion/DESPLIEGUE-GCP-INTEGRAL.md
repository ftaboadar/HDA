# Despliegue integral en GCP — DISP-03 + Gestión de Trabajos + Reputación + Mocks de Pagos + Pulsar + Observabilidad

Rol: `experto-gcp`. Este documento mapea cada componente construido en `implementacion/` a Terraform
real contra el proyecto `hda-projectt` (`southamerica-east1`), en el mismo estilo que ya usa
`proveedores/infra/` (prefijo `${entorno}` por stack, Service Account propia por servicio, IP pública +
red autorizada abierta en Cloud SQL "solo para PoC", `allUsers` como invoker público).

**ACTUALIZACIÓN: esto SÍ se aplicó contra GCP real** (`hda-projectt`), por pedido explícito del
usuario, en una sesión posterior a cuando se escribió el resto de este documento (el texto original
de abajo describe el estado ANTES del apply — se deja tal cual como referencia del diseño, y esta
sección nueva documenta lo que pasó al encenderlo de verdad). Ver "Estado real tras el despliegue"
más abajo para los bugs encontrados (varios que ni `validate` ni `plan` podían atrapar) y el estado
real de cada componente.

**Nada de esto se corrió contra GCP real desde ESTA REDACCIÓN INICIAL del documento.** Se validó
únicamente con `terraform fmt` + `terraform init -backend=false` + `terraform validate`
(sintaxis/tipos, sin tocar la API de GCP) y con `docker build` local del Dockerfile nuevo — ver el
resumen de verificación al final. El `terraform apply` real lo corre el equipo, explícitamente,
cuando decida encender esto (son recursos facturables).

**Incidente durante esta sesión, reportado con honestidad:** en un punto se invocó por error
`terraform plan` sobre `pulsar-infra/gcp` (violando la restricción de "nada de plan/apply contra GCP
real" de esta tarea). El proceso se mató de inmediato al notarlo. Su único efecto fue quedarse
esperando el valor interactivo de `var.project_id` (nunca se pasó `-var`) y salir con error — no llegó
a autenticar ni a leer ningún recurso real de `hda-projectt` (confirmado revisando el log de salida
del proceso). Se limpiaron los artefactos locales que dejó (`terraform.tfstate` vacío,
`.terraform.tfstate.lock.info`, un archivo `.tf` de prueba). No se repitió.

## Receta vigente: montar todo desde cero en un proyecto nuevo (desde `main`)

> **Forma recomendada (desde 2026-09-21): los scripts de [`scripts/`](scripts/).** Hacen exactamente esta
> receta, con el state de Terraform en un bucket GCS del proyecto (`gs://<PROYECTO>-tfstate`), así que
> **cualquiera con acceso al proyecto puede desplegar o destruir**, no solo quien desplegó:
>
> ```bash
> cd experimento-arquitectura/implementacion/scripts
> PROJECT=<tu-proyecto> ./desplegar-todo.sh          # imágenes → Pulsar (+namespaces) → mocks → servicios → Grafana
> PROJECT=<tu-proyecto> ./destruir-todo.sh           # orden inverso + bucket de Cloud Build + verificación
> PROJECT=<tu-proyecto> ./verificar-nada-facturando.sh
> ```
>
> Cambiar de proyecto (por ejemplo, si se acaban los créditos) = cambiar `PROJECT`. Antes de perder el
> proyecto viejo: guardar la evidencia en el repo y correr `destruir-todo.sh`.
> **Estado de los scripts:** `verificar-nada-facturando.sh` probado contra `hogaralpes`; `desplegar-todo.sh`
> y `destruir-todo.sh` validados (bash -n, shellcheck, `terraform validate` de los 10 stacks) pero
> **todavía no corridos de punta a punta contra GCP**. La primera persona que los corra actualiza
> `ESTADO-IMPLEMENTACION.md`.
>
> Si prefieres hacerlo a mano, sigue abajo. Desde que los stacks usan backend GCS, cada `terraform init`
> necesita `-backend-config="bucket=<PROYECTO>-tfstate" -backend-config="prefix=<stack>"`, y el bucket se
> crea antes: `gcloud storage buckets create gs://<PROYECTO>-tfstate --location <REGION> --uniform-bucket-level-access`.
> Los namespaces de Pulsar ya los crea la VM al arrancar.

Esta es la receta que se usó para levantar `hogaralpes` y la que debe seguir cualquier compañero. Lo que dice el resto del
documento es el diseño y la historia (mantiene `hda-projectt` y el estado de 2026-09-14). **Hacer merge del PR a `main` da el código
y el Terraform; no da la infraestructura**: cada persona levanta la suya en su propio proyecto.

Qué NO viaja con el PR (y por qué):
- **El estado de Terraform** (`terraform.tfstate`, ignorado por git): cada stack es local; tu compañero parte de cero y no toca lo tuyo.
- **Las imágenes de contenedor**: Terraform solo crea los servicios; las imágenes se construyen con Cloud Build.
- **Las URLs**: cada proyecto tiene URLs `*.run.app` distintas; hay que pasarlas entre stacks y actualizar `postman/HdA-GCP.postman_environment.json`.
- **La API de Cloud Build** (no está en Terraform) y la cuota: un proyecto nuevo suele tener **20 vCPU por región**; por eso `gestion-de-trabajos` (2 vCPU por instancia) se aplica con `max_instance_count=9`.

Prerrequisitos: proyecto con facturación, `gcloud auth login`, `gcloud auth application-default login` y
`gcloud auth application-default set-quota-project <PROYECTO>`, Terraform >= 1.5.

```bash
export PROJECT=<tu-proyecto> REGION=southamerica-east1
IMPL=experimento-arquitectura/implementacion        # ejecutar desde la raíz del repo
R=$REGION-docker.pkg.dev/$PROJECT
gcloud services enable cloudbuild.googleapis.com --project $PROJECT

# 0) Por cada servicio con imagen: crear SOLO su repositorio (Terraform habilita las APIs que necesita) y publicar la imagen.
#    Hay que hacerlo antes del apply completo: Cloud Run falla al crearse si la imagen no existe.
bootstrap() {  # <stack> <repo-artifact-registry> <imagen> <carpeta-con-Dockerfile>
  (cd $IMPL/$1 && terraform init -input=false -reconfigure -backend-config="bucket=${PROJECT}-tfstate" -backend-config="prefix=$1" \
     && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION \
        -target=google_artifact_registry_repository.hda)
  gcloud builds submit $IMPL/$4 --tag $R/$2/$3:latest --project $PROJECT --quiet
}
bootstrap mocks-pagos/infra          mocks-pagos-poc-hda        hda-mocks-pagos          mocks-pagos
bootstrap mocks-crm/infra            mocks-crm-poc-hda          hda-mocks-crm            mocks-crm
bootstrap pagos/infra                pagos-poc-hda              hda-pagos                pagos
bootstrap gestion-de-trabajos/infra  gestion-trabajos-poc-hda   hda-gestion-de-trabajos  gestion-de-trabajos
bootstrap reputacion/infra           reputacion-poc-hda         hda-reputacion           reputacion
bootstrap proveedores/infra          disp03-poc-hda             hda-disp03               proveedores   # el prefijo disp03-poc es el nombre histórico de los recursos

# 1) Pulsar (VM). Esperar 2-3 min a que el broker levante antes de seguir.
(cd $IMPL/pulsar-infra/gcp && terraform init -input=false -reconfigure -backend-config="bucket=${PROJECT}-tfstate" -backend-config="prefix=pulsar-infra/gcp" \
   && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)
PULSAR_IP=$(cd $IMPL/pulsar-infra/gcp && terraform output -raw ip_privada)     # IP PRIVADA, no la pública

# 2) Mocks de pagos y del CRM
(cd $IMPL/mocks-pagos/infra && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)
(cd $IMPL/mocks-crm/infra   && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)
STRIPE=$(cd $IMPL/mocks-pagos/infra && terraform output -raw mock_stripe_url)
MP=$(cd $IMPL/mocks-pagos/infra && terraform output -raw mock_mercadopago_url)
CRM=$(cd $IMPL/mocks-crm/infra && terraform output -raw mock_crm_url)

# 3) Servicios de negocio (usan las URLs anteriores; pagos y gestión no dependen entre sí)
(cd $IMPL/pagos/infra && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION \
   -var stripe_mock_url=$STRIPE -var mercadopago_mock_url=$MP)
(cd $IMPL/gestion-de-trabajos/infra && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION \
   -var max_instance_count=9 -var pulsar_service_url=pulsar://$PULSAR_IP:6650 \
   -var stripe_mock_url=$STRIPE -var mercadopago_mock_url=$MP -var crm_mock_url=$CRM)
(cd $IMPL/reputacion/infra  && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)
(cd $IMPL/proveedores/infra && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)

# 4) Grafana al final (el dashboard necesita servicios reales que graficar)
(cd $IMPL/observabilidad && terraform init -input=false -reconfigure -backend-config="bucket=${PROJECT}-tfstate" -backend-config="prefix=observabilidad" \
   && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION)
```

### Entrega 5: lo que cambia en esta receta

La receta de arriba despliega lo que existe hasta la Entrega 4. La Entrega 5 agrega **4 stacks nuevos** y un
**`worker` por servicio que consume Pulsar**. Todos siguen el patrón de
[`CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md`](CONVENCIONES-SERVICIO-Y-DESPLIEGUE.md) §5-§6. **Actualiza este bloque
cuando cada stack exista de verdad**: hasta entonces es el orden acordado, no una receta probada.

```bash
# 0) bootstrap de imágenes: agregar los 4 servicios nuevos
bootstrap marketplace/infra    marketplace-poc-hda    hda-marketplace    marketplace
bootstrap siniestros/infra     siniestros-poc-hda     hda-siniestros     siniestros
bootstrap suscripciones/infra  suscripciones-poc-hda  hda-suscripciones  suscripciones
bootstrap scoring/infra        scoring-poc-hda        hda-scoring        scoring

# 1b) después de Pulsar y ANTES de cualquier servicio: tenant + 8 namespaces (CONVENCIONES §4)

# 3) todos los servicios de negocio reciben -var pulsar_service_url=pulsar://$PULSAR_IP:6650
#    (antes solo gestion-de-trabajos); cada stack que consume despliega api + worker
for s in marketplace siniestros suscripciones scoring reputacion pagos proveedores; do
  (cd $IMPL/$s/infra && terraform apply -auto-approve -var project_id=$PROJECT -var region=$REGION \
     -var pulsar_service_url=pulsar://$PULSAR_IP:6650)      # + las -var propias de cada stack (mocks de pagos, etc.)
done
```

- **Cuota de vCPU:** con 8 servicios × (api + worker) conviene `cpu = "1"` y `max_instance_count` bajo (1-3)
  en los servicios nuevos y en todos los workers. Suma antes de aplicar (CONVENCIONES §6, regla 4).
- **Destroy:** los 4 stacks nuevos van **antes** de `pulsar-infra/gcp` en el bucle de apagado (dependen de su IP).
- **Postman:** agregar `marketplace_url`, `siniestros_url`, `suscripciones_url`, `scoring_url` a
  `postman/HdA-GCP.postman_environment.json`.

Después del despliegue:
1. URLs de todo: `gcloud run services list --region $REGION --project $PROJECT --format="value(metadata.name,status.url)"`; pégalas en `postman/HdA-GCP.postman_environment.json`.
2. Grafana: `terraform output grafana_url` (en `observabilidad/`), usuario `admin`, contraseña en Secret Manager (secreto `observabilidad-poc-grafana-admin-password`).
3. Correr los escenarios: ver `GUIA-DEMO-ESCENARIOS.md`.

Problemas conocidos al montar (ver `GUIA-DEMO-ESCENARIOS.md`, sección "Problemas frecuentes"): `403` tras recrear un servicio (repetir `terraform apply` en ese stack), imagen vieja
(`terraform apply -replace=<servicio>`) y cuota de CPU.

**Apagar todo (orden inverso; el `destroy` borra también las bases de Cloud SQL y sus datos):**

```bash
# Entrega 5: anteponer marketplace/infra siniestros/infra suscripciones/infra scoring/infra cuando existan
for s in observabilidad proveedores/infra reputacion/infra pagos/infra gestion-de-trabajos/infra mocks-crm/infra mocks-pagos/infra pulsar-infra/gcp; do
  (cd $IMPL/$s && terraform destroy -auto-approve -var project_id=$PROJECT -var region=$REGION)
done

# Después de los 8 destroy: el bucket que crea Cloud Build solo (NO está en Terraform) y donde sube el código de cada `gcloud builds submit`
gcloud storage rm -r gs://${PROJECT}_cloudbuild --quiet
```

Notas del destroy:
- `gestion-de-trabajos` va antes que `pulsar-infra/gcp` porque depende de su IP. Para `destroy` basta `project_id` y `region`; `gestion-de-trabajos` puede pedir además `-var max_instance_count=9` (su validación de cuota corre también al destruir).
- Cada `terraform destroy` usa el estado local de ese stack: solo puede apagar lo que esa misma carpeta desplegó.
- **Usuario de Cloud SQL:** Postgres no deja borrar el usuario `hda` mientras posee objetos y el destroy fallaba con
  `role "hda" cannot be dropped because some objects depend on it`. Los 4 stacks con Cloud SQL ya llevan `deletion_policy = "ABANDON"` en `google_sql_user.hda`,
  así que el usuario se omite y desaparece junto con la instancia. Si aun así ves ese error (estado creado con una versión anterior),
  `terraform state rm google_sql_user.hda` y repite el `destroy`.
- **Reutilizar nombres:** GCP no permite reutilizar el nombre de una instancia de Cloud SQL durante hasta una semana tras borrarla. En un proyecto
  nuevo no importa; si vuelves a montar en el MISMO proyecto justo después de un destroy, cambia el prefijo con `-var entorno=<otro>` en cada stack
  (cambia también los nombres y las URLs) o espera.
- Comprobación de que no queda nada facturando:
  `gcloud run services list`, `gcloud sql instances list`, `gcloud compute instances list`, `gcloud pubsub topics list` y
  `gcloud artifacts repositories list` (todos con `--project $PROJECT`) deben salir vacíos.

**Lo que esta receta garantiza y lo que no:** el orden, las variables y las correcciones salen de la sesión real en `hogaralpes`
(despliegue completo y destroy completo, con los 8 stacks en 0 recursos). No se ha repetido en un proyecto limpio desde este documento:
si un paso falla en la primera corrida de otra persona, corrígelo aquí.

---

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
proveedores/infra/                     YA EXISTÍA — solo se le agregó var.pulsar_service_url (plumbing,
                                    sin cambiar su comportamiento actual con Pub/Sub)
```

## Orden de apply

Cada stack es su propio state local (`terraform init` sin backend remoto configurado — igual que
`proveedores/infra/` hoy). Ejecutar desde el directorio de cada stack.

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

### 2. Los 3 microservicios propios + mocks + Proveedores (`proveedores/`, recursos `disp03-poc-*`) (orden entre ellos no importa, salvo que
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
# fuera de este Terraform (mismo criterio que Proveedores: infra/ solo aprovisiona,
# la imagen se construye/sube aparte, ver README.md de DISP-03 sección
# "Correr en GCP" — aquí no hay CLI equivalente a hda-gcp todavía, sería:
#   gcloud builds submit --tag <output.imagen_app> experimento-arquitectura/implementacion/gestion-de-trabajos
# y volver a aplicar para que Cloud Run tome la imagen nueva).

cd ../../reputacion/infra
terraform init
terraform apply -var project_id=hda-projectt -var region=southamerica-east1
# (ver limitación abajo: esto SOLO despliega la API, no el consumidor de Pulsar)

cd ../../proveedores/infra
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
cd ../proveedores/infra                                                   && terraform destroy -var project_id=hda-projectt
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

Igual que `proveedores/infra/mocks.tf` hace con policía/RUES/certificadora: un solo `Dockerfile`, dos
módulos FastAPI distintos arrancados por `command`/`args` (`app.stripe_mock:app` vs
`app.mercadopago_mock:app`), puerto 8000 (no el default 8080 del módulo — así lo expone
`mocks-pagos/Dockerfile` y así lo arranca su `docker-compose.yml` local, se respetó ese contrato en
vez de inventar un puerto distinto para GCP).

## Diferencias RabbitMQ/Pub/Sub/Pulsar — amenazas a la validez

Ya documentadas en detalle en `proveedores/README.md`, sección "Diferencias local (RabbitMQ) vs. GCP
(Pub/Sub) vs. Apache Pulsar" — aplica igual aquí para `gestion-de-trabajos`/`reputacion`, que usan
Pulsar como único transporte de integración (no hay variante Pub/Sub de esos dos servicios). Se agrega
un matiz nuevo, específico de correr Pulsar en una VM propia en vez de local: **el hallazgo #2 de este
documento (`advertisedListeners`) es una amenaza a la validez adicional, específica del despliegue en
GCP, que no existe ni en el docker-compose local ni en ningún experimento ya corrido** — cualquier
corrida de `run-experiment` o prueba de carga contra este entorno de GCP debe confirmar primero que el
override realmente resolvió el problema, no asumirlo.

## Estado real tras el despliegue en GCP (2026-09-14)

Los 6 stacks se aplicaron de verdad contra `hda-projectt` (106 recursos). Todos los servicios pasan
`/salud`. Se encontraron y corrigieron, en el camino, bugs reales que ni `terraform validate` ni
`terraform plan` podían atrapar (solo aparecen ejecutando de verdad):

1. **Cloud Run v2 rechaza `self_link` como `vpc_subnetwork`** (`gestion-de-trabajos/infra/service.tf`)
   — pedía el formato `projects/*/regions/*/subnetworks/*`, no la URL completa. Corregido a
   `data.google_compute_subnetwork.default.id`.
2. **`docker-compose-plugin` no existe en los repos de Debian por defecto**
   (`pulsar-infra/gcp/templates/startup.sh.tpl`) — `apt-get install` fallaba y, por
   `set -euxo pipefail`, abortaba el script completo antes de instalar Docker siquiera. Corregido
   usando `get.docker.com`.
3. **Los volúmenes nombrados de Docker se crean `root:root`** (`pulsar-infra/docker-compose.yml`) —
   el usuario `pulsar` (uid 10000) del contenedor no podía escribir en `zk-data`/`bk-data`.
   **Reproducido idéntico en local** (no es un problema de la VM) — este archivo nunca se había
   corrido de verdad antes de hoy. Corregido con `user: "0:0"` en `zookeeper` y `bookie`.
4. **Falta crear el tenant/namespace de Pulsar** — el cluster solo inicializa metadata
   (`pulsar initialize-cluster-metadata`), nunca crea el tenant `hda` ni sus namespaces. Sin esto,
   publicar en `persistent://hda/gestion-trabajos/trabajos.finalizado` falla con `TopicNotFound`. Se
   creó manualmente (`pulsar-admin tenants create hda` + `namespaces create hda/gestion-trabajos` y
   `hda/proveedores`) — **no está automatizado todavía**, es un paso manual pendiente de mover a
   Terraform (`pulsar-admin` no tiene provider oficial; alternativa: un
   `null_resource`+`local-exec` que lo corra vía el REST admin del broker, o un job de Kubernetes/VM
   que lo haga en el primer arranque).
5. **`gestion-de-trabajos/app/infrastructure/messaging/publicador_pulsar.py` serializaba con
   `pulsar.schema.AvroSchema`**, pero (a) `pulsar-client==3.5.0` sin el extra `[avro]` no trae
   `fastavro` y (b) el consumidor real de ese tópico
   (`reputacion/app/infrastructure/messaging/consumidor_pulsar.py`) espera JSON plano
   (`json.loads(mensaje.data())`) — dos servicios de equipos distintos, nunca probados juntos contra
   un broker real hasta hoy. Se unificó al mismo contrato JSON que ya usa
   `proveedores/app/common/publicador.py`.
6. **Bug de concurrencia real bajo carga (encontrado corriendo k6, no antes)**: todas las llamadas a
   los repositorios de `gestion-de-trabajos` (SQLAlchemy, síncronas) se invocaban directo dentro de
   handlers `async def` — bloqueaban el event loop del worker de Uvicorn en cada escritura/lectura a
   Cloud SQL. Bajo la carga de ESC-01 esto serializaba efectivamente cada instancia (sin importar
   `containerConcurrency=80`), causando p95 de 14.2s y 20% de requests fallidas. Se envolvió cada
   llamada en `asyncio.to_thread` (mismo patrón ya auditado en
   `proveedores/app/application/commands/registrar_intento.py`) en los 5 archivos que tocaban un
   repositorio. **Mejoró sustancialmente pero no resolvió el problema del todo**: una segunda corrida
   de ESC-01 post-fix bajó a p95 9.7s / 11.9% de fallo — sigue sin cumplir el umbral. La causa raíz
   residual (pool de conexiones a Cloud SQL, `max_instance_count`/tier insuficientes, u otra) no se
   investigó más a fondo por tiempo — ver `k6/README.md` sección ESC-01, "Qué falta".
7. **Imágenes construidas en Apple Silicon (arm64) sin `--platform linux/amd64`** fallan en Cloud Run
   ("Container manifest type ... must support amd64/linux") — afectó a los 3 servicios nuevos hasta
   que se reconstruyeron con esa flag explícita.

**No validado**: ESC-03 (la corrida limpia post-fix de concurrencia se interrumpió antes de terminar,
16 min de duración); el consumidor de Pulsar de Reputación sigue sin desplegarse (ver limitación ya
documentada arriba), así que nadie confirmó todavía que Reputación reciba y procese el evento real
publicado por Gestión de Trabajos, solo que el mensaje llega al tópico (confirmado vía
`pulsar-admin topics stats`, `msgInCounter: 1`).

## Resumen de verificación

| Stack | `terraform fmt` | `terraform init -backend=false` | `terraform validate` |
|---|---|---|---|
| `infra-modules/cloud-run-service` | OK | OK | OK |
| `gestion-de-trabajos/infra` | OK | OK | OK |
| `reputacion/infra` | OK | OK | OK |
| `mocks-pagos/infra` | OK | OK | OK |
| `pulsar-infra/gcp` | OK | OK | OK |
| `observabilidad` | OK | OK | OK |
| `proveedores/infra` (con `pulsar_service_url` agregado) | OK | ya inicializado previamente | OK |

`docker build` de `gestion-de-trabajos/Dockerfile` (nuevo): **exitoso**, imagen
`hda-gestion-de-trabajos:test` construida localmente sin correrla (no se hizo `docker run`, no se probó
contra una base de datos real — eso es responsabilidad de quien corra las pruebas de integración del
servicio, no de este stack de infraestructura).

**No verificado** (fuera de lo que esta tarea permitía tocar): ningún `terraform plan`/`apply` contra
`hda-projectt` real, ningún build/push de imagen a Artifact Registry, ningún arranque real de la VM de
Pulsar con el override, ninguna consulta real de Grafana contra Cloud Monitoring. Todo lo anterior
queda pendiente para cuando el equipo decida encender esto de verdad.
