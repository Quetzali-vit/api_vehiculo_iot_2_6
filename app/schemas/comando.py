from pydantic import BaseModel, Field, field_validator


class ConNombreDeComando(BaseModel):
    """Base de los esquemas que reciben el nombre de un comando: lo guarda en MAYÚSCULAS y sin espacios
    a los lados, para que «avanzar » y «AVANZAR» sean el mismo comando."""

    @field_validator("nombre", check_fields=False)
    @classmethod
    def _normalizar_nombre(cls, valor: str | None) -> str | None:
        return valor.strip().upper() if valor is not None else None


class ComandoCrear(ConNombreDeComando):
    nombre: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_ ]+$", examples=["CLAXON"])
    codigo: int = Field(ge=0, le=9999, examples=[10])
    descripcion: str | None = Field(default=None, max_length=255)


class ComandoActualizar(ConNombreDeComando):
    """Solo se cambian los campos enviados; los demás conservan su valor actual."""
    nombre: str | None = Field(default=None, min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_ ]+$")
    codigo: int | None = Field(default=None, ge=0, le=9999)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class ComandoRespuesta(BaseModel):
    id_comando: int
    id_vehiculo: int
    nombre: str
    codigo: int
    descripcion: str | None
    activo: bool


class ComandoCreado(BaseModel):
    mensaje: str
    id_comando: int
