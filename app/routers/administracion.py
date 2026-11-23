"""Administración comercial: Dashboard, clientes, modelos, unidades y auditoría.

Todo este router exige rol ADMIN salvo donde se indique. La comprobación la
hace FastAPI con la dependencia `solo_admin`, no el navegador.
"""

from asyncio import to_thread

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.autorizacion import identidad_actual, solo_admin
from app.dependencies import Contenedor, get_contenedor
from app.schemas.admin import (AsignacionSolicitud, AuditoriaItem, CatalogoItem, MetricasRespuesta,
                               MiVehiculo, ModeloActualizar, ModeloCrear, ModeloCreado,
                               ModeloRespuesta, SoporteRespuesta, SoporteSolicitud, UnidadComercial, UnidadCrear, UnidadCreada,
                               UnidadRespuesta, UsuarioActualizar, UsuarioCrear, UsuarioCreado,
                               UsuarioRespuesta)
from app.schemas.comunes import respuestas_error
from app.schemas.admin import (ModeloComandoActivo, ModeloComandoCrear, ModeloDemoCrear, UnidadEditar)
from app.services.auth_service import Identidad

router = APIRouter(prefix="/admin", tags=["Administración"])
publico = APIRouter(tags=["Catálogo público"])

IdUsuario = Path(ge=1, description="Identificador del usuario")
IdModelo = Path(ge=1, description="Identificador del modelo comercial")
IdUnidad = Path(ge=1, description="Identificador de la unidad física (mismo id_vehiculo de 4.1)")


