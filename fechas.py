# -*- coding: utf-8 -*-
import zoneinfo
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

def fecha_z_automatica():
  try:
    # Definir zona horaria Mexico
    tz_local = zoneinfo.ZoneInfo("America/Mexico_City")
    # Obtener el ahora reginal
    ahora_local = datetime.now(tz_local)
    # Calcular el lunes a las 00:00:00 De esta semana
    dias_al_lunes = ahora_local.weekday()
    inicio_lunes_local = ahora_local -timedelta(days=dias_al_lunes) -timedelta(days=7)
    inicio_lunes_local = inicio_lunes_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    final_domingo_local = inicio_lunes_local + timedelta(days=7) - timedelta(seconds=1)


    
    # Convertir a UTC
    inicio_lunes_utc = inicio_lunes_local.astimezone(timezone.utc)
    final_domingo_utc = final_domingo_local.astimezone(timezone.utc)

    

    start_time = inicio_lunes_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    end_time = final_domingo_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    logger.info("Parametros de fecha generados correctamente")

    return start_time, end_time

  except zoneinfo.ZoneInfoNotFoundError:
    logger.error("No se encontro la zona horaria Mexico")
    return None

def fecha_z_manual(dia_i, mes_i, ano_i, dia_f, mes_f, ano_f):
    try:
        # Definir zona horaria Mexico
        tz_local = zoneinfo.ZoneInfo("America/Mexico_City")
        
        # Crear objetos datetime basados en tus argumentos (asumiendo hora local)
        # Inicio a las 00:00:00 y fin a las 23:59:59 para cubrir el d�a completo
        inicio_local = datetime(ano_i, mes_i, dia_i, 0, 0, 0, tzinfo=tz_local)
        final_local = datetime(ano_f, mes_f, dia_f, 23, 59, 59, tzinfo=tz_local)
        
        # Convertir a UTC
        inicio_utc = inicio_local.astimezone(timezone.utc)
        final_utc = final_local.astimezone(timezone.utc)

        # Retornamos y convertimos a formato con milisegundos y Z
        start_time = inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        end_time = final_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        logger.info(f"Parametros de fecha manuales generados: {start_time} - {end_time}")

        return start_time, end_time

    except Exception as e:
        logger.error(f"Error al generar fechas manuales: {e}")
        return None

def fecha_milisegundos():
    try:
        # Definir zona horaria M�xico
        tz_local = zoneinfo.ZoneInfo("America/Mexico_City")

        # Obtener el ahora regional
        ahora_local = datetime.now(tz_local)

        # Calcular el lunes de la SEMANA ANTERIOR a las 00:00:00
        # (Tal como ten�as en tu l�gica original con el -timedelta(days=7))
        dias_al_lunes = ahora_local.weekday()
        inicio_lunes_local = ahora_local - timedelta(days=dias_al_lunes) - timedelta(days=7)
        inicio_lunes_local = inicio_lunes_local.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # El domingo finaliza justo antes del lunes actual
        final_domingo_local = inicio_lunes_local + timedelta(days=7) - timedelta(seconds=1)

        # Convertir a UTC (Opcional para timestamp, pero buena pr�ctica)
        inicio_lunes_utc = inicio_lunes_local.astimezone(timezone.utc)
        final_domingo_utc = final_domingo_local.astimezone(timezone.utc)

        # Convertir a milisegundos (timestamp() devuelve segundos con decimales)
        start_time_ms = int(inicio_lunes_utc.timestamp() * 1000)
        end_time_ms = int(final_domingo_utc.timestamp() * 1000)

        logger.info(f"Parametros generados: Start={start_time_ms}, End={end_time_ms}")

        return start_time_ms, end_time_ms

    except zoneinfo.ZoneInfoNotFoundError:
        logger.error("No se encontro la zona horaria Mexico")
        return None, None

def fecha_milisegundos_manual(dia_i, mes_i, ano_i, dia_f, mes_f, ano_f):
    """
    Genera timestamps en milisegundos usando argumentos manuales:
    (dia_inicio, mes_inicio, ano_inicio, dia_fin, mes_fin, ano_fin)
    """
    try:
        # Definir zona horaria M�xico
        tz_local = zoneinfo.ZoneInfo("America/Mexico_City")

        # 1. Crear el inicio (00:00:00)
        # Nota: datetime usa el orden (ano, mes, dia) internamente
        inicio_local = datetime(
            ano_i, mes_i, dia_i, 0, 0, 0, 0, tzinfo=tz_local
        )

        # 2. Crear el fin (23:59:59)
        fin_local = datetime(
            ano_f, mes_f, dia_f, 23, 59, 59, 0, tzinfo=tz_local
        )

        # 3. Convertir a UTC para obtener el timestamp correcto
        inicio_utc = inicio_local.astimezone(timezone.utc)
        fin_utc = fin_local.astimezone(timezone.utc)

        # 4. Convertir a milisegundos (enteros)
        start_time_ms = int(inicio_utc.timestamp() * 1000)
        end_time_ms = int(fin_utc.timestamp() * 1000)

        logger.info(f"Rango manual establecido: {inicio_local} a {fin_local}")
        
        return start_time_ms, end_time_ms

    except Exception as e:
        logger.error(f"Error al procesar fechas manuales: {e}")
        return None, None