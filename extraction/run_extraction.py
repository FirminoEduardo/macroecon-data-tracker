import sys
import os
from datetime import date, timedelta

# Permite importar os módulos da pasta extraction
sys.path.insert(0, os.path.dirname(__file__))

from extract_yfinance import extract_yfinance, save_to_json as save_yfinance
from extract_gdelt import extract_gdelt, save_to_json as save_gdelt


def run(target_date: date = None):
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    print(f'=== Iniciando extração para {target_date} ===\n')
    resultados = {}

    # --- yfinance ---
    dados_yfinance = extract_yfinance(target_date)
    if dados_yfinance:
        save_yfinance(dados_yfinance, target_date)
        resultados['yfinance'] = 'sucesso'
    else:
        resultados['yfinance'] = 'sem dado (fim de semana ou feriado)'

    print()

    # --- GDELT ---
    dados_gdelt = extract_gdelt(target_date)
    if dados_gdelt:
        save_gdelt(dados_gdelt, target_date)
        resultados['gdelt'] = 'sucesso'
    else:
        resultados['gdelt'] = 'falha'

    print(f'\n=== Resultado da extração ===')
    for fonte, status in resultados.items():
        print(f'  {fonte}: {status}')

    # Retorna False se alguma fonte falhou — útil para o ADF detectar erro
    return all(s == 'sucesso' or 'fim de semana' in s for s in resultados.values())


if __name__ == '__main__':
    sucesso = run()
    sys.exit(0 if sucesso else 1)