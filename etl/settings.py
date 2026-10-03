"""Configuración por variables de entorno (ver .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DbSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    driver: str

    @classmethod
    def from_env(cls, user_var: str = "DB_USER", password_var: str = "DB_PASSWORD",
                 default_user: str = "sa") -> DbSettings:
        """
        El ETL usa DB_USER/DB_PASSWORD (administrador: crea el esquema y escribe).
        La API usa DB_API_USER/DB_API_PASSWORD (solo lectura): ver for_api().
        """
        password = os.environ.get(password_var)
        if not password:
            raise RuntimeError(f"Falta la variable de entorno {password_var} (ver .env.example)")
        return cls(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "1433")),
            user=os.environ.get(user_var, default_user),
            password=password,
            database=os.environ.get("DB_NAME", "alarmas"),
            driver=os.environ.get("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        )

    @classmethod
    def for_api(cls) -> DbSettings:
        return cls.from_env("DB_API_USER", "DB_API_PASSWORD", default_user="api_lectura")

    def connection_string(self, database: str | None = None) -> str:
        # TrustServerCertificate: el contenedor de SQL Server usa un certificado
        # autofirmado. En producción se configuraría un certificado válido.
        return (
            f"DRIVER={{{self.driver}}};SERVER={self.host},{self.port};"
            f"DATABASE={database or self.database};UID={self.user};PWD={self.password};"
            "Encrypt=yes;TrustServerCertificate=yes"
        )
