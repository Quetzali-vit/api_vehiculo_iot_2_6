"""Gestión comercial: modelos, unidades, clientes, asignaciones y Dashboard.

Toda operación que cambia algo queda en la auditoría con quién la hizo.
"""

from app.core.exceptions import Conflicto, NoEncontrado, SolicitudInvalida

ESTADOS_COMERCIALES = ("DISPONIBLE", "VENDIDO", "EXHIBICION", "INACTIVO")


class AdminService:
    def __init__(self, db, usuarios, modelos, unidades, auditoria, vehiculos):
        self._db = db
        self._usuarios = usuarios
        self._modelos = modelos
        self._unidades = unidades
        self._auditoria = auditoria
        self._vehiculos = vehiculos

    # ----- Dashboard -----
    def metricas(self) -> dict:
        with self._db.transaccion() as sesion:
            return self._unidades.metricas(sesion)

    # ----- Clientes -----
    def listar_usuarios(self) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._usuarios.listar(sesion)

    def obtener_usuario(self, id_usuario: int) -> dict:
        with self._db.transaccion() as sesion:
            usuario = self._usuarios.obtener(sesion, id_usuario)
        if usuario is None:
            raise NoEncontrado(f"No existe el usuario {id_usuario}")
        return usuario

    def actualizar_usuario(self, actor, id_usuario: int, datos) -> dict:
        from app.core.contrasenas import hashear_contrasena

        if datos.contrasena is not None and len(datos.contrasena) < 8:
            raise SolicitudInvalida("La contraseña debe tener al menos 8 caracteres")
        hash_nuevo = hashear_contrasena(datos.contrasena) if datos.contrasena else None

        with self._db.transaccion() as sesion:
            if self._usuarios.obtener(sesion, id_usuario) is None:
                raise NoEncontrado(f"No existe el usuario {id_usuario}")
            actualizado = self._usuarios.actualizar(sesion, id_usuario, datos.nombre, datos.telefono,
                                                    hash_nuevo, datos.rol, datos.activo)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "ACTUALIZAR",
                                      "usuario", str(id_usuario), "OK",
                                      "cambio de contraseña" if hash_nuevo else None)
            return actualizado

    # ----- Modelos comerciales -----
    def listar_modelos(self) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._modelos.listar(sesion)

    def obtener_modelo(self, id_modelo: int) -> dict:
        with self._db.transaccion() as sesion:
            modelo = self._modelos.obtener(sesion, id_modelo)
        if modelo is None:
            raise NoEncontrado(f"No existe el modelo {id_modelo}")
        return modelo

    def crear_modelo(self, actor, datos) -> int:
        with self._db.transaccion() as sesion:
            id_modelo = self._modelos.crear(sesion, datos.nombre.strip(), datos.descripcion,
                                            datos.microcontrolador, datos.precio, datos.imagen_url)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "CREAR",
                                      "modelo", str(id_modelo), "OK", datos.nombre)
            return id_modelo

    def actualizar_modelo(self, actor, id_modelo: int, datos) -> dict:
        with self._db.transaccion() as sesion:
            if self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            actualizado = self._modelos.actualizar(sesion, id_modelo, datos.nombre, datos.descripcion,
                                                   datos.microcontrolador, datos.precio,
                                                   datos.imagen_url, datos.activo)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "ACTUALIZAR",
                                      "modelo", str(id_modelo), "OK", None)
            return actualizado

    def catalogo_publico(self) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._modelos.catalogo_publico(sesion)

    # ----- Unidades físicas -----
    def listar_unidades(self) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._unidades.listar(sesion)

    def obtener_unidad(self, id_vehiculo: int) -> dict:
        with self._db.transaccion() as sesion:
            unidad = self._unidades.obtener(sesion, id_vehiculo)
        if unidad is None:
            raise NoEncontrado(f"No existe la unidad {id_vehiculo}")
        return unidad

    def crear_unidad(self, actor, datos) -> int:
        """Da de alta una unidad física. Reutiliza sp_crear_vehiculo (4.1) y
        después le pone los datos comerciales, para no duplicar nada."""
        with self._db.transaccion() as sesion:
            if datos.id_modelo is not None and self._modelos.obtener(sesion, datos.id_modelo) is None:
                raise SolicitudInvalida(f"No existe el modelo {datos.id_modelo}")
            id_vehiculo = self._vehiculos.crear(sesion, datos.nombre.strip(), datos.modelo,
                                                datos.descripcion, datos.microcontrolador)
            self._unidades.actualizar_comercial(sesion, id_vehiculo, datos.id_modelo,
                                                datos.numero_serie, datos.estado_comercial)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "CREAR",
                                      "unidad", str(id_vehiculo), "OK", datos.nombre)
            return id_vehiculo

    def actualizar_comercial(self, actor, id_vehiculo: int, datos) -> dict:
        if datos.estado_comercial is not None and datos.estado_comercial not in ESTADOS_COMERCIALES:
            raise SolicitudInvalida(f"Estado comercial no válido. Usa uno de: {', '.join(ESTADOS_COMERCIALES)}")
        with self._db.transaccion() as sesion:
            actual = self._unidades.obtener(sesion, id_vehiculo)
            if actual is None:
                raise NoEncontrado(f"No existe la unidad {id_vehiculo}")
            # Una unidad con dueño no puede pasar a exhibición pública
            if datos.estado_comercial == "EXHIBICION" and actual["id_propietario"] is not None:
                raise Conflicto("La unidad tiene propietario: libérala antes de ponerla en exhibición")
            if datos.id_modelo is not None and self._modelos.obtener(sesion, datos.id_modelo) is None:
                raise SolicitudInvalida(f"No existe el modelo {datos.id_modelo}")
            actualizado = self._unidades.actualizar_comercial(sesion, id_vehiculo, datos.id_modelo,
                                                              datos.numero_serie, datos.estado_comercial)
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "ACTUALIZAR",
                                      "unidad", str(id_vehiculo), "OK",
                                      f"estado={datos.estado_comercial}" if datos.estado_comercial else None)
            return actualizado

    def asignar(self, actor, id_vehiculo: int, id_usuario: int | None) -> dict:
        """Vende/asigna una unidad a un comprador, o la libera con id_usuario = null.

        El historial del vehículo se conserva íntegro: solo cambia el dueño. Al
        reasignar, el titular anterior pierde el acceso de inmediato, porque el
        permiso se comprueba contra esta columna en cada petición.
        """
        with self._db.transaccion() as sesion:
            unidad = self._unidades.obtener(sesion, id_vehiculo)
            if unidad is None:
                raise NoEncontrado(f"No existe la unidad {id_vehiculo}")

            anterior = unidad["id_propietario"]

            if id_usuario is not None:
                comprador = self._usuarios.obtener(sesion, id_usuario)
                if comprador is None:
                    raise SolicitudInvalida(f"No existe el usuario {id_usuario}")
                if not comprador["activo"]:
                    raise Conflicto("Ese cliente está inactivo")
                if unidad["estado_comercial"] == "EXHIBICION":
                    raise Conflicto("La unidad está en exhibición: cámbiala de estado antes de venderla")

            actualizado = self._unidades.asignar(sesion, id_vehiculo, id_usuario)
            self._auditoria.registrar(
                sesion, actor.id_usuario, actor.etiqueta,
                "ASIGNAR" if id_usuario else "LIBERAR", "unidad", str(id_vehiculo), "OK",
                f"antes={anterior} ahora={id_usuario}")
            return actualizado

    def mis_vehiculos(self, id_usuario: int) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._unidades.mis_vehiculos(sesion, id_usuario)

    # ----- Auditoría -----
    def auditoria(self, limite: int = 50) -> list[dict]:
        with self._db.transaccion() as sesion:
            return self._auditoria.listar(sesion, limite)
