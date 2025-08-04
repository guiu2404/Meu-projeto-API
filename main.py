from fastapi import FastAPI
import yfinance as yf
import numpy as np
import httpx
from datetime import datetime, timedelta

app = FastAPI(
    title="API Mercado Financeiro",
    description="Retorna volatilidade implícita (NDX, SPX) e ajuste diário (NQ, ES) diretamente das fontes oficiais.",
    version="1.3"
)

# Cache para evitar requisições repetidas à CME
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

def pegar_settlement_cme(produto):
    """Busca o ajuste diário diretamente do endpoint JSON oficial da CME."""
    agora = datetime.utcnow()
    if produto in cache_cme and agora < cache_expira.get(produto, agora):
        return cache_cme[produto]

    url = f"https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/{produto}/G"
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

@app.get("/", summary="Página inicial")
def home():
    return {
        "mensagem": "API de Mercado Financeiro Online. Use /dados para acessar informações.",
        "documentacao": "/docs"
    }

@app.get("/dados", summary="Retorna volatilidade implícita e ajuste diário")
def get_dados():
    ndx_iv = calcular_iv("^NDX")
    spx_iv = calcular_iv("^GSPC")  # símbolo corrigido
    nq_settle = pegar_settlement_cme("NQ")  # usando JSON da CME
    es_settle = pegar_settlement_cme("ES")  # usando JSON da CME

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
