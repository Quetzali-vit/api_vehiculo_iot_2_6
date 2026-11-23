"""Dependencias de FastAPI que resuelven quién llama y qué puede hacer (4.3).

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


async def identidad_opcional(
    credenciales: HTTPAuthorizationCredentials | None = Security(esquema_bearer),
    c: Contenedor = Depends(get_contenedor),
) -> Identidad | None:
    """Para endpoints que funcionan con o sin sesión (por ejemplo, el catálogo)."""
    token = credenciales.credentials if credenciales else None
    if not token:
        return None
    return await to_thread(c.auth.identificar, token)


async def identidad_actual(
    identidad: Identidad | None = Depends(identidad_opcional),
) -> Identidad:
    """Exige sesión: 401 si no hay token válido."""
    if identidad is None:
        raise NoAutenticado("Inicia sesión para continuar")
    return identidad


async def solo_admin(
    identidad: Identidad = Depends(identidad_actual),
    c: Contenedor = Depends(get_contenedor),
) -> Identidad:
    """Exige rol ADMIN: 401 sin sesión, 403 si la sesión no es de administrador."""
    return c.auth.exigir_admin(identidad)


async def acceso_vehiculo(
    id_vehiculo: int,
    identidad: Identidad = Depends(identidad_actual),
    c: Contenedor = Depends(get_contenedor),
) -> Identidad:
    """Exige sesión Y permiso sobre la unidad que trae la URL.

    Toma `id_vehiculo` de la ruta, nunca del cuerpo: cambiar el id por el de
    otro comprador responde 404, sin revelar si esa unidad existe.
    """
    return await to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo, False)


async def operar_vehiculo(
    id_vehiculo: int,
    identidad: Identidad = Depends(identidad_actual),
    c: Contenedor = Depends(get_contenedor),
) -> Identidad:
    """Para acciones sobre DEMO (crearlas, editarlas, ejecutarlas o cancelarlas).

    El Administrador no puede operar una unidad que ya tiene dueño, y un
    invitado no toca demos: una demo podría incluir comandos fuera de la lista
    reducida de su prueba. Sus movimientos van por POST /movimientos, que sí
    filtra comando por comando.
    """
    if identidad.invitado:
        raise Prohibido("Una prueba de invitado no puede crear, editar ni ejecutar DEMO")
    return await to_thread(c.auth.exigir_acceso_vehiculo, identidad, id_vehiculo, True)


async def gestionar_demos(
    id_vehiculo: int,
    identidad: Identidad = Depends(identidad_actual),
    c: Contenedor = Depends(get_contenedor),
) -> Identidad:
    """Para crear, editar o borrar DEMO y sus movimientos.

    El Administrador puede hacerlo en cualquier carrito, también en los vendidos:
    es gestión de su catálogo, no mover la unidad. Un comprador solo en los suyos.
    """
    return await to_thread(c.auth.exigir_gestion_demos, identidad, id_vehiculo)


async def token_actual(
    credenciales: HTTPAuthorizationCredentials | None = Security(esquema_bearer),
) -> str:
    """El token en claro, para cerrar sesión o consultar una prueba."""
    if credenciales is None or not credenciales.credentials:
        raise NoAutenticado("Falta el encabezado Authorization: Bearer <token>")
    return credenciales.credentials
