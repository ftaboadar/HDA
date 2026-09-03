"""hda-gcp — CLI para aprovisionar y operar el experimento DISP-03 en GCP y
localmente, desde la máquina del desarrollador.

Ejemplos:
    python -m cli.hda_gcp.main check
    python -m cli.hda_gcp.main infra init
    python -m cli.hda_gcp.main infra plan   --project mi-proyecto
    python -m cli.hda_gcp.main infra apply  --project mi-proyecto
    python -m cli.hda_gcp.main images build-push --project mi-proyecto --repo disp03-poc-hda
    python -m cli.hda_gcp.main run-experiment --target local
    python -m cli.hda_gcp.main run-experiment --target gcp
    python -m cli.hda_gcp.main teardown --target gcp --project mi-proyecto

Ningún comando que crea o destruye recursos reales en GCP (`infra apply`,
`infra destroy`, `teardown --target gcp`) corre sin confirmación interactiva,
salvo que se pase --yes explícitamente — aprovisionar es una acción
facturable y con efecto en un sistema externo, no algo para automatizar sin
mirar."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import typer

app = typer.Typer(help="Herramientas CLI para el experimento de arquitectura DISP-03 (HdA)")
infra_app = typer.Typer(help="Aprovisionamiento de infraestructura GCP vía Terraform")
images_app = typer.Typer(help="Construcción y publicación de la imagen de contenedor")
app.add_typer(infra_app, name="infra")
app.add_typer(images_app, name="images")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DIR_INFRA = RAIZ / "infra"


def _ejecutar(cmd: list[str], cwd: pathlib.Path | None = None, env: dict | None = None) -> None:
    typer.secho(f"$ {' '.join(cmd)}", fg=typer.colors.CYAN)
    entorno = os.environ.copy()
    if env:
        entorno.update(env)
    resultado = subprocess.run(cmd, cwd=cwd, env=entorno, check=False)
    if resultado.returncode != 0:
        typer.secho(f"Comando falló con código {resultado.returncode}", fg=typer.colors.RED)
        raise typer.Exit(resultado.returncode)


@app.command()
def check():
    """Verifica que gcloud, terraform y docker estén disponibles, y muestra
    la configuración activa de gcloud (proyecto, cuenta)."""
    herramientas = ["gcloud", "terraform", "docker"]
    faltantes = [h for h in herramientas if shutil.which(h) is None]
    for h in herramientas:
        ok = h not in faltantes
        typer.secho(
            f"{h}: {'OK' if ok else 'NO ENCONTRADO'}",
            fg=typer.colors.GREEN if ok else typer.colors.RED,
        )

    if "gcloud" not in faltantes:
        subprocess.run(["gcloud", "config", "list"], check=False)

    if faltantes:
        typer.secho(
            f"\nFaltan herramientas: {', '.join(faltantes)}. Instálalas antes de aprovisionar en GCP.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)
    typer.secho("\nTodo listo para operar contra GCP.", fg=typer.colors.GREEN)


@infra_app.command("init")
def infra_init():
    """terraform init sobre infra/."""
    _ejecutar(["terraform", "init"], cwd=DIR_INFRA)


@infra_app.command("plan")
def infra_plan(
    project: str = typer.Option(..., "--project", "-p"),
    region: str = typer.Option("southamerica-east1"),
):
    """terraform plan — muestra qué se aprovisionaría, sin crear nada."""
    _ejecutar(
        ["terraform", "plan", f"-var=project_id={project}", f"-var=region={region}"],
        cwd=DIR_INFRA,
    )


@infra_app.command("apply")
def infra_apply(
    project: str = typer.Option(..., "--project", "-p"),
    region: str = typer.Option("southamerica-east1"),
    yes: bool = typer.Option(False, "--yes", help="Omite la confirmación interactiva"),
):
    """terraform apply — APROVISIONA recursos reales y FACTURABLES en GCP
    (Cloud Run, Cloud SQL, Pub/Sub, Artifact Registry, Secret Manager)."""
    if not yes:
        typer.confirm(
            f"Esto va a crear recursos FACTURABLES en el proyecto GCP '{project}'. ¿Continuar?",
            abort=True,
        )
    _ejecutar(
        [
            "terraform",
            "apply",
            "-auto-approve",
            f"-var=project_id={project}",
            f"-var=region={region}",
        ],
        cwd=DIR_INFRA,
    )


@infra_app.command("destroy")
def infra_destroy(
    project: str = typer.Option(..., "--project", "-p"),
    region: str = typer.Option("southamerica-east1"),
    yes: bool = typer.Option(False, "--yes"),
):
    """terraform destroy — elimina TODOS los recursos del experimento en GCP."""
    if not yes:
        typer.confirm(
            f"Esto va a DESTRUIR todos los recursos del experimento en '{project}'. ¿Continuar?",
            abort=True,
        )
    _ejecutar(
        [
            "terraform",
            "destroy",
            "-auto-approve",
            f"-var=project_id={project}",
            f"-var=region={region}",
        ],
        cwd=DIR_INFRA,
    )


@infra_app.command("output")
def infra_output():
    """Muestra los outputs de Terraform (URLs de Cloud Run, nombres de topics, etc.)."""
    _ejecutar(["terraform", "output"], cwd=DIR_INFRA)


def _terraform_output_json() -> dict:
    resultado = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=DIR_INFRA,
        capture_output=True,
        text=True,
        check=False,
    )
    if resultado.returncode != 0:
        typer.secho(
            "No se pudo leer el estado de Terraform. ¿Ya corriste 'infra apply'?",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    return {k: v["value"] for k, v in json.loads(resultado.stdout).items()}


@images_app.command("build-push")
def images_build_push(
    project: str = typer.Option(..., "--project", "-p"),
    region: str = typer.Option("southamerica-east1"),
    repo: str = typer.Option(
        ...,
        "--repo",
        help="repository_id de Artifact Registry (output de terraform: artifact_registry_repo)",
    ),
):
    """Construye la imagen compartida (api/worker/mocks) y la publica en
    Artifact Registry, lista para que 'infra apply' la despliegue."""
    registro = f"{region}-docker.pkg.dev/{project}/{repo}"
    tag = f"{registro}/hda-disp03:latest"
    _ejecutar(["gcloud", "auth", "configure-docker", f"{region}-docker.pkg.dev", "--quiet"])
    _ejecutar(["docker", "build", "-t", tag, "."], cwd=RAIZ)
    _ejecutar(["docker", "push", tag])
    typer.secho(f"Imagen publicada: {tag}", fg=typer.colors.GREEN)


@app.command("run-experiment")
def run_experiment(
    target: str = typer.Option("local", "--target", help="local | gcp"),
    solo: str = typer.Option(None, "--solo", help="Filtro -k de pytest, ej. cp4"),
):
    """Ejecuta la suite de casos de prueba (CP-1..CP-7) contra el entorno
    local (docker-compose) o contra el desplegado en GCP."""
    env = {}
    if target == "gcp":
        salidas = _terraform_output_json()
        env = {
            "API_URL": salidas["api_url"],
            "MOCK_POLICIA_URL": salidas["mock_policia_url"],
            "MOCK_RUES_URL": salidas["mock_rues_url"],
            "MOCK_CERTIFICADORA_URL": salidas["mock_certificadora_url"],
        }
    elif target != "local":
        typer.secho("--target debe ser 'local' o 'gcp'", fg=typer.colors.RED)
        raise typer.Exit(1)

    cmd = ["pytest", "tests/", "-v"]
    if solo:
        cmd += ["-k", solo]
    resultado_env = os.environ.copy()
    resultado_env.update(env)
    resultado = subprocess.run(cmd, cwd=RAIZ, env=resultado_env, check=False)

    _ejecutar([sys.executable, "tests/reporte.py"], cwd=RAIZ)

    if resultado.returncode != 0:
        raise typer.Exit(resultado.returncode)


@app.command("teardown")
def teardown(
    target: str = typer.Option("local", "--target"),
    project: str = typer.Option(None, "--project", "-p"),
    region: str = typer.Option("southamerica-east1"),
    yes: bool = typer.Option(False, "--yes"),
):
    """Limpia el entorno: docker compose down -v (local) o terraform destroy (gcp)."""
    if target == "local":
        _ejecutar(["docker", "compose", "down", "-v"], cwd=RAIZ)
    elif target == "gcp":
        if not project:
            typer.secho("--project es obligatorio para --target gcp", fg=typer.colors.RED)
            raise typer.Exit(1)
        infra_destroy(project=project, region=region, yes=yes)
    else:
        typer.secho("--target debe ser 'local' o 'gcp'", fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
