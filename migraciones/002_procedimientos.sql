-- =====================================================================
-- 002_procedimientos.sql · Práctica 4.3 (Administración IoT)
--
-- Procedimientos nuevos para usuarios, sesiones, modelos, unidades,
-- invitados, auditoría y métricas. Los 21 procedimientos de 4.1/4.2
-- NO se tocan: siguen sirviendo a CONTROL y MONITOREO tal cual.
--
-- Igual que los anteriores, toda la entrada entra por parámetros: FastAPI
-- nunca concatena SQL.
-- =====================================================================

SET NAMES utf8mb4;
DELIMITER $$

-- =====================================================================
-- USUARIOS Y SESIONES
-- =====================================================================

-- Devuelve el usuario por correo CON su hash, solo para validar el login.
DROP PROCEDURE IF EXISTS sp_login_usuario$$
CREATE PROCEDURE sp_login_usuario(IN p_correo VARCHAR(120))
BEGIN
  SELECT u.id_usuario, u.nombre, u.correo, u.hash_contrasena, u.activo,
         r.id_rol, r.clave AS rol
    FROM usuarios u
    JOIN roles r ON r.id_rol = u.id_rol
   WHERE u.correo = p_correo;
END$$

DROP PROCEDURE IF EXISTS sp_crear_usuario$$
CREATE PROCEDURE sp_crear_usuario(
  IN p_nombre VARCHAR(80), IN p_correo VARCHAR(120), IN p_hash VARCHAR(255),
  IN p_rol VARCHAR(20), IN p_telefono VARCHAR(30))
BEGIN
  DECLARE v_id_rol INT;
  SELECT id_rol INTO v_id_rol FROM roles WHERE clave = p_rol;
  IF v_id_rol IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El rol indicado no existe';
  END IF;
  INSERT INTO usuarios (nombre, correo, hash_contrasena, id_rol, telefono)
  VALUES (p_nombre, p_correo, p_hash, v_id_rol, p_telefono);
  SELECT LAST_INSERT_ID() AS id_usuario;
END$$

-- Lista de usuarios con cuántas unidades tiene cada uno. Nunca devuelve el hash.
DROP PROCEDURE IF EXISTS sp_obtener_usuarios$$
CREATE PROCEDURE sp_obtener_usuarios()
BEGIN
  SELECT u.id_usuario, u.nombre, u.correo, u.telefono, u.activo, u.fecha_registro,
         r.clave AS rol,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_propietario = u.id_usuario) AS unidades
    FROM usuarios u
    JOIN roles r ON r.id_rol = u.id_rol
   ORDER BY u.id_usuario;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_usuario$$
CREATE PROCEDURE sp_obtener_usuario(IN p_id_usuario INT)
BEGIN
  SELECT u.id_usuario, u.nombre, u.correo, u.telefono, u.activo, u.fecha_registro,
         r.clave AS rol,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_propietario = u.id_usuario) AS unidades
    FROM usuarios u
    JOIN roles r ON r.id_rol = u.id_rol
   WHERE u.id_usuario = p_id_usuario;
END$$

-- Solo cambia lo que llega distinto de NULL (baja lógica con p_activo = 0).
DROP PROCEDURE IF EXISTS sp_actualizar_usuario$$
CREATE PROCEDURE sp_actualizar_usuario(
  IN p_id_usuario INT, IN p_nombre VARCHAR(80), IN p_telefono VARCHAR(30),
  IN p_hash VARCHAR(255), IN p_rol VARCHAR(20), IN p_activo TINYINT)
