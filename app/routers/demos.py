"""DEMO de un vehículo: consulta, edición y ejecución.

Práctica 4.3: hay demos de FÁBRICA (sin dueño, las define la empresa) y demos
PRIVADAS (las crea un comprador para su unidad). Reglas que aplica el servidor:

* Ver: cualquiera con acceso a la unidad ve las de fábrica y las propias.
* Editar: el Administrador solo las de fábrica; un comprador solo las suyas.
* Ejecutar: hay que poder OPERAR la unidad. Un invitado no ejecuta demos,
  porque una demo podría incluir comandos fuera de su lista permitida.
"""

from asyncio import to_thread

from fastapi import APIRouter, Depends, Path, status

from app.core.autorizacion import acceso_vehiculo, operar_vehiculo
from app.dependencies import Contenedor, get_contenedor
from app.schemas.comunes import Mensaje, respuestas_error
from app.schemas.demo import (DemoActualizar, DemoCrear, DemoCreada, DemoEjecucionRespuesta, DemoEnCurso,
                              DemoRespuesta, MovimientoDemoActualizar, MovimientoDemoCrear,
                              MovimientoDemoRespuesta)
from app.services.auth_service import Identidad

router = APIRouter(prefix="/vehiculos/{id_vehiculo}/demos", tags=["DEMO"])
IdVehiculo = Path(ge=1, description="Identificador del vehículo")
IdDemo = Path(ge=1, description="Identificador de la DEMO")
IdMovimiento = Path(ge=1, description="Identificador del movimiento de la DEMO")

NOTA_VER = ("\n\n**Autorización (4.3).** Sesión con acceso a la unidad. Se ven las demos de fábrica "
            "y las propias; nunca las privadas de otra persona.")
NOTA_EDITAR = ("\n\n**Autorización (4.3).** Hay que poder operar la unidad y ser dueño de la demo: "
               "el Administrador edita las de fábrica y cada comprador solo las suyas.")


# ---------- DEMO ----------
@router.get("", response_model=list[DemoRespuesta], summary="DEMO del vehículo",
            description="**SP:** `sp_obtener_demos_visibles`" + NOTA_VER,
            responses=respuestas_error(401, 403, 404, 503))
async def listar(id_vehiculo: int = IdVehiculo, identidad: Identidad = Depends(acceso_vehiculo),
                 c: Contenedor = Depends(get_contenedor)):
    return await to_thread(c.auth.demos_visibles, identidad, id_vehiculo)


@router.post("", response_model=DemoCreada, status_code=status.HTTP_201_CREATED, summary="Crear DEMO",
             description="Crea una DEMO vacía; después se le agregan movimientos. Si la crea el "
                         "Administrador es de fábrica; si la crea un comprador, es privada suya.\n\n"
                         "**SP:** `sp_crear_demo_propietario`, `sp_registrar_auditoria`" + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 503))
async def crear(datos: DemoCrear, id_vehiculo: int = IdVehiculo,
                identidad: Identidad = Depends(operar_vehiculo), c: Contenedor = Depends(get_contenedor)):
    id_demo = await to_thread(c.auth.crear_demo, identidad, id_vehiculo, datos.nombre, datos.descripcion)
    return {"mensaje": "DEMO creada", "id_demo": id_demo}


@router.get("/ejecucion", response_model=DemoEnCurso, summary="¿Hay una DEMO en ejecución?",
            description="Consulta en memoria; no usa la base de datos." + NOTA_VER,
            dependencies=[Depends(acceso_vehiculo)], responses=respuestas_error(401, 403, 404, 503))
async def en_curso(id_vehiculo: int = IdVehiculo, c: Contenedor = Depends(get_contenedor)):
    ejecucion = c.ejecutor.en_curso(id_vehiculo)
    if ejecucion is None:
        return {"id_vehiculo": id_vehiculo, "en_ejecucion": False}
    return {"id_vehiculo": id_vehiculo, "en_ejecucion": True, "id_demo": ejecucion.id_demo, "demo": ejecucion.nombre}


@router.post("/cancelar", response_model=Mensaje, summary="Cancelar la DEMO en ejecución",
             description="Detiene de inmediato la emisión de movimientos, deja el estado en DETENER y publica "
                         "`demo_cancelada` por WebSocket.\n\n**SP:** `sp_actualizar_estado`\n\n"
                         "**Autorización (4.3).** Hay que poder operar la unidad.",
             dependencies=[Depends(operar_vehiculo)], responses=respuestas_error(401, 403, 404, 503))
async def cancelar(id_vehiculo: int = IdVehiculo, c: Contenedor = Depends(get_contenedor)):
    ejecucion = await c.ejecutor.cancelar(id_vehiculo)
    return {"mensaje": f"DEMO {ejecucion.id_demo} cancelada"}


@router.post("/{id_demo}/actualizar", response_model=DemoRespuesta, summary="Actualizar DEMO",
             description="Cambia solo los campos enviados.\n\n**SP:** `sp_obtener_demo`, `sp_actualizar_demo`"
                         + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 503))
async def actualizar(datos: DemoActualizar, id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                     identidad: Identidad = Depends(operar_vehiculo), c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, True)
    return await to_thread(c.demos.actualizar, id_vehiculo, id_demo, datos)