# =====================================================================
# Dashboard
# =====================================================================
@router.get("/metricas", response_model=MetricasRespuesta, summary="Métricas del Dashboard",
            description="Conteos reales de inventario, clientes, demos y pruebas en curso.\n\n"
                        "**SP:** `sp_metricas_dashboard`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def metricas(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.metricas)


# =====================================================================
# Clientes / usuarios
# =====================================================================
@router.get("/usuarios", response_model=list[UsuarioRespuesta], summary="Listar clientes y administradores",
            description="Nunca devuelve contraseñas ni hashes.\n\n**SP:** `sp_obtener_usuarios`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def listar_usuarios(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.listar_usuarios)


@router.post("/usuarios", response_model=UsuarioCreado, status_code=status.HTTP_201_CREATED,
             summary="Registrar cliente",
             description="Da de alta un comprador (o un administrador). La contraseña se guarda "
                         "como hash PBKDF2-SHA256.\n\n**SP:** `sp_crear_usuario`, `sp_registrar_auditoria`",
             responses=respuestas_error(400, 401, 403, 409, 503))
async def crear_usuario(datos: UsuarioCrear, actor: Identidad = Depends(solo_admin),
                        c: Contenedor = Depends(get_contenedor)):
    id_usuario = await to_thread(c.auth.crear_usuario, actor, datos.nombre, datos.correo,
                                 datos.contrasena, datos.rol, datos.telefono)
    return {"mensaje": "Cliente registrado", "id_usuario": id_usuario}


@router.get("/usuarios/{id_usuario}", response_model=UsuarioRespuesta, summary="Consultar un cliente",
            description="**SP:** `sp_obtener_usuario`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def obtener_usuario(id_usuario: int = IdUsuario, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.obtener_usuario, id_usuario)


@router.post("/usuarios/{id_usuario}/actualizar", response_model=UsuarioRespuesta,
             summary="Actualizar cliente",
             description="Cambia solo los campos enviados. Con `activo: false` se da de baja "
                         "lógica: conserva su historial y sus unidades, pero ya no puede entrar.\n\n"
                         "**SP:** `sp_actualizar_usuario`, `sp_registrar_auditoria`",
             responses=respuestas_error(400, 401, 403, 404, 503))
async def actualizar_usuario(datos: UsuarioActualizar, id_usuario: int = IdUsuario,
                             actor: Identidad = Depends(solo_admin),
                             c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.actualizar_usuario, actor, id_usuario, datos)


# =====================================================================
# Modelos comerciales
# =====================================================================
@router.get("/modelos", response_model=list[ModeloRespuesta], summary="Listar modelos comerciales",
            description="MODELO es lo que la empresa vende; UNIDAD es cada pieza física.\n\n"
                        "**SP:** `sp_obtener_modelos`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def listar_modelos(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.listar_modelos)


@router.post("/modelos", response_model=ModeloCreado, status_code=status.HTTP_201_CREATED,
             summary="Registrar modelo comercial",
             description="**SP:** `sp_crear_modelo`, `sp_registrar_auditoria`",
             responses=respuestas_error(401, 403, 409, 503))
async def crear_modelo(datos: ModeloCrear, actor: Identidad = Depends(solo_admin),
                       c: Contenedor = Depends(get_contenedor)):
    id_modelo = await to_thread(c.admin.crear_modelo, actor, datos)
    return {"mensaje": "Modelo registrado", "id_modelo": id_modelo}


@router.get("/modelos/{id_modelo}", response_model=ModeloRespuesta, summary="Consultar un modelo",
            description="**SP:** `sp_obtener_modelo`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def obtener_modelo(id_modelo: int = IdModelo, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.obtener_modelo, id_modelo)


@router.post("/modelos/{id_modelo}/actualizar", response_model=ModeloRespuesta,
             summary="Actualizar modelo",
             description="Con `activo: false` el modelo sale del catálogo público pero sus "
                         "unidades siguen funcionando.\n\n**SP:** `sp_actualizar_modelo`",
             responses=respuestas_error(401, 403, 404, 409, 503))
async def actualizar_modelo(datos: ModeloActualizar, id_modelo: int = IdModelo,
                            actor: Identidad = Depends(solo_admin),
                            c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.actualizar_modelo, actor, id_modelo, datos)


# =====================================================================
# Unidades físicas
# =====================================================================
@router.get("/unidades", response_model=list[UnidadRespuesta], summary="Inventario de unidades",
            description="Cada unidad con su modelo, número de serie, estado comercial y "
                        "propietario.\n\n**SP:** `sp_obtener_unidades`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def listar_unidades(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.listar_unidades)


@router.post("/unidades", response_model=UnidadCreada, status_code=status.HTTP_201_CREATED,
             summary="Registrar unidad física",
             description="Crea la unidad y le pone sus datos comerciales. El `id_vehiculo` que "
                         "devuelve es el mismo que usan CONTROL y MONITOREO.\n\n"
                         "**SP:** `sp_crear_vehiculo`, `sp_actualizar_comercial`, `sp_registrar_auditoria`",
             responses=respuestas_error(400, 401, 403, 409, 503))
async def crear_unidad(datos: UnidadCrear, actor: Identidad = Depends(solo_admin),
                       c: Contenedor = Depends(get_contenedor)):
    id_vehiculo = await to_thread(c.admin.crear_unidad, actor, datos)
    return {"mensaje": "Unidad registrada", "id_vehiculo": id_vehiculo}


@router.get("/unidades/{id_vehiculo}", response_model=UnidadRespuesta, summary="Consultar una unidad",
            description="**SP:** `sp_obtener_unidad`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def obtener_unidad(id_vehiculo: int = IdUnidad, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.obtener_unidad, id_vehiculo)


@router.post("/unidades/{id_vehiculo}/comercial", response_model=UnidadRespuesta,
             summary="Cambiar datos comerciales de la unidad",
             description="Modelo, número de serie y estado (DISPONIBLE, VENDIDO, EXHIBICION, "
                         "INACTIVO). Una unidad con dueño no puede pasar a EXHIBICION.\n\n"
                         "**SP:** `sp_actualizar_comercial`, `sp_registrar_auditoria`",
             responses=respuestas_error(400, 401, 403, 404, 409, 503))
async def actualizar_comercial(datos: UnidadComercial, id_vehiculo: int = IdUnidad,
                               actor: Identidad = Depends(solo_admin),
                               c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.actualizar_comercial, actor, id_vehiculo, datos)


@router.post("/unidades/{id_vehiculo}/asignar", response_model=UnidadRespuesta,
             summary="Asignar o liberar una unidad",
             description="Vende la unidad a un comprador. Con `id_usuario: null` la libera y el "
                         "titular anterior pierde el acceso en la siguiente petición. El historial "
                         "del vehículo se conserva íntegro.\n\n"
                         "**SP:** `sp_asignar_unidad`, `sp_registrar_auditoria`",
             responses=respuestas_error(400, 401, 403, 404, 409, 503))
async def asignar(datos: AsignacionSolicitud, id_vehiculo: int = IdUnidad,
                  actor: Identidad = Depends(solo_admin),
                  c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.asignar, actor, id_vehiculo, datos.id_usuario)


# =====================================================================
# Auditoría
# =====================================================================
@router.get("/auditoria", response_model=list[AuditoriaItem], summary="Bitácora de acciones",
            description="Quién hizo qué, sobre qué y con qué resultado. No guarda contraseñas "
                        "ni tokens.\n\n**SP:** `sp_obtener_auditoria`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def auditoria(limite: int = Query(default=50, ge=1, le=200), c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.auditoria, limite)


# =====================================================================
# Del comprador y del público
# =====================================================================
@publico.get("/mis-vehiculos", response_model=list[MiVehiculo], tags=["Mis vehículos"],
             summary="Unidades del usuario que inició sesión",
             description="Solo las unidades de las que esa persona es propietaria. El id de "
                         "usuario sale del token, nunca de la URL, así que no se puede pedir "
                         "la lista de otro.\n\n**SP:** `sp_obtener_mis_vehiculos`",
             responses=respuestas_error(401, 503))
async def mis_vehiculos(identidad: Identidad = Depends(identidad_actual),
                        c: Contenedor = Depends(get_contenedor)):
    if identidad.invitado or identidad.id_usuario is None:
        return []
    if identidad.es_admin:
        # El administrador ve su inventario en /admin/unidades, no aquí
        return []
    return await to_thread(c.admin.mis_vehiculos, identidad.id_usuario)


@publico.get("/catalogo", response_model=list[CatalogoItem], tags=["Catálogo público"],
             summary="Catálogo para clientes potenciales",
             description="Modelos activos y cuántas unidades de exhibición hay libres ahora "
                         "mismo. No expone propietarios ni el inventario privado. No necesita "
                         "sesión.\n\n**SP:** `sp_catalogo_publico`",
             responses=respuestas_error(503))
async def catalogo(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.admin.catalogo_publico)


# =====================================================================
# Autorización de soporte operativo (la concede el comprador)
# =====================================================================
IdMiUnidad = Path(ge=1, description="Unidad del comprador que inició sesión")


@publico.get("/mis-vehiculos/{id_vehiculo}/soporte", response_model=SoporteRespuesta, tags=["Mis vehículos"],
             summary="¿Tiene la empresa soporte autorizado en mi unidad?",
             description="Solo el dueño puede consultarlo. **SP:** `sp_soporte_vigente`",
             responses=respuestas_error(401, 403, 404, 503))
async def estado_soporte(id_vehiculo: int = IdMiUnidad, identidad: Identidad = Depends(identidad_actual),
                         c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.auth.estado_soporte, identidad, id_vehiculo)


@publico.post("/mis-vehiculos/{id_vehiculo}/soporte", response_model=SoporteRespuesta, tags=["Mis vehículos"],
              summary="Autorizar soporte operativo",
              description="El **comprador** permite que el Administrador opere su unidad durante 5 a 120 "
                          "minutos. Sin esta autorización la API rechaza con 403 cualquier movimiento del "
                          "Administrador sobre una unidad vendida. Queda en la auditoría.\n\n"
                          "**SP:** `sp_autorizar_soporte`, `sp_registrar_auditoria`",
              responses=respuestas_error(401, 403, 404, 409, 503))
async def autorizar_soporte(datos: SoporteSolicitud, id_vehiculo: int = IdMiUnidad,
                            identidad: Identidad = Depends(identidad_actual),
                            c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.auth.autorizar_soporte, identidad, id_vehiculo, datos.minutos)


@publico.post("/mis-vehiculos/{id_vehiculo}/soporte/revocar", response_model=SoporteRespuesta,
              tags=["Mis vehículos"], summary="Revocar el soporte",
              description="Termina de inmediato la autorización. **SP:** `sp_revocar_soporte`, "
                          "`sp_registrar_auditoria`",
              responses=respuestas_error(401, 403, 404, 503))
async def revocar_soporte(id_vehiculo: int = IdMiUnidad, identidad: Identidad = Depends(identidad_actual),
                          c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.auth.revocar_soporte, identidad, id_vehiculo)


# =====================================================================
# Gestión del administrador (006): carritos, sesiones, cuenta de cliente y modelos
# =====================================================================
@router.post("/unidades/{id_vehiculo}/editar", response_model=UnidadRespuesta, summary="Editar un carrito",
             description="Cambia nombre, descripción, microcontrolador, modelo, número de serie, estado comercial o activo. «Eliminar» es `activo: false` (baja lógica: se conserva el historial).\n\n**SP:** `sp_actualizar_vehiculo`, `sp_actualizar_comercial`, `sp_registrar_auditoria`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
async def editar_unidad(datos: UnidadEditar, id_vehiculo: int = IdUnidad,
                        actor: Identidad = Depends(solo_admin), c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.editar_unidad, actor, id_vehiculo, datos)


@router.get("/sesiones", summary="Sesiones activas y pruebas de invitado",
            description="Quién tiene sesión abierta y qué pruebas de exhibición están corriendo ahora.\n\n**SP:** `sp_sesiones_activas`, `sp_pruebas_activas`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 503))
async def sesiones(c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.sesiones_activas)


@router.get("/clientes/{id_usuario}/cuenta", summary="Cuenta de un cliente (vista del administrador)",
            description="Sus carritos, sus sesiones activas y su bitácora.\n\n**SP:** `sp_obtener_usuario`, `sp_obtener_unidades`, `sp_sesiones_activas`, `sp_auditoria_usuario`",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def cuenta_cliente(id_usuario: int = IdUsuario, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.cuenta_cliente, id_usuario)


@router.get("/modelos/{id_modelo}/comandos", summary="Movimientos habilitados de un modelo",
            description="Resumen de los comandos de todas las unidades del modelo y en cuántas está habilitado.",
            dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def comandos_modelo(id_modelo: int = IdModelo, c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.comandos_de_modelo, id_modelo)


@router.post("/modelos/{id_modelo}/comandos", summary="Agregar un movimiento a un modelo",
             description="Lo agrega a todas las unidades del modelo.\n\n**SP:** `sp_crear_comando`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 409, 503))
async def agregar_comando_modelo(datos: ModeloComandoCrear, id_modelo: int = IdModelo,
                                 actor: Identidad = Depends(solo_admin), c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.agregar_comando_modelo, actor, id_modelo, datos.nombre,
                           datos.codigo, datos.descripcion)


@router.post("/modelos/{id_modelo}/comandos/activo", summary="Habilitar o deshabilitar un movimiento de un modelo",
             description="Aplica a todas las unidades del modelo.\n\n**SP:** `sp_actualizar_comando`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def habilitar_comando_modelo(datos: ModeloComandoActivo, id_modelo: int = IdModelo,
                                   actor: Identidad = Depends(solo_admin), c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.habilitar_comando_modelo, actor, id_modelo, datos.nombre, datos.activo)


@router.post("/modelos/{id_modelo}/demos", summary="Crear una demo de fábrica para un modelo",
             description="Crea la demo en todas las unidades del modelo con los mismos pasos. Un paso cuyo movimiento no exista en una unidad se omite y se informa.\n\n**SP:** `sp_crear_demo`, `sp_agregar_movimiento_demo`",
             dependencies=[Depends(solo_admin)], responses=respuestas_error(401, 403, 404, 503))
async def demo_modelo(datos: ModeloDemoCrear, id_modelo: int = IdModelo,
                      actor: Identidad = Depends(solo_admin), c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.gestion.crear_demo_modelo, actor, id_modelo, datos.nombre, datos.descripcion, datos.pasos)
