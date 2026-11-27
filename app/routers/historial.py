from asyncio import to_thread

from fastapi import Depends, Path, Query

from app.core.autorizacion import identidad_actual
from app.schemas.comunes import respuestas_error
from app.schemas.historial import HistorialRespuesta
from app.services.auth_service import Identidad
from app.routers.base import Controlador, Ruta


class HistorialControlador(Controlador):
    """Bitácora de los 10 movimientos individuales más recientes."""

    prefijo = "/vehiculos/{id_vehiculo}/historial"
    etiquetas = ["Historial"]

    @Ruta.get("", response_model=HistorialRespuesta, summary="Últimos 10 movimientos individuales",
              description="Devuelve como máximo 10 movimientos individuales, del más reciente al más antiguo. "
                          "`total_registrados` indica cuántos hay en RDS y `devueltos` cuántos se muestran. "
                          "Si hay menos de 10, devuelve solo los disponibles. Los movimientos de DEMO nunca "
                          "aparecen porque no se guardan en el historial.\n\n"
                          "**Autorización (4.3).** Requiere sesión y acceso a esa unidad. Cambiar el id en la "
                          "URL por el de otro comprador responde 404: la API no confirma siquiera que exista.\n\n"
                          "**SP:** `sp_obtener_vehiculo`, `sp_obtener_historial`",
              responses=respuestas_error(401, 403, 404, 503))
    async def ultimos(self, id_vehiculo: int = Path(ge=1, description="Identificador del vehículo"),
                      limite: int = Query(10, ge=1, le=10, description="Cantidad máxima de registros (1 a 10)"),
                      identidad: Identidad = Depends(identidad_actual)):
        await to_thread(self.c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo)
        return await to_thread(self.c.historial.ultimos, id_vehiculo, limite)
