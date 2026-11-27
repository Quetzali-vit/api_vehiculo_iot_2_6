"""Dependencias de FastAPI que resuelven quién llama y qué puede hacer (4.3).

Son OBJETOS invocables: FastAPI llama a `__call__` en cada petición. Así cada
regla de acceso es una clase con su propia responsabilidad, y las reglas sobre
una unidad comparten una clase base (`PermisoUnidad`) y solo cambian su paso de
verificación (polimorfismo).

El token viaja en `Authorization: Bearer <token>`. Nunca se lee el rol ni el
id de usuario del cuerpo de la petición: salen siempre de la base de datos.
"""

from asyncio import to_thread

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import NoAutenticado, Prohibido
from app.dependencies import Contenedor, get_contenedor
from app.services.auth_service import Identidad

esquema_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="Sesión",
    description="Token devuelto por POST /auth/login o por POST /invitados/pruebas.",
)


class IdentidadOpcional:
    """Para endpoints que funcionan con o sin sesión (por ejemplo, el catálogo)."""

    async def __call__(
        self,
        credenciales: HTTPAuthorizationCredentials | None = Security(esquema_bearer),
        c: Contenedor = Depends(get_contenedor),
    ) -> Identidad | None:
        token = credenciales.credentials if credenciales else None
        if not token:
            return None
        return await to_thread(c.auth.identificar, token)


identidad_opcional = IdentidadOpcional()


class IdentidadActual:
    """Exige sesión: 401 si no hay token válido."""

    async def __call__(self, identidad: Identidad | None = Depends(identidad_opcional)) -> Identidad:
        if identidad is None:
            raise NoAutenticado("Inicia sesión para continuar")
        return identidad


identidad_actual = IdentidadActual()


class SoloAdmin:
    """Exige rol ADMIN: 401 sin sesión, 403 si la sesión no es de administrador."""

    async def __call__(
        self,
        identidad: Identidad = Depends(identidad_actual),
        c: Contenedor = Depends(get_contenedor),
    ) -> Identidad:
        return c.auth.exigir_admin(identidad)


solo_admin = SoloAdmin()


class PermisoUnidad:
    """Base de las reglas sobre UNA unidad concreta.

    Toma `id_vehiculo` de la ruta, nunca del cuerpo: cambiar el id por el de
    otro comprador responde 404, sin revelar si esa unidad existe. Cada
    subclase define en `verificar` qué significa «tener permiso».
    """

    async def __call__(
        self,
        id_vehiculo: int,
        identidad: Identidad = Depends(identidad_actual),
        c: Contenedor = Depends(get_contenedor),
    ) -> Identidad:
        return await self.verificar(c, identidad, id_vehiculo)

    async def verificar(self, c: Contenedor, identidad: Identidad, id_vehiculo: int) -> Identidad:
        raise NotImplementedError


class AccesoVehiculo(PermisoUnidad):
    """Ver la unidad: sesión y acceso a ella (dueño, admin o invitado de esa unidad)."""

    async def verificar(self, c: Contenedor, identidad: Identidad, id_vehiculo: int) -> Identidad:
        return await to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo, False)


class OperarVehiculo(PermisoUnidad):
    """Para acciones sobre DEMO (ejecutarlas o cancelarlas).

    El Administrador no puede operar una unidad que ya tiene dueño (salvo con
    soporte autorizado), y un invitado no toca demos: una demo podría incluir
    comandos fuera de la lista reducida de su prueba. Sus movimientos van por
    POST /movimientos, que sí filtra comando por comando.
    """

    async def verificar(self, c: Contenedor, identidad: Identidad, id_vehiculo: int) -> Identidad:
        if identidad.invitado:
            raise Prohibido("Una prueba de invitado no puede crear, editar ni ejecutar DEMO")
        return await to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo, True)


class GestionarDemos(PermisoUnidad):
    """Para crear, editar o borrar DEMO y sus movimientos.

    El Administrador puede hacerlo en cualquier carrito, también en los vendidos:
    es gestión de su catálogo, no mover la unidad. Un comprador solo en los suyos.
    """

    async def verificar(self, c: Contenedor, identidad: Identidad, id_vehiculo: int) -> Identidad:
        return await to_thread(c.auth.exigir_gestion_demos, identidad, id_vehiculo)


acceso_vehiculo = AccesoVehiculo()
operar_vehiculo = OperarVehiculo()
gestionar_demos = GestionarDemos()


class TokenActual:
    """El token en claro, para cerrar sesión o consultar una prueba."""

    async def __call__(
        self, credenciales: HTTPAuthorizationCredentials | None = Security(esquema_bearer),
    ) -> str:
        if credenciales is None or not credenciales.credentials:
            raise NoAutenticado("Falta el encabezado Authorization: Bearer <token>")
        return credenciales.credentials


token_actual = TokenActual()
