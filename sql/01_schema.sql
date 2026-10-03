/* =============================================================================
   Modelo de datos de alarmas industriales (SQL Server)

   FUENTE PLANA -> MODELO NORMALIZADO
   El CSV legacy repite en cada evento la descripción, el área, la unidad, el
   tipo de alarma y el límite. Esos datos NO describen el evento, sino el
   instrumento (tag) o la configuración de la alarma, así que se separan:

     area ──< tag ──< alarma ──< alarma_config ──< evento_alarma
                  (unidad)        (límite,           (valor, estado,
                                   criticidad)        timestamp)

   - La UNIDAD pertenece al instrumento: un transmisor de presión mide en bar
     sin importar cuántas alarmas tenga configuradas.
   - El LÍMITE pertenece a la alarma: PT-101 puede tener HI a 8,5 bar y HIHI a
     10 bar (misma unidad, distintos límites).
   - Límites y criticidades se guardan como DATOS y no como constantes en el
     código: en planta se re-racionalizan (ISA-18.2, gestión del cambio), y
     cambiarlos no debería requerir un redeploy. El código conserva la REGLA
     ("HI = valor > límite"); la base de datos conserva el NÚMERO.

   El script es idempotente: puede ejecutarse varias veces sin error.
   ============================================================================= */

/* ---------------------------------------------------------------------------
   Catálogo (configuración de planta, "Master Alarm Database" de ISA-18.2)
   --------------------------------------------------------------------------- */

IF OBJECT_ID('dbo.area') IS NULL
CREATE TABLE dbo.area (
    id      INT IDENTITY(1,1) CONSTRAINT pk_area PRIMARY KEY,
    nombre  NVARCHAR(50) NOT NULL CONSTRAINT uq_area_nombre UNIQUE
);
GO

IF OBJECT_ID('dbo.tag') IS NULL
CREATE TABLE dbo.tag (
    id           INT IDENTITY(1,1) CONSTRAINT pk_tag PRIMARY KEY,
    codigo       VARCHAR(20)   NOT NULL CONSTRAINT uq_tag_codigo UNIQUE,   -- 'PT-101'
    descripcion  NVARCHAR(200) NOT NULL,
    unidad       NVARCHAR(20)  NULL,   -- NULL en señales discretas (DISC), que no tienen unidad
    area_id      INT           NOT NULL CONSTRAINT fk_tag_area REFERENCES dbo.area(id)
);
GO

/* Tabla de referencia: 'nivel' permite filtros ordinales ("HIGH o superior"),
   que no se pueden expresar comparando texto. */
IF OBJECT_ID('dbo.criticidad') IS NULL
CREATE TABLE dbo.criticidad (
    id      TINYINT     NOT NULL CONSTRAINT pk_criticidad PRIMARY KEY,
    nombre  VARCHAR(10) NOT NULL CONSTRAINT uq_criticidad_nombre UNIQUE,
    nivel   TINYINT     NOT NULL CONSTRAINT uq_criticidad_nivel UNIQUE
);
GO

MERGE dbo.criticidad AS destino
USING (VALUES (1, 'LOW', 1), (2, 'MEDIUM', 2), (3, 'HIGH', 3), (4, 'CRITICAL', 4))
      AS origen (id, nombre, nivel)
ON destino.id = origen.id
WHEN NOT MATCHED THEN INSERT (id, nombre, nivel) VALUES (origen.id, origen.nombre, origen.nivel);
GO

/* Identidad de la alarma: "existe la alarma HI del TT-301". No cambia nunca. */
IF OBJECT_ID('dbo.alarma') IS NULL
CREATE TABLE dbo.alarma (
    id           INT IDENTITY(1,1) CONSTRAINT pk_alarma PRIMARY KEY,
    tag_id       INT        NOT NULL CONSTRAINT fk_alarma_tag REFERENCES dbo.tag(id),
    tipo_alarma  VARCHAR(5) NOT NULL
        CONSTRAINT ck_alarma_tipo CHECK (tipo_alarma IN ('HI', 'HIHI', 'LO', 'LOLO', 'DEV', 'ROC', 'DISC')),
    CONSTRAINT uq_alarma_tag_tipo UNIQUE (tag_id, tipo_alarma)
);
GO

/* Configuración versionada de cada alarma (Slowly Changing Dimension tipo 2).

   Los límites cambian con el tiempo. Si se sobrescribieran con UPDATE, un evento
   histórico se compararía con un límite que no existía cuando ocurrió. Por eso:
     - cambiar un límite = cerrar la versión vigente (vigente_hasta = ahora)
       e insertar una nueva; nunca se modifica el número de una versión;
     - cada evento apunta a la versión vigente en el momento en que ocurrió.
   Así el JOIN sigue siendo simple y el histórico se interpreta correctamente. */
