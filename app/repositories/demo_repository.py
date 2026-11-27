from app.db.database import SesionSP
from app.repositories.base import Repositorio


class DemoRepository(Repositorio):
    """Acceso a los SP de las tablas demos y demo_movimientos."""

    # --- demos ---
    def crear(self, sesion: SesionSP, id_vehiculo: int, nombre: str, descripcion: str | None) -> int:
        filas = sesion.llamar("sp_crear_demo", id_vehiculo, nombre, descripcion)
        return int(filas[0]["id_demo"])

    def listar_por_vehiculo(self, sesion: SesionSP, id_vehiculo: int) -> list[dict]:
        return sesion.llamar("sp_obtener_demos", id_vehiculo)

    def actualizar(self, sesion: SesionSP, id_demo: int, nombre: str, descripcion: str | None, activo: bool) -> None:
        sesion.llamar("sp_actualizar_demo", id_demo, nombre, descripcion, activo)

    def eliminar(self, sesion: SesionSP, id_demo: int) -> None:
        sesion.llamar("sp_eliminar_demo", id_demo)

    # --- demo_movimientos ---
    def agregar_movimiento(self, sesion: SesionSP, id_demo: int, id_comando: int, orden: int,
                           duracion_ms: int, pausa_ms: int) -> None:
        sesion.llamar("sp_agregar_movimiento_demo", id_demo, id_comando, orden, duracion_ms, pausa_ms)

    def listar_movimientos(self, sesion: SesionSP, id_demo: int) -> list[dict]:
        return sesion.llamar("sp_obtener_movimientos_demo", id_demo)

    def actualizar_movimiento(self, sesion: SesionSP, id_demo_movimiento: int, id_comando: int, orden: int,
                              duracion_ms: int, pausa_ms: int) -> None:
        sesion.llamar("sp_actualizar_movimiento_demo", id_demo_movimiento, id_comando, orden, duracion_ms, pausa_ms)

    def eliminar_movimiento(self, sesion: SesionSP, id_demo_movimiento: int) -> None:
        sesion.llamar("sp_eliminar_movimiento_demo", id_demo_movimiento)
