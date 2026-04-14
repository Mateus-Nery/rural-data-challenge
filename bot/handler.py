import logging

from langchain_core.messages import AIMessage, HumanMessage
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent.graph import create_agent

logger = logging.getLogger(__name__)

# Historico de conversa por chat — limitado a MAX_TURNS pares (human+ai)
_history: dict[int, list] = {}
MAX_TURNS = 8

# Agente singleton
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


# ---------------------------------------------------------------------------
# /start — onboarding
# ---------------------------------------------------------------------------
WELCOME_MSG = (
    "*AgroBot — Inteligencia de Mercado*\n\n"
    "Ola! Eu sou o AgroBot, seu assistente de mercado agro.\n\n"
    "Posso te ajudar com:\n"
    "  *Exportacoes* — volume e valor FOB de soja, milho e carne bovina\n"
    "  *Cambio* — cotacao do dolar em tempo real\n"
    "  *Clima* — previsao do tempo para sua cidade\n\n"
    "E so mandar sua pergunta! Exemplos:\n"
    '  _"Quanto o Brasil exportou de soja em 2024?"_\n'
    '  _"Qual o dolar agora?"_\n'
    '  _"Previsao do tempo em Goiania"_'
)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para o comando /start."""
    chat_id = update.effective_chat.id
    _history.pop(chat_id, None)  # reseta historico
    await update.message.reply_text(WELCOME_MSG, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Mensagens de texto — encaminha para o agente
# ---------------------------------------------------------------------------
MAX_TELEGRAM_LENGTH = 4096


async def handle_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Recebe mensagem do usuario, invoca o agente e responde."""
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Monta historico
    msgs = _history.setdefault(chat_id, [])
    msgs.append(HumanMessage(content=user_text))

    # Trimma para MAX_TURNS pares
    if len(msgs) > MAX_TURNS * 2:
        msgs[:] = msgs[-(MAX_TURNS * 2):]

    # Invoca agente
    try:
        agent = _get_agent()
        result = await agent.ainvoke({"messages": list(msgs)})
        ai_msg: AIMessage = result["messages"][-1]
        response_text = ai_msg.content
        msgs.append(AIMessage(content=response_text))
    except Exception:
        logger.exception("Erro ao invocar agente")
        response_text = (
            "Desculpe, ocorreu um erro ao processar sua pergunta. "
            "Tente novamente em alguns instantes."
        )

    # Envia resposta — tenta Markdown, fallback para texto puro
    for chunk in _split_message(response_text):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(chunk)


def _split_message(text: str) -> list[str]:
    """Divide mensagem longa em pedacos que cabem no Telegram."""
    if len(text) <= MAX_TELEGRAM_LENGTH:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:MAX_TELEGRAM_LENGTH])
        text = text[MAX_TELEGRAM_LENGTH:]
    return chunks


# ---------------------------------------------------------------------------
# Fabrica do bot
# ---------------------------------------------------------------------------
def create_bot(token: str) -> Application:
    """Cria e configura a Application do python-telegram-bot."""
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
