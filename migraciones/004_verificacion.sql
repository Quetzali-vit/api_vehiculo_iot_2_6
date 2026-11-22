-- =====================================================================
-- 004_verificacion.sql · Práctica 4.3
--
-- SOLO CONSULTA. No modifica nada. Sirve como evidencia de que la
-- migración conservó los datos históricos de Amazon RDS.
--
-- Compara el bloque 1 con los conteos que guardaste en el paso 2 de
-- 000_RESPALDO_Y_GUIA.md: deben ser IDÉNTICOS.
-- =====================================================================

SELECT '--- 1. TABLAS DE 4.1/4.2 (deben coincidir con el conteo previo) ---' AS seccion;

SELECT 'vehiculos'          AS tabla, COUNT(*) AS filas FROM vehiculos
UNION ALL SELECT 'comandos',           COUNT(*) FROM comandos
UNION ALL SELECT 'estado_vehiculo',    COUNT(*) FROM estado_vehiculo
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM historial_comandos
UNION ALL SELECT 'demos',              COUNT(*) FROM demos
UNION ALL SELECT 'demo_movimientos',   COUNT(*) FROM demo_movimientos;

SELECT '--- 2. TABLAS NUEVAS DE 4.3 ---' AS seccion;

SELECT 'roles'             AS tabla, COUNT(*) AS filas FROM roles
UNION ALL SELECT 'usuarios',          COUNT(*) FROM usuarios
UNION ALL SELECT 'sesiones',          COUNT(*) FROM sesiones
UNION ALL SELECT 'modelos',           COUNT(*) FROM modelos
UNION ALL SELECT 'sesiones_invitado', COUNT(*) FROM sesiones_invitado
UNION ALL SELECT 'auditoria',         COUNT(*) FROM auditoria;

SELECT '--- 3. COLUMNAS AGREGADAS A TABLAS EXISTENTES ---' AS seccion;

SELECT TABLE_NAME AS tabla, COLUMN_NAME AS columna, COLUMN_TYPE AS tipo, IS_NULLABLE AS acepta_null
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND ((TABLE_NAME = 'vehiculos' AND COLUMN_NAME IN ('id_modelo','id_propietario','numero_serie','estado_comercial'))
     OR (TABLE_NAME = 'demos'     AND COLUMN_NAME = 'id_propietario'))
 ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT '--- 4. LLAVES FORANEAS NUEVAS ---' AS seccion;

SELECT CONSTRAINT_NAME AS restriccion, TABLE_NAME AS tabla, COLUMN_NAME AS columna,
       REFERENCED_TABLE_NAME AS apunta_a
  FROM information_schema.KEY_COLUMN_USAGE
 WHERE TABLE_SCHEMA = DATABASE()
   AND CONSTRAINT_NAME IN ('fk_vehiculo_modelo','fk_vehiculo_propietario','fk_demo_propietario',
                           'fk_usuario_rol','fk_sesion_usuario','fk_invitado_vehiculo','fk_auditoria_usuario')
 ORDER BY TABLE_NAME, CONSTRAINT_NAME;

SELECT '--- 5. PROCEDIMIENTOS (21 anteriores + los nuevos de 4.3) ---' AS seccion;

SELECT COUNT(*) AS procedimientos_totales
  FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE';

-- Si alguno de los 21 originales falta, la lista siguiente lo revela
SELECT ROUTINE_NAME AS procedimiento
  FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE'
   AND ROUTINE_NAME IN ('sp_crear_vehiculo','sp_obtener_vehiculos','sp_obtener_vehiculo',
                        'sp_actualizar_vehiculo','sp_eliminar_vehiculo','sp_crear_comando',
                        'sp_obtener_comandos_vehiculo','sp_actualizar_comando','sp_eliminar_comando',
                        'sp_actualizar_estado','sp_obtener_estado','sp_registrar_historial',
                        'sp_obtener_historial','sp_crear_demo','sp_obtener_demos','sp_actualizar_demo',
                        'sp_eliminar_demo','sp_agregar_movimiento_demo','sp_obtener_movimientos_demo',
                        'sp_actualizar_movimiento_demo','sp_eliminar_movimiento_demo')
 ORDER BY ROUTINE_NAME;

SELECT '--- 6. INVENTARIO COMERCIAL RESULTANTE ---' AS seccion;

SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial,
       m.nombre AS modelo, u.correo AS propietario
  FROM vehiculos v
  LEFT JOIN modelos m  ON m.id_modelo = v.id_modelo
  LEFT JOIN usuarios u ON u.id_usuario = v.id_propietario
 ORDER BY v.id_vehiculo;

SELECT '--- 7. HISTORIAL INTACTO (los 10 mas recientes del vehiculo 1) ---' AS seccion;

SELECT h.id_historial, c.nombre AS comando, h.fecha_hora, h.origen
  FROM historial_comandos h
  LEFT JOIN comandos c ON c.id_comando = h.id_comando
 WHERE h.id_vehiculo = 1
 ORDER BY h.id_historial DESC
 LIMIT 10;
