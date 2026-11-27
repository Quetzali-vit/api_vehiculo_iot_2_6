from asyncio import to_thread

from fastapi import Depends, Path, status

from app.core.autorizacion import acceso_vehiculo, solo_admin
from app.schemas.comunes import Mensaje, respuestas_error
from app.schemas.vehiculo import (VehiculoActualizar, VehiculoCrear, VehiculoCreado, VehiculoDetalle,
                                  VehiculoRespuesta)
from app.routers.base import Controlador, Ruta

IdVehiculo = Path(ge=1, description="Identificador del vehículo")


class VehiculosControlador(Controlador):
    """Alta, consulta, actualización y baja de vehículos."""

    prefijo = "/vehiculos"
    etiquetas = ["Vehículos"]

    @Ruta.get("", response_model=list[VehiculoRespuesta], summary="Listar vehículos",
              description="Devuelve todos los vehículos registrados en RDS. Es el inventario de la "
                          "empresa, así que en 4.3 solo lo ve el Administrador; un comprador usa "
                          "`GET /mis-vehiculos`.\n\n**SP:** `sp_obtener_vehiculos`",
              dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
    async def listar(self):
        return await to_thread(self.c.vehiculos.listar)

    @Ruta.get("/{id_vehiculo}", response_model=VehiculoDetalle, summary="Consultar un vehículo",
              description="Vehículo con su catálogo de comandos, su último estado y sus DEMO.\n\n"
                          "**SP:** `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo`, `sp_obtener_estado`, "
                          "`sp_obtener_demos`\n\n"
                          "**Autorización (4.3).** Requiere sesión y acceso a esa unidad.",
              dependencies=[Depends(acceso_vehiculo)], responses=respuestas_error(401, 403, 404, 503))
    async def detalle(self, id_vehiculo: int = IdVehiculo):
        return await to_thread(self.c.vehiculos.detalle, id_vehiculo)

    @Ruta.post("", response_model=VehiculoCreado, status_code=status.HTTP_201_CREATED, summary="Registrar vehículo",
               description="Crea un vehículo nuevo (activo por defecto). En 4.3 conviene usar "
                           "`POST /admin/unidades`, que además registra modelo, número de serie y "
                           "estado comercial.\n\n**SP:** `sp_crear_vehiculo`",
               dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
    async def crear(self, datos: VehiculoCrear):
        id_vehiculo = await to_thread(self.c.vehiculos.crear, datos)
        return {"mensaje": "Vehículo registrado", "id_vehiculo": id_vehiculo}

    @Ruta.post("/{id_vehiculo}/actualizar", response_model=VehiculoRespuesta, summary="Actualizar vehículo",
               description="Cambia solo los campos enviados; con `activo: false` se desactiva.\n\n"
                           "**SP:** `sp_obtener_vehiculo`, `sp_actualizar_vehiculo`",
               dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
    async def actualizar(self, datos: VehiculoActualizar, id_vehiculo: int = IdVehiculo):
        return await to_thread(self.c.vehiculos.actualizar, id_vehiculo, datos)

    @Ruta.post("/{id_vehiculo}/eliminar", response_model=Mensaje, summary="Eliminar vehículo",
               description="Borra el vehículo y, en cascada, sus comandos, estado, historial y DEMO. "
                           "Requiere `X-API-Key`.\n\n**SP:** `sp_obtener_vehiculo`, `sp_eliminar_vehiculo`",
               dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
    async def eliminar(self, id_vehiculo: int = IdVehiculo):
        await to_thread(self.c.vehiculos.eliminar, id_vehiculo)
        return {"mensaje": f"Vehículo {id_vehiculo} eliminado"}
