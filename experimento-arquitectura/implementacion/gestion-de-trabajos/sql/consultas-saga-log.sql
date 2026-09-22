-- Consultas básicas al Saga Log

-- 1. Línea de tiempo de una saga
SELECT secuencia, paso, tipo, servicio, mensaje, ocurrido_en
FROM saga_log
WHERE saga_id = 'AQUI_UUID_DE_LA_SAGA'
ORDER BY secuencia ASC;

-- 2. Sagas compensadas
SELECT saga_id, origen, iniciada_en, actualizada_en
FROM saga_instancia
WHERE estado = 'COMPENSADA';

-- 3. Pasos expirados
SELECT id, saga_id, paso, ocurrido_en
FROM saga_log
WHERE tipo = 'PASO_EXPIRADO'
ORDER BY ocurrido_en DESC;

-- 4. Duración por paso (Diferencia de tiempo entre pasos consecutivos)
WITH OrderedLogs AS (
    SELECT 
        saga_id, 
        paso, 
        ocurrido_en,
        LAG(ocurrido_en) OVER (PARTITION BY saga_id ORDER BY secuencia) as paso_anterior_en
    FROM saga_log
)
SELECT 
    saga_id, 
    paso, 
    EXTRACT(EPOCH FROM (ocurrido_en - paso_anterior_en)) as duracion_segundos
FROM OrderedLogs
WHERE paso_anterior_en IS NOT NULL;
