from app.db.database import SesionSP
from app.repositories.base import Repositorio


class VehiculoRepository(Repositorio):
    """Acceso a los SP de la tabla vehiculos."""

    def crear(self, sesion: SesionSP, nombre: str, modelo: str | None, descripcion: str | None,
              microcontrolador: str | None) -> int:
        filas = sesion.llamar("sp_crear_vehiculo", nombre, modelo, descripcion, microcontrolador)
        return int(filas[0]["id_vehiculo"])

    def listar(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_obtener_vehiculos")

    def obtener(self, sesion: SesionSP, id_vehiculo: int) -> dict | None:
        filas = sesion.llamar("sp_obtener_vehiculo", id_vehiculo)
        return self._primera(filas)

    def actualizar(self, sesion: SesionSP, id_vehiculo: int, nombre: str, modelo: str | None,
                   descripcion: str | None, microcontrolador: str | None, activo: bool) -> None:
        sesion.llamar("sp_actualizar_vehiculo", id_vehiculo, nombre, modelo, descripcion, microcontrolador, activo)

    def eliminar(self, sesion: SesionSP, id_vehiculo: int) -> None:
        sesion.llamar("sp_eliminar_vehiculo", id_vehiculo)
