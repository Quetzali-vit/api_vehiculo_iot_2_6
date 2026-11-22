"""Esquemas Pydantic de la práctica 4.3 (Administración).

Ninguna respuesta incluye hashes ni tokens guardados: lo que no está aquí,
no sale de la API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Rol = Literal["ADMIN", "USUARIO"]
EstadoComercial = Literal["DISPONIBLE", "VENDIDO", "EXHIBICION", "INACTIVO"]

# Validación de correo sin depender de email-validator: así el despliegue en EC2
# sigue siendo `git pull` + reiniciar, sin instalar paquetes nuevos.
PATRON_CORREO = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"


# ---------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------
class LoginSolicitud(BaseModel):
    correo: str = Field(max_length=120, examples=["admin@iot.com"])
    contrasena: str = Field(min_length=1, max_length=200, examples=["Admin123#"])


class UsuarioSesion(BaseModel):
    id_usuario: int
    nombre: str
    correo: str
    rol: str


class LoginRespuesta(BaseModel):
    token: str = Field(description="Envíalo en el encabezado Authorization: Bearer <token>")
    expira_en_horas: int
    usuario: UsuarioSesion


class YoRespuesta(BaseModel):
    """Quién es quien llama, según su token."""

    id_usuario: int | None
    nombre: str
    correo: str
    rol: str
    invitado: bool = False
    id_vehiculo_invitado: int | None = None
    segundos_restantes: int | None = None


# ---------------------------------------------------------------------
# Usuarios / clientes
# ---------------------------------------------------------------------
class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80, examples=["María López"])
    correo: str = Field(max_length=120, pattern=PATRON_CORREO, examples=["maria@correo.com"])
    contrasena: str = Field(min_length=8, max_length=200, examples=["Cliente123#"])
    rol: Rol = Field(default="USUARIO")
    telefono: str | None = Field(default=None, max_length=30)


class UsuarioActualizar(BaseModel):
    """Solo se cambia lo que se envía; lo demás conserva su valor."""

    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    telefono: str | None = Field(default=None, max_length=30)
    contrasena: str | None = Field(default=None, min_length=8, max_length=200)
    rol: Rol | None = None
    activo: bool | None = None


class UsuarioRespuesta(BaseModel):
    id_usuario: int
    nombre: str
    correo: str
    telefono: str | None = None
    rol: str
    activo: bool
    fecha_registro: datetime | None = None
    unidades: int = 0


class UsuarioCreado(BaseModel):
    mensaje: str
    id_usuario: int


# ---------------------------------------------------------------------
# Modelos comerciales
# ---------------------------------------------------------------------
class ModeloCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80, examples=["Retroexcavadora IoT"])
    descripcion: str | None = Field(default=None, max_length=500)
    microcontrolador: str | None = Field(default=None, max_length=50, examples=["ESP32"])
    precio: Decimal | None = Field(default=None, ge=0, le=99999999, examples=[7500.00])
    imagen_url: str | None = Field(default=None, max_length=255)


class ModeloActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=500)
    microcontrolador: str | None = Field(default=None, max_length=50)
    precio: Decimal | None = Field(default=None, ge=0, le=99999999)
    imagen_url: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class ModeloRespuesta(BaseModel):
    id_modelo: int
    nombre: str
    descripcion: str | None = None
    microcontrolador: str | None = None
    precio: Decimal | None = None
    imagen_url: str | None = None
    activo: bool
    fecha_registro: datetime | None = None
    unidades: int = 0
    unidades_exhibicion: int = 0


class ModeloCreado(BaseModel):
    mensaje: str
    id_modelo: int


class CatalogoItem(BaseModel):
    """Lo que ve un cliente potencial. Sin propietarios ni inventario privado."""

    id_modelo: int
    nombre: str
    descripcion: str | None = None
    microcontrolador: str | None = None
    precio: Decimal | None = None
    imagen_url: str | None = None
    unidades_exhibicion: int = 0
    disponibles: int = 0


# ---------------------------------------------------------------------
# Unidades físicas
# ---------------------------------------------------------------------
class UnidadCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80, examples=["Retroexcavadora 002"])
    id_modelo: int | None = Field(default=None, ge=1, examples=[1])
    numero_serie: str | None = Field(default=None, max_length=40, examples=["UNI-0002"])
    estado_comercial: EstadoComercial = Field(default="DISPONIBLE")
    modelo: str | None = Field(default=None, max_length=80,
                               description="Texto libre heredado de 4.1; usa id_modelo para el modelo real")
    descripcion: str | None = Field(default=None, max_length=255)
    microcontrolador: str | None = Field(default=None, max_length=50, examples=["ESP32"])


class UnidadComercial(BaseModel):
    """Cambia los datos comerciales. Para el nombre y la descripción se sigue
    usando el endpoint de vehículos de 4.1."""

    id_modelo: int | None = Field(default=None, ge=1)
    numero_serie: str | None = Field(default=None, max_length=40)
    estado_comercial: EstadoComercial | None = None


class AsignacionSolicitud(BaseModel):
    id_usuario: int | None = Field(default=None, ge=1,
                                   description="null libera la unidad y le quita el acceso al dueño anterior")


class UnidadRespuesta(BaseModel):
    id_vehiculo: int
    nombre: str
    numero_serie: str | None = None
    estado_comercial: str
    activo: bool
    microcontrolador: str | None = None
    fecha_registro: datetime | None = None
    id_modelo: int | None = None
    modelo: str | None = None
    id_propietario: int | None = None
    propietario: str | None = None
    correo_propietario: str | None = None
    conectado: bool = False
    comandos: int = 0


class UnidadCreada(BaseModel):
    mensaje: str
    id_vehiculo: int


class MiVehiculo(BaseModel):
    id_vehiculo: int
    nombre: str
    numero_serie: str | None = None
    estado_comercial: str
    microcontrolador: str | None = None
    id_modelo: int | None = None
    modelo: str | None = None
    conectado: bool = False


# ---------------------------------------------------------------------
# Dashboard y auditoría
# ---------------------------------------------------------------------
class MetricasRespuesta(BaseModel):
    modelos: int
    unidades: int
    vendidas: int
    disponibles: int
    exhibicion: int
    clientes: int
    demos: int
    demos_fabrica: int
    conectadas: int
    pruebas_activas: int
    movimientos_totales: int


class AuditoriaItem(BaseModel):
    id_auditoria: int
    fecha_hora: datetime | None = None
    id_usuario: int | None = None
    actor: str
    accion: str
    recurso: str
    id_recurso: str | None = None
    resultado: str
    detalle: str | None = None


# ---------------------------------------------------------------------
# Sesiones de invitado
# ---------------------------------------------------------------------
class PruebaSolicitud(BaseModel):
    id_modelo: int | None = Field(default=None, ge=1,
                                  description="Modelo que se quiere probar; null toma cualquiera libre")
    nombre: str | None = Field(default=None, max_length=80, examples=["Visitante"])


class PruebaRespuesta(BaseModel):
    activa: bool
    id_vehiculo: int
    vehiculo: str | None = None
    modelo: str | None = None
    segundos_restantes: int
    comandos_permitidos: list[str]
    motivo_fin: str | None = None


class PruebaCreada(PruebaRespuesta):
    token: str = Field(description="Envíalo como Authorization: Bearer <token> mientras dure la prueba")
