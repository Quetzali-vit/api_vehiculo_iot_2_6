-- =====================================================================
-- 005_soporte_REVERSION.sql · deshace la migración 005
--
-- Quita la tabla de autorizaciones de soporte y sus procedimientos.
-- Después ejecuta 002_procedimientos.sql para restaurar las versiones
-- anteriores de sp_obtener_unidades, sp_obtener_unidad,
-- sp_obtener_mis_vehiculos y sp_asignar_unidad (sin la columna de soporte).
-- No toca vehículos, comandos, historial ni demos.
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_cerrar_soporte_vencido;
DROP PROCEDURE IF EXISTS sp_soporte_vigente;
DROP PROCEDURE IF EXISTS sp_autorizar_soporte;
DROP PROCEDURE IF EXISTS sp_revocar_soporte;
DROP TABLE IF EXISTS `autorizaciones_soporte`;

SELECT 'Reversión de 005 aplicada: ahora ejecuta 002_procedimientos.sql' AS resultado;
