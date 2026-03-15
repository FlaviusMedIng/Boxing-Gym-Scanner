from __future__ import annotations

import os
import requests


def send_telegram(message: str, logger) -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram disabled or missing TELEGRAM_TOKEN / TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": message[:4000]}, timeout=30)
    if response.ok:
        logger.info("Telegram notification sent.")
    else:
        logger.error("Telegram notification failed: %s %s", response.status_code, response.text)
