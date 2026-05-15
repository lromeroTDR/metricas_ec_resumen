# -*- coding: utf-8 -*-
import requests
import time
from datetime import  timedelta, datetime
import polars as pl
import os
from fechas import fecha_milisegundos, fecha_z_automatica, fecha_z_manual, fecha_milisegundos_manual
import logging
from config import headers, API_URLS, tags_filtro
from wrapp import retry_api

logger = logging.getLogger(__name__)



#================================
# Extraer ScoreTags
#===============================?
@retry_api(max_attempts=3, delay=10)
def extraer_score_tags(url, headers, scoreType, start_time, end_time):
    """ Extraemos los score y metricas de seguridad para seguridad """
    base_params = {
        "scoreType": scoreType,
        "startTime": start_time,
        "endTime": end_time,

    }

    all_events = []
    has_next_page = True
    cursor = None

    while has_next_page:
        # Copiamos los parámetros base para no ensuciarlos en cada ciclo
        current_params = base_params.copy()
        if cursor:
            current_params["after"] = cursor

        try:
            response = requests.get(url, headers=headers, params=current_params, timeout=30)
            response.raise_for_status()

            data = response.json()
            events = data.get("data", [])
            all_events.extend(events)

            # Extraer información de paginación
            pagination = data.get("pagination", {})
            has_next_page = pagination.get("has_next_page", False)
            cursor = pagination.get("endCursor") # O la llave que use tu API

            logger.info(f"Descargados {len(events)} eventos. Total acumulado: {len(all_events)}")

            if has_next_page:
                time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición: {e}")
            break # Detener si hay un error de red

    if all_events:
        logger.info("Proceso finalizado exitosamente")
        return pl.from_dicts(all_events, strict=False)
    else:
        logger.warning("No se encontraron eventos tras recorrer todas las páginas")
        return pl.DataFrame() 

def transformacion_scores(scores):
  """ Damos tratamiento al DF"""
  try:
    df_behaviors = (scores
                  .drop("speeding")
                  .explode("behaviors")
                  .unnest("behaviors")
                  .rename({
                    "behaviorType": "evento",
                    })

                  .with_columns(
                 pl.lit(None).cast(pl.Int64).alias("durationMilliseconds")
                  )
    )
    df_speeding = (scores
                  .drop("behaviors")
                  .explode("speeding")
                  .unnest("speeding")
                  .filter(pl.col("speedingType") == "maxSpeed")
                  .rename({
                    "speedingType": "evento",
                    })
                  .with_columns(
                 pl.lit(None).cast(pl.Int64).alias("count")
               )

    )
    df_speeding = df_speeding.select(df_behaviors.columns)
    df_final = pl.concat([df_behaviors, df_speeding], how="vertical")

    df_final = (df_final.with_columns(
        (pl.col("driveTimeMilliseconds")/ 3_600_000).round(3).alias("DriveDistanceHours"),
        (pl.col("durationMilliseconds")/ 3_600_000).round(3).alias("DurationHours"),
        (pl.col("driveDistanceMeters")/ 1_000).round(3).alias("DriveDistanceKilometers")
        )
        .drop(["driveTimeMilliseconds", "durationMilliseconds", "driveDistanceMeters"])
                )



    df_ancho = (df_final.filter(pl.col("evento").is_not_null())
                        .pivot(
                            index=["tagId", "tagScore", "DriveDistanceHours", "DriveDistanceKilometers"],
                            on="evento",
                            values="count",
                            aggregate_function="sum"
                            )
                        .rename({"tagId": "parentTagId", "tagScore":"parentTagScore"})
              )     

    logger.info("Transformación de scores finalizada exitosamente")

    return df_ancho

  except Exception as e:
    logger.error(f"Error en la transformación de scores: {e}")
    return None
