import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class GestorWebSocket:
    """Agrupa los clientes WebSocket por vehículo y les reparte los eventos."""

    TIEMPO_MAXIMO_ENVIO = 5  # segundos; un cliente lento no frena a los demás

    def __init__(self):
        self._clientes: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def conectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._clientes[id_vehiculo].add(websocket)
        logger.info("Cliente WebSocket conectado al vehículo %s (%s en total)", id_vehiculo, self.total(id_vehiculo))

    async def desconectar(self, id_vehiculo: int, websocket: WebSocket) -> None:
        async with self._lock:
            clientes = self._clientes.get(id_vehiculo)
            if clientes is not None:
                clientes.discard(websocket)
                if not clientes:
                    del self._clientes[id_vehiculo]
        logger.info("Cliente WebSocket desconectado del vehículo %s", id_vehiculo)

    def total(self, id_vehiculo: int) -> int:
        return len(self._clientes.get(id_vehiculo, ()))

    async def enviar(self, websocket: WebSocket, mensaje: dict) -> None:
        await asyncio.wait_for(websocket.send_json(jsonable_encoder(mensaje)), self.TIEMPO_MAXIMO_ENVIO)

    async def publicar(self, id_vehiculo: int, mensaje: dict) -> None:
        """Envía el evento solo a los clientes de ese vehículo y retira los que fallen."""
        async with self._lock:
            clientes = list(self._clientes.get(id_vehiculo, ()))
        if not clientes:
            return

        resultados = await asyncio.gather(*(self.enviar(c, mensaje) for c in clientes), return_exceptions=True)
        for cliente, resultado in zip(clientes, resultados):
            if isinstance(resultado, Exception):
                logger.warning("Se retira un cliente WebSocket que no respondió: %s", type(resultado).__name__)
                await self.desconectar(id_vehiculo, cliente)
