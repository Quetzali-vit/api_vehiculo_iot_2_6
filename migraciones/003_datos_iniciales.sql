-- =====================================================================
-- 003_datos_iniciales.sql · Práctica 4.3 (Administración IoT)
--
-- Siembra lo mínimo para que la plataforma arranque: los dos roles, tres
-- cuentas de demostración y un modelo comercial para la unidad que ya existe.
-- Todo con INSERT IGNORE / comprobación previa, así que se puede volver a
-- ejecutar sin duplicar nada.
--
-- Las contraseñas son hashes PBKDF2-SHA256 (210 000 iteraciones). La base
-- NUNCA guarda la contraseña en claro.
--
-- CUENTAS DE DEMOSTRACIÓN (cámbialas después de la primera entrada):
--   admin@iot.com     / Admin123#     → ADMINISTRADOR (la empresa)
--   cliente@iot.com   / Cliente123#   → USUARIO (comprador)
--   cliente2@iot.com  / Cliente123#   → USUARIO (segundo comprador, para
--                                        probar que no ve lo del primero)
-- =====================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 1. Roles
-- ---------------------------------------------------------------------
INSERT IGNORE INTO roles (clave, nombre, descripcion) VALUES
  ('ADMIN',   'Administrador', 'Empresa comercializadora: inventario, clientes, asignaciones y demos de exhibición'),
  ('USUARIO', 'Usuario',       'Cliente comprador: opera y monitorea únicamente sus unidades');

-- ---------------------------------------------------------------------
-- 2. Cuentas de demostración
-- ---------------------------------------------------------------------
INSERT IGNORE INTO usuarios (nombre, correo, hash_contrasena, id_rol, telefono) VALUES
  ('Administrador de la empresa', 'admin@iot.com',
   'pbkdf2_sha256$210000$nj5opujlyibCZPYPw9z6lg==$kOk1RQ2mrg6Vg9JssmuXDE1H1GzA/JdCkQagGkGdrN8=',
   (SELECT id_rol FROM roles WHERE clave = 'ADMIN'), NULL),
  ('Cliente de prueba', 'cliente@iot.com',
   'pbkdf2_sha256$210000$yjzv1txhv21pOgCLsUylAg==$w7ToBd2P7TSwx78VhbvLa5yFhgkrxSrzS0/xspCRom8=',
   (SELECT id_rol FROM roles WHERE clave = 'USUARIO'), NULL),
  ('Segundo cliente', 'cliente2@iot.com',
   'pbkdf2_sha256$210000$brL47HX8u8xo8RyV2pgDEA==$+4WUig3lpJvcee1+n8icJdmZfZga2q67ejkBQ9Gu9sE=',
   (SELECT id_rol FROM roles WHERE clave = 'USUARIO'), NULL);

-- ---------------------------------------------------------------------
-- 3. Modelo comercial para las unidades que ya existían
--    La columna `modelo` de vehiculos era texto libre; aquí nace el MODELO
--    como entidad propia, y las unidades sin modelo se enlazan a ella.
-- ---------------------------------------------------------------------
INSERT IGNORE INTO modelos (nombre, descripcion, microcontrolador, precio) VALUES
  ('Retroexcavadora IoT',
   'Retroexcavadora a escala con tracción, brazo y pala, controlada por Wi-Fi mediante ESP32 y dos registros de desplazamiento 74HC595.',
   'ESP32', 7500.00);

UPDATE vehiculos v
   SET v.id_modelo = (SELECT id_modelo FROM modelos WHERE nombre = 'Retroexcavadora IoT')
 WHERE v.id_modelo IS NULL;

-- ---------------------------------------------------------------------
-- 4. Estado comercial de la unidad de pruebas
--    El vehículo con el que se hicieron 4.1 y 4.2 pasa a EXHIBICION para que
--    el Invitado pueda probarlo. Las demás unidades quedan DISPONIBLE.
-- ---------------------------------------------------------------------
UPDATE vehiculos
   SET estado_comercial = 'EXHIBICION'
 WHERE id_vehiculo = 1 AND estado_comercial = 'DISPONIBLE';

-- Número de serie legible para las unidades que no tengan uno
UPDATE vehiculos
   SET numero_serie = CONCAT('UNI-', LPAD(id_vehiculo, 4, '0'))
 WHERE numero_serie IS NULL;

-- ---------------------------------------------------------------------
-- 5. Las demos que ya existían son «de fábrica» (sin dueño): así siguen
--    visibles para todos, igual que en 4.1 y 4.2.
-- ---------------------------------------------------------------------
-- (no hace falta UPDATE: id_propietario ya nace en NULL)

-- ---------------------------------------------------------------------
-- 6. Registro de la propia migración en la auditoría
-- ---------------------------------------------------------------------
INSERT INTO auditoria (id_usuario, actor, accion, recurso, id_recurso, resultado, detalle)
VALUES (NULL, 'migracion', 'MIGRAR', 'esquema', '4.3', 'OK',
        'Migraciones 001-003 de la práctica 4.3 aplicadas');

SELECT 'Migración 003 aplicada' AS resultado,
       (SELECT COUNT(*) FROM roles)    AS roles,
       (SELECT COUNT(*) FROM usuarios) AS usuarios,
       (SELECT COUNT(*) FROM modelos)  AS modelos;
