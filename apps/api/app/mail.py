import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("hotcrowd.mail")


def send_mail(to_email: str, subject: str, body: str) -> None:
    if not to_email:
        return
    if settings.email_host:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.email_from
        message["To"] = to_email
        message.set_content(body)
        with smtplib.SMTP(settings.email_host, settings.email_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.email_host_user:
                smtp.login(settings.email_host_user, settings.email_host_password)
            smtp.send_message(message)
        return
    log.warning("Open this link:\n%s", body)
    print(f"Open this link:\n{body}", flush=True)
