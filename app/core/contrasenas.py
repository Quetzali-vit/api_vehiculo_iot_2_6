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


class HasherContrasenas:
    """Convierte contraseñas en hashes PBKDF2 y las verifica.

    El formato guardado es 'pbkdf2_sha256$iteraciones$sal$hash' (base64), así
    que un hash viejo sigue verificándose aunque cambien las iteraciones.
    """

    ALGORITMO = "pbkdf2_sha256"
    ITERACIONES = 210_000
    TAMANO_SAL = 16

    def hashear(self, contrasena: str) -> str:
        sal = secrets.token_bytes(self.TAMANO_SAL)
        derivada = self._derivar(contrasena, sal, self.ITERACIONES)
        return "{}${}${}${}".format(
            self.ALGORITMO,
            self.ITERACIONES,
            base64.b64encode(sal).decode("ascii"),
            base64.b64encode(derivada).decode("ascii"),
        )

    def verificar(self, contrasena: str, guardado: str) -> bool:
        """Compara en tiempo constante. Devuelve False si el hash está mal formado."""
        try:
            algoritmo, iteraciones, sal_b64, hash_b64 = guardado.split("$")
            if algoritmo != self.ALGORITMO:
                return False
            sal = base64.b64decode(sal_b64)
            esperado = base64.b64decode(hash_b64)
            derivada = self._derivar(contrasena, sal, int(iteraciones))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(derivada, esperado)

    @staticmethod
    def _derivar(contrasena: str, sal: bytes, iteraciones: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)


class GeneradorTokens:
    """Tokens de sesión: el cliente recibe el token; la base solo guarda su huella."""

    BYTES = 32  # 256 bits

    def generar(self) -> str:
        """Token de sesión imposible de adivinar."""
        return secrets.token_urlsafe(self.BYTES)

    def huella(self, token: str) -> str:
        """SHA-256 en hexadecimal: lo único que se guarda en la base."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Instancias compartidas (no guardan estado, así que una basta para toda la API)
hasher_contrasenas = HasherContrasenas()
generador_tokens = GeneradorTokens()
