import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import ApiError, NoEncontrado
from app.dependencies import get_contenedor
from app.websocket.eventos import TipoEvento, crear_evento

logger = logging.getLogger(__name__)
router = APIRouter()

# Códigos de cierre propios (los 4000+ son de uso libre según el RFC)
CIERRE_SIN_SESION = 4401
CIERRE_SIN_PERMISO = 4403
CIERRE_NO_EXISTE = 4404


def _evento_estado(estado: dict) -> dict:
    return crear_evento(TipoEvento.ESTADO_ACTUAL, estado["id_vehiculo"], estado["comando"], estado["codigo"],
                        conectado=bool(estado["conectado"]), fecha_actualizacion=estado["fecha_actualizacion"])


@router.websocket("/ws/vehiculos/{id_vehiculo}")
async def monitorear(websocket: WebSocket, id_vehiculo: int):
    """Monitoreo de un vehículo. Documentado en README.md (Swagger no describe WebSocket).

    **Autorización (4.3).** El navegador no puede mandar encabezados al abrir un
    WebSocket, así que el token viaja en la cadena de consulta:

        wss://.../ws/vehiculos/1?token=<token de /auth/login o de una prueba>

    Se comprueba identidad **y** permiso sobre esa unidad antes de suscribir. Sin
    eso, cualquiera podría escuchar los eventos de un vehículo ajeno. CORS no
    aplica a WebSocket, de modo que esta es la única defensa del canal.
    """
    c = get_contenedor()
    token = websocket.query_params.get("token")

    identidad = await asyncio.to_thread(c.auth.identificar, token)
    if identidad is None:
        await websocket.close(code=CIERRE_SIN_SESION, reason="Sesion no valida")
        return

    try:
        await asyncio.to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo)
    except NoEncontrado:
        await websocket.close(code=CIERRE_NO_EXISTE, reason="El vehiculo no existe")
        return
    except ApiError:
        await websocket.close(code=CIERRE_SIN_PERMISO, reason="Sin permiso sobre esa unidad")
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

            # La sesión puede vencer o revocarse mientras el socket sigue abierto:
            # se vuelve a comprobar en cada mensaje, no solo al conectar.
            if not await _sigue_autorizado(c, token, id_vehiculo):
                await c.gestor_ws.enviar(websocket, crear_evento(
                    TipoEvento.ERROR, id_vehiculo, mensaje="La sesión terminó"))
                await websocket.close(code=CIERRE_SIN_SESION, reason="Sesion terminada")
                return

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


async def _sigue_autorizado(c, token: str | None, id_vehiculo: int) -> bool:
    try:
        identidad = await asyncio.to_thread(c.auth.identificar, token)
        if identidad is None:
            return False
        await asyncio.to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo)
        return True
    except ApiError:
        return False
    except Exception:
        logger.exception("No se pudo revalidar la sesión del WebSocket")
        return False