BEGIN
  DECLARE v_id_rol INT DEFAULT NULL;
  IF p_rol IS NOT NULL THEN
    SELECT id_rol INTO v_id_rol FROM roles WHERE clave = p_rol;
    IF v_id_rol IS NULL THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El rol indicado no existe';
    END IF;
  END IF;
  UPDATE usuarios
     SET nombre          = COALESCE(p_nombre, nombre),
         telefono        = COALESCE(p_telefono, telefono),
         hash_contrasena = COALESCE(p_hash, hash_contrasena),
         id_rol          = COALESCE(v_id_rol, id_rol),
         activo          = COALESCE(p_activo, activo)
   WHERE id_usuario = p_id_usuario;
  CALL sp_obtener_usuario(p_id_usuario);
END$$

DROP PROCEDURE IF EXISTS sp_crear_sesion$$
CREATE PROCEDURE sp_crear_sesion(IN p_id_usuario INT, IN p_token_hash CHAR(64), IN p_horas INT)
BEGIN
  -- Limpieza oportunista: quita sesiones vencidas de hace más de un día
  DELETE FROM sesiones WHERE fecha_expira < (NOW() - INTERVAL 1 DAY);
  INSERT INTO sesiones (id_usuario, token_hash, fecha_expira)
  VALUES (p_id_usuario, p_token_hash, NOW() + INTERVAL p_horas HOUR);
  SELECT LAST_INSERT_ID() AS id_sesion;
END$$

-- Devuelve el usuario dueño de un token vigente (vacío si expiró o se revocó).
DROP PROCEDURE IF EXISTS sp_obtener_sesion$$
CREATE PROCEDURE sp_obtener_sesion(IN p_token_hash CHAR(64))
BEGIN
  SELECT s.id_sesion, s.fecha_expira,
         u.id_usuario, u.nombre, u.correo, u.activo,
         r.clave AS rol
    FROM sesiones s
    JOIN usuarios u ON u.id_usuario = s.id_usuario
    JOIN roles r    ON r.id_rol = u.id_rol
   WHERE s.token_hash = p_token_hash
     AND s.revocada = 0
     AND s.fecha_expira > NOW();
END$$

DROP PROCEDURE IF EXISTS sp_revocar_sesion$$
CREATE PROCEDURE sp_revocar_sesion(IN p_token_hash CHAR(64))
BEGIN
  UPDATE sesiones SET revocada = 1 WHERE token_hash = p_token_hash;
  SELECT ROW_COUNT() AS revocadas;
END$$

-- =====================================================================
-- MODELOS COMERCIALES
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_crear_modelo$$
CREATE PROCEDURE sp_crear_modelo(
  IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(500),
  IN p_microcontrolador VARCHAR(50), IN p_precio DECIMAL(10,2), IN p_imagen_url VARCHAR(255))
BEGIN
  INSERT INTO modelos (nombre, descripcion, microcontrolador, precio, imagen_url)
  VALUES (p_nombre, p_descripcion, p_microcontrolador, p_precio, p_imagen_url);
  SELECT LAST_INSERT_ID() AS id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_modelos$$
CREATE PROCEDURE sp_obtener_modelos()
BEGIN
  SELECT m.id_modelo, m.nombre, m.descripcion, m.microcontrolador, m.precio,
         m.imagen_url, m.activo, m.fecha_registro,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_modelo = m.id_modelo) AS unidades,
         (SELECT COUNT(*) FROM vehiculos v
           WHERE v.id_modelo = m.id_modelo AND v.estado_comercial = 'EXHIBICION'
             AND v.activo = 1) AS unidades_exhibicion
    FROM modelos m
   ORDER BY m.id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_modelo$$
CREATE PROCEDURE sp_obtener_modelo(IN p_id_modelo INT)
BEGIN
  SELECT m.id_modelo, m.nombre, m.descripcion, m.microcontrolador, m.precio,
         m.imagen_url, m.activo, m.fecha_registro,
         (SELECT COUNT(*) FROM vehiculos v WHERE v.id_modelo = m.id_modelo) AS unidades,
         (SELECT COUNT(*) FROM vehiculos v
           WHERE v.id_modelo = m.id_modelo AND v.estado_comercial = 'EXHIBICION'
             AND v.activo = 1) AS unidades_exhibicion
    FROM modelos m
   WHERE m.id_modelo = p_id_modelo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_modelo$$
