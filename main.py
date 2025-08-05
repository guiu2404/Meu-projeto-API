from fastapi import FastAPI
import yfinance as yf
import numpy as np
import httpx
from datetime import datetime, timedelta

app = FastAPI(
    title="API Mercado Financeiro",
    description="Volatilidade implícita (NDX, SPX) e ajuste diário (NQ, ES) diretamente de fontes oficiais.",
    version="1.4"
)

# Cache para evitar requisições repetidas
cache_cme = {}
cache_expira = {}

def calcular_iv(ticker):
    """Calcula a volatilidade implícita média estimada do Yahoo Finance."""
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

def pegar_codigo_contrato(produto):
    """Busca o código do contrato ativo (front month) na CME."""
    url = f"https://www.cmegroup.com/CmeWS/mvc/Quotes/Front/{produto}/G"
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(url)
        data = r.json()
        if "contractMonth" in data:
            return data["contractMonth"]
    except Exception:
        return None
    return None

def pegar_settlement_cme(produto):
    """Busca o ajuste diário usando o código do contrato ativo."""
    agora = datetime.utcnow()
    if produto in cache_cme and agora < cache_expira.get(produto, agora):
        return cache_cme[produto]

    contrato = pegar_codigo_contrato(produto)
    if not contrato:
        return None

    url = f"https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/{produto}/{contrato}/G"
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(url)
        data = r.json()
        if "quotes" in data and len(data["quotes"]) > 0:
            settlement = data["quotes"][0].get("lastSettle", None)
            if settlement is not None:
                try:
                    settlement = float(settlement)
                except:
                    pass
                cache_cme[produto] = settlement
                cache_expira[produto] = agora + timedelta(hours=24)
                return settlement
    except Exception:
        return None
    return None

@app.get("/")
def home():
    return {
        "mensagem": "API de Mercado Financeiro Online",
        "endpoints": ["/dados", "/docs"]
    }

@app.get("/dados")
def get_dados():
    # Volatilidade NDX
    ndx_iv = calcular_iv("^NDX")

    # Volatilidade SPX (tentativa principal)
    spx_iv = calcular_iv("^GSPC")

    # Ajuste NQ e ES
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
