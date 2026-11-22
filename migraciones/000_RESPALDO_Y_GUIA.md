# Migraciones 4.3 — Administración IoT

Amplían el esquema `vehiculo_iot` para roles, usuarios, modelos comerciales, propiedad de
unidades, demos privadas, sesiones de invitado y auditoría. **No borran ni vacían nada de
lo que ya existe**: todas las tablas y los 21 procedimientos de 4.1/4.2 siguen igual.

> **MySQL confirma el DDL de forma implícita.** Un `CREATE TABLE` o un `ALTER TABLE` no se
> puede deshacer con `ROLLBACK`. Por eso el respaldo del paso 1 no es opcional: es la única
> vuelta atrás real si algo sale mal.

## Orden de aplicación

| Archivo | Qué hace | Reversible |
|---|---|---|
| `001_estructura.sql` | Crea tablas nuevas y agrega columnas a `vehiculos` y `demos` | Sí, con `001_estructura_REVERSION.sql` |
| `002_procedimientos.sql` | Crea los procedimientos nuevos (no toca los 21 anteriores) | Sí, con `DROP PROCEDURE` |
| `003_datos_iniciales.sql` | Inserta los dos roles, el usuario administrador y el modelo del vehículo que ya existe | Sí |
| `004_verificacion.sql` | Solo consulta: compara conteos y relaciones antes/después | No modifica nada |

## Paso 1 — Respaldo (obligatorio, antes de todo)

En el servidor EC2, con MySQL en el PATH:

```bash
mysqldump -h TU_ENDPOINT_RDS -u admin -p --routines --triggers --single-transaction vehiculo_iot > respaldo_antes_4_3.sql
```

`--routines` incluye los 21 procedimientos. Comprueba que el archivo **no** esté vacío y
anota su tamaño antes de seguir.

## Paso 2 — Conteos previos

Guarda este resultado para compararlo al final:

```sql
SELECT 'vehiculos' t, COUNT(*) n FROM vehiculos
UNION ALL SELECT 'comandos', COUNT(*) FROM comandos
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM historial_comandos
UNION ALL SELECT 'demos', COUNT(*) FROM demos
UNION ALL SELECT 'demo_movimientos', COUNT(*) FROM demo_movimientos
UNION ALL SELECT 'estado_vehiculo', COUNT(*) FROM estado_vehiculo;
```

## Paso 3 — Aplicar

```bash
mysql -h TU_ENDPOINT_RDS -u admin -p vehiculo_iot < migraciones/001_estructura.sql
mysql -h TU_ENDPOINT_RDS -u admin -p vehiculo_iot < migraciones/002_procedimientos.sql
mysql -h TU_ENDPOINT_RDS -u admin -p vehiculo_iot < migraciones/003_datos_iniciales.sql
mysql -h TU_ENDPOINT_RDS -u admin -p vehiculo_iot < migraciones/004_verificacion.sql
```

Si algún archivo da error, **detente ahí** y revisa el mensaje antes de continuar con el
siguiente: cada uno depende del anterior.

## Paso 4 — Comprobar

`004_verificacion.sql` imprime los conteos de las tablas antiguas (deben ser **idénticos**
a los del paso 2), las tablas nuevas y las relaciones. Si un conteo bajó, restaura el
respaldo y revisa qué pasó.

## Reversión

`001_estructura_REVERSION.sql` quita lo agregado y devuelve el esquema al estado de 4.2.
Borra los datos de las tablas nuevas (usuarios, sesiones, auditoría), que no existían antes,
pero **no** toca vehículos, comandos, historial ni demos.
