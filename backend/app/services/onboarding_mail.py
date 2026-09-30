"""Durable mail worker: python -m app.services.onboarding_mail."""

import asyncio
import json
import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.db.session import SessionLocal, close_db
from app.models.onboarding import OnboardingApplication, OnboardingMail
from app.services.onboarding import aware, mail_cipher, now

logger = logging.getLogger(__name__)


def send_email(payload: dict) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = payload["to"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])
    context = ssl.create_default_context()
    if settings.SMTP_SSL:
        client = smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context
        )
    else:
        client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
    with client:
        if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
            client.starttls(context=context)
        if settings.SMTP_USERNAME:
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        client.send_message(message)


async def deliver_one(session) -> bool:
    if not settings.SMTP_HOST:
        return False
    mail = await session.scalar(
        select(OnboardingMail)
        .where(OnboardingMail.status == "PENDING", OnboardingMail.available_at <= now())
        .order_by(OnboardingMail.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if mail is None:
        return False
    try:
        payload = json.loads(mail_cipher().decrypt(mail.encrypted_payload.encode()))
        application = await session.get(OnboardingApplication, mail.application_id)
        stale = application.status == "COMPLETED" or (
            mail.kind == "OTP"
            and (
                application.status != "PENDING_EMAIL_VERIFICATION"
                or application.otp_hash != payload.get("otp_hash")
                or not application.otp_expires_at
                or aware(application.otp_expires_at) <= now()
            )
        )
        if stale:
            mail.status = "CANCELLED"
            mail.encrypted_payload = None
        else:
            await run_in_threadpool(send_email, payload)
            mail.status = "SENT"
            mail.sent_at = now()
            mail.last_error = None
            mail.encrypted_payload = None
    except Exception as exc:
        # Only exception class is retained: SMTP exceptions may contain recipient data.
        mail.attempts += 1
        mail.last_error = type(exc).__name__
        mail.available_at = now() + timedelta(seconds=min(30 * 2**mail.attempts, 300))
        if mail.attempts >= 6:
            mail.status = "FAILED"
            mail.encrypted_payload = None
    await session.commit()
    return True


async def main():
    settings.assert_safe_for_production()
    logging.basicConfig(level=logging.INFO)
    if not settings.SMTP_HOST:
        logger.warning("SMTP_HOST is unset. Configure SMTP before starting the mail worker.")
        return
    try:
        while True:
            try:
                async with SessionLocal() as session:
                    delivered = await deliver_one(session)
                if not delivered:
                    await asyncio.sleep(3)
            except Exception:
                logger.exception("Mail worker iteration failed")
                await asyncio.sleep(5)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
