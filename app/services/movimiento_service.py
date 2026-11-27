import asyncio

from app.core.exceptions import Conflicto
from app.db.database import Database
from app.repositories.estado_repository import EstadoRepository
from app.repositories.historial_repository import HistorialRepository
from app.schemas.movimiento import MovimientoSolicitud
from app.services.demo_executor import EjecutorDemos
from app.services.reglas import ReglasNegocio
from app.websocket.eventos import EventoWebSocket, TipoEvento
from app.websocket.manager import GestorWebSocket


class MovimientoService:
    """Movimiento individual: valida, guarda estado + historial en una transacción y luego notifica."""

    def __init__(self, db: Database, reglas: ReglasNegocio, estados: EstadoRepository,
                 historial: HistorialRepository, gestor: GestorWebSocket, ejecutor: EjecutorDemos,
                 origen_por_defecto: str):
        self._db = db
        self._reglas = reglas
        self._estados = estados
        self._historial = historial
        self._gestor = gestor
        self._ejecutor = ejecutor
        self._origen_por_defecto = origen_por_defecto

    async def ejecutar(self, id_vehiculo: int, solicitud: MovimientoSolicitud) -> dict:
        comando = await asyncio.to_thread(self._validar, id_vehiculo, solicitud)

        if self._ejecutor.en_curso(id_vehiculo) is not None:
            if comando["nombre"] != "DETENER":
                raise Conflicto("Hay una DEMO en ejecución; cancélala o envía el comando DETENER")
            await self._ejecutor.cancelar(id_vehiculo)  # DETENER tiene prioridad sobre la DEMO

        origen = solicitud.origen or self._origen_por_defecto
        conectado = await asyncio.to_thread(self._registrar, id_vehiculo, comando["id_comando"], origen)

        # Solo se notifica cuando RDS ya confirmó la transacción.
        evento = EventoWebSocket.crear(TipoEvento.MOVIMIENTO, id_vehiculo, comando["nombre"], comando["codigo"],
                              id_comando=comando["id_comando"], origen=origen, conectado=conectado)
        await self._gestor.publicar(id_vehiculo, evento)
        return evento

    def describir_comando(self, id_vehiculo: int, solicitud: MovimientoSolicitud) -> dict:
        """Resuelve a qué comando se refiere la solicitud, sin ejecutar nada.

        La capa de autorización (4.3) lo usa para saber si un invitado tiene
        permitido ese comando antes de mover el vehículo.
        """
        return self._validar(id_vehiculo, solicitud)

    def _validar(self, id_vehiculo: int, solicitud: MovimientoSolicitud) -> dict:
        with self._db.transaccion() as sesion:
            self._reglas.vehiculo_activo(sesion, id_vehiculo)
            if solicitud.id_comando is not None:
                comando = self._reglas.comando_del_vehiculo(sesion, id_vehiculo, solicitud.id_comando)
            else:
                comando = self._reglas.comando_por_codigo(sesion, id_vehiculo, solicitud.codigo)
            return self._reglas.comando_activo(comando)

    def _registrar(self, id_vehiculo: int, id_comando: int, origen: str) -> bool:
        with self._db.transaccion() as sesion:
            estado = self._estados.obtener(sesion, id_vehiculo)
            # No se asume conectado = 1 solo porque llegó una petición HTTP.
            conectado = bool(estado["conectado"]) if estado else False
            self._estados.actualizar(sesion, id_vehiculo, id_comando, conectado)
            self._historial.registrar(sesion, id_vehiculo, id_comando, origen)
        return conectado
