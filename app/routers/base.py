"""Base orientada a objetos de los controladores HTTP.

Cada grupo de endpoints es una CLASE que hereda de `Controlador`:

    class VehiculosControlador(Controlador):
        prefijo = "/vehiculos"
        etiquetas = ["Vehículos"]

        @Ruta.get("", summary="Listar vehículos")
        async def listar(self):
            return await to_thread(self.c.vehiculos.listar)

* `Ruta` es un objeto que describe un endpoint (método HTTP, camino y opciones de
  Swagger) y se pega al método como decorador.
* `Controlador.__init__` recorre los métodos de la clase EN EL ORDEN EN QUE SE
  DEFINIERON y los registra en su propio `APIRouter`. El orden importa: por
  ejemplo `/demos/ejecucion` debe registrarse antes que `/demos/{id_demo}`.
* `self.c` es el contenedor de servicios (inyección de dependencias): el
  controlador no crea servicios, los pide.
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from app.dependencies import Contenedor, get_contenedor


class Ruta:
    """Descripción de un endpoint: método HTTP, camino y opciones de FastAPI/Swagger."""

    ATRIBUTO = "__ruta__"
    WEBSOCKET = "WEBSOCKET"

    def __init__(self, metodo: str, camino: str, opciones: dict[str, Any]):
        self.metodo = metodo
        self.camino = camino
        self.opciones = opciones

    def __call__(self, metodo_controlador: Callable) -> Callable:
        """Usada como decorador: marca el método para que el controlador lo registre."""
        setattr(metodo_controlador, self.ATRIBUTO, self)
        return metodo_controlador

    @classmethod
    def get(cls, camino: str, **opciones: Any) -> "Ruta":
        return cls("GET", camino, opciones)

    @classmethod
    def post(cls, camino: str, **opciones: Any) -> "Ruta":
        return cls("POST", camino, opciones)

    @classmethod
    def websocket(cls, camino: str) -> "Ruta":
        return cls(cls.WEBSOCKET, camino, {})

    @classmethod
    def de(cls, miembro: Any) -> "Ruta | None":
        """La ruta pegada a un miembro de la clase, o None si no es un endpoint."""
        return getattr(miembro, cls.ATRIBUTO, None)

    def registrar_en(self, router: APIRouter, endpoint: Callable) -> None:
        if self.metodo == self.WEBSOCKET:
            router.add_api_websocket_route(self.camino, endpoint)
        else:
            router.add_api_route(self.camino, endpoint, methods=[self.metodo], **self.opciones)


class Controlador:
    """Clase base: arma un APIRouter con los métodos marcados con `Ruta`."""

    prefijo: str = ""
    etiquetas: list[str] = []

    def __init__(self) -> None:
        self.router = APIRouter(prefix=self.prefijo, tags=list(self.etiquetas))
        for nombre, miembro in self._miembros_en_orden():
            ruta = Ruta.de(miembro)
            if ruta is not None:
                # getattr(self, ...) entrega el método ENLAZADO a esta instancia:
                # FastAPI ya no ve `self` en la firma, solo los parámetros reales.
                ruta.registrar_en(self.router, getattr(self, nombre))

    @property
    def c(self) -> Contenedor:
        """Servicios de la aplicación (una sola instancia compartida)."""
        return get_contenedor()

    @classmethod
    def _miembros_en_orden(cls) -> list[tuple[str, Any]]:
        """Miembros de la clase y de sus padres, en orden de definición."""
        miembros: dict[str, Any] = {}
        for clase in reversed(cls.__mro__):
            miembros.update(vars(clase))
        return list(miembros.items())
