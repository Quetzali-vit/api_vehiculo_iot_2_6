"""Gestión del administrador (práctica 4.3): carritos, clientes, modelos, demos y sesiones.

Reglas:
- «Eliminar» un carrito o un cliente es una baja lógica (activo = false): su historial
  de movimientos y su bitácora se conservan.
- Un cambio sobre un modelo (comandos o demos) se aplica a todas las unidades de ese modelo.
- Toda acción que cambia algo queda en la auditoría con quién la hizo.
"""

from app.core.exceptions import Conflicto, NoEncontrado, SolicitudInvalida


class GestionService:
    def __init__(self, db, usuarios, modelos, unidades, vehiculos, comandos, demos, sesiones, auditoria):
        self._db = db
        self._usuarios = usuarios
        self._modelos = modelos
        self._unidades = unidades
        self._vehiculos = vehiculos
        self._comandos = comandos
        self._demos = demos
        self._sesiones = sesiones
        self._auditoria = auditoria

    # =================================================================
    # Carritos (unidades físicas)
    # =================================================================
    def editar_unidad(self, actor, id_vehiculo: int, datos) -> dict:
        with self._db.transaccion() as sesion:
            actual = self._vehiculos.obtener(sesion, id_vehiculo)
            if actual is None:
                raise NoEncontrado(f"No existe la unidad {id_vehiculo}")

            if datos.nombre is not None or datos.descripcion is not None \
                    or datos.microcontrolador is not None or datos.activo is not None:
                self._vehiculos.actualizar(
                    sesion, id_vehiculo,
                    datos.nombre.strip() if datos.nombre is not None else actual["nombre"],
                    actual["modelo"],
                    datos.descripcion if datos.descripcion is not None else actual["descripcion"],
                    datos.microcontrolador if datos.microcontrolador is not None else actual["microcontrolador"],
                    datos.activo if datos.activo is not None else bool(actual["activo"]),
                )

            if datos.id_modelo is not None or datos.numero_serie is not None or datos.estado_comercial is not None:
                if datos.estado_comercial is not None and datos.estado_comercial == "EXHIBICION":
                    unidad = self._unidades.obtener(sesion, id_vehiculo)
                    if unidad and unidad["id_propietario"] is not None:
                        raise Conflicto("La unidad tiene dueño: libérala antes de ponerla en exhibición")
                if datos.id_modelo is not None and self._modelos.obtener(sesion, datos.id_modelo) is None:
                    raise SolicitudInvalida(f"No existe el modelo {datos.id_modelo}")
                self._unidades.actualizar_comercial(sesion, id_vehiculo, datos.id_modelo,
                                                    datos.numero_serie, datos.estado_comercial)

            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "EDITAR", "unidad",
                                      str(id_vehiculo), "OK", None)
            return self._unidades.obtener(sesion, id_vehiculo)

    def unidades_de_modelo(self, sesion, id_modelo: int) -> list[dict]:
        return [u for u in self._unidades.listar(sesion) if u.get("id_modelo") == id_modelo]

    # =================================================================
    # Sesiones activas y bitácora
    # =================================================================
    def sesiones_activas(self) -> dict:
        with self._db.transaccion() as sesion:
            return {
                "inicio_de_sesion": self._sesiones.sesiones_activas(sesion),
                "pruebas_de_invitado": self._sesiones.pruebas_activas(sesion),
            }

    # =================================================================
    # Cuenta de un cliente, vista del administrador
    # =================================================================
    def cuenta_cliente(self, id_usuario: int) -> dict:
        with self._db.transaccion() as sesion:
            usuario = self._usuarios.obtener(sesion, id_usuario)
            if usuario is None:
                raise NoEncontrado(f"No existe el usuario {id_usuario}")
            carritos = [u for u in self._unidades.listar(sesion) if u["id_propietario"] == id_usuario]
            sesiones = [s for s in self._sesiones.sesiones_activas(sesion) if s["id_usuario"] == id_usuario]
            bitacora = self._sesiones.auditoria_usuario(sesion, id_usuario, usuario["correo"], 50)
        return {
            "usuario": {k: usuario[k] for k in ("id_usuario", "nombre", "correo", "telefono", "rol", "activo")},
            "carritos": carritos,
            "sesiones_activas": sesiones,
            "bitacora": bitacora,
        }

    # =================================================================
    # Modelos: comandos habilitados y demos de fábrica (para todas sus unidades)
    # =================================================================
    def comandos_de_modelo(self, id_modelo: int) -> dict:
        with self._db.transaccion() as sesion:
            if self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            unidades = self.unidades_de_modelo(sesion, id_modelo)
            resumen: dict[str, dict] = {}
            for unidad in unidades:
                for c in self._comandos.listar_por_vehiculo(sesion, unidad["id_vehiculo"]):
                    fila = resumen.setdefault(c["nombre"], {
                        "nombre": c["nombre"], "codigo": c["codigo"], "descripcion": c.get("descripcion"),
                        "unidades_con_comando": 0, "unidades_habilitado": 0, "unidades_totales": len(unidades),
                    })
                    fila["unidades_con_comando"] += 1
                    if c["activo"]:
                        fila["unidades_habilitado"] += 1
        return {"id_modelo": id_modelo, "unidades": len(unidades), "comandos": sorted(resumen.values(), key=lambda x: x["codigo"])}

    def agregar_comando_modelo(self, actor, id_modelo: int, nombre: str, codigo: int, descripcion: str | None) -> dict:
        nombre = nombre.strip().upper()
        agregados, errores = 0, []
        with self._db.transaccion() as sesion:
            if self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            unidades = self.unidades_de_modelo(sesion, id_modelo)
        for unidad in unidades:
            try:
                with self._db.transaccion() as sesion:
                    self._comandos.crear(sesion, unidad["id_vehiculo"], nombre, codigo, descripcion)
                agregados += 1
            except Conflicto as error:
                errores.append({"id_vehiculo": unidad["id_vehiculo"], "motivo": error.mensaje})
        with self._db.transaccion() as sesion:
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "AGREGAR_COMANDO", "modelo",
                                      str(id_modelo), "OK", f"{nombre} cód {codigo} en {agregados} unidades")
        return {"id_modelo": id_modelo, "agregado_en": agregados, "errores": errores}

    def habilitar_comando_modelo(self, actor, id_modelo: int, nombre: str, activo: bool) -> dict:
        nombre = nombre.strip().upper()
        cambiados, sin_comando = 0, 0
        with self._db.transaccion() as sesion:
            if self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            for unidad in self.unidades_de_modelo(sesion, id_modelo):
                comando = next((c for c in self._comandos.listar_por_vehiculo(sesion, unidad["id_vehiculo"])
                                if c["nombre"] == nombre), None)
                if comando is None:
                    sin_comando += 1
                    continue
                if bool(comando["activo"]) != activo:
                    self._comandos.actualizar(sesion, comando["id_comando"], comando["nombre"], comando["codigo"],
                                              comando.get("descripcion"), activo)
                    cambiados += 1
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta,
                                      "HABILITAR" if activo else "DESHABILITAR", "modelo", str(id_modelo), "OK",
                                      f"{nombre}: {cambiados} unidades")
        return {"id_modelo": id_modelo, "comando": nombre, "activo": activo,
                "cambiados": cambiados, "unidades_sin_comando": sin_comando}

    def crear_demo_modelo(self, actor, id_modelo: int, nombre: str, descripcion: str | None, pasos: list) -> dict:
        creadas, omitidos = 0, []
        with self._db.transaccion() as sesion:
            if self._modelos.obtener(sesion, id_modelo) is None:
                raise NoEncontrado(f"No existe el modelo {id_modelo}")
            unidades = self.unidades_de_modelo(sesion, id_modelo)
        for unidad in unidades:
            with self._db.transaccion() as sesion:
                id_demo = self._demos.crear(sesion, unidad["id_vehiculo"], nombre.strip(), descripcion)
                por_nombre = {c["nombre"]: c["id_comando"]
                              for c in self._comandos.listar_por_vehiculo(sesion, unidad["id_vehiculo"])}
                for orden, paso in enumerate(pasos, 1):
                    id_comando = por_nombre.get(paso.comando.strip().upper())
                    if id_comando is None:
                        omitidos.append({"id_vehiculo": unidad["id_vehiculo"], "paso": paso.comando})
                        continue
                    self._demos.agregar_movimiento(sesion, id_demo, id_comando, orden,
                                                   paso.duracion_ms, paso.pausa_ms)
            creadas += 1
        with self._db.transaccion() as sesion:
            self._auditoria.registrar(sesion, actor.id_usuario, actor.etiqueta, "CREAR_DEMO_MODELO", "modelo",
                                      str(id_modelo), "OK", f"{nombre} en {creadas} unidades")
        return {"id_modelo": id_modelo, "demo": nombre, "creada_en": creadas, "pasos_omitidos": omitidos}
