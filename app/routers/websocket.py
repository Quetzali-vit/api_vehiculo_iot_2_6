import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import ApiError, NoEncontrado
from app.dependencies import get_contenedor
from app.websocket.eventos import TipoEvento, crear_evento
from app.websocket.manager import CANAL_GENERAL

logger = logging.getLogger(__name__)
router = APIRouter()

CIERRE_NO_EXISTE = 4404


def _evento_estado(estado: dict) -> dict:
    return crear_evento(TipoEvento.ESTADO_ACTUAL, estado["id_vehiculo"], estado["comando"], estado["codigo"],
                        conectado=bool(estado["conectado"]), fecha_actualizacion=estado["fecha_actualizacion"])


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def monitorear(websocket: WebSocket, id_vehiculo: int):
    """Escucha en vivo de una unidad. Documentado en README.md (Swagger no describe WebSocket).

    Cualquiera puede ESCUCHAR una unidad activa sin token:

        wss://quetzali-iot.duckdns.org/ws/vehiculos/1

    Escuchar no mueve nada: los movimientos van por REST (POST /vehiculos/{id}/movimientos)
    y ahí sí se exige sesión con permiso sobre la unidad. Una unidad inexistente o
    inactiva responde con el código 4404.
    """
    c = get_contenedor()

    try:
        unidad = await asyncio.to_thread(c.admin.obtener_unidad, id_vehiculo)
    except ApiError:
        unidad = None
    if unidad is None or not unidad.get("activo"):
        await websocket.accept()
        await websocket.close(code=CIERRE_NO_EXISTE, reason="El vehiculo no existe o esta inactivo")
        return

    await websocket.accept()

    try:
        estado = await asyncio.to_thread(c.estados.obtener, id_vehiculo)
    except ApiError as error:
        await c.gestor_ws.enviar(websocket, crear_evento(TipoEvento.ERROR, id_vehiculo, mensaje=error.mensaje))
        await websocket.close(code=CIERRE_NO_EXISTE if isinstance(error, NoEncontrado) else 1011)
        return

    await c.gestor_ws.conectar(id_vehiculo, websocket)
    try:
        await c.gestor_ws.enviar(websocket, _evento_estado(estado))
        while True:
            texto = (await websocket.receive_text()).strip().lower()

            if texto == "ping":
                await c.gestor_ws.enviar(websocket, crear_evento(TipoEvento.PONG, id_vehiculo))
            elif texto == "estado":
                estado = await asyncio.to_thread(c.estados.obtener, id_vehiculo)
                await c.gestor_ws.enviar(websocket, _evento_estado(estado))
            else:
                await c.gestor_ws.enviar(websocket, crear_evento(
                    TipoEvento.ERROR, id_vehiculo, mensaje="Mensaje no reconocido. Usa 'ping' o 'estado'."))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error en el WebSocket del vehículo %s", id_vehiculo)
    finally:
        await c.gestor_ws.desconectar(id_vehiculo, websocket)


@router.websocket("/ws/vehiculos")
async def monitorear_todas(websocket: WebSocket):
    """Canal general: escucha en vivo TODAS las unidades activas con una sola URL, sin token.

        wss://quetzali-iot.duckdns.org/ws/vehiculos

    Al conectarse recibe un `estado_actual` por cada unidad activa; después llega cada
    evento de cualquier unidad, con su `id_vehiculo`. Escuchar no mueve nada.
    """
    c = get_contenedor()
    await websocket.accept()

    try:
        unidades = await asyncio.to_thread(c.admin.listar_unidades)
    except ApiError as error:
        await websocket.close(code=1011, reason=error.mensaje[:120])
        return

    await c.gestor_ws.conectar(CANAL_GENERAL, websocket)
    try:
        for unidad in unidades:
            if not unidad.get("activo"):
                continue
            try:
                estado = await asyncio.to_thread(c.estados.obtener, unidad["id_vehiculo"])
            except ApiError:
                continue
            await c.gestor_ws.enviar(websocket, _evento_estado(estado))
        while True:
            texto = (await websocket.receive_text()).strip().lower()
            if texto == "ping":
                await c.gestor_ws.enviar(websocket, crear_evento(TipoEvento.PONG, CANAL_GENERAL))
            else:
                await c.gestor_ws.enviar(websocket, crear_evento(
                    TipoEvento.ERROR, CANAL_GENERAL, mensaje="Mensaje no reconocido. Usa 'ping'."))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error en el canal general de WebSocket")
    finally:
        await c.gestor_ws.desconectar(CANAL_GENERAL, websocket)