#===============================
# Extraer tags
#==============================
@retry_api(max_attempts=3, delay=10)
def extraer_tags_samsara(headers, url):
    """
    Obtiene la lista de tags usados en la organización.
    """

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json().get('data', [])

    if not data:
        logger.warning("Advertencia: No se encontraron Tags")
        print("Advertencia: No se encontraron tags.")
        return pl.DataFrame()

    # 2. Creación del DataFrame y Transformación
    df_tags = (
        pl.DataFrame(data)
        .rename({
            'id': 'tagId',
            'name': 'tagName',
            'parentTagId': 'parentTagId'
        })
        .with_columns([
            pl.col(['tagId', 'parentTagId']).cast(pl.Utf8)
        ])
    )
    print(f"Éxito: Se obtuvieron {df_tags.height} tags.")
    logger.info(f"Éxito: Se obtuvieron {df_tags.height} tags.")
    return df_tags

def transformacion_tags(df_tags, tags_filtro):
    """
    Selecciona las columnas del tag padre.
    """
    try:
        df_tags_transformado = (
            df_tags
            .select(["tagId", "tagName",])
            .rename({"tagName": "parentTagName", "tagId":"parentTagId"})
            .filter(pl.col("parentTagName").is_in(tags_filtro))
        )
        logger.info(f"Éxito: Se obtuvieron {df_tags_transformado.height} tags.")
        return df_tags_transformado
    except Exception as e:
        logger.error(f"Error en la transformación de tags: {e}")
        return None
def unir_tags_scores(df_scores, df_tags):
    """
    Une el nombre del tag padre al DataFrame maestro usando el ID del padre.
    """

    # Unión (Join) y Limpieza en un solo flujo
    df_unificado = (
        df_scores
        .with_columns([
            pl.col("parentTagId").cast(pl.Utf8)
        ])
        .join(
            df_tags.with_columns(pl.col("parentTagId").cast(pl.Utf8)),
            left_on="parentTagId",
            right_on="parentTagId",
            how="right"
        )

    )

    logger.info(f"Éxito: Columna 'nameParent' agregada correctamente.")
    return df_unificado
