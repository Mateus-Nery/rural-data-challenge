import logging
import os

from dotenv import load_dotenv

from bot.handler import create_bot


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
    )

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN nao encontrado. Crie um arquivo .env.")

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY nao encontrado. Crie um arquivo .env.")

    bot = create_bot(token)
    logging.info("AgroBot iniciado — polling ativo. Ctrl+C para parar.")
    bot.run_polling()


if __name__ == "__main__":
    main()
