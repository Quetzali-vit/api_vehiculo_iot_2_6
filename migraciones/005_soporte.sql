-- =====================================================================
-- 005_soporte.sql · Práctica 4.3 — Autorización de soporte operativo
--
-- «El Administrador requerirá autorización explícita para soporte operativo
-- en unidades vendidas.» El COMPRADOR concede al Administrador, por un tiempo
-- limitado, permiso para operar SU unidad; puede revocarlo cuando quiera y al
-- vencer se cierra solo. Mientras no exista una autorización vigente, la API
-- rechaza (403) cualquier movimiento del Administrador sobre una unidad vendida.
--
-- Solo agrega una tabla y procedimientos; no toca datos existentes.
-- Idempotente: se puede ejecutar más de una vez.
-- =====================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- Tabla: una autorización vigente como máximo por unidad.
-- activa = 1 mientras dura y NULL al terminar; el índice UNIQUE
-- (id_vehiculo, activa) lo garantiza en la base de datos.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `autorizaciones_soporte` (
  `id_autorizacion` BIGINT      NOT NULL AUTO_INCREMENT,
  `id_vehiculo`     INT         NOT NULL,
  `id_propietario`  INT         NOT NULL,
  `fecha_inicio`    TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_expira`    DATETIME    NOT NULL,
  `fecha_fin`       DATETIME    DEFAULT NULL,
  `motivo_fin`      VARCHAR(30) DEFAULT NULL,
  `activa`          TINYINT(1)  DEFAULT 1,
  PRIMARY KEY (`id_autorizacion`),
  UNIQUE KEY `uq_soporte_activo` (`id_vehiculo`, `activa`),
  KEY `fk_soporte_propietario` (`id_propietario`),
  CONSTRAINT `fk_soporte_vehiculo` FOREIGN KEY (`id_vehiculo`) REFERENCES `vehiculos` (`id_vehiculo`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_soporte_propietario` FOREIGN KEY (`id_propietario`) REFERENCES `usuarios` (`id_usuario`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELIMITER $$

-- Cierra las autorizaciones vencidas (se llama antes de consultar o conceder).
DROP PROCEDURE IF EXISTS sp_cerrar_soporte_vencido$$
CREATE PROCEDURE sp_cerrar_soporte_vencido()
BEGIN
  UPDATE autorizaciones_soporte
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'EXPIRADA'
   WHERE activa = 1 AND fecha_expira <= NOW();
END$$

-- Autorización vigente de una unidad (vacío si no hay).
DROP PROCEDURE IF EXISTS sp_soporte_vigente$$
CREATE PROCEDURE sp_soporte_vigente(IN p_id_vehiculo INT)
BEGIN
  CALL sp_cerrar_soporte_vencido();
  SELECT a.id_autorizacion, a.id_vehiculo, a.id_propietario, a.fecha_inicio, a.fecha_expira,
         GREATEST(TIMESTAMPDIFF(SECOND, NOW(), a.fecha_expira), 0) AS segundos_restantes
    FROM autorizaciones_soporte a
   WHERE a.id_vehiculo = p_id_vehiculo AND a.activa = 1 AND a.fecha_expira > NOW();
END$$

-- El dueño concede (o renueva) el soporte. Solo procede si p_id_usuario es
-- el propietario actual: el procedimiento lo vuelve a comprobar.
DROP PROCEDURE IF EXISTS sp_autorizar_soporte$$
CREATE PROCEDURE sp_autorizar_soporte(IN p_id_vehiculo INT, IN p_id_usuario INT, IN p_minutos INT)
BEGIN
  DECLARE v_dueno INT DEFAULT NULL;
  SELECT id_propietario INTO v_dueno FROM vehiculos WHERE id_vehiculo = p_id_vehiculo;
  IF v_dueno IS NULL OR v_dueno <> p_id_usuario THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo el propietario puede autorizar soporte en su unidad';
  END IF;

  -- Una sola vigente: la anterior se cierra y se crea una nueva con el plazo pedido
  UPDATE autorizaciones_soporte
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'RENOVADA'
   WHERE id_vehiculo = p_id_vehiculo AND activa = 1;

  INSERT INTO autorizaciones_soporte (id_vehiculo, id_propietario, fecha_expira)
  VALUES (p_id_vehiculo, p_id_usuario, NOW() + INTERVAL p_minutos MINUTE);

  CALL sp_soporte_vigente(p_id_vehiculo);
END$$

-- El dueño revoca el soporte antes de tiempo.
DROP PROCEDURE IF EXISTS sp_revocar_soporte$$
CREATE PROCEDURE sp_revocar_soporte(IN p_id_vehiculo INT, IN p_id_usuario INT)
BEGIN
  UPDATE autorizaciones_soporte
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'REVOCADA'
   WHERE id_vehiculo = p_id_vehiculo AND id_propietario = p_id_usuario AND activa = 1;
  SELECT ROW_COUNT() AS revocadas;
END$$

-- ---------------------------------------------------------------------
-- Versiones ampliadas: las listas de unidades informan si hay soporte vigente
-- (segundos que le quedan; 0 = sin autorización). Mismas columnas que antes
-- más soporte_segundos, así que las APIs anteriores siguen compatibles.
-- ---------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_obtener_unidades$$
CREATE PROCEDURE sp_obtener_unidades()
BEGIN
  CALL sp_cerrar_soporte_vencido();
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial, v.activo,
         v.microcontrolador, v.fecha_registro,
         v.id_modelo, m.nombre AS modelo,
         v.id_propietario, u.nombre AS propietario, u.correo AS correo_propietario,
         COALESCE(e.conectado, 0) AS conectado,
         (SELECT COUNT(*) FROM comandos c WHERE c.id_vehiculo = v.id_vehiculo AND c.activo = 1) AS comandos,
         COALESCE((SELECT GREATEST(TIMESTAMPDIFF(SECOND, NOW(), a.fecha_expira), 0)
                     FROM autorizaciones_soporte a
                    WHERE a.id_vehiculo = v.id_vehiculo AND a.activa = 1), 0) AS soporte_segundos
    FROM vehiculos v
    LEFT JOIN modelos m          ON m.id_modelo = v.id_modelo
    LEFT JOIN usuarios u         ON u.id_usuario = v.id_propietario
    LEFT JOIN estado_vehiculo e  ON e.id_vehiculo = v.id_vehiculo
   ORDER BY v.id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_unidad$$
CREATE PROCEDURE sp_obtener_unidad(IN p_id_vehiculo INT)
BEGIN
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial, v.activo,
         v.microcontrolador, v.fecha_registro,
         v.id_modelo, m.nombre AS modelo,
         v.id_propietario, u.nombre AS propietario, u.correo AS correo_propietario,
         COALESCE(e.conectado, 0) AS conectado,
         (SELECT COUNT(*) FROM comandos c WHERE c.id_vehiculo = v.id_vehiculo AND c.activo = 1) AS comandos,
         COALESCE((SELECT GREATEST(TIMESTAMPDIFF(SECOND, NOW(), a.fecha_expira), 0)
                     FROM autorizaciones_soporte a
                    WHERE a.id_vehiculo = v.id_vehiculo AND a.activa = 1
                      AND a.fecha_expira > NOW()), 0) AS soporte_segundos
    FROM vehiculos v
    LEFT JOIN modelos m          ON m.id_modelo = v.id_modelo
    LEFT JOIN usuarios u         ON u.id_usuario = v.id_propietario
    LEFT JOIN estado_vehiculo e  ON e.id_vehiculo = v.id_vehiculo
   WHERE v.id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_mis_vehiculos$$
CREATE PROCEDURE sp_obtener_mis_vehiculos(IN p_id_usuario INT)
BEGIN
  CALL sp_cerrar_soporte_vencido();
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial,
         v.microcontrolador, v.id_modelo, m.nombre AS modelo,
         COALESCE(e.conectado, 0) AS conectado,
         COALESCE((SELECT GREATEST(TIMESTAMPDIFF(SECOND, NOW(), a.fecha_expira), 0)
                     FROM autorizaciones_soporte a
                    WHERE a.id_vehiculo = v.id_vehiculo AND a.activa = 1), 0) AS soporte_segundos
    FROM vehiculos v
    LEFT JOIN modelos m         ON m.id_modelo = v.id_modelo
    LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
   WHERE v.id_propietario = p_id_usuario
     AND v.activo = 1
   ORDER BY v.id_vehiculo;
END$$

-- Asignar o liberar una unidad también cancela el soporte que hubiera
-- concedido el dueño anterior: el permiso era suyo, no de la unidad.
DROP PROCEDURE IF EXISTS sp_asignar_unidad$$
CREATE PROCEDURE sp_asignar_unidad(IN p_id_vehiculo INT, IN p_id_usuario INT)
BEGIN
  UPDATE autorizaciones_soporte
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'REASIGNADA'
   WHERE id_vehiculo = p_id_vehiculo AND activa = 1;

  IF p_id_usuario IS NULL THEN
    UPDATE vehiculos
       SET id_propietario = NULL,
           estado_comercial = IF(estado_comercial = 'VENDIDO', 'DISPONIBLE', estado_comercial)
     WHERE id_vehiculo = p_id_vehiculo;
  ELSE
    UPDATE vehiculos
       SET id_propietario = p_id_usuario,
           estado_comercial = 'VENDIDO'
     WHERE id_vehiculo = p_id_vehiculo;
  END IF;
  CALL sp_obtener_unidad(p_id_vehiculo);
END$$

DELIMITER ;

SELECT 'Migración 005 (soporte) aplicada' AS resultado;