CREATE PROCEDURE sp_actualizar_modelo(
  IN p_id_modelo INT, IN p_nombre VARCHAR(80), IN p_descripcion VARCHAR(500),
  IN p_microcontrolador VARCHAR(50), IN p_precio DECIMAL(10,2),
  IN p_imagen_url VARCHAR(255), IN p_activo TINYINT)
BEGIN
  UPDATE modelos
     SET nombre           = COALESCE(p_nombre, nombre),
         descripcion      = COALESCE(p_descripcion, descripcion),
         microcontrolador = COALESCE(p_microcontrolador, microcontrolador),
         precio           = COALESCE(p_precio, precio),
         imagen_url       = COALESCE(p_imagen_url, imagen_url),
         activo           = COALESCE(p_activo, activo)
   WHERE id_modelo = p_id_modelo;
  CALL sp_obtener_modelo(p_id_modelo);
END$$

-- =====================================================================
-- UNIDADES FÍSICAS (tabla vehiculos, vista comercial)
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_obtener_unidades$$
CREATE PROCEDURE sp_obtener_unidades()
BEGIN
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial, v.activo,
         v.microcontrolador, v.fecha_registro,
         v.id_modelo, m.nombre AS modelo,
         v.id_propietario, u.nombre AS propietario, u.correo AS correo_propietario,
         COALESCE(e.conectado, 0) AS conectado,
         (SELECT COUNT(*) FROM comandos c WHERE c.id_vehiculo = v.id_vehiculo AND c.activo = 1) AS comandos
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
         (SELECT COUNT(*) FROM comandos c WHERE c.id_vehiculo = v.id_vehiculo AND c.activo = 1) AS comandos
    FROM vehiculos v
    LEFT JOIN modelos m          ON m.id_modelo = v.id_modelo
    LEFT JOIN usuarios u         ON u.id_usuario = v.id_propietario
    LEFT JOIN estado_vehiculo e  ON e.id_vehiculo = v.id_vehiculo
   WHERE v.id_vehiculo = p_id_vehiculo;
END$$

DROP PROCEDURE IF EXISTS sp_actualizar_comercial$$
CREATE PROCEDURE sp_actualizar_comercial(
  IN p_id_vehiculo INT, IN p_id_modelo INT, IN p_numero_serie VARCHAR(40),
  IN p_estado_comercial VARCHAR(20))
BEGIN
  UPDATE vehiculos
     SET id_modelo        = COALESCE(p_id_modelo, id_modelo),
         numero_serie     = COALESCE(p_numero_serie, numero_serie),
         estado_comercial = COALESCE(p_estado_comercial, estado_comercial)
   WHERE id_vehiculo = p_id_vehiculo;
  CALL sp_obtener_unidad(p_id_vehiculo);
END$$

-- Asigna o libera (p_id_usuario NULL) una unidad. Ajusta el estado comercial
-- en consecuencia y conserva TODO el historial del vehículo.
DROP PROCEDURE IF EXISTS sp_asignar_unidad$$
CREATE PROCEDURE sp_asignar_unidad(IN p_id_vehiculo INT, IN p_id_usuario INT)
BEGIN
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

-- «Mis vehículos»: únicamente las unidades activas de ese comprador.
DROP PROCEDURE IF EXISTS sp_obtener_mis_vehiculos$$
CREATE PROCEDURE sp_obtener_mis_vehiculos(IN p_id_usuario INT)
BEGIN
  SELECT v.id_vehiculo, v.nombre, v.numero_serie, v.estado_comercial,
         v.microcontrolador, v.id_modelo, m.nombre AS modelo,
         COALESCE(e.conectado, 0) AS conectado
    FROM vehiculos v
    LEFT JOIN modelos m         ON m.id_modelo = v.id_modelo
    LEFT JOIN estado_vehiculo e ON e.id_vehiculo = v.id_vehiculo
   WHERE v.id_propietario = p_id_usuario
     AND v.activo = 1
   ORDER BY v.id_vehiculo;
