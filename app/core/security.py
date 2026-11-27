import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave definida en API_KEY. Protege las operaciones de control y eliminación.",
)


class VerificadorApiKey:
    """Dependencia del dispositivo (ESP32): exige el encabezado X-API-Key.

    Rechaza con 401 si falta la clave y con 403 si no coincide. La comparación
    es en tiempo constante para no filtrar la clave por tiempos de respuesta.
    """

    def __call__(
        self,
        api_key: str | None = Security(api_key_header),
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta el encabezado X-API-Key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if not secrets.compare_digest(api_key, settings.api_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La clave X-API-Key no es válida")


requiere_api_key = VerificadorApiKey()
