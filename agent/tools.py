import time
import httpx
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Cache em memoria — dict simples com TTL por chave
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}

TTL_COMEXSTAT = 86_400   # 24 h
TTL_CLIMA     = 3_600    # 1 h
# cambio: sem cache (sempre tempo real)


def _get_cached(key: str, ttl: int):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"] < ttl):
        return entry["data"]
    return None


def _set_cache(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


# ---------------------------------------------------------------------------
# Mapeamento de produtos para codigos NCM (8 digitos)
# ---------------------------------------------------------------------------
NCM_MAP: dict[str, dict] = {
    "soja": {
        "ncm": "12019000",
        "descricao": "Soja em graos (exceto para semeadura)",
    },
    "milho": {
        "ncm": "10059010",
        "descricao": "Milho em graos",
    },
    "carne bovina": {
        "ncm": "02023000",
        "descricao": "Carne bovina congelada, desossada",
    },
}

TIMEOUT = httpx.Timeout(15.0)


# ---------------------------------------------------------------------------
# Tool 1 — Exportacoes brasileiras (ComexStat / MDIC)
# ---------------------------------------------------------------------------
@tool
def consultar_exportacoes(produto: str, ano: int) -> str:
    """Consulta volume e valor FOB das exportacoes brasileiras de um produto agropecuario.

    Produtos disponiveis: soja, milho, carne bovina.
    Fonte: ComexStat/MDIC (Ministerio do Desenvolvimento, Industria e Comercio).

    Args:
        produto: Nome do produto — deve ser 'soja', 'milho' ou 'carne bovina'.
        ano: Ano da consulta (ex: 2023, 2024).
    """
    produto_lower = produto.lower().strip()
    info = NCM_MAP.get(produto_lower)
    if not info:
        disponiveis = ", ".join(NCM_MAP.keys())
        return f"Produto '{produto}' nao encontrado. Disponiveis: {disponiveis}."

    # Cache por ano — armazena lista completa; filtramos client-side por coNcm
    # (a API ComexStat nao suporta filtro server-side por NCM)
    cache_key = f"export:all:{ano}"
    lista = _get_cached(cache_key, TTL_COMEXSTAT)

    if lista is None:
        payload = {
            "flow": "export",
            "monthDetail": False,
            "period": {
                "from": f"{ano}-01",
                "to": f"{ano}-12",
            },
            "filters": [],
            "details": ["ncm"],
            "metrics": ["metricFOB", "metricKG"],
        }

        try:
            resp = httpx.post(
                "https://api-comexstat.mdic.gov.br/general",
                json=payload,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            lista = resp.json().get("data", {}).get("list", [])
            _set_cache(cache_key, lista)
        except httpx.HTTPStatusError as e:
            return (
                f"Erro ao consultar ComexStat (HTTP {e.response.status_code}). "
                "A API pode estar temporariamente indisponivel. Tente novamente mais tarde."
            )
        except (httpx.RequestError, httpx.TimeoutException):
            return (
                "Nao foi possivel conectar a API ComexStat. "
                "Verifique sua conexao ou tente novamente em alguns minutos."
            )

    try:
        registros = [r for r in lista if r.get("coNcm") == info["ncm"]]

        if not registros:
            return (
                f"Nenhum dado de exportacao encontrado para {info['descricao']} em {ano}. "
                "Isso pode significar que os dados ainda nao foram publicados para esse periodo."
            )

        fob_total = sum(float(r.get("metricFOB", 0)) for r in registros)
        kg_total = sum(float(r.get("metricKG", 0)) for r in registros)
        toneladas = kg_total / 1_000

        return (
            f"Exportacoes de {info['descricao']} — {ano}:\n"
            f"- Volume: {toneladas:,.0f} toneladas\n"
            f"- Valor FOB: US$ {fob_total:,.0f}\n"
            f"Fonte: ComexStat/MDIC"
        )

    except (KeyError, TypeError, ValueError) as e:
        return (
            f"Dados recebidos do ComexStat, mas houve erro ao processar a resposta ({e}). "
            "Tente novamente ou consulte outro periodo."
        )


# ---------------------------------------------------------------------------
# Tool 2 — Cotacao do dolar (AwesomeAPI)
# ---------------------------------------------------------------------------
@tool
def consultar_cambio() -> str:
    """Consulta a cotacao atual do dolar americano (USD) em relacao ao real brasileiro (BRL).

    Fonte: AwesomeAPI — dados em tempo real, sem cache.
    """
    try:
        resp = httpx.get(
            "https://economia.awesomeapi.com.br/json/last/USD-BRL",
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.RequestError, httpx.TimeoutException):
        return (
            "Nao foi possivel consultar a cotacao do dolar. "
            "Verifique sua conexao ou tente novamente."
        )
    except httpx.HTTPStatusError as e:
        return f"Erro ao consultar AwesomeAPI (HTTP {e.response.status_code})."

    try:
        usd = data["USDBRL"]
        bid = float(usd["bid"])
        ask = float(usd["ask"])
        high = float(usd["high"])
        low = float(usd["low"])
        timestamp = usd.get("create_date", "N/A")

        return (
            f"Cotacao USD/BRL (tempo real):\n"
            f"- Compra: R$ {bid:.4f}\n"
            f"- Venda: R$ {ask:.4f}\n"
            f"- Maxima do dia: R$ {high:.4f}\n"
            f"- Minima do dia: R$ {low:.4f}\n"
            f"- Atualizado em: {timestamp}\n"
            f"Fonte: AwesomeAPI"
        )
    except (KeyError, TypeError, ValueError) as e:
        return f"Dados recebidos da AwesomeAPI, mas houve erro ao processar ({e})."


# ---------------------------------------------------------------------------
# Tool 3 — Previsao do tempo (Open-Meteo)
# ---------------------------------------------------------------------------
_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@tool
def previsao_tempo(cidade: str) -> str:
    """Consulta a previsao do tempo para os proximos 5 dias em uma cidade brasileira.

    Fonte: Open-Meteo (geocodificacao + previsao).

    Args:
        cidade: Nome da cidade brasileira (ex: Goiania, Sao Paulo, Cuiaba, Rio Verde).
    """
    cache_key = f"clima:{cidade.lower().strip()}"
    cached = _get_cached(cache_key, TTL_CLIMA)
    if cached:
        return cached

    # 1) Geocodificar cidade
    try:
        geo_resp = httpx.get(
            _GEOCODE_URL,
            params={"name": cidade, "count": 1, "language": "pt", "country": "BR"},
            timeout=TIMEOUT,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except (httpx.RequestError, httpx.TimeoutException):
        return "Nao foi possivel localizar a cidade. Verifique o nome e tente novamente."

    results = geo_data.get("results", [])
    if not results:
        return (
            f"Cidade '{cidade}' nao encontrada. "
            "Tente usar o nome completo (ex: 'Rio Verde' em vez de 'RV')."
        )

    local = results[0]
    lat = local["latitude"]
    lon = local["longitude"]
    nome = local.get("name", cidade)
    admin = local.get("admin1", "")

    # 2) Buscar previsao
    try:
        forecast_resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
                "timezone": "America/Sao_Paulo",
                "forecast_days": 5,
            },
            timeout=TIMEOUT,
        )
        forecast_resp.raise_for_status()
        forecast = forecast_resp.json()
    except (httpx.RequestError, httpx.TimeoutException):
        return "Nao foi possivel obter a previsao do tempo. Tente novamente mais tarde."

    try:
        daily = forecast["daily"]
        dates = daily["time"]
        t_max = daily["temperature_2m_max"]
        t_min = daily["temperature_2m_min"]
        precip = daily["precipitation_sum"]
        codes = daily.get("weathercode", [None] * len(dates))

        lines = [f"Previsao do tempo — {nome}, {admin}:\n"]
        for i, date in enumerate(dates):
            weather_emoji = _weather_emoji(codes[i])
            lines.append(
                f"  {date}: {weather_emoji} "
                f"{t_min[i]:.0f}°C / {t_max[i]:.0f}°C, "
                f"chuva {precip[i]:.1f} mm"
            )
        lines.append("\nFonte: Open-Meteo")

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return result

    except (KeyError, TypeError, IndexError) as e:
        return f"Dados de previsao recebidos, mas houve erro ao processar ({e})."


def _weather_emoji(code) -> str:
    """Converte WMO weather code em emoji."""
    if code is None:
        return ""
    if code == 0:
        return "☀️"
    if code in (1, 2, 3):
        return "⛅"
    if code in (45, 48):
        return "🌫️"
    if code in (51, 53, 55, 56, 57):
        return "🌦️"
    if code in (61, 63, 65, 66, 67):
        return "🌧️"
    if code in (71, 73, 75, 77):
        return "❄️"
    if code in (80, 81, 82):
        return "🌧️"
    if code in (95, 96, 99):
        return "⛈️"
    return "🌤️"
