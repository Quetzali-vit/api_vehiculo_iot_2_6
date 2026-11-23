import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

# Canal general: recibe los eventos de TODAS las unidades. Los ids de vehículo
# empiezan en 1, así que el 0 no puede chocar con ninguna unidad.
CANAL_GENERAL = 0


class GestorWebSocket:
    """Agrupa los clientes WebSocket por vehículo (o en el canal general) y les reparte los eventos."""

    TIEMPO_MAXIMO_ENVIO = 5  # segundos; un cliente lento no frena a los demás

    def __init__(self):
        self._clientes: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def conectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._clientes[id_vehiculo].add(websocket)
        logger.info("Cliente WebSocket conectado al canal %s (%s en total)", id_vehiculo, self.total(id_vehiculo))

    async def desconectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        async with self._lock:
            clientes = self._clientes.get(id_vehiculo)
            if clientes is not None:
                clientes.discard(websocket)
                if not clientes:
                    del self._clientes[id_vehiculo]
        logger.info("Cliente WebSocket desconectado del canal %s", id_vehiculo)

    def total(self, id_vehiculo: int) -> int:
        return len(self._clientes.get(id_vehiculo, ()))

    async def enviar(self, websocket: WebSocket, mensaje: dict) -> None:
        await asyncio.wait_for(websocket.send_json(jsonable_encoder(mensaje)), self.TIEMPO_MAXIMO_ENVIO)

    async def publicar(self, id_vehiculo: int, mensaje: dict) -> None:
        """Envía el evento a los clientes de ese vehículo y al canal general; retira los que fallen."""
        async with self._lock:
            destinos = [(c, id_vehiculo) for c in self._clientes.get(id_vehiculo, ())]
            destinos += [(c, CANAL_GENERAL) for c in self._clientes.get(CANAL_GENERAL, ())]
        if not destinos:
            return

        resultados = await asyncio.gather(*(self.enviar(c, mensaje) for c, _ in destinos), return_exceptions=True)
        for (cliente, canal), resultado in zip(destinos, resultados):
            if isinstance(resultado, Exception):
                logger.warning("Se retira un cliente WebSocket que no respondió: %s", type(resultado).__name__)
                await self.desconectar(canal, cliente)
