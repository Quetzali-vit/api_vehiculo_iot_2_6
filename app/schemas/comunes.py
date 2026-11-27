from typing import ClassVar

from pydantic import BaseModel


class Mensaje(BaseModel):
    mensaje: str


class ErrorRespuesta(BaseModel):
    detail: str

    DESCRIPCIONES: ClassVar[dict[int, str]] = {
        400: "Solicitud inválida o referencia a un registro inexistente",
        401: "Falta el encabezado X-API-Key",
        403: "La clave X-API-Key no es válida",
        404: "El recurso no existe",
        409: "Conflicto con el estado actual (inactivo, duplicado, DEMO en curso…)",
        503: "Amazon RDS no está disponible",
    }

    @classmethod
    def documentar(cls, *codigos: int) -> dict:
        """Arma el bloque `responses` de Swagger para los códigos de error indicados."""
        return {c: {"model": cls, "description": cls.DESCRIPCIONES[c]} for c in codigos}


# Nombre corto que usan los controladores en sus decoradores
respuestas_error = ErrorRespuesta.documentar
