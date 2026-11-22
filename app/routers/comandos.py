from asyncio import to_thread

from fastapi import APIRouter, Depends, Path, status

from app.core.autorizacion import acceso_vehiculo, solo_admin
from app.dependencies import Contenedor, get_contenedor
from app.schemas.comando import ComandoActualizar, ComandoCrear, ComandoCreado, ComandoRespuesta
from app.schemas.comunes import Mensaje, respuestas_error

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/comandos", tags=["Comandos"])
IdVehiculo = Path(ge=1, description="Identificador del vehículo")
IdComando = Path(ge=1, description="Identificador del comando")


@router.get("", response_model=list[ComandoRespuesta], summary="Catálogo de comandos del vehículo",
            description="Comandos ordenados por código.\n\n**SP:** `sp_obtener_vehiculo`, "
                        "`sp_obtener_comandos_vehiculo`",
            dependencies=[Depends(acceso_vehiculo)], responses=respuestas_error(401, 403, 404, 503))
async def listar(id_vehiculo: int = IdVehiculo, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.comandos.listar, id_vehiculo)


@router.post("", response_model=ComandoCreado, status_code=status.HTTP_201_CREATED,
             summary="Agregar un comando al catálogo",
             description="Crea un comando nuevo; **no** lo ejecuta. Para mover el vehículo usa "
                         "`POST /vehiculos/{id}/movimientos`. Nombre y código no pueden repetirse en el vehículo.\n\n"
                         "**SP:** `sp_obtener_vehiculo`, `sp_crear_comando`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
async def crear(datos: ComandoCrear, id_vehiculo: int = IdVehiculo, c: Contenedor = Depends(get_contenedor)):
    id_comando = await to_thread(c.comandos.crear, id_vehiculo, datos)
    return {"mensaje": "Comando agregado al catálogo", "id_comando": id_comando}


@router.post("/{id_comando}/actualizar", response_model=ComandoRespuesta, summary="Actualizar comando",
             description="Cambia solo los campos enviados.\n\n**SP:** `sp_obtener_comandos_vehiculo`, "
                         "`sp_actualizar_comando`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
async def actualizar(datos: ComandoActualizar, id_vehiculo: int = IdVehiculo, id_comando: int = IdComando,
                     c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.comandos.actualizar, id_vehiculo, id_comando, datos)


@router.post("/{id_comando}/eliminar", response_model=Mensaje, summary="Eliminar comando",
             description="Requiere `X-API-Key`. Responde 409 si el comando se usa en una DEMO.\n\n"
                         "**SP:** `sp_obtener_comandos_vehiculo`, `sp_eliminar_comando`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
async def eliminar(id_vehiculo: int = IdVehiculo, id_comando: int = IdComando,
                   c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.comandos.eliminar, id_vehiculo, id_comando)
    return {"mensaje": f"Comando {id_comando} eliminado"}
