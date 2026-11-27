from datetime import datetime, timezone
from typing import Any


class TipoEvento:
    ESTADO_ACTUAL = "estado_actual"
    MOVIMIENTO = "movimiento"
    DEMO_INICIO = "demo_inicio"
    DEMO_MOVIMIENTO = "demo_movimiento"
    DEMO_FIN = "demo_fin"
    DEMO_CANCELADA = "demo_cancelada"
    DEMO_ERROR = "demo_error"
    PONG = "pong"
    ERROR = "error"


class EventoWebSocket:
    """Fábrica del mensaje JSON que viaja por el WebSocket.

    Todos los eventos comparten la misma forma: tipo de evento, vehículo,
    comando, código, datos extra y marca temporal UTC.
    """

    @staticmethod
    def crear(evento: str, id_vehiculo: int, comando: str | None = None, codigo: int | None = None,
              **datos: Any) -> dict:
        return {
            "evento": evento,
            "id_vehiculo": id_vehiculo,
            "comando": comando,
            "codigo": codigo,
            **datos,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }

    @classmethod
    def de_estado(cls, estado: dict) -> dict:
        """Evento `estado_actual` a partir de una fila de estado_vehiculo."""
        return cls.crear(TipoEvento.ESTADO_ACTUAL, estado["id_vehiculo"], estado["comando"], estado["codigo"],
                         conectado=bool(estado["conectado"]), fecha_actualizacion=estado["fecha_actualizacion"])
