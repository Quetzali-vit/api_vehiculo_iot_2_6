# API Vehículo IoT 

API en **Python + FastAPI**, organizada con programación orientada a objetos, que usa los
**21 Stored Procedures** del esquema `vehiculo_iot` alojado en **Amazon RDS**.
Incluye servicios GET y POST, monitoreo por **WebSocket** y ejecución de DEMO.

> Publicada en Amazon EC2 con HTTPS/WSS:
>
> - Swagger UI: https://quetzali-iot.duckdns.org/docs
> - WebSocket: 
      URL pública: `wss://quetzali-iot.duckdns.org/ws/vehiculos/{id_vehiculo}`
      URL local: `ws://localhost:8000/ws/vehiculos/{id_vehiculo}`
>
> En un equipo local también se puede ejecutar en `http://localhost:8000`.

## Práctica 4.3 — Administración comercial, roles y autorización

Ampliación **incremental** de la misma API: los 21 procedimientos y las rutas que usan CONTROL y MONITOREO siguen ahí, ahora protegidas por sesión. De 27 operaciones se pasó a **50**; solo cinco quedan públicas: `GET /`, `GET /salud`, `POST /auth/login`, `GET /catalogo` y `POST /invitados/pruebas`.

### Modelo de negocio

| Rol | Es | Puede |
|---|---|---|
| `ADMIN` | La empresa | Gestionar modelos, unidades, clientes, asignaciones, demos de fábrica y ver la auditoría. Opera unidades **sin dueño**; una unidad vendida solo la monitorea, salvo que el comprador le conceda una **autorización de soporte** vigente. |
| `USUARIO` | El comprador | Operar, monitorear y ver el historial **solo de sus unidades**; crear demos privadas y ejecutar las de fábrica. |
| Invitado | Cliente potencial (sin cuenta) | Una sesión temporal sobre una unidad en `EXHIBICION`: exclusiva, con tiempo límite y solo comandos de movimiento y DETENER. |

### Diagrama entidad-relación

```
roles 1───N usuarios 1───N sesiones
                │ 1
                │
                N (id_propietario, NULL = sin dueño)
modelos 1───N vehiculos (UNIDAD física) 1───N comandos
                │ 1        │ 1───1 estado_vehiculo
                │          │ 1───N historial_comandos
                │          │ 1───N sesiones_invitado (UNIQUE id_vehiculo+activa)
                │          └─1───N demos (id_propietario NULL = de fábrica) 1───N demo_movimientos
usuarios 1───N auditoria
```

- **MODELO** (`modelos`) es lo que se vende; **UNIDAD** (`vehiculos`) es la pieza física con `numero_serie` único, `estado_comercial` (DISPONIBLE, VENDIDO, EXHIBICION, INACTIVO) y `id_propietario`. El `id_vehiculo` no cambió: es el mismo que usan CONTROL y MONITOREO.
- Tablas nuevas: `roles`, `usuarios`, `sesiones`, `modelos`, `sesiones_invitado`, `auditoria`. Columnas nuevas: `vehiculos.id_modelo`, `id_propietario`, `numero_serie`, `estado_comercial`; `demos.id_propietario`. Todas admiten NULL o tienen valor por omisión, así que ninguna fila previa quedó inválida.
- Baja lógica en usuarios, modelos y unidades (`activo`). No se borra nada con historial.

### Migraciones (`migraciones/`)

| Archivo | Contenido |
|---|---|
| `000_RESPALDO_Y_GUIA.md` | Respaldo, orden de aplicación y reversión |
| `001_estructura.sql` | Tablas y columnas (idempotente: revisa `information_schema` antes de cada ALTER) |
| `001_estructura_REVERSION.sql` | Devuelve el esquema al de 4.2 |
| `002_procedimientos.sql` | 29 procedimientos nuevos; los 21 anteriores no se tocan |
| `003_datos_iniciales.sql` | Roles, cuentas de demostración y el modelo de la unidad existente |
| `004_verificacion.sql` | Solo consulta: conteos, columnas, llaves y procedimientos |
| `005_soporte.sql` | Tabla `autorizaciones_soporte` y sus procedimientos (reversión: `005_soporte_REVERSION.sql`) |
| `aplicar.py` | Respaldo → copia de prueba aislada → base real → comparación de conteos → registro |

