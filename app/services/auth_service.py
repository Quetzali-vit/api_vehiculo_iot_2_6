"""Autenticación de usuarios y autorización por recurso (práctica 4.3).

Tres reglas que no se negocian:

1. El rol NO basta. Antes de dejar consultar u operar una unidad se comprueba
   la PROPIEDAD en la base de datos, con el id que trae la URL.
2. Nada de lo que manda el navegador (rol, id_usuario, id_vehiculo del cuerpo)
   se cree: el usuario sale siempre del token, y la propiedad de la base.
3. El Administrador gestiona el inventario, pero NO toma el control de una
   unidad vendida salvo que el dueño lo haya autorizado explícitamente.
"""

from datetime import datetime, timezone

from app.core.contrasenas import generar_token, hash_token, hashear_contrasena, verificar_contrasena
from app.core.exceptions import NoAutenticado, NoEncontrado, Prohibido, SolicitudInvalida

ROL_ADMIN = "ADMIN"
ROL_USUARIO = "USUARIO"
HORAS_SESION = 8


class Identidad:
    """Quién está haciendo la petición. Se construye SOLO desde el token."""

    def __init__(self, id_usuario: int | None, nombre: str, correo: str, rol: str,
                 invitado: bool = False, id_vehiculo_invitado: int | None = None,
                 segundos_restantes: int | None = None):
        self.id_usuario = id_usuario
        self.nombre = nombre
        self.correo = correo
        self.rol = rol
        self.invitado = invitado
        self.id_vehiculo_invitado = id_vehiculo_invitado
        self.segundos_restantes = segundos_restantes

    @property
    def es_admin(self) -> bool:
        return self.rol == ROL_ADMIN

    @property
    def etiqueta(self) -> str:
        """Lo que se guarda en la auditoría como 'actor'."""
        return self.correo or f"invitado:{self.nombre}"


