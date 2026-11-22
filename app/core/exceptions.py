class ApiError(Exception):
    """Error de negocio que se traduce a una respuesta HTTP controlada."""

    status_code = 500

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class SolicitudInvalida(ApiError):
    status_code = 400


class NoAutenticado(ApiError):
    """Falta la sesión o el token ya no sirve (4.3)."""

    status_code = 401


class Prohibido(ApiError):
    """Hay sesión, pero ese usuario no tiene permiso sobre ese recurso (4.3)."""

    status_code = 403


class NoEncontrado(ApiError):
    status_code = 404


class Conflicto(ApiError):
    status_code = 409


class BaseDatosNoDisponible(ApiError):
    status_code = 503
