# La versión de Debian se fija (bookworm = Debian 12) porque el driver se instala
# desde el repositorio de Microsoft para Debian 12. Con la etiqueta genérica
# 'slim' la imagen pasó a Debian 13 y el driver no encontraba sus dependencias.
FROM python:3.12-slim-bookworm

# Driver ODBC 18 de Microsoft para conectarse a SQL Server desde Python (pyodbc).
# Instalarlo implica aceptar la licencia de Microsoft (ACCEPT_EULA).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl/ etl/
COPY api/ api/
COPY sql/ sql/
COPY config/ config/
COPY data_generation/ data_generation/

# Usuario sin privilegios: el contenedor no necesita ser root.
RUN useradd --create-home appuser
USER appuser
