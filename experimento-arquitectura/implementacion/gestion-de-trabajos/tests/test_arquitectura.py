import ast
import os
from pathlib import Path

def test_dominio_no_importa_infraestructura_ni_aplicacion():
    """Valida la Regla 5 de la Entrega 3: El dominio no debe depender de infraestructura ni de aplicación."""
    raiz = Path(__file__).parent.parent / "app" / "domain"
    if not raiz.exists():
        return
        
    for ruta_archivo in raiz.rglob("*.py"):
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            arbol = ast.parse(f.read(), filename=str(ruta_archivo))
            
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    modulo = alias.name
                    assert not modulo.startswith("app.infrastructure"), f"{ruta_archivo.name} viola la arquitectura hexagonal importando {modulo}"
                    assert not modulo.startswith("app.application"), f"{ruta_archivo.name} viola la arquitectura hexagonal importando {modulo}"
            elif isinstance(nodo, ast.ImportFrom):
                modulo = nodo.module
                if modulo:
                    assert not modulo.startswith("app.infrastructure"), f"{ruta_archivo.name} viola la arquitectura hexagonal importando {modulo}"
                    assert not modulo.startswith("app.application"), f"{ruta_archivo.name} viola la arquitectura hexagonal importando {modulo}"
