-- Se ejecuta conectado a la base 'master'.
IF DB_ID('alarmas') IS NULL
    CREATE DATABASE alarmas;
GO
