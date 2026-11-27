"""Pruebas comerciales para clientes potenciales (Invitado)."""

from asyncio import to_thread

from fastapi import Depends, status

from app.core.autorizacion import identidad_actual, token_actual
from app.schemas.admin import PruebaCreada, PruebaRespuesta, PruebaSolicitud
from app.schemas.comunes import Mensaje, respuestas_error
from app.services.auth_service import Identidad
from app.routers.base import Controlador, Ruta


class InvitadosControlador(Controlador):
    """Pruebas comerciales para clientes potenciales (Invitado)."""

    prefijo = "/invitados"
    etiquetas = ["Invitados"]

    @Ruta.post("/pruebas", response_model=PruebaCreada, status_code=status.HTTP_201_CREATED,
               summary="Iniciar una prueba de exhibición",
               description="Reserva **en exclusiva** una unidad en estado EXHIBICION por unos "
                           "minutos y devuelve un token temporal. Si todas están ocupadas responde "
                           "409. Nunca se ofrece una unidad vendida.\n\n"
                           "**SP:** `sp_crear_sesion_invitado`, `sp_registrar_auditoria`",
               responses=respuestas_error(404, 409, 503))
    async def iniciar(self, datos: PruebaSolicitud):
        return await to_thread(self.c.invitados.iniciar, datos.id_modelo, datos.nombre)

    @Ruta.get("/pruebas/actual", response_model=PruebaRespuesta,
              summary="Estado de mi prueba",
              description="Tiempo restante, unidad reservada y comandos permitidos.\n\n"
                          "**SP:** `sp_obtener_sesion_invitado`",
              responses=respuestas_error(401, 404, 503))
    async def actual(self, token: str = Depends(token_actual)):
        return await to_thread(self.c.invitados.estado, token)

    @Ruta.post("/pruebas/terminar", response_model=Mensaje,
               summary="Terminar mi prueba",
               description="Libera la unidad y le manda DETENER. Al vencer el tiempo ocurre lo "
                           "mismo de forma automática.\n\n"
                           "**SP:** `sp_finalizar_sesion_invitado`, `sp_actualizar_estado`, "
                           "`sp_registrar_historial`",
               responses=respuestas_error(401, 404, 503))
    async def terminar(self, token: str = Depends(token_actual)):
        return await self.c.invitados.terminar(token, "CERRADA")

    @Ruta.get("/pruebas/yo", response_model=PruebaRespuesta,
              summary="Comprobar mi sesión de invitado",
              description="Igual que `/pruebas/actual`, pero resolviendo la identidad desde el "
                           "token como lo hace el resto de la API.",
              responses=respuestas_error(401, 404, 503))
    async def yo(self, identidad: Identidad = Depends(identidad_actual), token: str = Depends(token_actual)):
        return await to_thread(self.c.invitados.estado, token)
