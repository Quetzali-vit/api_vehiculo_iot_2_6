"""Acceso a los SP de la práctica 4.3: usuarios, sesiones, modelos, unidades,
invitados y auditoría. Mismo estilo que los repositorios de 4.1/4.2: una clase
por área, sin lógica de negocio y sin SQL concatenado."""

from app.db.database import SesionSP
from app.repositories.base import Repositorio


class UsuarioRepository(Repositorio):
    """Usuarios, roles y sesiones de login."""

    def por_correo(self, sesion: SesionSP, correo: str) -> dict | None:
        filas = sesion.llamar("sp_login_usuario", correo)
        return self._primera(filas)

    def crear(self, sesion: SesionSP, nombre: str, correo: str, hash_contrasena: str,
              rol: str, telefono: str | None) -> int:
        filas = sesion.llamar("sp_crear_usuario", nombre, correo, hash_contrasena, rol, telefono)
        return int(filas[0]["id_usuario"])

    def listar(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_obtener_usuarios")

    def obtener(self, sesion: SesionSP, id_usuario: int) -> dict | None:
        filas = sesion.llamar("sp_obtener_usuario", id_usuario)
        return self._primera(filas)

    def actualizar(self, sesion: SesionSP, id_usuario: int, nombre: str | None, telefono: str | None,
                   hash_contrasena: str | None, rol: str | None, activo: bool | None) -> dict | None:
        filas = sesion.llamar("sp_actualizar_usuario", id_usuario, nombre, telefono,
                              hash_contrasena, rol, None if activo is None else int(activo))
        return self._primera(filas)

    # ----- sesiones de login -----

    def crear_sesion(self, sesion: SesionSP, id_usuario: int, token_hash: str, horas: int) -> int:
        filas = sesion.llamar("sp_crear_sesion", id_usuario, token_hash, horas)
        return int(filas[0]["id_sesion"])

    def obtener_sesion(self, sesion: SesionSP, token_hash: str) -> dict | None:
        filas = sesion.llamar("sp_obtener_sesion", token_hash)
        return self._primera(filas)

    def revocar_sesion(self, sesion: SesionSP, token_hash: str) -> int:
        filas = sesion.llamar("sp_revocar_sesion", token_hash)
        return int(filas[0]["revocadas"]) if filas else 0


class ModeloRepository(Repositorio):
    """Modelos comerciales (lo que la empresa vende)."""

    def crear(self, sesion: SesionSP, nombre: str, descripcion: str | None,
              microcontrolador: str | None, precio, imagen_url: str | None) -> int:
        filas = sesion.llamar("sp_crear_modelo", nombre, descripcion, microcontrolador, precio, imagen_url)
        return int(filas[0]["id_modelo"])

    def listar(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_obtener_modelos")

    def obtener(self, sesion: SesionSP, id_modelo: int) -> dict | None:
        filas = sesion.llamar("sp_obtener_modelo", id_modelo)
        return self._primera(filas)

    def actualizar(self, sesion: SesionSP, id_modelo: int, nombre: str | None, descripcion: str | None,
                   microcontrolador: str | None, precio, imagen_url: str | None,
                   activo: bool | None) -> dict | None:
        filas = sesion.llamar("sp_actualizar_modelo", id_modelo, nombre, descripcion, microcontrolador,
                              precio, imagen_url, None if activo is None else int(activo))
        return self._primera(filas)

    def catalogo_publico(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_catalogo_publico")


class UnidadRepository(Repositorio):
    """Vista comercial de la tabla vehiculos (unidades físicas)."""

    def listar(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_obtener_unidades")

    def obtener(self, sesion: SesionSP, id_vehiculo: int) -> dict | None:
        filas = sesion.llamar("sp_obtener_unidad", id_vehiculo)
        return self._primera(filas)

    def actualizar_comercial(self, sesion: SesionSP, id_vehiculo: int, id_modelo: int | None,
                             numero_serie: str | None, estado_comercial: str | None) -> dict | None:
        filas = sesion.llamar("sp_actualizar_comercial", id_vehiculo, id_modelo,
                              numero_serie, estado_comercial)
        return self._primera(filas)

    def asignar(self, sesion: SesionSP, id_vehiculo: int, id_usuario: int | None) -> dict | None:
        filas = sesion.llamar("sp_asignar_unidad", id_vehiculo, id_usuario)
        return self._primera(filas)

    def mis_vehiculos(self, sesion: SesionSP, id_usuario: int) -> list[dict]:
        return sesion.llamar("sp_obtener_mis_vehiculos", id_usuario)

    def metricas(self, sesion: SesionSP) -> dict:
        filas = sesion.llamar("sp_metricas_dashboard")
        return filas[0] if filas else {}


class InvitadoRepository(Repositorio):
    """Sesiones temporales de prueba comercial."""

    def crear(self, sesion: SesionSP, id_modelo: int | None, token_hash: str,
              nombre: str | None, minutos: int) -> dict | None:
        filas = sesion.llamar("sp_crear_sesion_invitado", id_modelo, token_hash, nombre, minutos)
        return self._primera(filas)

    def obtener(self, sesion: SesionSP, token_hash: str) -> dict | None:
        filas = sesion.llamar("sp_obtener_sesion_invitado", token_hash)
        return self._primera(filas)

    def finalizar(self, sesion: SesionSP, token_hash: str, motivo: str) -> int:
        filas = sesion.llamar("sp_finalizar_sesion_invitado", token_hash, motivo)
        return int(filas[0]["finalizadas"]) if filas else 0

    def reserva_activa(self, sesion: SesionSP, id_vehiculo: int) -> bool:
        """¿Hay una prueba de invitado vigente sobre esa unidad?"""
        filas = sesion.llamar("sp_reserva_activa_vehiculo", id_vehiculo)
        return bool(filas and int(filas[0]["reservas"]) > 0)

    def expirar_vencidas(self, sesion: SesionSP) -> list[int]:
        """Cierra las vencidas y devuelve los vehículos que quedaron libres."""
        filas = sesion.llamar("sp_expirar_sesiones_invitado")
        return [int(f["id_vehiculo"]) for f in filas]


class AuditoriaRepository(Repositorio):
    """Bitácora de acciones sensibles. Nunca guarda contraseñas ni tokens."""

    def registrar(self, sesion: SesionSP, id_usuario: int | None, actor: str, accion: str,
                  recurso: str, id_recurso: str | None, resultado: str, detalle: str | None) -> None:
        sesion.llamar("sp_registrar_auditoria", id_usuario, actor, accion, recurso,
                      id_recurso, resultado, (detalle or "")[:255] or None)

    def listar(self, sesion: SesionSP, limite: int = 50) -> list[dict]:
        return sesion.llamar("sp_obtener_auditoria", limite)


class DemoAdminRepository(Repositorio):
    """Demos con dueño: de fábrica (sin dueño) o privadas de un comprador."""

    def crear(self, sesion: SesionSP, id_vehiculo: int, nombre: str,
              descripcion: str | None, id_propietario: int | None) -> int:
        filas = sesion.llamar("sp_crear_demo_propietario", id_vehiculo, nombre, descripcion, id_propietario)
        return int(filas[0]["id_demo"])

    def visibles(self, sesion: SesionSP, id_vehiculo: int, id_usuario: int | None) -> list[dict]:
        return sesion.llamar("sp_obtener_demos_visibles", id_vehiculo, id_usuario)

    def obtener(self, sesion: SesionSP, id_demo: int) -> dict | None:
        filas = sesion.llamar("sp_obtener_demo", id_demo)
        return self._primera(filas)


class SoporteRepository(Repositorio):
    """Autorizaciones de soporte operativo que el comprador da al Administrador (005)."""

    def vigente(self, sesion: SesionSP, id_vehiculo: int) -> dict | None:
        filas = sesion.llamar("sp_soporte_vigente", id_vehiculo)
        return self._primera(filas)

    def autorizar(self, sesion: SesionSP, id_vehiculo: int, id_usuario: int, minutos: int) -> dict | None:
        filas = sesion.llamar("sp_autorizar_soporte", id_vehiculo, id_usuario, minutos)
        return self._primera(filas)

    def revocar(self, sesion: SesionSP, id_vehiculo: int, id_usuario: int) -> int:
        filas = sesion.llamar("sp_revocar_soporte", id_vehiculo, id_usuario)
        return int(filas[0]["revocadas"]) if filas else 0


class SesionesRepository(Repositorio):
    """Vistas de sesiones y bitácora para la cuenta de cliente del administrador (006)."""

    def sesiones_activas(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_sesiones_activas")

    def pruebas_activas(self, sesion: SesionSP) -> list[dict]:
        return sesion.llamar("sp_pruebas_activas")

    def auditoria_usuario(self, sesion: SesionSP, id_usuario: int, correo: str, limite: int) -> list[dict]:
        return sesion.llamar("sp_auditoria_usuario", id_usuario, correo, limite)