@router.post("/{id_demo}/eliminar", response_model=Mensaje, summary="Eliminar DEMO",
             description="Borra la DEMO y sus movimientos.\n\n**SP:** `sp_obtener_demo`, `sp_eliminar_demo`"
                         + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 503))
async def eliminar(id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                   identidad: Identidad = Depends(operar_vehiculo), c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, True)
    await to_thread(c.demos.eliminar, id_vehiculo, id_demo)
    await to_thread(c.auth.auditar, identidad, "ELIMINAR", "demo", str(id_demo), None)
    return {"mensaje": f"DEMO {id_demo} eliminada"}


@router.post("/{id_demo}/ejecutar", response_model=DemoEjecucionRespuesta, status_code=status.HTTP_202_ACCEPTED,
             summary="Iniciar una DEMO",
             description="Valida la DEMO, lee sus N movimientos de RDS y los transmite en segundo plano por "
                         "WebSocket: `demo_inicio`, un `demo_movimiento` por cada uno (respetando `duracion_ms` "
                         "y `pausa_ms`) y `demo_fin`. Actualiza el estado con cada movimiento, pero **no** "
                         "escribe en el historial. Responde 409 si ya hay una DEMO en curso. DETENER la "
                         "cancela con prioridad.\n\n"
                         "**SP:** `sp_obtener_demo`, `sp_obtener_movimientos_demo`, `sp_actualizar_estado`\n\n"
                         "**Autorización (4.3).** Hay que poder operar la unidad y la demo debe ser de "
                         "fábrica o propia.",
             responses=respuestas_error(401, 403, 404, 409, 503))
async def ejecutar(id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                   identidad: Identidad = Depends(operar_vehiculo), c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, False)
    info = await c.ejecutor.iniciar(id_vehiculo, id_demo)
    return {
        "mensaje": "DEMO iniciada; los movimientos se envían por WebSocket",
        "id_vehiculo": id_vehiculo,
        "id_demo": id_demo,
        **info,
        "websocket": f"/ws/vehiculos/{id_vehiculo}",
    }


# ---------- Movimientos de la DEMO ----------
@router.get("/{id_demo}/movimientos", response_model=list[MovimientoDemoRespuesta],
            summary="Movimientos ordenados de una DEMO",
            description="**SP:** `sp_obtener_demo`, `sp_obtener_movimientos_demo`" + NOTA_VER,
            responses=respuestas_error(401, 403, 404, 503))
async def listar_movimientos(id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                             identidad: Identidad = Depends(acceso_vehiculo),
                             c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, False)
    return await to_thread(c.demos.listar_movimientos, id_vehiculo, id_demo)


@router.post("/{id_demo}/movimientos", response_model=list[MovimientoDemoRespuesta],
             status_code=status.HTTP_201_CREATED, summary="Agregar movimiento a la DEMO",
             description="El comando debe pertenecer al vehículo (así una excavadora no recibe comandos de "
                         "otro modelo) y el `orden` no puede repetirse. Duración de 1 a 60 000 ms. "
                         "Devuelve la secuencia actualizada.\n\n"
                         "**SP:** `sp_obtener_comandos_vehiculo`, `sp_agregar_movimiento_demo`, "
                         "`sp_obtener_movimientos_demo`" + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 409, 503))
async def agregar_movimiento(datos: MovimientoDemoCrear, id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                             identidad: Identidad = Depends(operar_vehiculo),
                             c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, True)
    return await to_thread(c.demos.agregar_movimiento, id_vehiculo, id_demo, datos)


@router.post("/{id_demo}/movimientos/{id_demo_movimiento}/actualizar", response_model=list[MovimientoDemoRespuesta],
             summary="Actualizar movimiento de la DEMO",
             description="Cambia solo los campos enviados (comando, orden, duración o pausa) y devuelve la "
                         "secuencia actualizada.\n\n"
                         "**SP:** `sp_obtener_movimientos_demo`, `sp_obtener_comandos_vehiculo`, "
                         "`sp_actualizar_movimiento_demo`" + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 409, 503))
async def actualizar_movimiento(datos: MovimientoDemoActualizar, id_vehiculo: int = IdVehiculo,
                                id_demo: int = IdDemo, id_demo_movimiento: int = IdMovimiento,
                                identidad: Identidad = Depends(operar_vehiculo),
                                c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, True)
    return await to_thread(c.demos.actualizar_movimiento, id_vehiculo, id_demo, id_demo_movimiento, datos)


@router.post("/{id_demo}/movimientos/{id_demo_movimiento}/eliminar", response_model=Mensaje,
             summary="Eliminar movimiento de la DEMO",
             description="**SP:** `sp_obtener_movimientos_demo`, `sp_eliminar_movimiento_demo`" + NOTA_EDITAR,
             responses=respuestas_error(401, 403, 404, 503))
async def eliminar_movimiento(id_vehiculo: int = IdVehiculo, id_demo: int = IdDemo,
                              id_demo_movimiento: int = IdMovimiento,
                              identidad: Identidad = Depends(operar_vehiculo),
                              c: Contenedor = Depends(get_contenedor)):
    await to_thread(c.auth.exigir_demo, identidad, id_vehiculo, id_demo, True)
    await to_thread(c.demos.eliminar_movimiento, id_vehiculo, id_demo, id_demo_movimiento)
    return {"mensaje": f"Movimiento {id_demo_movimiento} eliminado de la DEMO {id_demo}"}