```bash
.venv\Scripts\python.exe migraciones\aplicar.py
```

MySQL confirma el DDL de forma implícita (un `ALTER` no se deshace con `ROLLBACK`); por eso `aplicar.py` respalda primero, prueba en una base `vehiculo_iot_prueba_<fecha>` y solo si los conteos se conservan toca la real. **Aplicada en Amazon RDS el 23/11/2026:** respaldo de 158 934 bytes, copia de prueba correcta y conteos idénticos antes/después (859 movimientos de historial, 21 comandos, 5 demos, 21 pasos). Total: 50 procedimientos.

### Autenticación y autorización

- `POST /auth/login` devuelve un token aleatorio de 256 bits. La base guarda **solo su SHA-256** en `sesiones`; la contraseña se guarda como hash PBKDF2-SHA256 (210 000 iteraciones), sin dependencias nuevas. `POST /auth/logout` revoca el token; expira a las 8 h.
- Cada ruta protegida usa `Authorization: Bearer <token>`. El usuario, su rol y la propiedad de la unidad se leen **de la base en cada petición**; nunca del cuerpo. Un comprador que cambia el id en la URL recibe **404** (no se confirma que la unidad exista). 401 sin sesión, 403 sin permiso, 409 en conflictos de negocio.
- **WebSocket:** `wss://…/ws/vehiculos/{id}?token=<token>`. Excepción: la unidad en **EXHIBICION** (la del catálogo público) se puede *escuchar* sin token (`wss://…/ws/vehiculos/1`); escuchar no permite mover nada y las unidades vendidas siguen exigiendo token. Los rechazos llegan con su código y motivo (4401, 4403, 4404), no como 1006. Se valida identidad y acceso a la unidad antes de suscribir y en cada mensaje; cierra con 4401 (sin sesión), 4403 (sin permiso) o 4404. El ESP32 se identifica como dispositivo con `?clave=<API_KEY>`.
- **Invitados:** la exclusividad la garantiza la base con el índice `UNIQUE (id_vehiculo, activa)`; dos peticiones simultáneas no pueden reservar la misma unidad. Un vigilante cada 20 s cierra las pruebas vencidas y manda DETENER por el camino normal (estado, historial y WebSocket). Mientras hay prueba vigente, ni el Admin mueve esa unidad.
- **Soporte operativo:** el comprador concede desde «Mis vehículos» de 5 a 120 minutos (`POST /mis-vehiculos/{id}/soporte`) y puede revocarlo (`…/soporte/revocar`). Sin autorización vigente, la API responde 403 a cualquier movimiento del Admin sobre una unidad vendida; con ella, el movimiento queda en el historial como `WEB-SOPORTE`. Una sola autorización vigente por unidad (`UNIQUE id_vehiculo+activa`), y reasignar la unidad la cancela.
- **Auditoría:** login, altas, cambios, asignaciones, demos y pruebas, con actor, acción, recurso y resultado. Nunca guarda contraseñas ni tokens.

### Endpoints nuevos

| Método y ruta | Rol |
|---|---|
| `POST /auth/login` · `POST /auth/logout` · `GET /auth/yo` | Público / sesión |
| `GET /admin/metricas` | ADMIN |
| `GET·POST /admin/usuarios` · `GET /admin/usuarios/{id}` · `POST …/actualizar` | ADMIN |
| `GET·POST /admin/modelos` · `GET /admin/modelos/{id}` · `POST …/actualizar` | ADMIN |
| `GET·POST /admin/unidades` · `GET /admin/unidades/{id}` · `POST …/comercial` · `POST …/asignar` | ADMIN |
| `GET /admin/auditoria` | ADMIN |
| `GET /mis-vehiculos` | USUARIO |
| `GET·POST /mis-vehiculos/{id}/soporte` · `POST …/soporte/revocar` | USUARIO dueño |
| `GET /catalogo` | Público |
| `POST /invitados/pruebas` · `GET …/actual` · `POST …/terminar` | Público / invitado |

Las rutas de 4.1/4.2 ahora exigen sesión y acceso a la unidad; las de DEMO distinguen de fábrica (las edita el Admin) y privadas (solo su dueño).

