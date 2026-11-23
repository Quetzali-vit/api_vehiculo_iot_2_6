-- Deshace 006_gestion_admin.sql: solo quita los procedimientos de consulta nuevos.
DROP PROCEDURE IF EXISTS sp_sesiones_activas;
DROP PROCEDURE IF EXISTS sp_pruebas_activas;
DROP PROCEDURE IF EXISTS sp_auditoria_usuario;

SELECT 'Reversión de 006 aplicada' AS resultado;
