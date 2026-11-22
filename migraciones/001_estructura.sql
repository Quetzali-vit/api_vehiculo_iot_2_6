-- =====================================================================
-- 001_estructura.sql · Práctica 4.3 (Administración IoT)
-- Esquema: vehiculo_iot (Amazon RDS MySQL 8)
--
-- Agrega: roles, usuarios, sesiones, modelos comerciales, propiedad de
-- unidades, demos privadas, sesiones de invitado y auditoría.
-- NO borra ni modifica datos existentes. Las columnas nuevas admiten NULL
-- o traen valor por omisión, así que las filas actuales siguen siendo válidas.
--
-- AVISO: en MySQL el DDL confirma de forma implícita. ROLLBACK no deshace
-- un CREATE/ALTER. Respalda antes (ver 000_RESPALDO_Y_GUIA.md).
-- =====================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 1. Roles del negocio
--    El INVITADO no es una cuenta: usa una sesión temporal (ver más abajo).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `roles` (
  `id_rol`      INT          NOT NULL AUTO_INCREMENT,
  `clave`       VARCHAR(20)  NOT NULL,
  `nombre`      VARCHAR(60)  NOT NULL,
  `descripcion` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_rol`),
  UNIQUE KEY `uq_rol_clave` (`clave`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. Usuarios (empresa y compradores)
--    La contraseña se guarda SOLO como hash PBKDF2-SHA256 generado por FastAPI.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id_usuario`       INT          NOT NULL AUTO_INCREMENT,
  `nombre`           VARCHAR(80)  NOT NULL,
  `correo`           VARCHAR(120) NOT NULL,
  `hash_contrasena`  VARCHAR(255) NOT NULL,
  `id_rol`           INT          NOT NULL,
  `telefono`         VARCHAR(30)  DEFAULT NULL,
  `activo`           TINYINT(1)   NOT NULL DEFAULT 1,
  `fecha_registro`   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `uq_usuario_correo` (`correo`),
  KEY `fk_usuario_rol` (`id_rol`),
  CONSTRAINT `fk_usuario_rol` FOREIGN KEY (`id_rol`) REFERENCES `roles` (`id_rol`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. Sesiones de usuario (login / logout real)
--    Se guarda el SHA-256 del token, nunca el token en claro.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sesiones` (
  `id_sesion`     BIGINT      NOT NULL AUTO_INCREMENT,
  `id_usuario`    INT         NOT NULL,
  `token_hash`    CHAR(64)    NOT NULL,
  `fecha_inicio`  TIMESTAMP   NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_expira`  DATETIME    NOT NULL,
  `revocada`      TINYINT(1)  NOT NULL DEFAULT 0,
  PRIMARY KEY (`id_sesion`),
  UNIQUE KEY `uq_sesion_token` (`token_hash`),
  KEY `fk_sesion_usuario` (`id_usuario`),
  KEY `ix_sesion_expira` (`fecha_expira`),
  CONSTRAINT `fk_sesion_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `usuarios` (`id_usuario`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4. Modelos comerciales
--    MODELO = lo que la empresa vende. UNIDAD = la pieza física (tabla vehiculos).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `modelos` (
  `id_modelo`        INT          NOT NULL AUTO_INCREMENT,
  `nombre`           VARCHAR(80)  NOT NULL,
  `descripcion`      VARCHAR(500) DEFAULT NULL,
  `microcontrolador` VARCHAR(50)  DEFAULT NULL,
  `precio`           DECIMAL(10,2) DEFAULT NULL,
  `imagen_url`       VARCHAR(255) DEFAULT NULL,
  `activo`           TINYINT(1)   NOT NULL DEFAULT 1,
  `fecha_registro`   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_modelo`),
  UNIQUE KEY `uq_modelo_nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5. vehiculos: columnas comerciales
--    Se agregan con NULL / valor por omisión para no invalidar las filas actuales.
--    El id_vehiculo NO cambia: CONTROL y MONITOREO siguen funcionando igual.
-- ---------------------------------------------------------------------
SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'id_modelo');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD COLUMN `id_modelo` INT DEFAULT NULL AFTER `modelo`',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'id_propietario');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD COLUMN `id_propietario` INT DEFAULT NULL AFTER `id_modelo`',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'numero_serie');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD COLUMN `numero_serie` VARCHAR(40) DEFAULT NULL AFTER `id_propietario`',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND COLUMN_NAME = 'estado_comercial');
SET @sql := IF(@hay = 0,
  "ALTER TABLE `vehiculos` ADD COLUMN `estado_comercial` ENUM('DISPONIBLE','VENDIDO','EXHIBICION','INACTIVO') NOT NULL DEFAULT 'DISPONIBLE' AFTER `numero_serie`",
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Índices y llaves foráneas (solo si aún no existen)
SET @hay := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND INDEX_NAME = 'uq_vehiculo_serie');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD UNIQUE KEY `uq_vehiculo_serie` (`numero_serie`)',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND CONSTRAINT_NAME = 'fk_vehiculo_modelo');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD CONSTRAINT `fk_vehiculo_modelo` FOREIGN KEY (`id_modelo`) REFERENCES `modelos` (`id_modelo`) ON DELETE SET NULL ON UPDATE CASCADE',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Al borrar un usuario la unidad queda sin dueño, nunca se borra la unidad
SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehiculos' AND CONSTRAINT_NAME = 'fk_vehiculo_propietario');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `vehiculos` ADD CONSTRAINT `fk_vehiculo_propietario` FOREIGN KEY (`id_propietario`) REFERENCES `usuarios` (`id_usuario`) ON DELETE SET NULL ON UPDATE CASCADE',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ---------------------------------------------------------------------
-- 6. demos: dueño (NULL = demo de fábrica, de la empresa)
-- ---------------------------------------------------------------------
SET @hay := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'demos' AND COLUMN_NAME = 'id_propietario');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `demos` ADD COLUMN `id_propietario` INT DEFAULT NULL AFTER `descripcion`',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @hay := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'demos' AND CONSTRAINT_NAME = 'fk_demo_propietario');
SET @sql := IF(@hay = 0,
  'ALTER TABLE `demos` ADD CONSTRAINT `fk_demo_propietario` FOREIGN KEY (`id_propietario`) REFERENCES `usuarios` (`id_usuario`) ON DELETE CASCADE ON UPDATE CASCADE',
  'DO 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ---------------------------------------------------------------------
-- 7. Sesiones de invitado (prueba comercial temporal y EXCLUSIVA)
--    El índice uq_invitado_activo garantiza, a nivel de base de datos, que
--    un vehículo no pueda tener dos sesiones activas al mismo tiempo:
--    activa = 1 mientras dura; al terminar se pone NULL, y MySQL permite
--    muchos NULL en un índice UNIQUE pero un solo 1 por vehículo.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sesiones_invitado` (
  `id_sesion_invitado` BIGINT       NOT NULL AUTO_INCREMENT,
  `token_hash`         CHAR(64)     NOT NULL,
  `id_vehiculo`        INT          NOT NULL,
  `nombre_invitado`    VARCHAR(80)  DEFAULT NULL,
  `fecha_inicio`       TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_expira`       DATETIME     NOT NULL,
  `fecha_fin`          DATETIME     DEFAULT NULL,
  `motivo_fin`         VARCHAR(40)  DEFAULT NULL,
  `activa`             TINYINT(1)   DEFAULT 1,
  PRIMARY KEY (`id_sesion_invitado`),
  UNIQUE KEY `uq_invitado_token` (`token_hash`),
  UNIQUE KEY `uq_invitado_activo` (`id_vehiculo`, `activa`),
  KEY `ix_invitado_expira` (`fecha_expira`),
  CONSTRAINT `fk_invitado_vehiculo` FOREIGN KEY (`id_vehiculo`) REFERENCES `vehiculos` (`id_vehiculo`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 8. Auditoría de acciones sensibles
--    Nunca guarda contraseñas ni tokens: solo quién, qué, sobre qué y el resultado.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auditoria` (
  `id_auditoria` BIGINT       NOT NULL AUTO_INCREMENT,
  `fecha_hora`   TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
  `id_usuario`   INT          DEFAULT NULL,
  `actor`        VARCHAR(120) NOT NULL,
  `accion`       VARCHAR(60)  NOT NULL,
  `recurso`      VARCHAR(40)  NOT NULL,
  `id_recurso`   VARCHAR(40)  DEFAULT NULL,
  `resultado`    VARCHAR(20)  NOT NULL,
  `detalle`      VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`id_auditoria`),
  KEY `ix_auditoria_fecha` (`fecha_hora`),
  KEY `fk_auditoria_usuario` (`id_usuario`),
  CONSTRAINT `fk_auditoria_usuario` FOREIGN KEY (`id_usuario`) REFERENCES `usuarios` (`id_usuario`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Migración 001 aplicada' AS resultado;
