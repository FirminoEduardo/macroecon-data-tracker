import requests
import json
import os
import time
from datetime import date, timedelta

GDELT_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'
OUTPUT_DIR = 'data/raw/gdelt'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def extract_gdelt(target_date: date = None) -> dict:
    """
    Busca o Tone Score médio do GDELT para um dia específico.
    Por padrão, busca o dia anterior (ontem).
    Agrega os valores horários em uma média diária.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    # Formata o timespan para cobrir exatamente o dia alvo
    # GDELT aceita timespan em horas — buscamos 24h
    params = {
        'query': 'Middle East conflict geopolitical tension',
        'mode': 'timelinetone',
        'timespan': '24h',
        'format': 'json'
    }

    print(f'[gdelt] Buscando Tone Score para {target_date}...')

    for tentativa in range(3):
        time.sleep(6)  # Respeita rate limit de 1 req/5s
        response = requests.get(GDELT_URL, params=params, headers=HEADERS)

        if response.status_code == 200:
            break
        elif response.status_code == 429:
            espera = 30 * (tentativa + 1)
            print(f'[gdelt] Rate limit atingido. Aguardando {espera}s (tentativa {tentativa + 1}/3)...')
            time.sleep(espera)
        else:
            print(f'[gdelt] Erro inesperado: {response.status_code}')
            return None

    if response.status_code != 200:
        print(f'[gdelt] Falha após 3 tentativas.')
        return None

    raw = response.json()
    registros = raw.get('timeline', [{}])[0].get('data', [])

    if not registros:
        print(f'[gdelt] Nenhum dado retornado.')
        return None

    # Agrega valores horários em média diária
    valores = [r['value'] for r in registros if r.get('value') is not None]
    tone_medio = round(sum(valores) / len(valores), 4)

    resultado = {
        'fonte': 'gdelt',
        'query': 'Middle East conflict geopolitical tension',
        'data': str(target_date),
        'tone_score_medio': tone_medio,
        'total_registros_horarios': len(valores)
    }

    print(f'[gdelt] {target_date} → Tone Score médio: {tone_medio}')
    return resultado


def save_to_json(data: dict, target_date: date) -> str:
    """Salva o resultado em JSON particionado por data."""
    folder = os.path.join(
        OUTPUT_DIR,
        str(target_date.year),
        str(target_date.month).zfill(2),
        str(target_date.day).zfill(2)
    )
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, 'tone.json')
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f'[gdelt] Salvo em: {filepath}')
    return filepath


if __name__ == '__main__':
    target = date.today() - timedelta(days=1)
    dados = extract_gdelt(target)

    if dados:
        save_to_json(dados, target)
    else:
        print('[gdelt] Nenhum dado para salvar.')