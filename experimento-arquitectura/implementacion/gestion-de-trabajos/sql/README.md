# Gestión de Trabajos — Conexión al Saga Log en Cloud SQL

Este documento proporciona una guía paso a paso para conectarse a la base de datos PostgreSQL del servicio **Gestión de Trabajos** (GT) alojada en Google Cloud SQL, donde reside el **Saga Log**. Utilizaremos [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy) para crear una conexión local segura sin exponer la base de datos a internet, ideal para interactuar con las tablas `saga_instancia` y `saga_log`.

## Requisitos Previos

1. Instalar [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) y autenticarse con permisos sobre el proyecto:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project <TU_PROJECT_ID>
   ```
2. Descargar el [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy#install). En sistemas Unix, puedes darle permisos de ejecución:
   ```bash
   # Ejemplo para macOS ARM64 / Linux:
   curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.11.0/cloud-sql-proxy.darwin.arm64
   chmod +x cloud-sql-proxy
   ```
3. Tener instalado un cliente de PostgreSQL (como `psql` para CLI o [DBeaver](https://dbeaver.io/) para GUI).

---

## Paso 1: Levantar el Cloud SQL Auth Proxy

El proxy abrirá un puerto local (túnel) que reenvía el tráfico seguro a la instancia de Cloud SQL en GCP. El nombre de la instancia en la infraestructura actual por defecto es `gestion-trabajos-poc-gestion-trabajos` en la región `southamerica-east1`.

Ejecuta el siguiente comando en tu terminal, reemplazando `<TU_PROJECT_ID>` por el nombre de tu proyecto en GCP:

```bash
./cloud-sql-proxy <TU_PROJECT_ID>:southamerica-east1:gestion-trabajos-poc-gestion-trabajos --port 5432
```
*Si tienes un PostgreSQL local ocupando el puerto 5432, utiliza otro puerto como `--port 5433`.*

> **Importante:** Deja esta terminal abierta mientras necesites la conexión. El proxy indicará que está escuchando en `127.0.0.1:5432`.

---

## Paso 2: Obtener las credenciales (Secret Manager)

La contraseña de la base de datos se autogenera mediante Terraform (`random_password`) y se almacena en Secret Manager. El usuario es `hda` y la base de datos es `gestion_trabajos`.

Para extraer tu contraseña, solicita el valor del secreto `gestion-trabajos-poc-database-url`:

```bash
gcloud secrets versions access latest \
    --secret="gestion-trabajos-poc-database-url" \
    --project="<TU_PROJECT_ID>"
```

La salida tendrá este formato:
`postgresql+psycopg2://hda:<CONTRASEÑA>@/gestion_trabajos?host=/cloudsql/...`

Copia el texto correspondiente a `<CONTRASEÑA>` (entre los dos puntos `:` y la arroba `@`).

---

## Paso 3A: Conexión vía CLI (`psql`) y prueba del Saga Log

Abre una **nueva terminal** (manteniendo el proxy en ejecución en la otra) y conéctate:

```bash
psql -h 127.0.0.1 -p 5432 -U hda -d gestion_trabajos
```
*Cuando se te solicite, pega la `<CONTRASEÑA>` que obtuviste en el Paso 2.*

### Ejecutar las consultas del Saga Log

Para probar la conexión y visualizar la traza de eventos y comandos del Motor de Workflow (Saga Orquestada), usa el script `consultas-saga-log.sql` que se encuentra en este mismo directorio.

Desde fuera de psql:
```bash
psql -h 127.0.0.1 -p 5432 -U hda -d gestion_trabajos -f consultas-saga-log.sql
```

O si ya estás dentro de la consola interactiva `psql`:
```sql
\i consultas-saga-log.sql
```

> **Nota:** La primera consulta de `consultas-saga-log.sql` ("Línea de tiempo de una saga") requiere que reemplaces el valor `'AQUI_UUID_DE_LA_SAGA'` por un `trabajo_id` real que se haya generado durante un flujo de prueba. Puedes ignorar el resultado en blanco de esa consulta hasta que insertes el ID válido.

---

## Paso 3B: Conexión vía Interfaz Gráfica (DBeaver)

Si prefieres usar herramientas visuales, sigue estos pasos:

1. Abre **DBeaver**.
2. Ve a **Nueva Conexión** y selecciona **PostgreSQL**.
3. En la pestaña **Principal (Main)**, ingresa los datos:
   - **Host:** `127.0.0.1`
   - **Port:** `5432` *(o el puerto que hayas configurado en el proxy)*
   - **Database:** `gestion_trabajos`
   - **Username:** `hda`
   - **Password:** *(la contraseña copiada en el Paso 2)*
4. Presiona **Test Connection** para asegurar que el proxy está enrutando el tráfico adecuadamente y luego presiona **Finish**.
5. Abre un nuevo **SQL Editor**, arrastra el archivo `consultas-saga-log.sql` o copia su contenido y ejecútalo para inspeccionar las tablas `saga_instancia` y `saga_log`.

---

## Resolución de Problemas

- **`bind: address already in use`**: Tu puerto 5432 ya está ocupado. Reinicia el proxy con `--port 5433` y ajusta el puerto en `psql` o DBeaver.
- **`connection refused` o `insufficient permissions`**: Asegúrate de estar autenticado en `gcloud` con la cuenta correcta y que tu usuario tenga el rol de **Cliente de Cloud SQL** (`roles/cloudsql.client`) en el proyecto.
