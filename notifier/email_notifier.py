from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


def send_email(subject: str, body: str, logger) -> None:
    host = os.getenv("EMAIL_HOST")
    port = os.getenv("EMAIL_PORT")
    username = os.getenv("EMAIL_USERNAME")
    password = os.getenv("EMAIL_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if not all([host, port, username, password, email_to]):
        logger.warning("Email disabled or missing SMTP environment variables.")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = email_to

    with smtplib.SMTP(host, int(port), timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(username, [email_to], msg.as_string())

    logger.info("Email notification sent.")
