from app.db.database import SesionSP
from app.repositories.base import Repositorio


class HistorialRepository(Repositorio):
    """Acceso a los SP de la tabla historial_comandos."""

    def registrar(self, sesion: SesionSP, id_vehiculo: int, id_comando: int, origen: str) -> None:
        sesion.llamar("sp_registrar_historial", id_vehiculo, id_comando, origen)

    def obtener(self, sesion: SesionSP, id_vehiculo: int) -> list[dict]:
        """Devuelve el historial completo, del más reciente al más antiguo."""
        return sesion.llamar("sp_obtener_historial", id_vehiculo)
