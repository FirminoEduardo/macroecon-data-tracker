import yfinance as yf
import json
import os
from datetime import date, timedelta

TICKER_BRENT = 'BZ=F'
OUTPUT_DIR = 'data/raw/yfinance'


def extract_yfinance(target_date: date = None) -> dict:
    """
    Busca o preço de fechamento do Brent para um dia específico.
    Por padrão, busca o dia anterior (ontem).
    Retorna um dicionário com os dados ou None se não houver dado (fim de semana).
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    # yfinance precisa de um intervalo — buscamos 5 dias e filtramos o alvo
    start = target_date - timedelta(days=5)
    end = target_date + timedelta(days=1)

    brent = yf.Ticker(TICKER_BRENT)
    df = brent.history(start=str(start), end=str(end))

    if df.empty:
        print(f'[yfinance] Nenhum dado retornado para {target_date}')
        return None

    # Normalizar índice removendo timezone
    df.index = df.index.date

    if target_date not in df.index:
        print(f'[yfinance] Sem dado para {target_date} (provável fim de semana ou feriado)')
        return None

    preco = round(float(df.loc[target_date, 'Close']), 4)

    resultado = {
        'fonte': 'yfinance',
        'ticker': TICKER_BRENT,
        'data': str(target_date),
        'preco_fechamento_usd': preco
    }

    print(f'[yfinance] {target_date} → USD {preco}')
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

    filepath = os.path.join(folder, 'brent.json')
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f'[yfinance] Salvo em: {filepath}')
    return filepath


if __name__ == '__main__':
    target = date.today() - timedelta(days=1)
    dados = extract_yfinance(target)

    if dados:
        save_to_json(dados, target)
    else:
        print('[yfinance] Nenhum dado para salvar.')