import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.dependencies import get_contenedor
from app.routers.administracion import AdministracionControlador, PublicoControlador
from app.routers.auth import AuthControlador
from app.routers.base import Controlador
from app.routers.comandos import ComandosControlador
from app.routers.demos import DemosControlador
from app.routers.estado import EstadoControlador
from app.routers.historial import HistorialControlador
from app.routers.invitados import InvitadosControlador
from app.routers.movimientos import MovimientosControlador
from app.routers.sistema import SistemaControlador
from app.routers.vehiculos import VehiculosControlador
from app.routers.websocket import WebSocketControlador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api_vehiculo_iot")

DESCRIPCION = """
API REST del vehículo IoT, desplegada en **Amazon EC2** y conectada a la base **vehiculo_iot** de Amazon RDS.
Todas las operaciones usan los 21 Stored Procedures de las prácticas 2.3 y 2.4.

* **GET** para consultas y **POST** para crear, actualizar, eliminar y ejecutar acciones.
* Las operaciones de control y eliminación piden el encabezado `X-API-Key` (botón **Authorize**).
* Un **movimiento individual** actualiza el estado y se guarda en el historial.
* Una **DEMO** se transmite por WebSocket y actualiza el estado, pero **no** entra al historial.

**WebSocket:** `wss://quetzali-iot.duckdns.org/ws/vehiculos/{id_vehiculo}` (mensajes descritos en README.md).

**GitHub:** [Quetzali-vit/api_vehiculo_iot_2_6](https://github.com/Quetzali-vit/api_vehiculo_iot_2_6)
"""

ETIQUETAS = [
    {"name": "Vehículos", "description": "Alta, consulta, actualización y baja de vehículos."},
    {"name": "Comandos", "description": "Catálogo de comandos de cada vehículo."},
    {"name": "Estado", "description": "Último estado registrado del vehículo."},
    {"name": "Movimientos", "description": "Ejecución de un movimiento individual (genera historial)."},
    {"name": "Historial", "description": "Bitácora de los 10 movimientos individuales más recientes."},
    {"name": "DEMO", "description": "Secuencias de N movimientos y su ejecución por WebSocket."},
    {"name": "Sistema", "description": "Información y salud del servicio."},
    {"name": "Autenticación", "description": "Inicio y cierre de sesión (práctica 4.3)."},
    {"name": "Administración", "description": "Gestión comercial: modelos, unidades, clientes, "
                                              "asignaciones y auditoría (solo ADMIN)."},
    {"name": "Mis vehículos", "description": "Unidades del comprador que inició sesión."},
    {"name": "Catálogo público", "description": "Modelos y disponibilidad para clientes potenciales."},
    {"name": "Invitados", "description": "Pruebas de exhibición temporales y exclusivas."},
]


class AplicacionApi:
    """Arma la aplicación FastAPI: configuración, CORS, errores, Swagger y controladores."""

    # El orden importa: es el orden en que FastAPI prueba las rutas y el de Swagger
    CONTROLADORES: tuple[type[Controlador], ...] = (
        SistemaControlador, AuthControlador, AdministracionControlador, PublicoControlador,
        InvitadosControlador, VehiculosControlador, ComandosControlador, EstadoControlador,
        MovimientosControlador, HistorialControlador, DemosControlador, WebSocketControlador,
    )

    # Swagger UI siempre en modo claro, aunque el navegador o el sistema estén en modo oscuro.
    MODO_CLARO = """
<meta name="color-scheme" content="only light">
<style>html { color-scheme: only light; } body { background: #fff; }</style>
<script>
  new MutationObserver(() => document.documentElement.classList.remove("dark-mode"))
    .observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
</script>
"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.app = FastAPI(
            title="API Vehículo IoT",
            description=DESCRIPCION,
            version="1.0.0",
            openapi_tags=ETIQUETAS,
            lifespan=self._ciclo_de_vida,
            docs_url=None,
        )
        self._configurar_cors()
        self._registrar_errores()
        self.app.add_api_route("/docs", self.documentacion, methods=["GET"], include_in_schema=False)
        for controlador in self.CONTROLADORES:
            self.app.include_router(controlador().router)

    # ----- Arranque y parada -----
    @asynccontextmanager
    async def _ciclo_de_vida(self, app: FastAPI) -> AsyncIterator[None]:
        contenedor = get_contenedor()  # valida las variables de entorno al arrancar
        await contenedor.invitados.iniciar_vigilancia()  # cierra las pruebas vencidas (4.3)
        logger.info("API lista en el puerto 8000 (Swagger en /docs)")
        yield
        await contenedor.invitados.detener_vigilancia()
        await contenedor.ejecutor.cancelar_todas()

    # ----- CORS -----
    def _configurar_cors(self) -> None:
        # El frontend vive en otro origen (GitHub Pages), así que el navegador exige CORS.
        # CORS no es autenticación: la protección real son la sesión y los permisos por recurso.
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.settings.lista_cors,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key", "Authorization"],
            allow_credentials=False,
            max_age=600,
        )

    # ----- Errores -----
    def _registrar_errores(self) -> None:
        self.app.add_exception_handler(ApiError, self.manejar_error_api)
        self.app.add_exception_handler(Exception, self.manejar_error_inesperado)

    @staticmethod
    async def manejar_error_api(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.mensaje})

    @staticmethod
    async def manejar_error_inesperado(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

    # ----- Swagger -----
    async def documentacion(self) -> HTMLResponse:
        pagina = get_swagger_ui_html(openapi_url=self.app.openapi_url, title=f"{self.app.title} - Swagger UI")
        html = pagina.body.decode().replace("</head>", f"{self.MODO_CLARO}</head>", 1)
        return HTMLResponse(html)


# Objeto que arranca uvicorn: `uvicorn app.main:app`
app = AplicacionApi().app


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
