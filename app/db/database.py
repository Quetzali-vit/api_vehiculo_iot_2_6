import logging
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import Settings
from app.core.exceptions import BaseDatosNoDisponible, Conflicto, SolicitudInvalida

logger = logging.getLogger(__name__)

# Los 21 Stored Procedures del esquema vehiculo_iot (prácticas 2.3 y 2.4).
PROCEDIMIENTOS_BASE = frozenset({
    "sp_crear_vehiculo", "sp_obtener_vehiculos", "sp_obtener_vehiculo",
    "sp_actualizar_vehiculo", "sp_eliminar_vehiculo",
    "sp_crear_comando", "sp_obtener_comandos_vehiculo", "sp_actualizar_comando", "sp_eliminar_comando",
    "sp_actualizar_estado", "sp_obtener_estado",
    "sp_registrar_historial", "sp_obtener_historial",
    "sp_crear_demo", "sp_obtener_demos", "sp_actualizar_demo", "sp_eliminar_demo",
    "sp_agregar_movimiento_demo", "sp_obtener_movimientos_demo",
    "sp_actualizar_movimiento_demo", "sp_eliminar_movimiento_demo",
})

# Procedimientos agregados por la práctica 4.3 (migración 002_procedimientos.sql).
PROCEDIMIENTOS_ADMIN = frozenset({
    "sp_login_usuario", "sp_crear_usuario", "sp_obtener_usuarios", "sp_obtener_usuario",
    "sp_actualizar_usuario",
    "sp_crear_sesion", "sp_obtener_sesion", "sp_revocar_sesion",
    "sp_crear_modelo", "sp_obtener_modelos", "sp_obtener_modelo", "sp_actualizar_modelo",
    "sp_obtener_unidades", "sp_obtener_unidad", "sp_actualizar_comercial", "sp_asignar_unidad",
    "sp_obtener_mis_vehiculos", "sp_catalogo_publico",
    "sp_crear_sesion_invitado", "sp_obtener_sesion_invitado", "sp_finalizar_sesion_invitado",
    "sp_expirar_sesiones_invitado",
    "sp_registrar_auditoria", "sp_obtener_auditoria", "sp_metricas_dashboard",
    "sp_crear_demo_propietario", "sp_obtener_demos_visibles", "sp_obtener_demo",
})

PROCEDIMIENTOS = PROCEDIMIENTOS_BASE | PROCEDIMIENTOS_ADMIN


class SesionSP:
    """Ejecuta Stored Procedures sobre una conexión abierta dentro de una transacción."""

    def __init__(self, conexion: pymysql.connections.Connection):
        self._conexion = conexion

    def llamar(self, procedimiento: str, *parametros: Any) -> list[dict]:
        if procedimiento not in PROCEDIMIENTOS:
            raise ValueError(f"Procedimiento no permitido: {procedimiento}")

        # El nombre sale de la lista fija; los valores siempre van enlazados (%s).
        marcadores = ", ".join(["%s"] * len(parametros))
        sentencia = f"CALL {procedimiento}({marcadores})"
        try:
            with self._conexion.cursor() as cursor:
                cursor.execute(sentencia, parametros)
                filas = list(cursor.fetchall())
                while cursor.nextset():
                    pass
            return filas
        except pymysql.err.IntegrityError as error:
            raise _traducir_integridad(error) from error
        except pymysql.err.DataError as error:
            raise SolicitudInvalida("Algún valor está fuera del rango permitido por la base de datos") from error
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as error:
            logger.error("Fallo de RDS al ejecutar %s (código %s)", procedimiento, error.args[0] if error.args else "?")
            raise BaseDatosNoDisponible("Se perdió la conexión con Amazon RDS") from error


class Database:
    """Abre conexiones a Amazon RDS y controla las transacciones."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _conectar(self) -> pymysql.connections.Connection:
        try:
            return pymysql.connect(
                host=self._settings.db_host,
                port=self._settings.db_port,
                user=self._settings.db_user,
                password=self._settings.db_password,
                database=self._settings.db_name,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=self._settings.db_connect_timeout,
            )
        except pymysql.err.MySQLError as error:
            logger.error("No se pudo conectar a RDS (código %s)", error.args[0] if error.args else "?")
            raise BaseDatosNoDisponible("La base de datos en Amazon RDS no está disponible") from error

    @contextmanager
    def transaccion(self) -> Iterator[SesionSP]:
        """Confirma todo al salir del bloque o revierte si hubo un error."""
        conexion = self._conectar()
        try:
            yield SesionSP(conexion)
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def verificar(self) -> None:
        conexion = self._conectar()
        try:
            conexion.ping(reconnect=False)
        finally:
            conexion.close()


def _traducir_integridad(error: pymysql.err.IntegrityError) -> Exception:
    codigo = error.args[0] if error.args else None
    if codigo == 1062:
        return Conflicto("Ya existe un registro con esos datos (valor duplicado)")
    if codigo == 1451:
        return Conflicto("No se puede eliminar: el registro se usa en otra tabla (por ejemplo, en una DEMO)")
    if codigo == 1452:
        return SolicitudInvalida("Se hace referencia a un registro que no existe")
    return Conflicto("La operación viola una regla de integridad de la base de datos")
