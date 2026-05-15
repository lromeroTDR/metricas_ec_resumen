import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

# Obtener el token de la variable de entorno
token = os.getenv("SAMSARA_TOKEN")

# Headers 
headers = {
    "accept": "application/json",
    "authorization": f"Bearer {token}"
}

#BD Config

# -*- coding: utf-8 -*-
DB_CONFIG = {
    "server": os.getenv("DB_SERVER"),
    "database": os.getenv("DB_DATABASE"),
    "schema": os.getenv("DB_SCHEMA"),
    "table": os.getenv("DB_TABLE"),
    "user": os.getenv("DB_USER"),
    "pass": os.getenv("DB_PASS")
}

API_URLS = {
    "tags_scores": os.getenv("URL_TAGS_SCORES"),
    "tags": os.getenv("URL_TAGS"),
    "vehicles": os.getenv("URL_VEHICLES"),
    "trips": os.getenv("URL_TRIPS")
}

tags_filtro = ["EC-01", "EC-02","EC-03", "EC-05","EC-08", "EC-10"]