class AuthService:
    def __init__(self, db, usuarios, unidades, invitados, auditoria):
        self._db = db
        self._usuarios = usuarios
        self._unidades = unidades
        self._invitados = invitados
        self._auditoria = auditoria

    # -----------------------------------------------------------------
    # Login y logout
    # -----------------------------------------------------------------
    def login(self, correo: str, contrasena: str) -> dict:
        correo = (correo or "").strip().lower()
        with self._db.transaccion() as sesion:
            usuario = self._usuarios.por_correo(sesion, correo)

            # Mismo mensaje y mismo trabajo si el correo no existe o la clave está mal:
            # así no se puede averiguar qué correos están registrados.
            valida = bool(usuario) and verificar_contrasena(contrasena, usuario["hash_contrasena"])
            if not valida or not usuario["activo"]:
                self._auditoria.registrar(sesion, usuario["id_usuario"] if usuario else None,
                                          correo or "desconocido", "LOGIN", "sesion", None,
                                          "RECHAZADO", "Credenciales no válidas o cuenta inactiva")
                raise NoAutenticado("Correo o contraseña incorrectos")

            token = generar_token()
            self._usuarios.crear_sesion(sesion, usuario["id_usuario"], hash_token(token), HORAS_SESION)
            self._auditoria.registrar(sesion, usuario["id_usuario"], correo, "LOGIN", "sesion",
                                      None, "OK", None)
            return {
                "token": token,
                "expira_en_horas": HORAS_SESION,
                "usuario": {
                    "id_usuario": usuario["id_usuario"],
                    "nombre": usuario["nombre"],
                    "correo": usuario["correo"],
                    "rol": usuario["rol"],
                },
            }

    def logout(self, token: str) -> None:
        with self._db.transaccion() as sesion:
            self._usuarios.revocar_sesion(sesion, hash_token(token))

    # -----------------------------------------------------------------
    # Identificación a partir del token
    # -----------------------------------------------------------------
    def identificar(self, token: str | None) -> Identidad | None:
        """Devuelve quién es, o None si no hay token válido. No lanza error:
        así un endpoint público puede funcionar con o sin sesión."""
        if not token:
            return None
        huella = hash_token(token)
        with self._db.transaccion() as sesion:
            # 1) ¿Es una sesión de usuario registrado?
            fila = self._usuarios.obtener_sesion(sesion, huella)
            if fila and fila["activo"]:
                return Identidad(fila["id_usuario"], fila["nombre"], fila["correo"], fila["rol"])

            # 2) ¿Es una sesión temporal de invitado?
            invitado = self._invitados.obtener(sesion, huella)
            if invitado and invitado["activa"] and _restantes(invitado) > 0:
                return Identidad(None, invitado["nombre_invitado"] or "Invitado", "", "INVITADO",
                                 invitado=True, id_vehiculo_invitado=invitado["id_vehiculo"],
                                 segundos_restantes=_restantes(invitado))
        return None

    # -----------------------------------------------------------------
    # Autorización por recurso
    # -----------------------------------------------------------------
    def exigir_identidad(self, identidad: Identidad | None) -> Identidad:
        if identidad is None:
            raise NoAutenticado("Inicia sesión para continuar")
        return identidad

    def exigir_admin(self, identidad: Identidad | None) -> Identidad:
        identidad = self.exigir_identidad(identidad)
        if not identidad.es_admin:
            raise Prohibido("Esta operación es solo del Administrador")
        return identidad

    def exigir_acceso_vehiculo(self, identidad: Identidad | None, id_vehiculo: int,
                               operar: bool = False) -> Identidad:
        """Comprueba que esa persona puede ver (o mover) ESA unidad.

        - Invitado: solo la unidad de exhibición que tiene reservada y vigente.
        - Usuario: solo las unidades de las que es propietario.
        - Admin: puede VER cualquier unidad (es su inventario), pero NO puede
          moverla si ya tiene dueño: eso necesita consentimiento del comprador.
        """
        identidad = self.exigir_identidad(identidad)

        if identidad.invitado:
            if identidad.id_vehiculo_invitado != id_vehiculo:
                raise Prohibido("Tu sesión de prueba es de otra unidad")
            return identidad

        with self._db.transaccion() as sesion:
            unidad = self._unidades.obtener(sesion, id_vehiculo)
        if unidad is None:
            raise NoEncontrado(f"No existe la unidad {id_vehiculo}")

        propietario = unidad["id_propietario"]

        if identidad.es_admin:
            if operar and propietario is not None:
                raise Prohibido(
                    "La unidad pertenece a un comprador. El Administrador no puede operarla "
                    "sin una autorización de soporte del dueño."
                )
            return identidad

        if propietario != identidad.id_usuario:
            # 404 y no 403: así un comprador no puede averiguar qué IDs existen
            raise NoEncontrado(f"No existe la unidad {id_vehiculo}")
        return identidad

    # -----------------------------------------------------------------
    # Alta de usuarios (la hace el Administrador)
    # -----------------------------------------------------------------
    def crear_usuario(self, actor: Identidad, nombre: str, correo: str, contrasena: str,
                      rol: str, telefono: str | None) -> int:
        if rol not in (ROL_ADMIN, ROL_USUARIO):
            raise SolicitudInvalida("El rol debe ser ADMIN o USUARIO")
        if len(contrasena) < 8:
            raise SolicitudInvalida("La contraseña debe tener al menos 8 caracteres")
        correo = correo.strip().lower()
        with self._db.transaccion() as sesion:
            id_usuario = self._usuarios.crear(sesion, nombre.strip(), correo,
                                              hashear_contrasena(contrasena), rol, telefono)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "CREAR",
                                      "usuario", str(id_usuario), "OK", f"rol={rol}")
            return id_usuario


def _restantes(invitado: dict) -> int:
    """Segundos que le quedan a una sesión de invitado, según el reloj del servidor."""
    valor = invitado.get("segundos_restantes")
    if valor is not None:
        return int(valor)
    expira = invitado.get("fecha_expira")
    if not isinstance(expira, datetime):
        return 0
    if expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    return int((expira - datetime.now(timezone.utc)).total_seconds())