# ===========================
# Vehiculs con Etiqueta
#==========================
@retry_api(max_attempts=3, delay=10)
def extraer_vehiculos(headers, url_operadores):
    """
    Obtiene y limpia la lista de operadores desde la API de Samsara
    usando Polars y manejo de paginación robusto.
    """
    all_events = []
    params = {}

    # 1. Fase de Extracción (Ingesta de datos)
    while True:
        response = requests.get(url_operadores, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        events = data.get('data', [])

        if events:
          all_events.extend(events)

        # Lógica de paginación de Samsara
        pagination = data.get('pagination', {})
        if pagination.get('hasNextPage') and pagination.get('endCursor'):
            params['after'] = pagination.get('endCursor')
        else:
            break

    # 2. Fase de Transformación con Polars
    if not all_events:
        logger.warning("La lista de operadores está vacía.")
        return pl.DataFrame()

    # Convertimos a DataFrame de Polars
    df = pl.DataFrame(all_events)

    logger.info(f"Éxito: Se obtuvieron {df.height} registros activos.")
    return df
def transformacion_vehiculos(df):
    """
    Realiza la transformación de los datos de los vehiculos
    """
    if df.is_empty():
        logger.warning("La lista de vehiculos está vacía.")
        return df

    df_vehiculos_transf = (
        df
        # Filtramos los Operadores activos
        .rename({"id":"vehicleId", "name":"vehicleName"})
        # Seleccionamos las columnas Necesarias
        .select(["vehicleId", "vehicleName","tags"])
        .with_columns([
            pl.col("tags").list.get(0).struct.field("id").alias("tagId"),
            pl.col("tags").list.get(0).struct.field("name").alias("tagName"),
            pl.col("tags").list.get(0).struct.field("parentTagId").alias("parentTagId"),
        ])
        # 3. Limpieza de columnas y casteo masivo a String
        .drop(["tags"])
        .with_columns([
            pl.col(['vehicleId', 'tagId', 'parentTagId'])
            .cast(pl.Utf8)
        ])

    )
    print(f"Éxito: Vehículos transformados. Columnas: {df_vehiculos_transf.columns}")
    logger.info(f"Iniciando intento {df_vehiculos_transf.columns}")
    return df_vehiculos_transf
def unir_tags_vehiculos(df_vehiculos, df_tags, tags_filtro):
    """
    Une el nombre del tag padre al DataFrame maestro usando el ID del padre.
    """

    # Limpieza y preparación de la tabla de referencia
    df_ref_tags = (
        df_tags
       # .select(["tagId", "tagName"])
       # .rename({"tagName": "parentTagName", "tagId" : "parentTagId"}) # Truco: en Samsara los tagsPadre se encuentran tambien como tagsHijos
        .unique()
    )

    # Unión (Join) y Limpieza en un solo flujo (Method Chaining)
    df_unificado = (
        df_vehiculos
        # Aseguramos tipos consistentes para el join
        .with_columns([
            pl.col("parentTagId").cast(pl.Utf8)
        ])
        .join(
            df_ref_tags.with_columns(pl.col("parentTagId").cast(pl.Utf8)),
            left_on="parentTagId",
            right_on="parentTagId",
            how="left"
        )

        # Renombrado y eliminación de nulos residuales

        .with_columns(
            pl.col("parentTagName").fill_null("Sin Parent Tag"), # Opcional: manejar nulos
        ).filter( pl.col("parentTagName").is_in(tags_filtro))
    )

    logger.info(f"Éxito: Columna agregada correctamente.")
    return df_unificado

#===========================
# Asignaciones Usando trips
#==========================

def extraer_viajes(url, headers, list_vehicles, start_time, end_time):
    all_data_frames = []
    max_retries = 3
    retry_delay = 5  # segundos

    for i, v_id in enumerate(list_vehicles):
        success = False
        trips = []

        # --- INICIO LÓGICA DE REINTENTOS ---
        for intento in range(1, max_retries + 1):
            try:
                params = {
                    "vehicleId": v_id,
                    "startMs": start_time,
                    "endMs": end_time
                }

                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()

                trips = response.json().get("trips", [])
                print(f"{i} | ID {v_id} | Viajes: {len(trips)}")
                success = True
                break  # Salimos del bucle de reintentos si todo salió bien

            except (requests.exceptions.RequestException, Exception) as e:
                logging.warning(f"Intento {intento}/{max_retries} fallido para ID {v_id}: {e}")

                if intento < max_retries:
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Se agotaron los intentos para el vehículo {v_id}. Saltando...")
        # --- FIN LÓGICA DE REINTENTOS ---

        # Si después de los reintentos no tuvimos éxito, pasamos al siguiente vehículo
        if not success:
            continue

        if trips:
            try:
                df_temp = pl.from_dicts(trips)
                df_temp = df_temp.with_columns(
                    pl.lit(str(v_id)).alias("vehicleId")
                )

                cols_ok = ["vehicleId", "startMs", "endMs", "driverId"]

                # Procesamiento seguro de columnas
                df_temp = df_temp.select([
                    pl.col(c).cast(pl.String) for c in cols_ok if c in df_temp.columns
                ])
                all_data_frames.append(df_temp)
            except Exception as e:
                logger.error(f"Error procesando datos del vehículo {v_id}: {e}")

    if all_data_frames:
        logger.info("Consolidando datos...")
        return pl.concat(all_data_frames, how="diagonal")

    return pl.DataFrame()

def proporcion_viajes(viajes, vehicleTags):

    viajes_tipados = (viajes.select(pl.col("driverId"),
                                pl.col("vehicleId")
                        ).with_columns(
                            pl.when((pl.col("driverId") == "0"))
                            .then(0)
                            .otherwise(1)
                            .alias("indicador")
                        ).drop("driverId")
                  )

    proporcion_viajes_ec = viajes_tipados.join(
                                vehicleTags,
                                left_on="vehicleId",
                                right_on="vehicleId",
                                how="left"
                                ).group_by("parentTagName").agg(
                                    pl.col("indicador").sum().alias("viajesAsignados"),
                                    pl.len().alias("totalViajes"),
                                    (pl.col("indicador").sum()/pl.len()).alias("proporcionAsignados")
                                )
    return proporcion_viajes_ec
def unir_metricas_ec(proporcion_viajes, metricas, end_time):
  fecha_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
  # Para extraer las metricas pasamos directamente el parantTag como un tag, por el id derecho es tagName, pero en izquierdo si lo tenemos con el nombre de parentTagName
  metricas_finales = (proporcion_viajes.
                      join(metricas, left_on="parentTagName", right_on="parentTagName", how="right")
                      .with_columns(
    # Usamos el objeto ya procesado y restamos las 6 horas
                                    fecha_corte = pl.lit(fecha_dt) - timedelta(hours=6)
                                    )
                      )

  return metricas_finales


def pipeline ():  
  start_time, end_time = fecha_z_automatica()
  url = API_URLS["tags_scores"]
  scoreType = "vehicle"
  scores = extraer_score_tags(url, headers, scoreType, start_time, end_time)
  df_score_transformado = transformacion_scores(scores)
  df_score_transformado.tail()
  url = API_URLS["tags"]
  tags = extraer_tags_samsara(headers, url)
  filtro = tags_filtro
  tags_transformado = transformacion_tags(df_tags=tags, tags_filtro=filtro)
  tags_transformado.head()
  tags_scores = unir_tags_scores(df_score_transformado, tags_transformado)
  url_metadata = API_URLS["vehicles"]
  df = extraer_vehiculos(headers=headers, url_operadores=url_metadata)
  df.head()
  df_vehiculos_transformado = transformacion_vehiculos(df = df)
  df_vehiculos_transformado.head()
  df_vehicle_tags = unir_tags_vehiculos(df_vehiculos=df_vehiculos_transformado, df_tags=tags_transformado, tags_filtro=tags_filtro)
  (df_vehicle_tags.head())
  list_vehicles =  df_vehicle_tags["vehicleId"].to_list()
  start_timeM, end_timeM = fecha_milisegundos()
  url = API_URLS["trips"]
  datos = extraer_viajes(url, headers, list_vehicles, start_timeM, end_timeM)
  proporcionViajes = proporcion_viajes(datos, df_vehicle_tags)
  df_final = unir_metricas_ec(proporcionViajes, tags_scores, end_time)
  logger.info(df_final.glimpse())

  return df_final


def pipeline_manual (dia_i, mes_i, ano_i, dia_f, mes_f, ano_f):  
  start_time, end_time = fecha_z_manual(dia_i, mes_i, ano_i, dia_f, mes_f, ano_f)
  url = API_URLS["tags_scores"]
  scoreType = "vehicle"
  scores = extraer_score_tags(url, headers, scoreType, start_time, end_time)
  df_score_transformado = transformacion_scores(scores)
  df_score_transformado.tail()
  url = API_URLS["tags"]
  tags = extraer_tags_samsara(headers, url)
  filtro = tags_filtro
  tags_transformado = transformacion_tags(df_tags=tags, tags_filtro=filtro)
  tags_transformado.head()
  tags_scores = unir_tags_scores(df_score_transformado, tags_transformado)
  url_metadata =API_URLS["vehicles"]
  df = extraer_vehiculos(headers=headers, url_operadores=url_metadata)
  df.head()
  df_vehiculos_transformado = transformacion_vehiculos(df = df)
  df_vehiculos_transformado.head()
  df_vehicle_tags = unir_tags_vehiculos(df_vehiculos=df_vehiculos_transformado, df_tags=tags_transformado, tags_filtro=tags_filtro)
  (df_vehicle_tags.head())
  list_vehicles =  df_vehicle_tags["vehicleId"].to_list()
  start_timeM, end_timeM = fecha_milisegundos_manual(dia_i, mes_i, ano_i, dia_f, mes_f, ano_f)
  url =  API_URLS["trips"]
  datos = extraer_viajes(url, headers, list_vehicles, start_timeM, end_timeM)
  proporcionViajes = proporcion_viajes(datos, df_vehicle_tags)
  df_final = unir_metricas_ec(proporcionViajes, tags_scores, end_time)
  df_final.glimpse()

  return df_final