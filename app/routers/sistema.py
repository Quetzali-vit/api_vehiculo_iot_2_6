from asyncio import to_thread

from app.routers.base import Controlador, Ruta
from app.schemas.comunes import Mensaje, respuestas_error


class SistemaControlador(Controlador):
    """Información y salud del servicio."""

    etiquetas = ["Sistema"]

    @Ruta.get("/", summary="Estado del servicio")
    async def raiz(self):
        return {"api": "Vehículo IoT", "estado": "Online", "documentacion": "/docs"}

    @Ruta.get("/salud", response_model=Mensaje, summary="Comprobar la conexión con Amazon RDS",
              responses=respuestas_error(503))
    async def salud(self):
        await to_thread(self.c.db.verificar)
        return {"mensaje": "Conexión con Amazon RDS correcta"}
