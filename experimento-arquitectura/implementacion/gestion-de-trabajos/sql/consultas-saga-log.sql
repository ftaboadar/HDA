-- Consultas para el log de la saga
-- 1. Ver el estado actual de una saga
SELECT * FROM saga_instancia WHERE id = :saga_id;

-- 2. Ver el historial de eventos de una saga (Saga Log)
SELECT * FROM saga_log WHERE saga_id = :saga_id ORDER BY timestamp ASC;

-- 3. Ver sagas fallidas
SELECT * FROM saga_instancia WHERE estado = 'FALLIDA';

-- 4. Ver sagas compensadas
SELECT * FROM saga_instancia WHERE estado = 'COMPENSADA';
