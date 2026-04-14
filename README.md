# AgroBot — Inteligencia de Mercado para o Produtor Rural

Chatbot de IA no Telegram que fornece dados reais de exportacoes agro, cambio e clima para produtores rurais brasileiros.

Desenvolvido como desafio tecnico para o processo seletivo da **Rural Data**.

---

## Funcionalidades

| # | Funcao | Fonte de dados | Descricao |
|---|--------|---------------|-----------|
| 1 | Consulta de exportacoes | ComexStat/MDIC | Volume (toneladas) e valor FOB (USD) de soja, milho e carne bovina por ano |
| 2 | Cotacao do dolar | AwesomeAPI | USD/BRL em tempo real — compra, venda, maxima e minima do dia |
| 3 | Previsao do tempo | Open-Meteo | Previsao de 5 dias para qualquer cidade brasileira |
| 4 | Historico de conversa | — | Ultimos 8 turnos mantidos em memoria para conversa natural |
| 5 | Onboarding /start | — | Apresenta o bot e lista exemplos de uso |
| 6 | Cache inteligente | — | TTL por tool: cambio = tempo real, clima = 1h, exportacoes = 24h |

---

## Arquitetura

```
Usuario (Telegram)
       |
       v
  bot/handler.py        # recebe mensagem, gerencia historico
       |
       v
  agent/graph.py         # LangGraph ReAct agent (GPT-4o-mini)
       |
       v
  agent/tools.py         # 3 tools com cache embutido
       |
       v
  APIs publicas          # ComexStat, AwesomeAPI, Open-Meteo
```

O LLM **nao inventa dados** — ele atua apenas como interface de conversa e roteador de tools. Todos os numeros vem das APIs.

---

## Como rodar

### Pre-requisitos

- Python 3.11+
- Chave da OpenAI API
- Token de bot do Telegram (crie via [@BotFather](https://t.me/BotFather))

### Passo a passo

```bash
# 1. Clone o repositorio
git clone https://github.com/Mateus-Nery/rural-data-challenge.git
cd rural-data-challenge

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. Instale as dependencias
pip install -r requirements.txt

# 4. Configure as variaveis de ambiente
cp .env.example .env
# Edite .env com suas chaves:
#   OPENAI_API_KEY=sk-...
#   TELEGRAM_BOT_TOKEN=123456:ABC...

# 5. Rode o bot
python main.py
```

O bot inicia em modo **polling** — sem necessidade de servidor publico, webhook ou ngrok.

---

## Exemplos de uso

| Voce pergunta | O bot responde |
|---------------|----------------|
| "Quanto o Brasil exportou de soja em 2024?" | Volume em toneladas e valor FOB em USD, fonte ComexStat |
| "E o dolar, como ta?" | Cotacao de compra/venda, maxima/minima do dia |
| "Previsao do tempo em Goiania" | Proximos 5 dias com temperatura e precipitacao |
| "Compara exportacao de milho 2023 e 2024" | Duas consultas sequenciais com comparativo |

---

## Estrutura do projeto

```
rural-data-challenge/
├── agent/
│   ├── __init__.py
│   ├── graph.py          # LangGraph ReAct agent + system prompt
│   └── tools.py          # 3 tools com cache (ComexStat, AwesomeAPI, Open-Meteo)
├── bot/
│   ├── __init__.py
│   └── handler.py        # handlers do Telegram + historico de conversa
├── main.py               # entrypoint
├── .env.example           # template de variaveis de ambiente
├── requirements.txt
└── README.md
```

---

## Decisoes tecnicas

| Decisao | Justificativa |
|---------|---------------|
| **Telegram em vez de WhatsApp** | Pragmatismo para demo local — sem necessidade de servidor publico ou conta Business. A arquitetura de tools e desacoplada do canal e pode ser portada para WhatsApp via Evolution API ou Twilio com mudancas apenas no modulo `bot/`. |
| **Polling em vez de webhook** | Elimina necessidade de IP publico, certificado SSL ou ngrok. Ideal para desenvolvimento e demonstracao. |
| **GPT-4o-mini** | Suficiente para roteamento de tools e formatacao de resposta. Mais rapido e economico que GPT-4o. |
| **Cache em memoria (dict + TTL)** | Sem dependencias externas (Redis, etc). TTL diferente por tool porque a frequencia de atualizacao de cada dado e diferente: cambio muda a cada segundo, clima a cada hora, exportacoes uma vez por dia. |
| **Historico limitado a 8 turnos** | Evita estourar o contexto do LLM em conversas longas sem perder fluidez. |
| **Sem preco de commodity direto** | Nao existe API publica e confiavel com preco de soja/milho/boi gordo em BRL. A estrategia foi usar dados de exportacao (volume + valor FOB) do ComexStat como proxy de demanda de mercado, combinado com cambio em tempo real. |
| **handler.py (nome agnostico)** | O modulo do bot nao se chama `telegram.py` — usa nome generico para explicitar que o canal de mensageria e intercambiavel. |

---

## APIs utilizadas

Todas publicas, sem chave de acesso, sem cadastro.

| API | Endpoint | Dado |
|-----|----------|------|
| [ComexStat (MDIC)](https://comexstat.mdic.gov.br/) | `POST https://api-comexstat.mdic.gov.br/general` | Exportacoes brasileiras por NCM |
| [AwesomeAPI](https://docs.awesomeapi.com.br/) | `GET https://economia.awesomeapi.com.br/json/last/USD-BRL` | Cotacao USD/BRL |
| [Open-Meteo](https://open-meteo.com/) | `GET https://api.open-meteo.com/v1/forecast` | Previsao do tempo |

---

## Uso de IA no desenvolvimento

| Etapa | Responsavel |
|-------|-------------|
| Planejamento de arquitetura e escopo | Assistido por IA (Claude) |
| Escolha das APIs e justificativas tecnicas | Assistido por IA (Claude) |
| Codigo-fonte | Assistido por IA (Claude Code) |
| Decisoes tecnicas finais, revisao e validacao | Humano (Mateus Nery Bailao) |

O uso de IA foi integral ao processo de desenvolvimento. Todas as decisoes de produto, arquitetura e escolha de APIs passaram por revisao humana. O codigo foi gerado com assistencia de IA e revisado/validado manualmente.

---

## Autor

**Mateus Nery Bailao**
- Pesquisador de IA no CEIA-UFG | BSc em IA — UFG
- GitHub: [Mateus-Nery](https://github.com/Mateus-Nery)
- Email: mnbailao@gmail.com
