class Repositorio:
    """Base de todos los repositorios.

    Un repositorio traduce operaciones del negocio («crear un modelo», «asignar
    una unidad») a llamadas a Stored Procedures sobre una `SesionSP`. No abre
    conexiones ni confirma transacciones: eso lo decide el servicio que lo usa.
    """

    @staticmethod
    def _primera(filas: list[dict]) -> dict | None:
        """La primera fila de un resultado, o None si el procedimiento no devolvió nada."""
        return filas[0] if filas else None

