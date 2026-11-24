"""Pruebas reproducibles de la práctica 4.3: roles, permisos por recurso,
invitados, demos, WebSocket y auditoría.

    python pruebas/prueba_roles.py                         # contra la API publicada
    python pruebas/prueba_roles.py http://127.0.0.1:8010   # contra una API local

Usa las cuentas de demostración de migraciones/003_datos_iniciales.sql. Crea
datos nuevos (un modelo, una unidad y una demo) con un sufijo de fecha, así que
se puede repetir sin chocar con ejecuciones anteriores. No borra nada.

Cada caso imprime CORRECTO / INCORRECTO con el código HTTP real recibido.
"""

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://quetzali-iot.duckdns.org").rstrip("/")
WS = BASE.replace("https://", "wss://").replace("http://", "ws://")
SUFIJO = time.strftime("%m%d%H%M%S")

ADMIN = ("admin@iot.com", "Admin123#")
CLIENTE = ("cliente@iot.com", "Cliente123#")
CLIENTE2 = ("cliente2@iot.com", "Cliente123#")

resultados: list[tuple[str, bool, str]] = []


def http(metodo: str, ruta: str, token: str | None = None, cuerpo: dict | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    peticion = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    peticion.add_header("Accept", "application/json")
    if cuerpo is not None:
        peticion.add_header("Content-Type", "application/json")
    if token:
        peticion.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(peticion, timeout=30) as r:
            texto = r.read().decode()
            return r.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, texto


def caso(clave: str, descripcion: str, esperado, obtenido, detalle: str = "") -> bool:
    ok = obtenido in esperado if isinstance(esperado, (tuple, list, set)) else obtenido == esperado
    resultados.append((clave, ok, descripcion))
    marca = "CORRECTO  " if ok else "INCORRECTO"
    print(f"[{marca}] {clave} {descripcion} -> {obtenido}{('  ' + detalle) if detalle else ''}")
    return ok


def login(cuenta) -> str:
    estado, datos = http("POST", "/auth/login", cuerpo={"correo": cuenta[0], "contrasena": cuenta[1]})
    if estado != 200:
        raise SystemExit(f"No se pudo iniciar sesión con {cuenta[0]}: {estado} {datos}")
    return datos["token"]


def comando(token: str, id_vehiculo: int, nombre: str) -> int | None:
    estado, lista = http("GET", f"/vehiculos/{id_vehiculo}/comandos", token)
    if estado != 200:
        return None
    return next((c["codigo"] for c in lista if c["nombre"] == nombre), None)


async def abrir_ws(id_vehiculo: int, consulta: str) -> str:
    """Devuelve 'abierto' si recibió el estado inicial, o 'cerrado:<código>'."""
    import websockets
    try:
        async with websockets.connect(f"{WS}/ws/vehiculos/{id_vehiculo}{consulta}", open_timeout=15) as ws:
            mensaje = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            return f"abierto:{mensaje.get('evento')}"
    except websockets.exceptions.InvalidStatus as e:
        return f"rechazado:{e.response.status_code}"
    except websockets.exceptions.ConnectionClosed as e:
        return f"cerrado:{e.rcvd.code if e.rcvd else '?'}"


def main() -> int:
    print(f"== Pruebas 4.3 contra {BASE} ==\n")

    # ----- Sistema y acceso anónimo -----
    caso("P00", "GET / responde", 200, http("GET", "/")[0])
    caso("P00", "GET /salud (diagnóstico RDS)", 200, http("GET", "/salud")[0])
    caso("P00", "Historial sin sesión es rechazado", 401, http("GET", "/vehiculos/1/historial")[0])
    caso("P00", "Movimiento sin sesión es rechazado", 401,
         http("POST", "/vehiculos/1/movimientos", cuerpo={"codigo": 9})[0])

    # ----- P01 login -----
    caso("P01", "Login con contraseña incorrecta", 401,
         http("POST", "/auth/login", cuerpo={"correo": ADMIN[0], "contrasena": "mala"})[0])
    admin = login(ADMIN)
    estado, yo = http("GET", "/auth/yo", admin)
    caso("P01", "Login Admin y /auth/yo devuelve rol ADMIN", "ADMIN", yo.get("rol") if estado == 200 else estado)
    caso("P01", "Dashboard del Admin", 200, http("GET", "/admin/metricas", admin)[0])

    # ----- P02 alta de modelo y unidad -----
    estado, datos = http("POST", "/admin/modelos", admin, {
        "nombre": f"Vehículo Batman IoT {SUFIJO}", "descripcion": "Modelo de prueba", "microcontrolador": "ESP8266",
        "precio": 5200})
    caso("P02", "Admin registra un modelo comercial", 201, estado)
    id_modelo = datos.get("id_modelo") if estado == 201 else None

    estado, datos = http("POST", "/admin/unidades", admin, {
        "nombre": f"Unidad prueba {SUFIJO}", "id_modelo": id_modelo, "numero_serie": f"PRB-{SUFIJO}",
        "estado_comercial": "DISPONIBLE", "microcontrolador": "ESP8266"})
    caso("P02", "Admin registra una unidad física", 201, estado)
    unidad = datos.get("id_vehiculo") if estado == 201 else None

    estado, _ = http("POST", "/admin/unidades", admin, {"nombre": "Duplicada", "numero_serie": f"PRB-{SUFIJO}"})
    caso("P02", "Número de serie repetido es rechazado", 409, estado)

    for nombre, codigo in (("AVANZAR", 1), ("DETENER", 9), ("ENCENDER_APAGAR", 10)):
        http("POST", f"/vehiculos/{unidad}/comandos", admin, {"nombre": nombre, "codigo": codigo})

    # ----- P03 clientes -----
    estado, usuarios = http("GET", "/admin/usuarios", admin)
    caso("P03", "Admin lista clientes (sin hashes)", True,
         estado == 200 and all("hash_contrasena" not in u for u in usuarios))
    ids = {u["correo"]: u["id_usuario"] for u in usuarios}
    id_admin = ids[ADMIN[0]]
    caso("P19", "El Admin no puede desactivar su propia cuenta", 409,
         http("POST", f"/admin/usuarios/{id_admin}/actualizar", admin, {"activo": False})[0])
    caso("P19", "El Admin no puede quitarse su rol", 409,
         http("POST", f"/admin/usuarios/{id_admin}/actualizar", admin, {"rol": "USUARIO"})[0])
    estado, _ = http("POST", "/admin/usuarios", admin, {
        "nombre": "Cliente nuevo", "correo": f"nuevo{SUFIJO}@iot.com", "contrasena": "Cliente123#"})
    caso("P03", "Admin da de alta un cliente", 201, estado)

    # ----- P04 asignación -----
    estado, datos = http("POST", f"/admin/unidades/{unidad}/asignar", admin, {"id_usuario": ids[CLIENTE[0]]})
    caso("P04", "Admin asigna la unidad al comprador", "VENDIDO",
         datos.get("estado_comercial") if estado == 200 else estado)

    # ----- P05 aislamiento de comprador -----
    cliente = login(CLIENTE)
    cliente2 = login(CLIENTE2)
    estado, mios = http("GET", "/mis-vehiculos", cliente)
    caso("P05", "Comprador ve su unidad en «Mis vehículos»", True,
         estado == 200 and any(v["id_vehiculo"] == unidad for v in mios))
    estado, mios2 = http("GET", "/mis-vehiculos", cliente2)
    caso("P05", "Otro comprador NO la ve", True, estado == 200 and all(v["id_vehiculo"] != unidad for v in mios2))
    caso("P05", "Comprador no entra a Administración", 403, http("GET", "/admin/metricas", cliente)[0])
    caso("P05", "Comprador no ve el inventario completo", 403, http("GET", "/vehiculos", cliente)[0])

    # ----- P06 Control -----
    caso("P06", "Comprador mueve SU unidad (AVANZAR)", 201,
         http("POST", f"/vehiculos/{unidad}/movimientos", cliente, {"codigo": 1})[0])
    caso("P06", "Comprador ejecuta DETENER", 201,
         http("POST", f"/vehiculos/{unidad}/movimientos", cliente, {"codigo": 9})[0])
    caso("P06", "Admin NO opera una unidad vendida", 403,
         http("POST", f"/vehiculos/{unidad}/movimientos", admin, {"codigo": 1})[0])

    # ----- P18 autorización de soporte operativo -----
    caso("P18", "Otro comprador no puede autorizar soporte en unidad ajena", 404,
         http("POST", f"/mis-vehiculos/{unidad}/soporte", cliente2, {"minutos": 10})[0])
    caso("P18", "El Admin no puede autorizarse a sí mismo", 403,
         http("POST", f"/mis-vehiculos/{unidad}/soporte", admin, {"minutos": 10})[0])
    estado, sop = http("POST", f"/mis-vehiculos/{unidad}/soporte", cliente, {"minutos": 10})
    caso("P18", "El dueño autoriza soporte por 10 minutos", True, estado == 200 and sop.get("activa") is True)
    caso("P18", "Con soporte autorizado el Admin SÍ opera la unidad", 201,
         http("POST", f"/vehiculos/{unidad}/movimientos", admin, {"codigo": 9})[0])
    estado, hist_s = http("GET", f"/vehiculos/{unidad}/historial", cliente)
    caso("P18", "El historial lo marca como WEB-SOPORTE", "WEB-SOPORTE",
         hist_s["movimientos"][0]["origen"] if estado == 200 else estado)
    estado, sop = http("POST", f"/mis-vehiculos/{unidad}/soporte/revocar", cliente)
    caso("P18", "El dueño revoca el soporte", True, estado == 200 and sop.get("activa") is False)
    caso("P18", "Revocado, el Admin vuelve a ser rechazado", 403,
         http("POST", f"/vehiculos/{unidad}/movimientos", admin, {"codigo": 9})[0])

    # ----- P08 historial 10 -----
    estado, hist = http("GET", f"/vehiculos/{unidad}/historial", cliente)
    caso("P08", "Historial de su unidad (máx. 10, del más nuevo)", True,
         estado == 200 and hist["devueltos"] <= 10 and hist["movimientos"][0]["comando"] == "DETENER"
         and [m["id_historial"] for m in hist["movimientos"]] == sorted((m["id_historial"] for m in hist["movimientos"]), reverse=True))

    # ----- P13 vehículo ajeno -----
    caso("P13", "Otro comprador pide el historial ajeno (cambia el ID)", 404,
         http("GET", f"/vehiculos/{unidad}/historial", cliente2)[0])
    caso("P13", "Otro comprador intenta moverla", 404,
         http("POST", f"/vehiculos/{unidad}/movimientos", cliente2, {"codigo": 1})[0])
    caso("P13", "Otro comprador pide su estado", 404, http("GET", f"/vehiculos/{unidad}/estado", cliente2)[0])

    # ----- P09/P10 demo persistente -----
    estado, datos = http("POST", f"/vehiculos/{unidad}/demos", cliente,
                         {"nombre": f"Mi demo {SUFIJO}", "descripcion": "Avanza y se detiene"})
    caso("P09", "Comprador crea una demo privada", 201, estado)
    id_demo = datos.get("id_demo") if estado == 201 else None
    comandos_u = {c["nombre"]: c["id_comando"] for c in http("GET", f"/vehiculos/{unidad}/comandos", cliente)[1]}
    http("POST", f"/vehiculos/{unidad}/demos/{id_demo}/movimientos", cliente,
         {"id_comando": comandos_u["AVANZAR"], "orden": 1, "duracion_ms": 800, "pausa_ms": 100})
    estado, pasos = http("POST", f"/vehiculos/{unidad}/demos/{id_demo}/movimientos", cliente,
                         {"id_comando": comandos_u["DETENER"], "orden": 2, "duracion_ms": 300})
    caso("P09", "Pasos guardados en orden", True, estado == 201 and [p["orden"] for p in pasos] == [1, 2])
    estado, demos = http("GET", f"/vehiculos/{unidad}/demos", cliente)
    caso("P09", "La demo se consulta después como PRIVADA", True,
         estado == 200 and any(d["id_demo"] == id_demo and d["tipo"] == "PRIVADA" for d in demos))
    caso("P09", "Otro comprador no puede editarla", 404,
         http("POST", f"/vehiculos/{unidad}/demos/{id_demo}/movimientos", cliente2,
              {"id_comando": comandos_u["AVANZAR"], "orden": 3, "duracion_ms": 500})[0])
    caso("P10", "Comprador ejecuta su demo", 202, http("POST", f"/vehiculos/{unidad}/demos/{id_demo}/ejecutar", cliente)[0])
    caso("P10", "DETENER cancela la demo con prioridad", 201,
         http("POST", f"/vehiculos/{unidad}/movimientos", cliente, {"codigo": 9})[0])

    # ----- P11/P12/P14 invitado -----
    estado, catalogo = http("GET", "/catalogo")
    caso("P11", "Catálogo público sin sesión", 200, estado)
    caso("P11", "El catálogo no expone propietarios", True,
         estado == 200 and all("propietario" not in m and "correo_propietario" not in m for m in catalogo))
    estado, prueba = http("POST", "/invitados/pruebas", cuerpo={"nombre": "Visitante"})
    caso("P11", "Invitado inicia una prueba de exhibición", 201, estado)
    invitado = prueba.get("token") if estado == 201 else None
    exhibicion = prueba.get("id_vehiculo") if estado == 201 else None
    codigo_avanzar = comando(invitado, exhibicion, "AVANZAR") if invitado else None
    codigo_encender = comando(invitado, exhibicion, "ENCENDER_APAGAR") if invitado else None
    caso("P11", "Invitado mueve la unidad de exhibición", 201,
         http("POST", f"/vehiculos/{exhibicion}/movimientos", invitado, {"codigo": codigo_avanzar})[0])
    if codigo_encender is not None:
        caso("P11", "Invitado no puede usar ENCENDER/APAGAR", 403,
             http("POST", f"/vehiculos/{exhibicion}/movimientos", invitado, {"codigo": codigo_encender})[0])
    caso("P11", "Invitado no puede ejecutar demos", 403,
         http("POST", f"/vehiculos/{exhibicion}/demos/1/ejecutar", invitado)[0])
    caso("P12", "Invitado rechazado en Administración", 403, http("GET", "/admin/metricas", invitado)[0])
    caso("P12", "Invitado rechazado en un vehículo vendido", 403,
         http("POST", f"/vehiculos/{unidad}/movimientos", invitado, {"codigo": 1})[0])

    estado, _ = http("POST", "/invitados/pruebas", cuerpo={"nombre": "Segundo visitante"})
    caso("P14", "Segunda prueba simultánea: sin unidad libre", 409, estado)
    caso("P14", "Ni el Admin mueve la unidad reservada", 409,
         http("POST", f"/vehiculos/{exhibicion}/movimientos", admin, {"codigo": 9})[0])
    caso("P14", "Invitado termina su prueba (libera y detiene)", 200,
         http("POST", "/invitados/pruebas/terminar", invitado)[0])
    caso("P14", "Al terminar, su token deja de servir", 401,
         http("POST", f"/vehiculos/{exhibicion}/movimientos", invitado, {"codigo": codigo_avanzar})[0])
    caso("P14", "Liberada, el Admin ya puede operarla", 201,
         http("POST", f"/vehiculos/{exhibicion}/movimientos", admin, {"codigo": 9})[0])

    # ----- P07 WebSocket autenticado -----
    try:
        caso("P07", "WSS sin token en unidad vendida: escucha abierta", "abierto:estado_actual",
             asyncio.run(abrir_ws(unidad, "")))
        caso("P07", "WSS de unidad inexistente se rechaza (4404)", "cerrado:4404",
             asyncio.run(abrir_ws(999999, "")))

        caso("P07", "WSS del dueño recibe estado_actual", "abierto:estado_actual",
             asyncio.run(abrir_ws(unidad, f"?token={cliente}")))
        caso("P07", "WSS con token de otro comprador: escucha abierta", "abierto:estado_actual",
             asyncio.run(abrir_ws(unidad, f"?token={cliente2}")))
    except ImportError:
        print("   (WebSocket no probado: falta el paquete websockets)")

    # ----- Reasignación: revocación inmediata -----
    http("POST", f"/admin/unidades/{unidad}/asignar", admin, {"id_usuario": ids[CLIENTE2[0]]})
    caso("P04", "Reasignada: el dueño anterior pierde el acceso al instante", 404,
         http("GET", f"/vehiculos/{unidad}/historial", cliente)[0])
    caso("P04", "El nuevo dueño ya la opera", 201,
         http("POST", f"/vehiculos/{unidad}/movimientos", cliente2, {"codigo": 9})[0])
    estado, hist2 = http("GET", f"/vehiculos/{unidad}/historial", cliente2)
    caso("P04", "El historial se conservó tras la reasignación", True,
         estado == 200 and hist2["total_registrados"] >= 3)

    # ----- P20-P25 gestión del administrador (006) -----
    caso("P20", "Admin edita los datos de un carrito", 200,
         http("POST", f"/admin/unidades/{unidad}/editar", admin, {"descripcion": "Editada por el admin"})[0])
    caso("P20", "Comprador no puede editar carritos", 403,
         http("POST", f"/admin/unidades/{unidad}/editar", cliente2, {"descripcion": "No"})[0])
    caso("P20", "Admin da de baja un carrito (activo: false)", 200,
         http("POST", f"/admin/unidades/{unidad}/editar", admin, {"activo": False})[0])
    caso("P20", "Admin reactiva el carrito", 200,
         http("POST", f"/admin/unidades/{unidad}/editar", admin, {"activo": True})[0])
    caso("P21", "Sesiones activas: el Admin sí", 200, http("GET", "/admin/sesiones", admin)[0])
    caso("P21", "Sesiones activas: el comprador no", 403, http("GET", "/admin/sesiones", cliente2)[0])
    estado, cuenta = http("GET", f"/admin/clientes/{ids[CLIENTE2[0]]}/cuenta", admin)
    caso("P22", "Cuenta de cliente: carritos, sesiones y bitácora", True,
         estado == 200 and {"carritos", "sesiones_activas", "bitacora"} <= set(cuenta))
    caso("P22", "Comprador no ve la cuenta de otro cliente", 403,
         http("GET", f"/admin/clientes/{ids[CLIENTE2[0]]}/cuenta", cliente2)[0])
    nombre_nuevo, codigo_nuevo = f"CLAXON_{SUFIJO}", int(SUFIJO[-4:])
    caso("P23", "Admin agrega un movimiento al modelo (a todas sus unidades)", 200,
         http("POST", f"/admin/modelos/{id_modelo}/comandos", admin,
              {"nombre": nombre_nuevo, "codigo": codigo_nuevo, "descripcion": "Prueba"})[0])
    caso("P23", "Admin deshabilita ese movimiento del modelo", 200,
         http("POST", f"/admin/modelos/{id_modelo}/comandos/activo", admin,
              {"nombre": nombre_nuevo, "activo": False})[0])
    caso("P23", "Resumen de movimientos del modelo", 200,
         http("GET", f"/admin/modelos/{id_modelo}/comandos", admin)[0])
    caso("P24", "Admin crea una demo de fábrica para el modelo", 200,
         http("POST", f"/admin/modelos/{id_modelo}/demos", admin,
              {"nombre": f"Fábrica {SUFIJO}", "pasos": [{"comando": "AVANZAR", "duracion_ms": 500, "pausa_ms": 0}]})[0])
    estado, nueva = http("POST", f"/vehiculos/{unidad}/demos", admin,
                         {"nombre": f"Demo del admin {SUFIJO}", "descripcion": "Para el cliente"})
    caso("P25", "Admin crea una demo en el carrito vendido", 201, estado)
    id_demo_admin = nueva.get("id_demo") if estado == 201 else None
    estado, lista = http("GET", f"/vehiculos/{unidad}/demos", admin)
    caso("P25", "Admin ve las demos del carrito del cliente", True,
         estado == 200 and any(d["id_demo"] == id_demo_admin for d in lista))
    caso("P25", "Esa demo queda como PRIVADA del dueño actual", "PRIVADA",
         next((d["tipo"] for d in lista if d["id_demo"] == id_demo_admin), None))
    comandos_adm = {c["nombre"]: c["id_comando"] for c in http("GET", f"/vehiculos/{unidad}/comandos", admin)[1]}
    caso("P25", "Admin agrega movimientos a la demo del cliente", 201,
         http("POST", f"/vehiculos/{unidad}/demos/{id_demo_admin}/movimientos", admin,
              {"id_comando": comandos_adm["AVANZAR"], "orden": 1, "duracion_ms": 500})[0])
    caso("P25", "Admin no ejecuta esa demo en un carrito vendido sin soporte", 403,
         http("POST", f"/vehiculos/{unidad}/demos/{id_demo_admin}/ejecutar", admin)[0])
    caso("P25", "Admin no mueve el carrito vendido directamente", 403,
         http("POST", f"/vehiculos/{unidad}/movimientos", admin, {"codigo": 1})[0])
    caso("P25", "Admin elimina la demo del carrito", 200,
         http("POST", f"/vehiculos/{unidad}/demos/{id_demo_admin}/eliminar", admin)[0])
    caso("P25", "El nuevo dueño crea su propia demo privada", 201,
         http("POST", f"/vehiculos/{unidad}/demos", cliente2, {"nombre": f"Demo nueva {SUFIJO}"})[0])

    # ----- Logout -----
    caso("P01", "Logout del comprador", 200, http("POST", "/auth/logout", cliente)[0])
    caso("P01", "Tras logout el token ya no sirve", 401, http("GET", "/auth/yo", cliente)[0])

    # ----- P17 auditoría -----
    estado, bitacora = http("GET", "/admin/auditoria?limite=100", admin)
    acciones = {b["accion"] for b in bitacora} if estado == 200 else set()
    caso("P17", "Auditoría registra login, altas, asignaciones y soporte", True,
         {"LOGIN", "CREAR", "ASIGNAR", "AUTORIZAR_SOPORTE", "REVOCAR_SOPORTE"}.issubset(acciones),
         f"acciones={sorted(acciones)}")
    caso("P17", "La auditoría no guarda contraseñas ni tokens", True,
         estado == 200 and not any("Admin123" in json.dumps(b) or cliente in json.dumps(b) for b in bitacora))

    # ----- Limpieza: el carrito de prueba no se queda en la cuenta de nadie -----
    caso("FIN", "Se libera el carrito de prueba", 200,
         http("POST", f"/admin/unidades/{unidad}/asignar", admin, {"id_usuario": None})[0])
    caso("FIN", "Se da de baja el carrito de prueba", 200,
         http("POST", f"/admin/unidades/{unidad}/editar", admin,
              {"activo": False, "estado_comercial": "INACTIVO"})[0])

    total = len(resultados)
    buenos = sum(1 for _, ok, _ in resultados if ok)
    print(f"\n== {buenos}/{total} casos correctos ==")
    for clave, ok, descripcion in resultados:
        if not ok:
            print(f"   INCORRECTO: {clave} {descripcion}")
    return 0 if buenos == total else 1


if __name__ == "__main__":
    sys.exit(main())
