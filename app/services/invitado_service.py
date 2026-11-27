"""Sesiones de prueba para clientes potenciales (Invitado).

Reglas comerciales que impone el servidor, no el navegador:

* Solo unidades en estado EXHIBICION. Una unidad vendida JAMÁS se ofrece.
* Reserva exclusiva: mientras alguien prueba una unidad, nadie más la controla.
  Lo garantiza el índice UNIQUE (id_vehiculo, activa) de la base de datos, así
  que dos peticiones simultáneas no pueden colarse.
* Tiempo límite. Al vencer, la sesión se cierra, la unidad se libera y se le
  manda DETENER.
* Lista reducida de comandos: nada de encender/apagar ni luces.
"""

import asyncio
import logging

from app.core.contrasenas import generador_tokens
from app.core.exceptions import Conflicto, NoEncontrado, Prohibido, SolicitudInvalida
from app.schemas.movimiento import MovimientoSolicitud

logger = logging.getLogger(__name__)

MINUTOS_PRUEBA = 5
INTERVALO_VIGILANCIA_S = 20
ORIGEN_INVITADO = "WEB-INVITADO"

# Comandos que un invitado puede usar. Movimiento y DETENER, nada más.
COMANDOS_INVITADO = frozenset({
    "AVANZAR", "RETROCEDER", "GIRAR_IZQUIERDA", "GIRAR_DERECHA",
    "SUBIR_BRAZO", "BAJAR_BRAZO", "ABRIR_PALA", "CERRAR_PALA", "DETENER",
})


class InvitadoService:
    def __init__(self, db, invitados, unidades, modelos, auditoria, comandos):
        self._db = db
        self._invitados = invitados
        self._unidades = unidades
        self._modelos = modelos
        self._auditoria = auditoria
        self._comandos = comandos
        self._movimientos = None   # se inyecta después (evita dependencia circular)
        self._vigilante: asyncio.Task | None = None

    def conectar_movimientos(self, movimientos) -> None:
        self._movimientos = movimientos

    # -----------------------------------------------------------------
    # Alta y baja de la sesión de prueba
    # -----------------------------------------------------------------
    def iniciar(self, id_modelo: int | None, nombre: str | None) -> dict:
        token = generador_tokens.generar()
        with self._db.transaccion() as sesion:
            if id_modelo is not None and self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            try:
                datos = self._invitados.crear(sesion, id_modelo, generador_tokens.huella(token),
                                              (nombre or "Invitado")[:80], MINUTOS_PRUEBA)
            except Conflicto as error:
                if "duplicado" in error.mensaje:
                    # El índice UNIQUE saltó: otra persona ganó la reserva por milisegundos
                    raise Conflicto("Esa unidad acaba de ser reservada por otra persona. "
                                    "Inténtalo de nuevo en unos segundos.") from error
                raise  # p. ej. «no hay unidades de exhibición disponibles»
            if datos is None:
                raise Conflicto("No hay unidades de exhibición disponibles en este momento")
            self._auditoria.registrar(sesion, None, f"invitado:{nombre or 'Invitado'}", "INICIAR",
                                      "prueba", str(datos["id_vehiculo"]), "OK",
                                      f"{MINUTOS_PRUEBA} minutos")
        return {"token": token, **self._publico(datos)}

    def estado(self, token: str) -> dict:
        with self._db.transaccion() as sesion:
            datos = self._invitados.obtener(sesion, generador_tokens.huella(token))
        if datos is None:
            raise NoEncontrado("Esa sesión de prueba no existe")
        return self._publico(datos)

    async def terminar(self, token: str, motivo: str = "CERRADA") -> dict:
        with self._db.transaccion() as sesion:
            datos = self._invitados.obtener(sesion, generador_tokens.huella(token))
            if datos is None:
                raise NoEncontrado("Esa sesión de prueba no existe")
            self._invitados.finalizar(sesion, generador_tokens.huella(token), motivo)
            id_vehiculo = datos["id_vehiculo"]
        await self._detener(id_vehiculo)   # la unidad nunca se queda en movimiento
        return {"mensaje": "Sesión de prueba terminada y unidad detenida"}

    # -----------------------------------------------------------------
    # Validación de cada comando del invitado
    # -----------------------------------------------------------------
    def validar_comando(self, identidad, id_vehiculo: int, nombre_comando: str) -> None:
        """Se llama ANTES de mover. Comprueba sesión vigente, unidad reservada
        y que el comando esté en la lista corta."""
        if identidad.id_vehiculo_invitado != id_vehiculo:
            raise Prohibido("Tu sesión de prueba es de otra unidad")
        if (identidad.segundos_restantes or 0) <= 0:
            raise Prohibido("Tu sesión de prueba terminó")
        if nombre_comando not in COMANDOS_INVITADO:
            raise Prohibido(f"El comando {nombre_comando} no está permitido en una prueba")

    # -----------------------------------------------------------------
    # Vigilante: cierra las sesiones vencidas y detiene sus unidades
    # -----------------------------------------------------------------
    async def iniciar_vigilancia(self) -> None:
        if self._vigilante is None or self._vigilante.done():
            self._vigilante = asyncio.create_task(self._vigilar())

    async def detener_vigilancia(self) -> None:
        if self._vigilante and not self._vigilante.done():
            self._vigilante.cancel()
            try:
                await self._vigilante
            except asyncio.CancelledError:
                pass

    async def _vigilar(self) -> None:
        while True:
            try:
                await asyncio.sleep(INTERVALO_VIGILANCIA_S)
                liberados = await asyncio.to_thread(self._expirar)
                for id_vehiculo in liberados:
                    logger.info("Sesión de invitado vencida: deteniendo la unidad %s", id_vehiculo)
                    await self._detener(id_vehiculo)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Un fallo puntual de RDS no debe matar al vigilante
                logger.exception("Error al revisar las sesiones de invitado")

    def _expirar(self) -> list[int]:
        with self._db.transaccion() as sesion:
            return self._invitados.expirar_vencidas(sesion)

    async def _detener(self, id_vehiculo: int) -> None:
        """Manda DETENER por el camino normal, para que quede en estado,
        historial y WebSocket igual que cualquier otro movimiento."""
        if self._movimientos is None:
            return
        try:
            comando = await asyncio.to_thread(self._buscar_detener, id_vehiculo)
            if comando is None:
                return
            await self._movimientos.ejecutar(
                id_vehiculo, MovimientoSolicitud(id_comando=comando, origen=ORIGEN_INVITADO))
        except Exception:
            logger.exception("No se pudo detener la unidad %s al cerrar la prueba", id_vehiculo)

    def _buscar_detener(self, id_vehiculo: int) -> int | None:
        with self._db.transaccion() as sesion:
            for comando in self._comandos.listar_por_vehiculo(sesion, id_vehiculo):
                if comando["nombre"] == "DETENER" and comando["activo"]:
                    return int(comando["id_comando"])
        return None

    # -----------------------------------------------------------------
    @staticmethod
    def _publico(datos: dict) -> dict:
        """Lo que se le devuelve al invitado. Sin tokens ni datos de compradores."""
        restantes = int(datos.get("segundos_restantes") or 0)
        activa = bool(datos.get("activa")) and restantes > 0
        return {
            "activa": activa,
            "id_vehiculo": datos["id_vehiculo"],
            "vehiculo": datos.get("vehiculo"),
            "modelo": datos.get("modelo"),
            "segundos_restantes": max(restantes, 0),
            "comandos_permitidos": sorted(COMANDOS_INVITADO),
            "motivo_fin": datos.get("motivo_fin"),
        }
