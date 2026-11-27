from app.db.database import SesionSP
from app.repositories.base import Repositorio


class ComandoRepository(Repositorio):
    """Acceso a los SP de la tabla comandos."""

    def crear(self, sesion: SesionSP, id_vehiculo: int, nombre: str, codigo: int, descripcion: str | None) -> int:
        filas = sesion.llamar("sp_crear_comando", id_vehiculo, nombre, codigo, descripcion)
        return int(filas[0]["id_comando"])

    def listar_por_vehiculo(self, sesion: SesionSP, id_vehiculo: int) -> list[dict]:
        return sesion.llamar("sp_obtener_comandos_vehiculo", id_vehiculo)

    def actualizar(self, sesion: SesionSP, id_comando: int, nombre: str, codigo: int,
                   descripcion: str | None, activo: bool) -> None:
        sesion.llamar("sp_actualizar_comando", id_comando, nombre, codigo, descripcion, activo)

    def eliminar(self, sesion: SesionSP, id_comando: int) -> None:
        sesion.llamar("sp_eliminar_comando", id_comando)
