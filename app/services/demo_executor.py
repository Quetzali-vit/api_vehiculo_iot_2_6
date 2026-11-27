import asyncio
import logging
from dataclasses import dataclass
from functools import partial

from app.core.exceptions import Conflicto, NoEncontrado
from app.services.demo_service import DemoService
from app.websocket.eventos import EventoWebSocket, TipoEvento
from app.websocket.manager import GestorWebSocket

logger = logging.getLogger(__name__)


@dataclass
class EjecucionDemo:
    id_demo: int
    nombre: str
    tarea: asyncio.Task


class EjecutorDemos:
    """Transmite por WebSocket los N movimientos de una DEMO sin bloquear la API."""

    def __init__(self, demos: DemoService, gestor: GestorWebSocket):
        self._demos = demos
        self._gestor = gestor
        self._en_curso: dict[int, EjecucionDemo] = {}
        self._lock = asyncio.Lock()

    def en_curso(self, id_vehiculo: int) -> EjecucionDemo | None:
        return self._en_curso.get(id_vehiculo)

    async def iniciar(self, id_vehiculo: int, id_demo: int) -> dict:
        async with self._lock:
            actual = self.en_curso(id_vehiculo)
            if actual is not None:
                raise Conflicto(f"El vehículo {id_vehiculo} ya está ejecutando la DEMO {actual.id_demo}")

            plan = await asyncio.to_thread(self._demos.preparar_ejecucion, id_vehiculo, id_demo)
            tarea = asyncio.create_task(self._ejecutar(id_vehiculo, plan), name=f"demo-{id_vehiculo}-{id_demo}")
            self._en_curso[id_vehiculo] = EjecucionDemo(id_demo, plan["demo"]["nombre"], tarea)
            tarea.add_done_callback(partial(self._al_terminar, id_vehiculo))

        return {"demo": plan["demo"]["nombre"], "total_movimientos": len(plan["movimientos"])}

    async def cancelar(self, id_vehiculo: int) -> EjecucionDemo:
        ejecucion = self.en_curso(id_vehiculo)
        if ejecucion is None:
            raise NoEncontrado(f"El vehículo {id_vehiculo} no tiene una DEMO en ejecución")
        ejecucion.tarea.cancel()
        # Se espera a que termine la limpieza (DETENER y aviso por WebSocket).
        await asyncio.wait({ejecucion.tarea}, timeout=10)
        return ejecucion

    async def cancelar_todas(self) -> None:
        for id_vehiculo in list(self._en_curso):
            await self.cancelar(id_vehiculo)

    def _al_terminar(self, id_vehiculo: int, tarea: asyncio.Task) -> None:
        ejecucion = self._en_curso.get(id_vehiculo)
        if ejecucion is not None and ejecucion.tarea is tarea:
            del self._en_curso[id_vehiculo]

    async def _ejecutar(self, id_vehiculo: int, plan: dict) -> None:
        demo, movimientos, conectado = plan["demo"], plan["movimientos"], plan["conectado"]
        total = len(movimientos)
        datos_demo = {"id_demo": demo["id_demo"], "demo": demo["nombre"]}

        try:
            await self._gestor.publicar(id_vehiculo, EventoWebSocket.crear(
                TipoEvento.DEMO_INICIO, id_vehiculo, **datos_demo, total_movimientos=total))
            for movimiento in movimientos:
                await asyncio.to_thread(self._demos.actualizar_estado, id_vehiculo, movimiento["id_comando"], conectado)
                await self._gestor.publicar(id_vehiculo, EventoWebSocket.crear(
                    TipoEvento.DEMO_MOVIMIENTO, id_vehiculo, movimiento["comando"], movimiento["codigo"],
                    **datos_demo, orden=movimiento["orden"], total_movimientos=total,
                    duracion_ms=movimiento["duracion_ms"], pausa_ms=movimiento["pausa_ms"]))
                await asyncio.sleep(movimiento["duracion_ms"] / 1000)
                await asyncio.sleep(movimiento["pausa_ms"] / 1000)
        except asyncio.CancelledError:
            detener = await self._detener_seguro(id_vehiculo, plan)
            await self._gestor.publicar(id_vehiculo, EventoWebSocket.crear(
                TipoEvento.DEMO_CANCELADA, id_vehiculo, *detener, **datos_demo,
                mensaje="La DEMO se canceló; no se enviarán más movimientos"))
            return
        except Exception:
            logger.exception("La DEMO %s del vehículo %s se detuvo por un error", demo["id_demo"], id_vehiculo)
            detener = await self._detener_seguro(id_vehiculo, plan)
            await self._gestor.publicar(id_vehiculo, EventoWebSocket.crear(
                TipoEvento.DEMO_ERROR, id_vehiculo, *detener, **datos_demo,
                mensaje="La DEMO se detuvo por un error al comunicarse con la base de datos"))
            return

        await self._gestor.publicar(id_vehiculo, EventoWebSocket.crear(
            TipoEvento.DEMO_FIN, id_vehiculo, **datos_demo, total_movimientos=total))

    async def _detener_seguro(self, id_vehiculo: int, plan: dict) -> tuple[str | None, int | None]:
        """Deja el estado en DETENER (si existe) para que la secuencia termine de forma segura."""
        detener = plan["detener"]
        if detener is None:
            return None, None
        try:
            await asyncio.to_thread(self._demos.actualizar_estado, id_vehiculo, detener["id_comando"], plan["conectado"])
        except Exception:
            logger.exception("No se pudo guardar DETENER al finalizar la DEMO del vehículo %s", id_vehiculo)
        return detener["nombre"], detener["codigo"]
