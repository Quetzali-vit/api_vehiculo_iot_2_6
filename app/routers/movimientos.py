from asyncio import to_thread

from fastapi import APIRouter, Depends, Path, status

from app.core.autorizacion import identidad_actual
from app.dependencies import Contenedor, get_contenedor
from app.schemas.comunes import respuestas_error
from app.schemas.movimiento import MovimientoRespuesta, MovimientoSolicitud
from app.services.auth_service import Identidad

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/movimientos", tags=["Movimientos"])


@router.post("", response_model=MovimientoRespuesta, status_code=status.HTTP_201_CREATED,
             summary="Ejecutar un movimiento individual",
             description="Valida que el vehículo exista y esté activo, y que el comando exista, esté activo y "
                         "pertenezca a ese vehículo. Después guarda el estado y el historial **en una sola "
                         "transacción** y, ya confirmada, publica el evento `movimiento` por WebSocket. "
                         "Si hay una DEMO en curso responde 409, salvo con DETENER, que la cancela primero.\n\n"
                         "**Autorización (4.3).** Requiere sesión. Un comprador solo mueve las unidades de "
                         "las que es propietario; un invitado, solo la unidad que tiene reservada y "
                         "únicamente con los comandos permitidos en una prueba. El Administrador **no** "
                         "puede mover una unidad ya vendida.\n\n"
                         "**SP:** `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo`, `sp_obtener_estado`, "
                         "`sp_actualizar_estado`, `sp_registrar_historial`",
             responses=respuestas_error(401, 403, 404, 409, 503))
async def ejecutar(solicitud: MovimientoSolicitud,
                   id_vehiculo: int = Path(ge=1, description="Identificador del vehículo"),
                   identidad: Identidad = Depends(identidad_actual),
                   c: Contenedor = Depends(get_contenedor)):
    # 1) ¿Puede esta persona operar ESTA unidad?
    await to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo, True)

    # 2) Si es invitado, además el comando debe estar en la lista corta de la prueba
    if identidad.invitado:
        comando = await to_thread(c.movimientos.describir_comando, id_vehiculo, solicitud)
        c.invitados.validar_comando(identidad, id_vehiculo, comando["nombre"])

    # 3) El origen lo decide el servidor según quién llama, no el navegador
    solicitud = solicitud.model_copy(update={"origen": _origen(identidad, solicitud.origen)})
    evento = await c.movimientos.ejecutar(id_vehiculo, solicitud)
    return {"mensaje": "Movimiento registrado y notificado", **evento}


def _origen(identidad: Identidad, pedido: str | None) -> str:
    """El historial debe decir la verdad sobre de dónde vino la orden."""
    if identidad.invitado:
        return "WEB-INVITADO"
    if identidad.es_admin:
        return "WEB-ADMIN"
    return (pedido or "WEB-CONTROL")[:30]