IF OBJECT_ID('dbo.alarma_config') IS NULL
CREATE TABLE dbo.alarma_config (
    id             INT IDENTITY(1,1) CONSTRAINT pk_alarma_config PRIMARY KEY,
    alarma_id      INT            NOT NULL CONSTRAINT fk_alarma_config_alarma REFERENCES dbo.alarma(id),
    limite         DECIMAL(18, 4) NOT NULL,
    criticidad_id  TINYINT        NOT NULL CONSTRAINT fk_alarma_config_criticidad REFERENCES dbo.criticidad(id),
    vigente_desde  DATETIME2(0)   NOT NULL,
    vigente_hasta  DATETIME2(0)   NULL,     -- NULL = versión vigente
    CONSTRAINT uq_alarma_config_version UNIQUE (alarma_id, vigente_desde),
    CONSTRAINT ck_alarma_config_vigencia CHECK (vigente_hasta IS NULL OR vigente_hasta > vigente_desde)
);
GO

/* ---------------------------------------------------------------------------
   Trazabilidad del ETL
   --------------------------------------------------------------------------- */

IF OBJECT_ID('dbo.lote_carga') IS NULL
CREATE TABLE dbo.lote_carga (
    id                 INT IDENTITY(1,1) CONSTRAINT pk_lote_carga PRIMARY KEY,
    archivo            NVARCHAR(260) NOT NULL,
    inicio             DATETIME2(0)  NOT NULL CONSTRAINT df_lote_carga_inicio DEFAULT SYSUTCDATETIME(),
    fin                DATETIME2(0)  NULL,
    estado             VARCHAR(10)   NOT NULL CONSTRAINT df_lote_carga_estado DEFAULT 'EN_CURSO'
        CONSTRAINT ck_lote_carga_estado CHECK (estado IN ('EN_CURSO', 'OK', 'ERROR')),
    mensaje_error      NVARCHAR(1000) NULL,
    filas_leidas       INT NULL,
    filas_duplicadas   INT NULL,     -- duplicados dentro del archivo
    filas_ya_cargadas  INT NULL,     -- ya existían en la BD (re-ejecución idempotente)
    filas_cargadas     INT NULL,
    filas_rechazadas   INT NULL
);
GO

/* Las filas que no se pueden limpiar no se pierden en silencio: se guardan tal
   como llegaron, con el motivo, para que alguien pueda revisarlas. */
IF OBJECT_ID('dbo.evento_rechazado') IS NULL
CREATE TABLE dbo.evento_rechazado (
    id              BIGINT IDENTITY(1,1) CONSTRAINT pk_evento_rechazado PRIMARY KEY,
    lote_id         INT            NOT NULL CONSTRAINT fk_evento_rechazado_lote REFERENCES dbo.lote_carga(id),
    fila_original   NVARCHAR(2000) NOT NULL,   -- JSON con la fila tal como venía en el CSV
    motivo          NVARCHAR(500)  NOT NULL
);
GO

/* ---------------------------------------------------------------------------
   Hechos: eventos del ciclo de vida de las alarmas (ACTIVE -> ACK -> RTN)
   --------------------------------------------------------------------------- */

IF OBJECT_ID('dbo.evento_alarma') IS NULL
CREATE TABLE dbo.evento_alarma (
    id                BIGINT IDENTITY(1,1) NOT NULL,
    id_evento_origen  BIGINT       NOT NULL,   -- id del SCADA: evita duplicados y permite trazar
    alarma_config_id  INT          NOT NULL CONSTRAINT fk_evento_alarma_config REFERENCES dbo.alarma_config(id),
    timestamp_utc     DATETIME2(3) NOT NULL,
    estado            VARCHAR(6)   NOT NULL CONSTRAINT ck_evento_estado CHECK (estado IN ('ACTIVE', 'ACK', 'RTN')),
    /* Desnormalización deliberada: la criticidad ya está en alarma_config, pero
       el filtro más común de la API es criticidad + rango de tiempo. Tenerla en
       esta tabla permite resolverlo con el índice ix_evento_criticidad_tiempo
       sin JOINs. */
    criticidad_id     TINYINT      NOT NULL CONSTRAINT fk_evento_criticidad REFERENCES dbo.criticidad(id),
    valor             FLOAT        NULL,       -- NULL si la lectura no era confiable
    /* GOOD = lectura válida; BAD = el SCADA reportó fallo ('Bad Quality', 'NaN'...);
       NULL = la fuente no trajo valor. Distingue "no hay dato" de "dato inválido". */
    calidad_valor     VARCHAR(4)   NULL CONSTRAINT ck_evento_calidad CHECK (calidad_valor IN ('GOOD', 'BAD')),
    lote_id           INT          NOT NULL CONSTRAINT fk_evento_lote REFERENCES dbo.lote_carga(id),
    CONSTRAINT pk_evento_alarma PRIMARY KEY NONCLUSTERED (id),
    CONSTRAINT uq_evento_id_origen UNIQUE (id_evento_origen)   -- hace la carga idempotente
);
GO