### Variables de entorno (solo nombres)

`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `API_KEY` (clave del dispositivo), `ORIGEN_MOVIMIENTO`, `CORS_ORIGINS`, `HOST`, `PORT`.

### Pruebas

```bash
python pruebas/prueba_roles.py                          # contra la API publicada
python pruebas/prueba_roles.py http://127.0.0.1:8000    # contra una API local
```

53 casos P00–P17 (login, alta de unidad y cliente, asignación, aislamiento entre compradores, control, WSS, historial de 10, demo persistente, ejecución y cancelación, invitado, rechazos 403/404, exclusividad, reasignación con revocación inmediata, logout y auditoría). Resultado contra `https://quetzali-iot.duckdns.org` el 23/11/2026: **53/53 correctos**.

## Arquitectura

```
app/
├── main.py                  # Crea la app FastAPI, registra routers y manejo de errores
├── dependencies.py          # Contenedor: crea y conecta una instancia de cada componente
├── core/
│   ├── config.py            # Settings: variables de entorno (.env)
│   ├── exceptions.py        # Errores de negocio → códigos HTTP
│   └── security.py          # Autorización con el encabezado X-API-Key
├── db/database.py           # Database y SesionSP: conexión a RDS, transacciones y CALL con parámetros enlazados
├── repositories/            # Una clase por tabla; cada método llama a un Stored Procedure
├── services/                # Reglas de negocio (validaciones, transacciones, DEMO)
│   ├── reglas.py            # Existencia, pertenencia y estado activo
│   ├── movimiento_service.py# Movimiento individual: estado + historial en una transacción
│   ├── demo_service.py      # CRUD de DEMO y preparación de la ejecución
│   └── demo_executor.py     # Ejecución asíncrona de la DEMO, cancelación y concurrencia
├── schemas/                 # Modelos Pydantic de entrada y salida
├── routers/                 # Endpoints HTTP y WebSocket (sin lógica de persistencia)
└── websocket/               # GestorWebSocket (clientes por vehículo) y formato de eventos
```

Flujo: **Router → Service → Repository → Stored Procedure → Amazon RDS**.

## Ejecución local

1. Clona el repositorio y entra a la carpeta.
2. Crea y activa el entorno virtual:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Copia `.env.example` como `.env` y escribe el endpoint, el usuario y la contraseña de RDS,
   además de una clave propia en `API_KEY`. **El archivo `.env` no se sube a GitHub.**
4. En el Security Group de RDS, la regla MySQL/Aurora (TCP 3306) debe tener como origen **Mi IP**.
5. Inicia el servidor:
   ```powershell
   python -m app.main
   ```
6. Abre `http://localhost:8000/docs` (Swagger UI) y prueba `GET /salud` para confirmar la conexión con RDS.

## Seguridad

Las operaciones de **control** (movimientos, estado manual, iniciar o cancelar DEMO) y de **eliminación**
piden el encabezado `X-API-Key` con el valor de `API_KEY`. Sin él responde **401** y con una clave
incorrecta **403**. En Swagger se usa el botón **Authorize**.

Los Stored Procedures se llaman con parámetros enlazados (`CALL sp_x(%s, %s)`); nunca se concatenan valores
del usuario en el SQL. Además, solo se permiten los 21 nombres de la lista fija de `database.py`.

## Endpoints y Stored Procedures

