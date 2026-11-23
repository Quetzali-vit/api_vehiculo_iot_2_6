from functools import cached_property, lru_cache

from app.core.config import get_settings
from app.db.database import Database
from app.repositories.admin_repository import (AuditoriaRepository, DemoAdminRepository,
                                               InvitadoRepository, ModeloRepository,
                                               UnidadRepository, UsuarioRepository)
from app.repositories.comando_repository import ComandoRepository
from app.repositories.demo_repository import DemoRepository
from app.repositories.estado_repository import EstadoRepository
from app.repositories.historial_repository import HistorialRepository
from app.repositories.vehiculo_repository import VehiculoRepository
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.comando_service import ComandoService
from app.services.invitado_service import InvitadoService
from app.services.demo_executor import EjecutorDemos
from app.services.demo_service import DemoService
from app.services.estado_service import EstadoService
from app.services.historial_service import HistorialService
from app.services.movimiento_service import MovimientoService
from app.services.reglas import ReglasNegocio
from app.services.vehiculo_service import VehiculoService
from app.websocket.manager import GestorWebSocket


class Contenedor:
    """Crea una sola instancia de cada componente y las conecta entre sí."""

    def __init__(self):
        self.settings = get_settings()
        self.db = Database(self.settings)
        self.gestor_ws = GestorWebSocket()

        self._vehiculos = VehiculoRepository()
        self._comandos = ComandoRepository()
        self._estados = EstadoRepository()
        self._historial = HistorialRepository()
        self._demos = DemoRepository()
        self._reglas = ReglasNegocio(self._vehiculos, self._comandos, self._demos)

        # Práctica 4.3: administración comercial
        self._usuarios = UsuarioRepository()
        self._modelos = ModeloRepository()
        self._unidades = UnidadRepository()
        self._invitados_repo = InvitadoRepository()
        self._auditoria = AuditoriaRepository()
        self._demos_admin = DemoAdminRepository()

    @cached_property
    def vehiculos(self) -> VehiculoService:
        return VehiculoService(self.db, self._reglas, self._vehiculos, self._comandos, self._estados, self._demos)

    @cached_property
    def comandos(self) -> ComandoService:
        return ComandoService(self.db, self._reglas, self._comandos)

    @cached_property
    def estados(self) -> EstadoService:
        return EstadoService(self.db, self._reglas, self._estados)

    @cached_property
    def historial(self) -> HistorialService:
        return HistorialService(self.db, self._reglas, self._historial)

    @cached_property
    def demos(self) -> DemoService:
        return DemoService(self.db, self._reglas, self._demos, self._comandos, self._estados)

    @cached_property
    def ejecutor(self) -> EjecutorDemos:
        return EjecutorDemos(self.demos, self.gestor_ws)

    @cached_property
    def movimientos(self) -> MovimientoService:
        return MovimientoService(self.db, self._reglas, self._estados, self._historial, self.gestor_ws,
                                 self.ejecutor, self.settings.origen_movimiento)

    # ----- Práctica 4.3 -----

    @cached_property
    def auth(self) -> AuthService:
        return AuthService(self.db, self._usuarios, self._unidades, self._invitados_repo, self._auditoria,
                           self._demos_admin)

    @cached_property
    def admin(self) -> AdminService:
        return AdminService(self.db, self._usuarios, self._modelos, self._unidades,
                            self._auditoria, self._vehiculos)

    @cached_property
    def invitados(self) -> InvitadoService:
        servicio = InvitadoService(self.db, self._invitados_repo, self._unidades, self._modelos,
                                   self._auditoria, self._comandos)
        # Se conecta después para evitar una dependencia circular con movimientos
        servicio.conectar_movimientos(self.movimientos)
        return servicio

    @cached_property
    def demos_admin(self) -> DemoAdminRepository:
        return self._demos_admin


@lru_cache
def get_contenedor() -> Contenedor:
    return Contenedor()