END$$

-- Catálogo público del Invitado: modelos activos y si hay unidad de exhibición libre.
-- No expone propietarios ni inventario privado.
DROP PROCEDURE IF EXISTS sp_catalogo_publico$$
CREATE PROCEDURE sp_catalogo_publico()
BEGIN
  SELECT m.id_modelo, m.nombre, m.descripcion, m.microcontrolador, m.precio, m.imagen_url,
         (SELECT COUNT(*) FROM vehiculos v
           WHERE v.id_modelo = m.id_modelo AND v.activo = 1
             AND v.estado_comercial = 'EXHIBICION') AS unidades_exhibicion,
         (SELECT COUNT(*) FROM vehiculos v
           WHERE v.id_modelo = m.id_modelo AND v.activo = 1
             AND v.estado_comercial = 'EXHIBICION'
             AND NOT EXISTS (SELECT 1 FROM sesiones_invitado si
                              WHERE si.id_vehiculo = v.id_vehiculo
                                AND si.activa = 1 AND si.fecha_expira > NOW())) AS disponibles
    FROM modelos m
   WHERE m.activo = 1
   ORDER BY m.id_modelo;
END$$

-- =====================================================================
-- SESIONES DE INVITADO (prueba temporal y exclusiva)
-- =====================================================================

-- Toma la primera unidad de exhibición libre del modelo y la reserva.
-- El índice uq_invitado_activo impide, a nivel de BD, una segunda reserva.
DROP PROCEDURE IF EXISTS sp_crear_sesion_invitado$$
CREATE PROCEDURE sp_crear_sesion_invitado(
  IN p_id_modelo INT, IN p_token_hash CHAR(64),
  IN p_nombre VARCHAR(80), IN p_minutos INT)
BEGIN
  DECLARE v_id_vehiculo INT DEFAULT NULL;

  -- Cierra primero lo que ya venció, para que su unidad vuelva a estar libre
  UPDATE sesiones_invitado
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'EXPIRADA'
   WHERE activa = 1 AND fecha_expira <= NOW();

  SELECT v.id_vehiculo INTO v_id_vehiculo
    FROM vehiculos v
   WHERE v.activo = 1
     AND v.estado_comercial = 'EXHIBICION'
     AND (p_id_modelo IS NULL OR v.id_modelo = p_id_modelo)
     AND NOT EXISTS (SELECT 1 FROM sesiones_invitado si
                      WHERE si.id_vehiculo = v.id_vehiculo AND si.activa = 1)
   ORDER BY v.id_vehiculo
   LIMIT 1;

  IF v_id_vehiculo IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay unidades de exhibicion disponibles en este momento';
  END IF;

  INSERT INTO sesiones_invitado (token_hash, id_vehiculo, nombre_invitado, fecha_expira)
  VALUES (p_token_hash, v_id_vehiculo, p_nombre, NOW() + INTERVAL p_minutos MINUTE);

  CALL sp_obtener_sesion_invitado(p_token_hash);
END$$

DROP PROCEDURE IF EXISTS sp_obtener_sesion_invitado$$
CREATE PROCEDURE sp_obtener_sesion_invitado(IN p_token_hash CHAR(64))
BEGIN
  SELECT si.id_sesion_invitado, si.id_vehiculo, si.nombre_invitado,
         si.fecha_inicio, si.fecha_expira, si.activa, si.motivo_fin,
         TIMESTAMPDIFF(SECOND, NOW(), si.fecha_expira) AS segundos_restantes,
         v.nombre AS vehiculo, v.estado_comercial,
         m.id_modelo, m.nombre AS modelo
    FROM sesiones_invitado si
    JOIN vehiculos v       ON v.id_vehiculo = si.id_vehiculo
    LEFT JOIN modelos m    ON m.id_modelo = v.id_modelo
   WHERE si.token_hash = p_token_hash;
