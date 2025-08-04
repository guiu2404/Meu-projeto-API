from fastapi import FastAPI
import yfinance as yf
import numpy as np
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="API Mercado Financeiro",
    description="Retorna Volatilidade Implícita (NDX, SPX) e Ajuste Diário Oficial CME (NQ, ES).",
    version="1.0"
)

def calcular_iv(ticker):
    """
    Calcula a volatilidade implícita média estimada
    usando as opções do Yahoo Finance.
    """
    ativo = yf.Ticker(ticker)
    expiracoes = ativo.options
    if not expiracoes:
        return None
    primeira_expiracao = expiracoes[0]
    calls = ativo.option_chain(primeira_expiracao).calls
    if "impliedVolatility" in calls.columns:
        return round(np.mean(calls["impliedVolatility"]), 4)
    return None

def pegar_settlement_cme(codigo):
    """
    Busca o Ajuste Diário (Settlement Price) diretamente do site da CME.
    """
    url = f"https://www.cmegroup.com/market-data/daily-settlements.html?code={codigo}"
    with httpx.Client(timeout=10) as client:
        r = client.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    tabela = soup.find("table")
    if not tabela:
        return None

    linhas = tabela.find_all("tr")
    for linha in linhas:
        colunas = [c.get_text(strip=True) for c in linha.find_all("td")]
        if colunas and len(colunas) >= 5:
            try:
                return float(colunas[4].replace(",", ""))
            except:
                continue
    return None

@app.get("/dados", summary="Retorna dados de volatilidade e ajuste diário")
def get_dados():
    """
    Este endpoint retorna:
    - Volatilidade implícita estimada para os índices NDX e SPX.
    - Ajuste diário oficial da CME para os futuros NQ e ES.
    """

    # Volatilidade implícita (NDX e SPX)
    ndx_iv = calcular_iv("^NDX")
    spx_iv = calcular_iv("^GSPC")

    # Ajuste diário (NQ e ES) via CME
    nq_settle = pegar_settlement_cme("NQ")
    es_settle = pegar_settlement_cme("ES")

    return {
        "ativos_spot": {
            "NDX": {"volatilidade_implícita_estim": ndx_iv},
            "SPX": {"volatilidade_implícita_estim": spx_iv}
        },
        "futuros_cme": {
            "NQ": {"ajuste_diário": nq_settle},
            "ES": {"ajuste_diário": es_settle}
        }
    }
