from fastapi import FastAPI
import yfinance as yf
import numpy as np
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

app = FastAPI(
    title="API Mercado Financeiro",
    description="""
API gratuita para consultar:
- Volatilidade implícita estimada (ativos à vista pelo Yahoo Finance)
- Ajuste diário oficial da CME (futuros)

Fontes:
- Volatilidade: Yahoo Finance
- Ajuste diário: CME Group
""",
    version="1.2"
)

# Cache para evitar requisições repetidas à CME
cache_ajuste = {}
cache_expira = {}

def calcular_iv(ticker):
    """Calcula a volatilidade implícita média estimada usando as opções do Yahoo Finance."""
    try:
        ativo = yf.Ticker(ticker)
        expiracoes = ativo.options
        if not expiracoes:
            return None
        primeira_expiracao = expiracoes[0]
        calls = ativo.option_chain(primeira_expiracao).calls
        if "impliedVolatility" in calls.columns:
            return round(np.mean(calls["impliedVolatility"]), 4)
    except Exception:
        return None
    return None

def pegar_settlement_cme(codigo):
    """Busca o Ajuste Diário (Settlement Price) diretamente do site da CME com cache de 24h."""
    agora = datetime.utcnow()

    if codigo in cache_ajuste and agora < cache_expira.get(codigo, agora):
        return cache_ajuste[codigo]

    url = f"https://www.cmegroup.com/market-data/daily-settlements.html?code={codigo}"
    try:
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
                    valor = float(colunas[4].replace(",", ""))
                    cache_ajuste[codigo] = valor
                    cache_expira[codigo] = agora + timedelta(hours=24)
                    return valor
                except:
                    continue
    except Exception:
        return None
    return None

@app.get("/", summary="Página inicial")
def home():
    return {
        "mensagem": "API de Mercado Financeiro Online.",
        "endpoints": {
            "dados": "/dados",
            "ativo_especifico": "/ativos/{codigo}",
            "documentacao": "/docs"
        }
    }

@app.get("/dados", summary="Retorna dados fixos de volatilidade e ajuste diário")
def get_dados():
    ndx_iv = calcular_iv("^NDX")
    spx_iv = calcular_iv("^GSPC")
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

@app.get("/ativos/{codigo}", summary="Consulta um ativo específico")
def get_ativo(codigo: str):
    """
    Consulta a volatilidade implícita (se for ativo do Yahoo Finance)
    ou o ajuste diário (se for código da CME).
    """
    if codigo.upper() in ["NQ", "ES", "YM", "RTY"]:
        ajuste = pegar_settlement_cme(codigo.upper())
        return {codigo.upper(): {"ajuste_diário": ajuste}}

    else:
        iv = calcular_iv(codigo)
        return {codigo: {"volatilidade_implícita_estim": iv}}

