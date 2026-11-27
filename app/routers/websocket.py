import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.core.exceptions import ApiError, NoEncontrado
from app.routers.base import Controlador, Ruta
from app.websocket.eventos import EventoWebSocket, TipoEvento

logger = logging.getLogger(__name__)


class WebSocketControlador(Controlador):
    """Canal en vivo de una unidad: `wss://quetzali-iot.duckdns.org/ws/vehiculos/{id}`.

    Swagger no describe WebSocket; los mensajes están documentados en README.md.
    """

    CIERRE_NO_EXISTE = 4404

    @Ruta.websocket("/ws/vehiculos/{id_vehiculo}")
    async def monitorear(self, websocket: WebSocket, id_vehiculo: int):
        """Escucha en vivo de una unidad.

        Cualquiera puede ESCUCHAR una unidad activa sin token:

            wss://quetzali-iot.duckdns.org/ws/vehiculos/1

        Escuchar no mueve nada: los movimientos van por REST (POST /vehiculos/{id}/movimientos)
        y ahí sí se exige sesión con permiso sobre la unidad. Una unidad inexistente o
        inactiva responde con el código 4404.
        """
        c = self.c

        try:
            unidad = await asyncio.to_thread(c.admin.obtener_unidad, id_vehiculo)
        except ApiError:
            unidad = None
        if unidad is None or not unidad.get("activo"):
            await websocket.accept()
            await websocket.close(code=self.CIERRE_NO_EXISTE, reason="El vehiculo no existe o esta inactivo")
            return

        await websocket.accept()

        try:
            estado = await asyncio.to_thread(c.estados.obtener, id_vehiculo)
        except ApiError as error:
            await c.gestor_ws.enviar(websocket, EventoWebSocket.crear(TipoEvento.ERROR, id_vehiculo,
                                                                      mensaje=error.mensaje))
            await websocket.close(code=self.CIERRE_NO_EXISTE if isinstance(error, NoEncontrado) else 1011)
            return

        await c.gestor_ws.conectar(id_vehiculo, websocket)
        try:
            await c.gestor_ws.enviar(websocket, EventoWebSocket.de_estado(estado))
            while True:
                texto = (await websocket.receive_text()).strip().lower()

                if texto == "ping":
                    await c.gestor_ws.enviar(websocket, EventoWebSocket.crear(TipoEvento.PONG, id_vehiculo))
                elif texto == "estado":
                    estado = await asyncio.to_thread(c.estados.obtener, id_vehiculo)
                    await c.gestor_ws.enviar(websocket, EventoWebSocket.de_estado(estado))
                else:
                    await c.gestor_ws.enviar(websocket, EventoWebSocket.crear(
                        TipoEvento.ERROR, id_vehiculo, mensaje="Mensaje no reconocido. Usa 'ping' o 'estado'."))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Error en el WebSocket del vehículo %s", id_vehiculo)
        finally:
            await c.gestor_ws.desconectar(id_vehiculo, websocket)
