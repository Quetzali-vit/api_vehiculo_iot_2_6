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


class LimpiadorUnidadesPrueba:
    """Libera y da de baja (baja lógica) los carritos de prueba indicados por su serie."""

    def __init__(self, contenedor: Contenedor):
        self.c = contenedor

    def _actor_admin(self) -> Identidad | None:
        """El primer administrador activo: firma en la bitácora lo que haga este script."""
        admin = next((u for u in self.c.admin.listar_usuarios() if u["rol"] == "ADMIN" and u["activo"]), None)
        if admin is None:
            return None
        return Identidad(admin["id_usuario"], admin["nombre"], admin["correo"], admin["rol"])

    def ejecutar(self, series: list[str], aplicar: bool) -> int:
        if not series or any(not s.startswith("PRB-") for s in series):
            print("Indica una o más series de prueba (empiezan con PRB-).")
            return 2

        actor = self._actor_admin()
        if actor is None:
            print("No hay un administrador activo para firmar la bitácora.")
            return 1

        unidades = {u["numero_serie"]: u for u in self.c.admin.listar_unidades()}
        for serie in series:
            u = unidades.get(serie)
            if u is None:
                print(f"{serie}: no existe, se omite")
                continue
            print(f"{serie}: unidad {u['id_vehiculo']} «{u['nombre']}» dueño={u['id_propietario']}")
            if aplicar:
                self._dar_de_baja(actor, u)

        if not aplicar:
            print("\n(Solo se mostró. Agrega --aplicar para hacerlo.)")
        return 0

    def _dar_de_baja(self, actor: Identidad, unidad: dict) -> None:
        if unidad["id_propietario"] is not None:
            self.c.admin.asignar(actor, unidad["id_vehiculo"], None)
        self.c.gestion.editar_unidad(actor, unidad["id_vehiculo"],
                                     UnidadEditar(activo=False, estado_comercial="INACTIVO"))
        print("   liberada y dada de baja")


if __name__ == "__main__":
    series = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(LimpiadorUnidadesPrueba(Contenedor()).ejecutar(series, aplicar="--aplicar" in sys.argv))