| Método | Ruta | Stored Procedures |
|---|---|---|
| GET | `/vehiculos` | `sp_obtener_vehiculos` |
| GET | `/vehiculos/{id}` | `sp_obtener_vehiculo`, `sp_obtener_comandos_vehiculo`, `sp_obtener_estado`, `sp_obtener_demos` |
| POST | `/vehiculos` | `sp_crear_vehiculo` |
| POST | `/vehiculos/{id}/actualizar` | `sp_actualizar_vehiculo` |
| POST 🔒 | `/vehiculos/{id}/eliminar` | `sp_eliminar_vehiculo` |
| GET | `/vehiculos/{id}/comandos` | `sp_obtener_comandos_vehiculo` |
| POST | `/vehiculos/{id}/comandos` | `sp_crear_comando` |
| POST | `/vehiculos/{id}/comandos/{id_comando}/actualizar` | `sp_actualizar_comando` |
| POST 🔒 | `/vehiculos/{id}/comandos/{id_comando}/eliminar` | `sp_eliminar_comando` |
| GET | `/vehiculos/{id}/estado` | `sp_obtener_estado` |
| POST 🔒 | `/vehiculos/{id}/estado` | `sp_actualizar_estado` |
| POST 🔒 | `/vehiculos/{id}/movimientos` | `sp_actualizar_estado` + `sp_registrar_historial` (una transacción) |
| GET | `/vehiculos/{id}/historial` | `sp_obtener_historial` (máximo 10) |
| GET | `/vehiculos/{id}/demos` | `sp_obtener_demos` |
| POST | `/vehiculos/{id}/demos` | `sp_crear_demo` |
| POST | `/vehiculos/{id}/demos/{id_demo}/actualizar` | `sp_actualizar_demo` |
| POST 🔒 | `/vehiculos/{id}/demos/{id_demo}/eliminar` | `sp_eliminar_demo` |
| GET | `/vehiculos/{id}/demos/{id_demo}/movimientos` | `sp_obtener_movimientos_demo` |
| POST | `/vehiculos/{id}/demos/{id_demo}/movimientos` | `sp_agregar_movimiento_demo` |
| POST | `/vehiculos/{id}/demos/{id_demo}/movimientos/{id_mov}/actualizar` | `sp_actualizar_movimiento_demo` |
| POST 🔒 | `/vehiculos/{id}/demos/{id_demo}/movimientos/{id_mov}/eliminar` | `sp_eliminar_movimiento_demo` |
| POST 🔒 | `/vehiculos/{id}/demos/{id_demo}/ejecutar` | `sp_obtener_movimientos_demo`, `sp_actualizar_estado` (sin historial) |
| POST 🔒 | `/vehiculos/{id}/demos/cancelar` | `sp_actualizar_estado` (DETENER) |
| GET | `/vehiculos/{id}/demos/ejecucion` | — (consulta en memoria) |
| GET | `/salud` | — (prueba la conexión con RDS) |

🔒 = requiere `X-API-Key`. Swagger UI detalla en cada operación todos los SP que intervienen.

### Códigos de respuesta

| Código | Cuándo |
|---|---|
| 200 | Consulta o actualización correcta |
| 201 | Registro creado o movimiento registrado |
| 202 | DEMO aceptada; los movimientos llegan por WebSocket |
| 400 | Referencia a un registro inexistente o valor fuera de rango en la base |
| 401 / 403 | Falta `X-API-Key` / la clave no es válida |
| 404 | El vehículo, comando, DEMO o movimiento no existe o no pertenece al vehículo |
| 409 | Vehículo o comando inactivo, valor duplicado, comando usado en una DEMO o DEMO en curso |
| 422 | El JSON no cumple el modelo (tipos, rangos, campos obligatorios) |
| 500 | Error interno (sin exponer detalles) |
| 503 | Amazon RDS no responde |

## Reglas de negocio

**Movimiento individual** (`POST /vehiculos/{id}/movimientos`)
1. El vehículo debe existir y estar activo.
2. El comando (por `id_comando` o `codigo`) debe existir, estar activo y pertenecer a **ese** vehículo.
3. `sp_actualizar_estado` y `sp_registrar_historial` se ejecutan en **una sola transacción**.
4. Solo después del `COMMIT` se publica el evento `movimiento` por WebSocket.
5. Si algo falla, no se modifica nada ni se envía un evento exitoso.
6. El campo `conectado` conserva su valor en RDS: recibir un POST no significa que el ESP32 esté conectado.

**DEMO** (`POST /vehiculos/{id}/demos/{id_demo}/ejecutar`)
- Lee los N movimientos con `sp_obtener_movimientos_demo`; no hay ninguna secuencia fija en el código.
- Los procesa en orden y espera `duracion_ms` y después `pausa_ms` en cada uno, sin bloquear la API.
- Actualiza el estado con `sp_actualizar_estado`, pero **nunca** llama a `sp_registrar_historial`.
- Solo puede haber una DEMO a la vez por vehículo (409).
- `POST /vehiculos/{id}/demos/cancelar` o un movimiento `DETENER` la cancelan de inmediato. El estado queda en DETENER.