END$$

DROP PROCEDURE IF EXISTS sp_finalizar_sesion_invitado$$
CREATE PROCEDURE sp_finalizar_sesion_invitado(IN p_token_hash CHAR(64), IN p_motivo VARCHAR(40))
BEGIN
  UPDATE sesiones_invitado
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = p_motivo
   WHERE token_hash = p_token_hash AND activa = 1;
  SELECT ROW_COUNT() AS finalizadas;
END$$

-- Cierra todas las vencidas y devuelve qué vehículos quedaron libres,
-- para que la API les mande DETENER.
-- Se fija un instante de corte y se usa en la consulta y en el UPDATE: así las
-- unidades que se devuelven son exactamente las que se cerraron (sin tabla
-- temporal, que en RDS con GTID puede no estar permitida).
DROP PROCEDURE IF EXISTS sp_expirar_sesiones_invitado$$
CREATE PROCEDURE sp_expirar_sesiones_invitado()
BEGIN
  DECLARE v_corte DATETIME DEFAULT NOW();

  SELECT DISTINCT id_vehiculo
    FROM sesiones_invitado
   WHERE activa = 1 AND fecha_expira <= v_corte;

  UPDATE sesiones_invitado
     SET activa = NULL, fecha_fin = NOW(), motivo_fin = 'EXPIRADA'
   WHERE activa = 1 AND fecha_expira <= v_corte;
END$$

-- ¿Hay una prueba de invitado vigente sobre esta unidad? (exclusividad)
DROP PROCEDURE IF EXISTS sp_reserva_activa_vehiculo$$
CREATE PROCEDURE sp_reserva_activa_vehiculo(IN p_id_vehiculo INT)
BEGIN
  SELECT COUNT(*) AS reservas
    FROM sesiones_invitado
   WHERE id_vehiculo = p_id_vehiculo AND activa = 1 AND fecha_expira > NOW();
END$$

-- =====================================================================
-- AUDITORÍA Y MÉTRICAS
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_registrar_auditoria$$
CREATE PROCEDURE sp_registrar_auditoria(
  IN p_id_usuario INT, IN p_actor VARCHAR(120), IN p_accion VARCHAR(60),
  IN p_recurso VARCHAR(40), IN p_id_recurso VARCHAR(40),
  IN p_resultado VARCHAR(20), IN p_detalle VARCHAR(255))
BEGIN
  INSERT INTO auditoria (id_usuario, actor, accion, recurso, id_recurso, resultado, detalle)
  VALUES (p_id_usuario, p_actor, p_accion, p_recurso, p_id_recurso, p_resultado, p_detalle);
  SELECT LAST_INSERT_ID() AS id_auditoria;
END$$

DROP PROCEDURE IF EXISTS sp_obtener_auditoria$$
CREATE PROCEDURE sp_obtener_auditoria(IN p_limite INT)
BEGIN
  IF p_limite IS NULL OR p_limite < 1 THEN SET p_limite = 50; END IF;
  IF p_limite > 200 THEN SET p_limite = 200; END IF;
  SELECT a.id_auditoria, a.fecha_hora, a.id_usuario, a.actor, a.accion,
         a.recurso, a.id_recurso, a.resultado, a.detalle
    FROM auditoria a
   ORDER BY a.id_auditoria DESC
   LIMIT p_limite;
END$$

