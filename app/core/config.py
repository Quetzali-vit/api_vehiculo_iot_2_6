from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ARCHIVO_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Configuración de la API leída desde variables de entorno o del archivo .env."""

    model_config = SettingsConfigDict(env_file=ARCHIVO_ENV, env_file_encoding="utf-8", extra="ignore")

    db_host: str = Field(description="Endpoint de la instancia Amazon RDS")
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "vehiculo_iot"
    db_connect_timeout: int = 10

    api_key: str = Field(min_length=8, description="Clave del dispositivo (ESP32) para reportar su estado")

    cors_origins: str = Field(
        default="https://quetzali-vit.github.io",
        description="Orígenes del frontend separados por coma. Ejemplo: "
                    "https://quetzali-vit.github.io,http://127.0.0.1:5500",
    )
    origen_movimiento: str = Field(default="API-LOCAL", max_length=30)

    host: str = "127.0.0.1"
    port: int = 8000


    @property
    def lista_cors(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
