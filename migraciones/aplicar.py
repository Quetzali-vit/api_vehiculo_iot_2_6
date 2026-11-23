"""Aplica las migraciones de la práctica 4.3 de forma controlada.

    python migraciones/aplicar.py              # respaldo + copia de prueba + base real
    python migraciones/aplicar.py --solo-respaldo
    python migraciones/aplicar.py --sin-copia  # si el usuario de RDS no puede crear bases

Pasos (se detiene en el primero que falle):

1. RESPALDO de `vehiculo_iot` a migraciones/respaldos/ (tablas, datos y los 21
   procedimientos). Es la única vuelta atrás real: MySQL confirma el DDL de forma
   implícita y ROLLBACK no deshace un CREATE/ALTER.
2. CONTEOS previos de las tablas de 4.1/4.2.
3. COPIA DE PRUEBA: crea `vehiculo_iot_prueba_<fecha>`, carga el respaldo y
   aplica ahí las migraciones. Si los conteos cambian, se aborta SIN tocar la
   base real.
4. Aplica 001, 002 y 003 en la base real.
5. Compara los conteos: deben ser idénticos.
6. Deja constancia en migraciones/registro_aplicacion.txt.

Lee las credenciales del mismo .env que usa la API. Nunca imprime la contraseña.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import pymysql  # noqa: E402
from pymysql.cursors import DictCursor  # noqa: E402

from app.core.config import get_settings  # noqa: E402

CARPETA = Path(__file__).resolve().parent
RESPALDOS = CARPETA / "respaldos"
REGISTRO = CARPETA / "registro_aplicacion.txt"
MIGRACIONES = ["001_estructura.sql", "002_procedimientos.sql", "003_datos_iniciales.sql"]
TABLAS_PREVIAS = ["vehiculos", "comandos", "estado_vehiculo", "historial_comandos", "demos", "demo_movimientos"]


# ---------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------
def conectar(base: str | None):
    s = get_settings()
    return pymysql.connect(host=s.db_host, port=s.db_port, user=s.db_user, password=s.db_password,
                           database=base, charset="utf8mb4", cursorclass=DictCursor,
                           autocommit=True, connect_timeout=s.db_connect_timeout)


# ---------------------------------------------------------------------
# Lectura de archivos .sql con DELIMITER (como el cliente mysql)
# ---------------------------------------------------------------------
def dividir_sql(texto: str) -> list[str]:
    """Separa un script en sentencias respetando DELIMITER, comillas y comentarios."""
    sentencias: list[str] = []
    delimitador = ";"
    actual: list[str] = []

    en_simple = en_doble = en_tilde = en_bloque = False

    for linea in texto.splitlines(keepends=True):
        limpia = linea.strip()
        fuera = not (en_simple or en_doble or en_tilde or en_bloque)
        if fuera and limpia.upper().startswith("DELIMITER "):
            delimitador = limpia.split(None, 1)[1].strip()
            continue

        i = 0
        en_linea = False
        while i < len(linea):
            ch = linea[i]
            sig = linea[i + 1] if i + 1 < len(linea) else ""

            if en_linea:
                actual.append(ch)
                i += 1
                continue
            if en_bloque:
                actual.append(ch)
                if ch == "*" and sig == "/":
                    actual.append(sig)
                    i += 2
                    en_bloque = False
                    continue
                i += 1
                continue
            if en_simple or en_doble:
                actual.append(ch)
                if ch == "\\" and sig:
                    actual.append(sig)
                    i += 2
                    continue
                if (en_simple and ch == "'") or (en_doble and ch == '"'):
                    en_simple = en_doble = False
                i += 1
                continue
            if en_tilde:
                actual.append(ch)
                if ch == "`":
                    en_tilde = False
                i += 1
                continue

            # Fuera de comillas y comentarios
            if ch == "-" and sig == "-" and (i + 2 >= len(linea) or linea[i + 2] in " \t\r\n"):
                en_linea = True
                actual.append(ch)
                i += 1
                continue
            if ch == "#":
                en_linea = True
                actual.append(ch)
                i += 1
                continue
            if ch == "/" and sig == "*":
                en_bloque = True
                actual.extend(ch + sig)
                i += 2
                continue
            if ch == "'":
                en_simple = True
            elif ch == '"':
                en_doble = True
            elif ch == "`":
                en_tilde = True
            elif linea.startswith(delimitador, i):
                _agregar(sentencias, actual)
                actual = []
                i += len(delimitador)
                continue
            actual.append(ch)
            i += 1

    _agregar(sentencias, actual)
    return sentencias


def _agregar(sentencias: list[str], trozo: list[str]) -> None:
    texto = "".join(trozo).strip()
    if not texto:
        return
    util = [l for l in texto.splitlines() if l.strip() and not l.strip().startswith("--")]
    if util:
        sentencias.append(texto)


def ejecutar_archivo(conexion, archivo: Path) -> int:
    sentencias = dividir_sql(archivo.read_text(encoding="utf-8"))
    with conexion.cursor() as cursor:
        for numero, sentencia in enumerate(sentencias, 1):
            try:
                cursor.execute(sentencia)
                while cursor.nextset():
                    pass
            except pymysql.MySQLError as error:
                inicio = " ".join(sentencia.split())[:120]
                raise RuntimeError(f"{archivo.name}, sentencia {numero}: {error.args}\n    -> {inicio}") from error
    return len(sentencias)


# ---------------------------------------------------------------------
# Respaldo
# ---------------------------------------------------------------------
def respaldar(conexion, base: str) -> Path:
    RESPALDOS.mkdir(exist_ok=True)
    destino = RESPALDOS / f"respaldo_{base}_{datetime.now():%Y%m%d_%H%M%S}.sql"
    with conexion.cursor() as cursor, destino.open("w", encoding="utf-8") as salida:
        salida.write(f"-- Respaldo de {base} generado {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        salida.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS = 0;\n\n")

        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tablas = [list(f.values())[0] for f in cursor.fetchall()]
        for tabla in tablas:
            cursor.execute(f"SHOW CREATE TABLE `{tabla}`")
            ddl = cursor.fetchone()["Create Table"]
            salida.write(f"DROP TABLE IF EXISTS `{tabla}`;\n{ddl};\n\n")
            cursor.execute(f"SELECT * FROM `{tabla}`")
            filas = cursor.fetchall()
            for fila in filas:
                columnas = ", ".join(f"`{c}`" for c in fila)
                valores = ", ".join(conexion.escape(v) for v in fila.values())
                salida.write(f"INSERT INTO `{tabla}` ({columnas}) VALUES ({valores});\n")
            salida.write("\n")

        cursor.execute("SHOW PROCEDURE STATUS WHERE Db = %s", (base,))
        procedimientos = [f["Name"] for f in cursor.fetchall()]
        salida.write("DELIMITER $$\n")
        for nombre in procedimientos:
            cursor.execute(f"SHOW CREATE PROCEDURE `{nombre}`")
            cuerpo = cursor.fetchone()["Create Procedure"]
            if not cuerpo:
                raise RuntimeError(f"No se pudo leer el cuerpo de {nombre} (¿privilegios?).")
            salida.write(f"DROP PROCEDURE IF EXISTS `{nombre}`$$\n{cuerpo}$$\n\n")
        salida.write("DELIMITER ;\n\nSET FOREIGN_KEY_CHECKS = 1;\n")

    print(f"   {len(tablas)} tablas y {len(procedimientos)} procedimientos -> {destino.name} "
          f"({destino.stat().st_size:,} bytes)")
    if destino.stat().st_size < 500:
        raise RuntimeError("El respaldo salió casi vacío; no se continúa.")
    return destino


def conteos(conexion) -> dict[str, int]:
    resultado = {}
    with conexion.cursor() as cursor:
        for tabla in TABLAS_PREVIAS:
            cursor.execute(f"SELECT COUNT(*) AS n FROM `{tabla}`")
            resultado[tabla] = int(cursor.fetchone()["n"])
    return resultado


def comparar(antes: dict, despues: dict, etiqueta: str) -> None:
    for tabla, n in antes.items():
        marca = "OK " if despues[tabla] == n else "!! "
        print(f"   {marca}{tabla:20} antes {n:6}  despues {despues[tabla]:6}")
    if antes != despues:
        raise RuntimeError(f"Los conteos cambiaron en {etiqueta}: la migración no preservó los datos.")


def aplicar(conexion, etiqueta: str) -> None:
    for nombre in MIGRACIONES:
        total = ejecutar_archivo(conexion, CARPETA / nombre)
        print(f"   {etiqueta}: {nombre} ({total} sentencias) aplicado")


def registrar(texto: str) -> None:
    with REGISTRO.open("a", encoding="utf-8") as salida:
        salida.write(texto + "\n")


# ---------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--solo-respaldo", action="store_true")
    parser.add_argument("--sin-copia", action="store_true", help="Omite la prueba en copia aislada")
    args = parser.parse_args()

    base = get_settings().db_name
    inicio = datetime.now()
    print(f"== Migración 4.3 sobre `{base}` ({get_settings().db_host.split('.')[0]}...) ==")

    real = conectar(base)
    print("1) Respaldo")
    respaldo = respaldar(real, base)
    if args.solo_respaldo:
        return 0

    print("2) Conteos previos")
    antes = conteos(real)
    for tabla, n in antes.items():
        print(f"   {tabla:20} {n}")

    if not args.sin_copia:
        prueba = f"{base}_prueba_{inicio:%Y%m%d%H%M%S}"
        print(f"3) Copia de prueba `{prueba}`")
        servidor = conectar(None)
        with servidor.cursor() as cursor:
            # La copia hereda el juego de caracteres y la collation de la base real:
            # si difieren, los procedimientos comparan textos con collations mezcladas.
            cursor.execute("SELECT DEFAULT_CHARACTER_SET_NAME AS cs, DEFAULT_COLLATION_NAME AS co "
                           "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s", (base,))
            fila = cursor.fetchone()
            cursor.execute(f"CREATE DATABASE `{prueba}` CHARACTER SET {fila['cs']} COLLATE {fila['co']}")
        copia = conectar(prueba)
        ejecutar_archivo(copia, respaldo)
        print("   respaldo cargado en la copia")
        antes_copia = conteos(copia)
        aplicar(copia, "copia")
        comparar(antes_copia, conteos(copia), "la copia de prueba")
        print("   la copia de prueba pasó: los datos se conservaron")
        copia.close()
    else:
        print("3) Copia de prueba omitida (--sin-copia)")

    print("4) Base real")
    aplicar(real, "real")

    print("5) Verificación")
    comparar(antes, conteos(real), "la base real")
    with real.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM information_schema.ROUTINES "
                       "WHERE ROUTINE_SCHEMA = %s AND ROUTINE_TYPE = 'PROCEDURE'", (base,))
        procs = cursor.fetchone()["n"]
        cursor.execute("SELECT (SELECT COUNT(*) FROM roles) r, (SELECT COUNT(*) FROM usuarios) u, "
                       "(SELECT COUNT(*) FROM modelos) m")
        nuevos = cursor.fetchone()
    print(f"   procedimientos totales: {procs} | roles {nuevos['r']} | usuarios {nuevos['u']} | modelos {nuevos['m']}")

    registrar(f"{inicio:%Y-%m-%d %H:%M:%S} | migración 4.3 (001-003) | base {base} | OK | "
              f"respaldo {respaldo.name} | conteos {antes} | procedimientos {procs}")
    print("== Migración aplicada correctamente ==")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # se informa y se deja constancia
        print(f"\n!! SE DETUVO: {error}")
        registrar(f"{datetime.now():%Y-%m-%d %H:%M:%S} | migración 4.3 | ERROR | {error}")
        sys.exit(1)
