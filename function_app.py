import azure.functions as func
import logging
import json
import time
import requests
import yfinance as yf
from datetime import date, timedelta
from azure.storage.blob import BlobServiceClient
import os

app = func.FunctionApp()

# Configurações
ADLS_CONNECTION_STRING = os.environ.get('ADLS_CONNECTION_STRING')
CONTAINER_BRONZE = 'bronze'
GDELT_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'
TICKER_BRENT = 'BZ=F'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def upload_to_adls(data: dict, blob_path: str):
    """Salva um dicionário como JSON no ADLS Gen2."""
    client = BlobServiceClient.from_connection_string(ADLS_CONNECTION_STRING)
    blob_client = client.get_blob_client(container=CONTAINER_BRONZE, blob=blob_path)
    blob_client.upload_blob(
        json.dumps(data, indent=2),
        overwrite=True
    )
    logging.info(f'Salvo em: {blob_path}')


def extract_yfinance(target_date: date):
    """Extrai preço de fechamento do Brent."""
    start = target_date - timedelta(days=5)
    end = target_date + timedelta(days=1)

    brent = yf.Ticker(TICKER_BRENT)
    df = brent.history(start=str(start), end=str(end))

    if df.empty:
        logging.warning(f'[yfinance] Sem dado para {target_date}')
        return None

    df.index = df.index.date

    if target_date not in df.index:
        logging.warning(f'[yfinance] Sem dado para {target_date} (fim de semana ou feriado)')
        return None

    preco = round(float(df.loc[target_date, 'Close']), 4)
    logging.info(f'[yfinance] {target_date} → USD {preco}')

    return {
        'fonte': 'yfinance',
        'ticker': TICKER_BRENT,
        'data': str(target_date),
        'preco_fechamento_usd': preco
    }


def extract_gdelt(target_date: date):
    """Extrai Tone Score médio do GDELT."""
    params = {
        'query': 'Middle East conflict geopolitical tension',
        'mode': 'timelinetone',
        'timespan': '24h',
        'format': 'json'
    }

    for tentativa in range(3):
        time.sleep(6)
        response = requests.get(GDELT_URL, params=params, headers=HEADERS)

        if response.status_code == 200:
            break
        elif response.status_code == 429:
            espera = 30 * (tentativa + 1)
            logging.warning(f'[gdelt] Rate limit. Aguardando {espera}s...')
            time.sleep(espera)
        else:
            logging.error(f'[gdelt] Erro: {response.status_code}')
            return None

    if response.status_code != 200:
        logging.error('[gdelt] Falha após 3 tentativas.')
        return None

    raw = response.json()
    registros = raw.get('timeline', [{}])[0].get('data', [])

    if not registros:
        logging.warning('[gdelt] Nenhum dado retornado.')
        return None

    valores = [r['value'] for r in registros if r.get('value') is not None]
    tone_medio = round(sum(valores) / len(valores), 4)
    logging.info(f'[gdelt] {target_date} → Tone Score médio: {tone_medio}')

    return {
        'fonte': 'gdelt',
        'query': 'Middle East conflict geopolitical tension',
        'data': str(target_date),
        'tone_score_medio': tone_medio,
        'total_registros_horarios': len(valores)
    }


@app.timer_trigger(
    schedule='0 0 1 * * *',  # Todo dia à 01:00 UTC (22:00 BRT)
    arg_name='timer',
    run_on_startup=False
)
def extraction_timer(timer: func.TimerRequest) -> None:
    """Azure Function principal — roda diariamente e extrai as duas fontes."""
    logging.info('=== Extração iniciada ===')

    target_date = date.today() - timedelta(days=1)
    ano = target_date.strftime('%Y')
    mes = target_date.strftime('%m')
    dia = target_date.strftime('%d')

    # yfinance
    dados_yfinance = extract_yfinance(target_date)
    if dados_yfinance:
        upload_to_adls(
            dados_yfinance,
            f'yfinance/{ano}/{mes}/{dia}/brent.json'
        )

    # GDELT
    dados_gdelt = extract_gdelt(target_date)
    if dados_gdelt:
        upload_to_adls(
            dados_gdelt,
            f'gdelt/{ano}/{mes}/{dia}/tone.json'
        )

    logging.info('=== Extração concluída ===')