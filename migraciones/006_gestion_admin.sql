-- =====================================================================
-- 006_gestion_admin.sql · Práctica 4.3 — Gestión del administrador
--
-- Solo agrega procedimientos de consulta para la vista de cuenta de cliente:
-- sesiones activas (login e invitados) y bitácora de un cliente.
-- No modifica tablas ni datos existentes.
-- =====================================================================

SET NAMES utf8mb4;
DELIMITER $$

-- Sesiones de inicio de sesión vigentes (usuarios que tienen un token válido).
DROP PROCEDURE IF EXISTS sp_sesiones_activas$$
CREATE PROCEDURE sp_sesiones_activas()
BEGIN
  SELECT s.id_sesion, s.id_usuario, u.nombre, u.correo, r.clave AS rol,
         s.fecha_inicio, s.fecha_expira,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), s.fecha_expira), 0) AS segundos_restantes
    FROM sesiones s
    JOIN usuarios u ON u.id_usuario = s.id_usuario
    JOIN roles r    ON r.id_rol = u.id_rol
   WHERE s.revocada = 0 AND s.fecha_expira > NOW()
   ORDER BY s.fecha_inicio DESC;
END$$

-- Pruebas de invitado vigentes (cada una ocupa una unidad de exhibición).
DROP PROCEDURE IF EXISTS sp_pruebas_activas$$
CREATE PROCEDURE sp_pruebas_activas()
BEGIN
  SELECT si.id_sesion_invitado, si.id_vehiculo, v.nombre AS vehiculo,
         si.nombre_invitado, si.fecha_inicio, si.fecha_expira,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), si.fecha_expira), 0) AS segundos_restantes
    FROM sesiones_invitado si
    JOIN vehiculos v ON v.id_vehiculo = si.id_vehiculo
   WHERE si.activa = 1 AND si.fecha_expira > NOW()
   ORDER BY si.fecha_inicio DESC;
END$$

-- Bitácora de un cliente: lo que hizo él o se hizo sobre sus recursos.
DROP PROCEDURE IF EXISTS sp_auditoria_usuario$$
CREATE PROCEDURE sp_auditoria_usuario(IN p_id_usuario INT, IN p_correo VARCHAR(120), IN p_limite INT)
BEGIN
  IF p_limite IS NULL OR p_limite < 1 THEN SET p_limite = 50; END IF;
  IF p_limite > 200 THEN SET p_limite = 200; END IF;
  SELECT a.id_auditoria, a.fecha_hora, a.id_usuario, a.actor, a.accion,
         a.recurso, a.id_recurso, a.resultado, a.detalle
    FROM auditoria a
   WHERE a.id_usuario = p_id_usuario OR a.actor = p_correo
   ORDER BY a.id_auditoria DESC
   LIMIT p_limite;
END$$

DELIMITER ;

SELECT 'Migración 006 (gestión admin) aplicada' AS resultado;
