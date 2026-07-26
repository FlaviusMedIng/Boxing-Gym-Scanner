from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email(subject: str, body: str, logger, attachment_path: str | None = None) -> None:
    host = os.getenv("EMAIL_HOST")
    port = os.getenv("EMAIL_PORT")
    username = os.getenv("EMAIL_USERNAME")
    password = os.getenv("EMAIL_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if not all([host, port, username, password, email_to]):
        logger.warning("Email disabled or missing SMTP environment variables.")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = email_to
    msg.set_content(body)

    if attachment_path:
        path = Path(attachment_path)
        if path.is_file():
            msg.add_attachment(
                path.read_bytes(),
                maintype="text",
                subtype="html",
                filename=path.name,
            )
        else:
            logger.warning("Email attachment not found: %s", attachment_path)

    with smtplib.SMTP(host, int(port), timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)

    logger.info("Email notification sent.")
