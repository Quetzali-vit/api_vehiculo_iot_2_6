"""Crea dos demos privadas del dueño en una unidad (por defecto la 7).

Uso (en el servidor, desde la carpeta de la API):
    python pruebas\\crear_demos_cliente.py            # usa la unidad 7
    python pruebas\\crear_demos_cliente.py 7

Las demos quedan como PRIVADAS del dueño actual de la unidad (las firma el
Administrador en la bitácora). Si ya existe una demo con el mismo nombre en esa
unidad, no se duplica.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dependencies import Contenedor  # noqa: E402
from app.schemas.demo import MovimientoDemoCrear  # noqa: E402
from app.services.auth_service import Identidad  # noqa: E402


class CreadorDemosCliente:
    """Crea demos privadas del dueño de una unidad, sin duplicar las que ya existen."""

    PASO_MS, PAUSA_MS = 1500, 300

    DEMOS = [
        ("Recorrido completo",
         "Apaga y vuelve a prender el sonido y luego hace todos los movimientos del carrito",
         ["SONIDO", "SONIDO", "AVANZAR", "RETROCEDER", "GIRAR_IZQUIERDA", "GIRAR_DERECHA",
          "SUBIR_BRAZO", "BAJAR_BRAZO", "ABRIR_PALA", "CERRAR_PALA", "DETENER"]),
        ("Frente, atras y pala",
         "Avanza, retrocede, sube y baja la pala",
         ["AVANZAR", "RETROCEDER", "SUBIR_BRAZO", "BAJAR_BRAZO", "DETENER"]),
    ]

    def __init__(self, contenedor: Contenedor):
        self.c = contenedor

    def _actor_admin(self) -> Identidad | None:
        """El primer administrador activo: firma en la bitácora lo que haga este script."""
        admin = next((u for u in self.c.admin.listar_usuarios() if u["rol"] == "ADMIN" and u["activo"]), None)
        if admin is None:
            return None
        return Identidad(admin["id_usuario"], admin["nombre"], admin["correo"], admin["rol"])

    def ejecutar(self, id_vehiculo: int) -> int:
        actor = self._actor_admin()
        if actor is None:
            print("No hay un administrador activo.")
            return 1

        comandos = {x["nombre"]: x["id_comando"] for x in self.c.comandos.listar(id_vehiculo) if x["activo"]}
        existentes = {d["nombre"] for d in self.c.auth.demos_visibles(actor, id_vehiculo)}

        for nombre, descripcion, pasos in self.DEMOS:
            if nombre in existentes:
                print(f"«{nombre}»: ya existe, se omite")
                continue
            faltan = [p for p in pasos if p not in comandos]
            if faltan:
                print(f"«{nombre}»: la unidad no tiene {faltan}, se omite")
                continue
            id_demo = self._crear(actor, id_vehiculo, nombre, descripcion, [comandos[p] for p in pasos])
            print(f"«{nombre}»: demo {id_demo} con {len(pasos)} pasos")
        return 0

    def _crear(self, actor: Identidad, id_vehiculo: int, nombre: str, descripcion: str,
               id_comandos: list[int]) -> int:
        id_demo = self.c.auth.crear_demo(actor, id_vehiculo, nombre, descripcion)
        for orden, id_comando in enumerate(id_comandos, start=1):
            self.c.demos.agregar_movimiento(id_vehiculo, id_demo, MovimientoDemoCrear(
                id_comando=id_comando, orden=orden, duracion_ms=self.PASO_MS, pausa_ms=self.PAUSA_MS))
        return id_demo


if __name__ == "__main__":
    unidad = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    sys.exit(CreadorDemosCliente(Contenedor()).ejecutar(unidad))
