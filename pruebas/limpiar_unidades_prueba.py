"""Libera y da de baja carritos que dejó la prueba de roles.

Uso (en el servidor, desde la carpeta de la API):
    python pruebas\\limpiar_unidades_prueba.py PRB-1123162646 PRB-1123180758            # solo muestra
    python pruebas\\limpiar_unidades_prueba.py PRB-1123162646 PRB-1123180758 --aplicar  # aplica

Es baja lógica: el carrito queda sin dueño, INACTIVO y con activo = false. Su
historial y su bitácora se conservan. Solo toca unidades con serie «PRB-».
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import Contenedor  # noqa: E402
from app.schemas.admin import UnidadEditar  # noqa: E402
from app.services.auth_service import Identidad  # noqa: E402


def main() -> int:
    series = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    if not series or any(not s.startswith("PRB-") for s in series):
        print("Indica una o más series de prueba (empiezan con PRB-).")
        return 2

    c = Contenedor()
    admin = next((u for u in c.admin.listar_usuarios() if u["rol"] == "ADMIN" and u["activo"]), None)
    if admin is None:
        print("No hay un administrador activo para firmar la bitácora.")
        return 1
    actor = Identidad(admin["id_usuario"], admin["nombre"], admin["correo"], admin["rol"])

    unidades = {u["numero_serie"]: u for u in c.admin.listar_unidades()}
    for serie in series:
        u = unidades.get(serie)
        if u is None:
            print(f"{serie}: no existe, se omite")
            continue
        print(f"{serie}: unidad {u['id_vehiculo']} «{u['nombre']}» dueño={u['id_propietario']}")
        if not aplicar:
            continue
        if u["id_propietario"] is not None:
            c.admin.asignar(actor, u["id_vehiculo"], None)
        c.gestion.editar_unidad(actor, u["id_vehiculo"],
                                UnidadEditar(activo=False, estado_comercial="INACTIVO"))
        print("   liberada y dada de baja")

    if not aplicar:
        print("\n(Solo se mostró. Agrega --aplicar para hacerlo.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
