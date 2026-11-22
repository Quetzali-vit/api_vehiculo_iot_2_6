import logging
from asyncio import to_thread
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.dependencies import get_contenedor
from app.routers import (administracion, auth, comandos, demos, estado, historial, invitados,
                         movimientos, vehiculos, websocket)
from app.schemas.comunes import Mensaje, respuestas_error

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


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    contenedor = get_contenedor()  # valida las variables de entorno al arrancar
    await contenedor.invitados.iniciar_vigilancia()  # cierra las pruebas vencidas (4.3)
    logger.info("API lista en el puerto 8000 (Swagger en /docs)")
    yield
    await contenedor.invitados.detener_vigilancia()
    await contenedor.ejecutor.cancelar_todas()


app = FastAPI(
    title="API Vehículo IoT",
    description=DESCRIPCION,
    version="1.0.0",
    openapi_tags=ETIQUETAS,
    lifespan=ciclo_de_vida,
    docs_url=None,
)

# El frontend vive en otro origen (GitHub Pages), así que el navegador exige CORS.
# CORS no es autenticación: la protección real son la sesión y los permisos por recurso.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    allow_credentials=False,
    max_age=600,
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


@app.get("/docs", include_in_schema=False)
async def documentacion():
    pagina = get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{app.title} - Swagger UI")
    html = pagina.body.decode().replace("</head>", f"{MODO_CLARO}</head>", 1)
    return HTMLResponse(html)


@app.exception_handler(ApiError)
async def manejar_error_api(request: Request, error: ApiError):
    return JSONResponse(status_code=error.status_code, content={"detail": error.mensaje})


@app.exception_handler(Exception)
async def manejar_error_inesperado(request: Request, error: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/", tags=["Sistema"], summary="Estado del servicio")
async def raiz():
    return {"api": "Vehículo IoT", "estado": "Online", "documentacion": "/docs"}


@app.get("/salud", response_model=Mensaje, tags=["Sistema"], summary="Comprobar la conexión con Amazon RDS",
         responses=respuestas_error(503))
async def salud():
    await to_thread(get_contenedor().db.verificar)
    return {"mensaje": "Conexión con Amazon RDS correcta"}


for router in (auth.router, administracion.router, administracion.publico, invitados.router,
               vehiculos.router, comandos.router, estado.router, movimientos.router,
               historial.router, demos.router, websocket.router):
    app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
