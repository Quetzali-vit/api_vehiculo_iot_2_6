-- =====================================================================
-- 001_estructura_REVERSION.sql · deshace la migración 001
--
-- Devuelve el esquema al estado de la práctica 4.2.
-- Borra las tablas creadas en 4.3 (usuarios, sesiones, modelos, invitados,
-- auditoría) porque antes no existían. NO toca vehiculos, comandos,
-- estado_vehiculo, historial_comandos, demos ni demo_movimientos: solo les
-- quita las columnas que 001 les agregó.
--
-- Úsalo en el ambiente de prueba. En producción, la vuelta atrás real es
-- restaurar el respaldo del paso 1.
-- =====================================================================

SET NAMES utf8mb4;

-- 1. Quitar llaves foráneas y columnas agregadas a tablas existentes
SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'demos' AND CONSTRAINT_NAME = 'fk_demo_propietario');
SET @sql := IF(@hay > 0, 'ALTER TABLE `demos` DROP FOREIGN KEY `fk_demo_propietario`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'demos' AND COLUMN_NAME = 'id_propietario');
SET @sql := IF(@hay > 0, 'ALTER TABLE `demos` DROP COLUMN `id_propietario`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND CONSTRAINT_NAME = 'fk_vehiculo_propietario');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP FOREIGN KEY `fk_vehiculo_propietario`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND CONSTRAINT_NAME = 'fk_vehiculo_modelo');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP FOREIGN KEY `fk_vehiculo_modelo`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND INDEX_NAME = 'uq_vehiculo_serie');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP INDEX `uq_vehiculo_serie`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'estado_comercial');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP COLUMN `estado_comercial`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'numero_serie');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP COLUMN `numero_serie`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'id_propietario');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP COLUMN `id_propietario`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'id_modelo');
SET @sql := IF(@hay > 0, 'ALTER TABLE `vehiculos` DROP COLUMN `id_modelo`', 'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 2. Procedimientos nuevos de 4.3 (los 21 originales NO se tocan)
DROP PROCEDURE IF EXISTS sp_login_usuario;
DROP PROCEDURE IF EXISTS sp_crear_usuario;
DROP PROCEDURE IF EXISTS sp_obtener_usuarios;
DROP PROCEDURE IF EXISTS sp_obtener_usuario;
DROP PROCEDURE IF EXISTS sp_actualizar_usuario;
DROP PROCEDURE IF EXISTS sp_crear_sesion;
DROP PROCEDURE IF EXISTS sp_obtener_sesion;
DROP PROCEDURE IF EXISTS sp_revocar_sesion;
DROP PROCEDURE IF EXISTS sp_crear_modelo;
DROP PROCEDURE IF EXISTS sp_obtener_modelos;
DROP PROCEDURE IF EXISTS sp_obtener_modelo;
DROP PROCEDURE IF EXISTS sp_actualizar_modelo;
DROP PROCEDURE IF EXISTS sp_obtener_unidades;
DROP PROCEDURE IF EXISTS sp_obtener_unidad;
DROP PROCEDURE IF EXISTS sp_actualizar_comercial;
DROP PROCEDURE IF EXISTS sp_asignar_unidad;
DROP PROCEDURE IF EXISTS sp_obtener_mis_vehiculos;
DROP PROCEDURE IF EXISTS sp_catalogo_publico;
DROP PROCEDURE IF EXISTS sp_crear_sesion_invitado;
DROP PROCEDURE IF EXISTS sp_obtener_sesion_invitado;
DROP PROCEDURE IF EXISTS sp_finalizar_sesion_invitado;
DROP PROCEDURE IF EXISTS sp_expirar_sesiones_invitado;
DROP PROCEDURE IF EXISTS sp_registrar_auditoria;
DROP PROCEDURE IF EXISTS sp_obtener_auditoria;
DROP PROCEDURE IF EXISTS sp_metricas_dashboard;
DROP PROCEDURE IF EXISTS sp_crear_demo_propietario;
DROP PROCEDURE IF EXISTS sp_obtener_demos_visibles;
DROP PROCEDURE IF EXISTS sp_obtener_demo;
DROP PROCEDURE IF EXISTS sp_reserva_activa_vehiculo;

-- 3. Tablas nuevas (en orden inverso a las dependencias)
DROP TABLE IF EXISTS `auditoria`;
DROP TABLE IF EXISTS `sesiones_invitado`;
DROP TABLE IF EXISTS `sesiones`;
DROP TABLE IF EXISTS `usuarios`;
DROP TABLE IF EXISTS `roles`;
DROP TABLE IF EXISTS `modelos`;

SELECT 'Reversión de 001 aplicada' AS resultado;
