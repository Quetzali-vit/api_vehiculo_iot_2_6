"""Hash de contraseñas y generación de tokens.

Usa PBKDF2-SHA256 de la biblioteca estándar: no agrega dependencias nuevas al
despliegue y es el algoritmo que recomienda NIST para contraseñas.

La base de datos guarda SOLO el hash, nunca la contraseña. De los tokens de
sesión se guarda su SHA-256: si alguien leyera la tabla `sesiones` no podría
reconstruir un token válido.
"""

import base64
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 210_000
TAMANO_SAL = 16


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve 'pbkdf2_sha256$iteraciones$sal$hash' en base64."""
    sal = secrets.token_bytes(TAMANO_SAL)
    derivada = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, ITERACIONES)
    return "{}${}${}${}".format(
        ALGORITMO,
        ITERACIONES,
        base64.b64encode(sal).decode("ascii"),
        base64.b64encode(derivada).decode("ascii"),
    )


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    """Compara en tiempo constante. Devuelve False si el hash está mal formado."""
    try:
        algoritmo, iteraciones, sal_b64, hash_b64 = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(hash_b64)
        derivada = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, int(iteraciones))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivada, esperado)


def generar_token() -> str:
    """Token de sesión imposible de adivinar (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 en hexadecimal: lo único que se guarda en la base."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
