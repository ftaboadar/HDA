import os

for root, dirs, files in os.walk(
    "/Users/jhoansarmiento/HDA/experimento-arquitectura/implementacion/proveedores/app"
):
    for f in files:
        if "consumidor" in f:
            print(os.path.join(root, f))