/* Índices orientados a las consultas de la API.

   El índice CLUSTERED (orden físico de la tabla) es por tiempo, no por id:
   casi todas las consultas piden un rango de fechas, y así se leen páginas
   contiguas del disco. Los eventos llegan en orden cronológico, por lo que las
   inserciones van al final y no fragmentan el índice. */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'cix_evento_tiempo')
    CREATE CLUSTERED INDEX cix_evento_tiempo ON dbo.evento_alarma (timestamp_utc, id);
GO

-- Filtro por criticidad (+ rango de tiempo)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_evento_criticidad_tiempo')
    CREATE INDEX ix_evento_criticidad_tiempo ON dbo.evento_alarma (criticidad_id, timestamp_utc)
        INCLUDE (estado, valor, alarma_config_id);
GO

-- Filtro por tag/alarma (+ rango de tiempo) y agregación de top tags
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_evento_config_tiempo')
    CREATE INDEX ix_evento_config_tiempo ON dbo.evento_alarma (alarma_config_id, timestamp_utc)
        INCLUDE (estado);
GO

-- Resolver la versión de configuración vigente al cargar un evento
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_alarma_config_vigencia')
    CREATE INDEX ix_alarma_config_vigencia ON dbo.alarma_config (alarma_id, vigente_desde)
        INCLUDE (vigente_hasta);
GO

/* ---------------------------------------------------------------------------
   Vista de consulta: reconstruye la vista "plana" para otros sistemas de
   planta sin duplicar datos. La unidad y el límite los aporta el JOIN, no
   la aplicación.
   --------------------------------------------------------------------------- */

CREATE OR ALTER VIEW dbo.v_evento_alarma AS
SELECT
    e.id,
    e.id_evento_origen,
    e.timestamp_utc,
    t.codigo          AS tag,
    t.descripcion,
    ar.nombre         AS area,
    a.tipo_alarma,
    c.nombre          AS criticidad,
    c.nivel           AS criticidad_nivel,
    e.estado,
    e.valor,
    e.calidad_valor,
    t.unidad,
    ac.limite,                              -- límite vigente cuando ocurrió el evento
    /* Positiva = por encima del límite, negativa = por debajo. Su lectura depende
       del tipo: en HI/HIHI una alarma real es positiva, en LO/LOLO es negativa. */
    /* valor es FLOAT (así lo entrega el SCADA) y limite es DECIMAL: se redondea
       para no exponer ruido de punto flotante (5.1999999999999602E-2 -> 0.0520). */
    CAST(e.valor - ac.limite AS DECIMAL(18, 4)) AS desviacion_limite
FROM dbo.evento_alarma e
JOIN dbo.alarma_config ac ON ac.id = e.alarma_config_id
JOIN dbo.alarma a         ON a.id  = ac.alarma_id
JOIN dbo.tag t            ON t.id  = a.tag_id
JOIN dbo.area ar          ON ar.id = t.area_id
JOIN dbo.criticidad c     ON c.id  = e.criticidad_id;
GO

/* Catálogo con la configuración VIGENTE de cada alarma (para la API y el frontend). */
CREATE OR ALTER VIEW dbo.v_catalogo AS
SELECT
    t.codigo        AS tag,
    t.descripcion,
    ar.nombre       AS area,
    t.unidad,
    a.tipo_alarma,
    ac.limite,
    c.nombre        AS criticidad,
    ac.vigente_desde
FROM dbo.tag t
JOIN dbo.area ar          ON ar.id = t.area_id
JOIN dbo.alarma a         ON a.tag_id = t.id
JOIN dbo.alarma_config ac ON ac.alarma_id = a.id AND ac.vigente_hasta IS NULL
JOIN dbo.criticidad c     ON c.id = ac.criticidad_id;
GO
