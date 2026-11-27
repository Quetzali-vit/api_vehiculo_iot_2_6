"""Inicio y cierre de sesión (práctica 4.3)."""

from asyncio import to_thread

from fastapi import Depends

from app.core.autorizacion import identidad_actual, token_actual
from app.schemas.admin import LoginRespuesta, LoginSolicitud, YoRespuesta
from app.schemas.comunes import Mensaje, respuestas_error
from app.services.auth_service import Identidad
from app.routers.base import Controlador, Ruta


class AuthControlador(Controlador):
    """Inicio y cierre de sesión (práctica 4.3)."""

    prefijo = "/auth"
    etiquetas = ["Autenticación"]

    @Ruta.post("/login", response_model=LoginRespuesta, summary="Iniciar sesión",
               description="Devuelve un token de sesión para el encabezado "
                           "`Authorization: Bearer <token>`. La contraseña viaja por HTTPS y "
                           "se compara contra un hash PBKDF2; la base nunca la guarda en claro.\n\n"
                           "**SP:** `sp_login_usuario`, `sp_crear_sesion`, `sp_registrar_auditoria`",
               responses=respuestas_error(401, 503))
    async def login(self, datos: LoginSolicitud):
        return await to_thread(self.c.auth.login, datos.correo, datos.contrasena)

    @Ruta.post("/logout", response_model=Mensaje, summary="Cerrar sesión",
               description="Revoca el token actual: deja de servir aunque no haya expirado.\n\n"
                           "**SP:** `sp_revocar_sesion`",
               responses=respuestas_error(401, 503))
    async def logout(self, token: str = Depends(token_actual)):
        await to_thread(self.c.auth.logout, token)
        return {"mensaje": "Sesión cerrada"}

    @Ruta.get("/yo", response_model=YoRespuesta, summary="Quién soy",
              description="Datos de la sesión vigente. El frontend lo usa para pintar el menú "
                          "del rol; la seguridad real está en cada endpoint, no en el menú.",
              responses=respuestas_error(401, 503))
    async def yo(self, identidad: Identidad = Depends(identidad_actual)):
        return {
            "id_usuario": identidad.id_usuario,
            "nombre": identidad.nombre,
            "correo": identidad.correo,
            "rol": identidad.rol,
            "invitado": identidad.invitado,
            "id_vehiculo_invitado": identidad.id_vehiculo_invitado,
            "segundos_restantes": identidad.segundos_restantes,
        }
