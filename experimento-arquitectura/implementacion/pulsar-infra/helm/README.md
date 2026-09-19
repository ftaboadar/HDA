# Despliegue del cluster de Pulsar en GKE — Helm chart oficial

No se escribe un chart propio: se usa el chart **oficial** de Apache Pulsar
(`apache/pulsar-helm-chart`), solo se parametriza vía `values.yaml` en este directorio.

## Prerrequisitos

- Un cluster de GKE ya creado (fuera del alcance de este archivo — ver
  `experimento-arquitectura/implementacion/proveedores/infra/` para cómo el equipo ya aprovisiona GCP).
- `helm` v3 y `kubectl` apuntando al cluster de GKE correcto (`kubectl config current-context`).

## Comando esperado

```bash
# 1. Agregar el repo oficial (una sola vez)
helm repo add apache https://pulsar.apache.org/charts
helm repo update

# 2. Namespace de Kubernetes dedicado (no confundir con el namespace lógico
#    de Pulsar `hda/*` del README del docker-compose local — son conceptos
#    de capas distintas: este es de Kubernetes, ese es de Pulsar)
kubectl create namespace pulsar

# 3. Instalar con los overrides de este directorio
helm install hda-pulsar apache/pulsar \
  --namespace pulsar \
  --values values.yaml \
  --timeout 15m
```

## Verificar que quedó sano

```bash
kubectl get pods -n pulsar
kubectl exec -n pulsar -it deploy/hda-pulsar-toolset -- bin/pulsar-admin brokers healthcheck
```

## Después de instalar

Crear los mismos tenants/namespaces/tópicos que en el cluster local (ver
`../README.md`, sección "Cómo crear los tópicos y namespaces"), pero ejecutando los comandos desde
el pod `toolset` en vez de `docker exec`:

```bash
kubectl exec -n pulsar -it deploy/hda-pulsar-toolset -- bin/pulsar-admin tenants create hda \
  --allowed-clusters cluster-hda
# ... resto de namespaces/tópicos, mismos comandos que en el README local
```

## Qué falta / qué queda pendiente

- **No se ejecutó este `helm install` de verdad** en la sesión donde se escribió este archivo (sin
  acceso a un cluster GKE ni a `helm`/`kubectl` en este entorno) — los valores son razonables para
  un PoC según la documentación pública del chart, pero deben confirmarse contra la versión exacta
  del chart que el equipo termine usando (`helm show values apache/pulsar` para comparar claves
  disponibles antes de aplicar, por si el chart cambió de esquema entre versiones).
- El `proxy.service.type: LoadBalancer` va a crear un Load Balancer real de GCP (costo asociado) —
  si el PoC no necesita exponer el cluster fuera de GKE (los otros microservicios ya corren dentro
  del mismo cluster/VPC), cambiar a `ClusterIP` y acceder por DNS interno de Kubernetes en vez de IP
  pública.
- `monitoring.prometheus`/`grafana` quedaron desactivados a propósito (ver comentario en
  `values.yaml`) — si `experimento-runner` necesita dashboards en vivo durante la inyección de
  fallas de DISP-03/02, es un cambio de un solo valor, no una reestructuración.
