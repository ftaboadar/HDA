# Infraestructura del cluster de Apache Pulsar — Hogar de los Alpes (Entrega 4)

> Dueño: Daniel (ver `experimento-arquitectura/contexto/12-plan-entrega-4.md`, sección 8).
> **Este es el componente más urgente de todo el reparto**: sin este cluster corriendo, ni
> Gestión de Trabajos (Frans) ni Proveedores (Johan) pueden probar sus publicadores/consumidores
> reales contra Pulsar. Avisar al equipo apenas `docker-compose up` levante sano.

## Por qué esto y no `bin/pulsar standalone`

La rúbrica exige explícitamente que el equipo **configuró, desplegó y usó un cluster** (5pt,
sección 3 y 7 del plan de Entrega 4). `bin/pulsar standalone` empaqueta Zookeeper, BookKeeper y el
Broker en un solo proceso — sirve para una demo de 2 minutos, pero no demuestra que el equipo supo
separar y coordinar los componentes reales de un cluster. Aquí cada componente es su propio
contenedor Docker, con su propio ciclo de vida y su propia configuración — 1 réplica de cada uno ya
es suficiente para que cuente como "cluster real, no monolítico" (así lo dice el plan).

## Cómo levantarlo

```bash
cd experimento-arquitectura/implementacion/pulsar-infra
docker-compose up -d
```

Orden real de arranque (encadenado por `depends_on` + healthchecks, no hay que hacer nada manual):

1. `zookeeper` arranca y se espera a que su healthcheck (`pulsar-zookeeper-ruok.sh`) pase.
2. `pulsar-init` corre `bin/pulsar initialize-cluster-metadata` una sola vez contra Zookeeper y
   termina — es el equivalente a un init container de Kubernetes. Si este contenedor termina con
   código distinto de 0, ningún otro servicio arranca.
3. `bookie` arranca una vez `pulsar-init` terminó con éxito.
4. `broker` arranca una vez `bookie` está en marcha — expone `6650` (protocolo binario Pulsar) y
   `8080` (admin REST) al host.

Para ver el estado de cada contenedor:

```bash
docker-compose ps
docker-compose logs -f broker
```

## Cómo verificar que está sano

```bash
# Opción 1: pulsar-admin dentro del propio contenedor del broker
docker exec hda-pulsar-broker bin/pulsar-admin brokers healthcheck

# Opción 2: curl directo al admin REST, desde el host
curl -sf http://localhost:8080/admin/v2/brokers/health && echo "OK"

# Ver qué brokers conoce el cluster
docker exec hda-pulsar-broker bin/pulsar-admin brokers list cluster-hda
```

Si `curl` devuelve `200 OK` (cuerpo vacío es normal), el cluster está listo para recibir tópicos y
tráfico real.

## Cómo crear los tópicos y namespaces que necesita el equipo

Pulsar auto-crea tópicos al primer uso si el namespace tiene `allowAutoTopicCreation` activo (el
default), pero **para esta entrega los creamos explícitos** — deja trazabilidad de qué tópicos
existen y permite fijar políticas (retención, dead-letter) por namespace desde el día 1, en vez de
depender del comportamiento por defecto.

```bash
BROKER=hda-pulsar-broker

# 1. Tenant "hda" (agrupa todos los namespaces del proyecto)
docker exec $BROKER bin/pulsar-admin tenants create hda \
  --allowed-clusters cluster-hda

# 2. Un namespace por Bounded Context/microservicio propio (ver plan, sección 3)
docker exec $BROKER bin/pulsar-admin namespaces create hda/gestion-trabajos
docker exec $BROKER bin/pulsar-admin namespaces create hda/proveedores
docker exec $BROKER bin/pulsar-admin namespaces create hda/reputacion

# 3. Tópicos concretos que ya se conocen (ver plan, sección 3 y 4.1)
docker exec $BROKER bin/pulsar-admin topics create \
  persistent://hda/gestion-trabajos/trabajos.finalizado

docker exec $BROKER bin/pulsar-admin topics create \
  persistent://hda/proveedores/verificacion.solicitada
docker exec $BROKER bin/pulsar-admin topics create \
  persistent://hda/proveedores/verificacion.fallida-dlq
docker exec $BROKER bin/pulsar-admin topics create \
  persistent://hda/proveedores/proveedor.habilitado

# Reputación no publica tópicos propios en esta entrega (solo consume
# trabajos.finalizado) — el namespace hda/reputacion queda reservado para
# cuando eso cambie (ej. si a futuro publica un evento de integración
# propio hacia Scoring, ver plan sección 1.1).
```

Verificar que quedaron creados:

```bash
docker exec $BROKER bin/pulsar-admin topics list hda/gestion-trabajos
docker exec $BROKER bin/pulsar-admin topics list hda/proveedores
```

## Cómo apagar / limpiar

```bash
docker-compose down          # detiene los contenedores, conserva los volúmenes (datos persisten)
docker-compose down -v       # además borra zk-data y bk-data (cluster completamente limpio)
```

## Qué falta / qué queda pendiente

- **No pude ejecutar `docker-compose up` en este entorno de trabajo** (sin Docker disponible en la
  sesión donde se escribió este archivo) — el compose se construyó siguiendo el patrón oficial
  documentado por Apache Pulsar para desplegar ZK+BK+Broker separados con Docker (mismo patrón que
  usa el repo `apache/pulsar` en sus ejemplos de despliegue en contenedores), pero **la primera
  persona que lo levante debe confirmarlo de verdad** y reportar si algún healthcheck o variable de
  entorno necesita ajuste (versiones de imagen, memoria, etc. son las variables más probables de
  necesitar tuning en una máquina con menos RAM).
- El tag de imagen (`apachepulsar/pulsar:3.2.2`) es una versión estable conocida — si el equipo
  prefiere fijar otra, es un cambio de una sola línea (el YAML anchor `x-pulsar-image` centraliza el
  tag para los 4 servicios).
- Políticas de retención y Dead Letter Policy nativa de Pulsar (mencionadas en el plan, sección
  2.2 punto 2) se configuran del lado de cada microservicio consumidor (Proveedores, Reputación),
  no aquí — este README solo cubre la existencia del tópico, no su política de suscripción.
- El despliegue en GKE (ver `helm/`) es el siguiente paso una vez el cluster local esté validado.

## Ver también

- `helm/values.yaml` + `helm/README.md` — mismo cluster, para GKE, vía el chart oficial de Pulsar.
- `experimento-arquitectura/contexto/12-plan-entrega-4.md`, sección 3 — contexto completo de por
  qué Pulsar y por qué cluster autogestionado (no hay servicio gestionado nativo de Pulsar en GCP).