**Historial** (`GET /vehiculos/{id}/historial`): devuelve como máximo los **10** movimientos individuales
más recientes. `total_registrados` muestra cuántos hay en RDS y `devueltos` cuántos se envían. Si hay menos
de 10, devuelve solo los disponibles. El historial completo se conserva en RDS.

## WebSocket

Swagger UI no documenta WebSocket, por eso se describe aquí.

**URL pública:** `wss://quetzali-iot.duckdns.org/ws/vehiculos/{id_vehiculo}`

**URL local:** `ws://localhost:8000/ws/vehiculos/{id_vehiculo}`

- Cada cliente recibe solo los eventos del vehículo que monitorea.
- Varios clientes pueden conectarse al mismo vehículo.
- Al conectarse, recibe de inmediato el último estado guardado en RDS.
- El cliente puede enviar `ping` (responde `pong`) o `estado` (vuelve a enviar el estado actual).
- Si el vehículo no existe, recibe un evento `error` y la conexión se cierra con el código 4404.

Todos los mensajes comparten estos campos:

```json
{ "evento": "…", "id_vehiculo": 1, "comando": "AVANZAR", "codigo": 1, "timestamp": "2026-10-15T13:00:00.000+00:00" }
```

| Evento | Cuándo | Campos extra |
|---|---|---|
| `estado_actual` | Al conectarse o al enviar `estado` | `conectado`, `fecha_actualizacion` |
| `movimiento` | Un POST registró un movimiento individual | `id_comando`, `origen`, `conectado` |
| `demo_inicio` | Empieza una DEMO | `id_demo`, `demo`, `total_movimientos` |
| `demo_movimiento` | Cada uno de los N movimientos | `id_demo`, `demo`, `orden`, `total_movimientos`, `duracion_ms`, `pausa_ms` |
| `demo_fin` | Terminó la DEMO | `id_demo`, `demo`, `total_movimientos` |
| `demo_cancelada` | Se canceló la DEMO | `id_demo`, `demo`, `mensaje` (comando = DETENER) |
| `demo_error` | Falló RDS durante la DEMO | `id_demo`, `demo`, `mensaje` |
| `pong` / `error` | Respuesta a `ping` / mensaje no reconocido o vehículo inexistente | `mensaje` |

Ejemplo de una DEMO:

```json
{"evento":"demo_inicio","id_vehiculo":1,"comando":null,"codigo":null,"id_demo":1,"demo":"Demo principal","total_movimientos":8,"timestamp":"…"}
{"evento":"demo_movimiento","id_vehiculo":1,"comando":"AVANZAR","codigo":1,"id_demo":1,"demo":"Demo principal","orden":1,"total_movimientos":8,"duracion_ms":2000,"pausa_ms":400,"timestamp":"…"}
…
{"evento":"demo_fin","id_vehiculo":1,"comando":null,"codigo":null,"id_demo":1,"demo":"Demo principal","total_movimientos":8,"timestamp":"…"}
```

> Los eventos solo avisan que se envió un movimiento; no confirman que el motor lo ejecutó.
> La confirmación del ESP8266/ESP32 se integrará en una práctica posterior.

## Pruebas en Thunder Client

Las pruebas públicas usan `https://quetzali-iot.duckdns.org` y `wss://quetzali-iot.duckdns.org`
en lugar de `http://localhost:8000` y `ws://localhost:8000`.

1. **POST** `http://localhost:8000/vehiculos/1/movimientos` con el encabezado `X-API-Key` y el cuerpo
   `{"codigo": 1}` → 201. Después se comprueba con `GET /vehiculos/1/estado` y `GET /vehiculos/1/historial`.
2. **GET** `http://localhost:8000/vehiculos/1/historial` → máximo 10 registros, del más reciente al más antiguo.
3. **WebSocket** `ws://localhost:8000/ws/vehiculos/1` y, con la conexión abierta,
   **POST** `http://localhost:8000/vehiculos/1/demos/1/ejecutar` (con `X-API-Key`). Se reciben `demo_inicio`,
   los N `demo_movimiento` y `demo_fin`. El `total_registrados` del historial es el mismo antes y después.
