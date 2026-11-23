from pydantic import BaseModel, Field


class DemoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80, examples=["Demo corta"])
    descripcion: str | None = Field(default=None, max_length=255)


class DemoActualizar(BaseModel):
    """Solo se cambian los campos enviados; los demás conservan su valor actual."""
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class DemoRespuesta(BaseModel):
    id_demo: int
    id_vehiculo: int
    nombre: str
    descripcion: str | None
    activo: bool
    # Práctica 4.3: dueño de la demo (null = de fábrica, de la empresa)
    id_propietario: int | None = None
    tipo: str | None = Field(default=None, description="FABRICA o PRIVADA")
    total_movimientos: int | None = None


class DemoCreada(BaseModel):
    mensaje: str
    id_demo: int


class MovimientoDemoCrear(BaseModel):
    id_comando: int = Field(ge=1, examples=[1])
    orden: int = Field(ge=1, le=1000, examples=[1])
    duracion_ms: int = Field(ge=1, le=60000, examples=[2000])
    pausa_ms: int = Field(default=0, ge=0, le=60000, examples=[400])


class MovimientoDemoActualizar(BaseModel):
    """Solo se cambian los campos enviados; los demás conservan su valor actual."""
    id_comando: int | None = Field(default=None, ge=1)
    orden: int | None = Field(default=None, ge=1, le=1000)
    duracion_ms: int | None = Field(default=None, ge=1, le=60000)
    pausa_ms: int | None = Field(default=None, ge=0, le=60000)


class MovimientoDemoRespuesta(BaseModel):
    id_demo_movimiento: int
    orden: int
    id_comando: int
    comando: str
    codigo: int
    duracion_ms: int
    pausa_ms: int


class DemoEjecucionRespuesta(BaseModel):
    mensaje: str
    id_vehiculo: int
    id_demo: int
    demo: str
    total_movimientos: int
    websocket: str


class DemoEnCurso(BaseModel):
    id_vehiculo: int
    en_ejecucion: bool
    id_demo: int | None = None
    demo: str | None = None