DROP PROCEDURE IF EXISTS sp_metricas_dashboard$$
CREATE PROCEDURE sp_metricas_dashboard()
BEGIN
  SELECT
    (SELECT COUNT(*) FROM modelos  WHERE activo = 1)                                   AS modelos,
    (SELECT COUNT(*) FROM vehiculos WHERE activo = 1)                                  AS unidades,
    (SELECT COUNT(*) FROM vehiculos WHERE activo = 1 AND estado_comercial = 'VENDIDO')    AS vendidas,
    (SELECT COUNT(*) FROM vehiculos WHERE activo = 1 AND estado_comercial = 'DISPONIBLE') AS disponibles,
    (SELECT COUNT(*) FROM vehiculos WHERE activo = 1 AND estado_comercial = 'EXHIBICION') AS exhibicion,
    (SELECT COUNT(*) FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol
      WHERE r.clave = 'USUARIO' AND u.activo = 1)                                      AS clientes,
    (SELECT COUNT(*) FROM demos WHERE activo = 1)                                      AS demos,
    (SELECT COUNT(*) FROM demos WHERE activo = 1 AND id_propietario IS NULL)           AS demos_fabrica,
    (SELECT COUNT(*) FROM estado_vehiculo e JOIN vehiculos v ON v.id_vehiculo = e.id_vehiculo
      WHERE e.conectado = 1 AND v.activo = 1)                                          AS conectadas,
    (SELECT COUNT(*) FROM sesiones_invitado WHERE activa = 1 AND fecha_expira > NOW()) AS pruebas_activas,
    (SELECT COUNT(*) FROM historial_comandos)                                          AS movimientos_totales;
END$$

-- =====================================================================
-- DEMOS CON DUEÑO
-- =====================================================================

-- Crea una demo de fábrica (p_id_propietario NULL) o privada de un comprador.
DROP PROCEDURE IF EXISTS sp_crear_demo_propietario$$
CREATE PROCEDURE sp_crear_demo_propietario(
  IN p_id_vehiculo INT, IN p_nombre VARCHAR(80),
  IN p_descripcion VARCHAR(255), IN p_id_propietario INT)
BEGIN
  INSERT INTO demos (id_vehiculo, nombre, descripcion, id_propietario)
  VALUES (p_id_vehiculo, p_nombre, p_descripcion, p_id_propietario);
  SELECT LAST_INSERT_ID() AS id_demo;
END$$

-- Demos que una persona puede ver de un vehículo: las de fábrica y las suyas.
-- Con p_id_usuario NULL (invitado) solo devuelve las de fábrica.
DROP PROCEDURE IF EXISTS sp_obtener_demos_visibles$$
CREATE PROCEDURE sp_obtener_demos_visibles(IN p_id_vehiculo INT, IN p_id_usuario INT)
BEGIN
  SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
         d.id_propietario,
         IF(d.id_propietario IS NULL, 'FABRICA', 'PRIVADA') AS tipo,
         (SELECT COUNT(*) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS total_movimientos
    FROM demos d
   WHERE d.id_vehiculo = p_id_vehiculo
     AND d.activo = 1
     AND (d.id_propietario IS NULL OR d.id_propietario = p_id_usuario)
   ORDER BY d.id_demo;
END$$

-- Una demo concreta, para comprobar de quién es antes de dejar editarla.
DROP PROCEDURE IF EXISTS sp_obtener_demo$$
CREATE PROCEDURE sp_obtener_demo(IN p_id_demo INT)
BEGIN
  SELECT d.id_demo, d.id_vehiculo, d.nombre, d.descripcion, d.activo,
         d.id_propietario,
         IF(d.id_propietario IS NULL, 'FABRICA', 'PRIVADA') AS tipo,
         v.id_propietario AS propietario_vehiculo,
         (SELECT COUNT(*) FROM demo_movimientos dm WHERE dm.id_demo = d.id_demo) AS total_movimientos
    FROM demos d
    JOIN vehiculos v ON v.id_vehiculo = d.id_vehiculo
   WHERE d.id_demo = p_id_demo;
END$$

DELIMITER ;

SELECT 'Migración 002 aplicada' AS resultado,
       COUNT(*) AS procedimientos_totales
  FROM information_schema.ROUTINES
 WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE';
