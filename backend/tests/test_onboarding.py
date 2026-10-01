"""Onboarding API tests use isolated storage, mail delivery, and a disposable database."""

import json
import re
from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.api.v1.endpoints import onboarding as endpoints
from app.core.config import Settings, settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.identity import Role, User
from app.models.onboarding import OnboardingApplication, OnboardingDocument, OnboardingMail
from app.models.partner import Country, Partner, PartnerType
from app.services import onboarding as flow
from app.services import onboarding_mail as mailer

PASSWORD = "Onboarding-test-password-123"
PDF = b"%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF"
NUMBERS = {"COMPANY_LICENSE": "COMPANY-123", "PAN": "ABCDE1234F", "GSTIN": "27ABCDE1234F1Z5"}


@compiles(JSONB, "sqlite")
def sqlite_json(element, compiler, **kw):
    return "JSON"


@pytest.fixture
async def onboarding(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enforce_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids = {}
    async with factory() as session:
        roles = {
            code: Role(code=code, name=code, permissions=[])
            for code in ["TCG_ADMIN", "TCG_LEGAL", "TCG_SALES", "PARTNER_ADMIN"]
        }
        session.add_all(list(roles.values()))
        session.add(Country(code="IN", name="India"))
        session.add_all(
            [
                PartnerType(code=code, name=code)
                for code in ["RESELLER", "REFERRAL", "SYSTEM_INTEGRATOR"]
            ]
        )
        for name, role in [
            ("admin", "TCG_ADMIN"),
            ("legal", "TCG_LEGAL"),
            ("other_legal", "TCG_LEGAL"),
            ("sales", "TCG_SALES"),
        ]:
            user = User(
                email=name + "@example.com",
                full_name=name,
                roles=[roles[role]],
                hashed_password=hash_password(PASSWORD),
                is_active=True,
            )
            session.add(user)
            await session.flush()
            ids[name] = user.id
        await session.commit()

    async def database():
        async with factory() as session:
            yield session

    objects = {}
    monkeypatch.setattr(
        endpoints, "put_private_object", lambda key, data, content: objects.update({key: data})
    )
    monkeypatch.setattr(
        endpoints, "presigned_download_url", lambda key, filename: "https://private.example/" + key
    )
    monkeypatch.setattr(flow, "scan_file", lambda data: "CLEAN")
    app.dependency_overrides[get_db] = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client, factory, ids, objects
    app.dependency_overrides.clear()
    await engine.dispose()


def auth(ids, role):
    return {"Authorization": "Bearer " + create_access_token(str(ids[role]))}


def payload(email="applicant@example.com", capabilities=None):
    return {
        "company_name": "Example Company",
        "company_email": "company@example.com",
        "capability_codes": capabilities or ["RESELLER"],
        "country_codes": ["IN"],
        "primary_contact_name": "Applicant User",
        "primary_contact_email": email,
        "password": PASSWORD,
    }


async def draft(client, **kwargs):
    result = await client.post("/onboarding/applications", json=payload(**kwargs))
    assert result.status_code == 201, result.text
    data = result.json()
    return data["application"], {"X-Application-Token": data["token"]}


async def upload_all(client, headers):
    for kind, number in NUMBERS.items():
        result = await client.post(
            "/onboarding/me/documents",
            headers=headers,
            data={"kind": kind, "number": number},
            files={"file": ("document.pdf", PDF, "application/pdf")},
        )
        assert result.status_code == 201, result.text
    return result.json()


async def send_for_review(client, ids, application, headers):
    application = await upload_all(client, headers)
    result = await client.post("/onboarding/me/submit", headers=headers)
    assert result.status_code == 200, result.text
    result = await client.post(
        f"/onboarding/applications/{application['id']}/assign-legal",
        json={"reviewer_id": str(ids["legal"])},
        headers=auth(ids, "admin"),
    )
    assert result.status_code == 200, result.text
    return result.json()


async def approve(client, ids, application):
    return await client.post(
        f"/onboarding/applications/{application['id']}/decision",
        json={"decision": "APPROVE", "revision": application["revision"]},
        headers=auth(ids, "legal"),
    )


async def otp(factory):
    # SQLite timestamps have second precision; choose the active challenge, not
    # whichever row happens to sort first when approval and resend share a second.
    async with factory() as session:
        mails = await session.scalars(select(OnboardingMail).where(OnboardingMail.kind == "OTP"))
        for row in mails:
            payload = json.loads(flow.mail_cipher().decrypt(row.encrypted_payload.encode()))
            application = await session.get(OnboardingApplication, row.application_id)
            if payload["otp_hash"] == application.otp_hash:
                return re.search(r"code is (\d{6})", payload["body"]).group(1)
    raise AssertionError("No active OTP email")


async def test_required_documents_and_file_validation(onboarding):
    client, factory, ids, objects = onboarding
    application, headers = await draft(client, capabilities=["SYSTEM_INTEGRATOR", "REFERRAL"])
    assert set(application["required_documents"]) == set(NUMBERS)
    assert (await client.post("/onboarding/me/submit", headers=headers)).status_code == 422
    bad = await client.post(
        "/onboarding/me/documents",
        headers=headers,
        data={"kind": "PAN", "number": NUMBERS["PAN"]},
        files={"file": ("document.pdf", b"<script>bad</script>", "application/pdf")},
    )
    assert bad.status_code == 422
    assert not objects
    bad_number = await client.post(
        "/onboarding/me/documents",
        headers=headers,
        data={"kind": "PAN", "number": "wrong"},
        files={"file": ("doc.pdf", PDF, "application/pdf")},
    )
    assert bad_number.status_code == 422
    await upload_all(client, headers)
    assert (await client.post("/onboarding/me/submit", headers=headers)).status_code == 200
    locked = await client.post(
        "/onboarding/me/documents",
        headers=headers,
        data={"kind": "PAN", "number": NUMBERS["PAN"]},
        files={"file": ("doc.pdf", PDF, "application/pdf")},
    )
    assert locked.status_code == 409


async def test_workflow_activation_and_replay(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    blocked = await client.post(
        f"/partners/{application['partner_id']}/approve", json={}, headers=auth(ids, "admin")
    )
    assert blocked.status_code == 409
    login = await client.post(
        "/auth/token", data={"username": "applicant@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401
    application = await send_for_review(client, ids, application, headers)
    result = await approve(client, ids, application)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "PENDING_EMAIL_VERIFICATION"
    assert "otp_hash" not in result.json()
    code = await otp(factory)
    async with factory() as session:
        partner = await session.get(Partner, UUID(application["partner_id"]))
        assert partner.status == "PENDING_APPROVAL"
        mails = list(await session.scalars(select(OnboardingMail)))
        assert all(code not in (mail.encrypted_payload or "") for mail in mails)
    result = await client.post("/onboarding/me/verify", json={"code": code}, headers=headers)
    assert result.status_code == 200, result.text
    assert (
        await client.post("/onboarding/me/verify", json={"code": code}, headers=headers)
    ).status_code == 401
    login = await client.post(
        "/auth/token", data={"username": "applicant@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    me = await client.get(
        "/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
    )
    assert me.status_code == 200


async def test_role_scope_and_application_tokens(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    application = await send_for_review(client, ids, application, headers)
    path = f"/onboarding/applications/{application['id']}"
    for role in ["sales", "other_legal"]:
        assert (await client.get(path, headers=auth(ids, role))).status_code == 403
        denied = await client.post(
            path + "/decision",
            headers=auth(ids, role),
            json={"decision": "APPROVE", "revision": application["revision"]},
        )
        assert denied.status_code == 403
    denied = await client.post(
        path + "/decision",
        headers=auth(ids, "admin"),
        json={"decision": "APPROVE", "revision": application["revision"]},
    )
    assert denied.status_code == 403
    doc = application["documents"][0]
    assert (
        await client.get(path + f"/documents/{doc['id']}/download", headers=auth(ids, "sales"))
    ).status_code == 403
    assert (
        await client.get(path + f"/documents/{doc['id']}/download", headers=auth(ids, "legal"))
    ).status_code == 200
    assert (
        await client.get(
            "/auth/me", headers={"Authorization": "Bearer " + headers["X-Application-Token"]}
        )
    ).status_code == 401
    assert (
        await client.get(
            "/onboarding/me",
            headers={"X-Application-Token": create_access_token(str(ids["admin"]))},
        )
    ).status_code == 401


async def test_corrections_preserve_versions_and_require_rerouting(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    application = await send_for_review(client, ids, application, headers)
    path = f"/onboarding/applications/{application['id']}"
    changed = await client.post(
        path + "/decision",
        headers=auth(ids, "legal"),
        json={
            "decision": "REQUEST_CHANGES",
            "revision": application["revision"],
            "comment": "Upload a clearer company license",
        },
    )
    assert changed.status_code == 200, changed.text
    updated = await client.post(
        "/onboarding/me/documents",
        headers=headers,
        data={"kind": "COMPANY_LICENSE", "number": "UPDATED-123"},
        files={"file": ("new.pdf", PDF, "application/pdf")},
    )
    assert updated.status_code == 201
    assert (await approve(client, ids, application)).status_code == 409
    await client.post("/onboarding/me/submit", headers=headers)
    assigned = await client.post(
        path + "/assign-legal", headers=auth(ids, "admin"), json={"reviewer_id": str(ids["legal"])}
    )
    assert assigned.status_code == 200
    assert (await approve(client, ids, application)).status_code == 409
    assert (await approve(client, ids, assigned.json())).status_code == 200
    async with factory() as session:
        docs = list(await session.scalars(select(OnboardingDocument)))
        assert len(docs) == 4


async def test_rejection_never_issues_activation(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    application = await send_for_review(client, ids, application, headers)
    result = await client.post(
        f"/onboarding/applications/{application['id']}/decision",
        headers=auth(ids, "legal"),
        json={
            "decision": "REJECT",
            "revision": application["revision"],
            "comment": "License invalid",
        },
    )
    assert result.status_code == 200
    assert (await client.post("/onboarding/me/resend", headers=headers)).status_code == 409
    async with factory() as session:
        assert (
            await session.scalar(select(OnboardingMail).where(OnboardingMail.kind == "OTP")) is None
        )


async def test_otp_limits_expiry_and_resend(onboarding, monkeypatch):
    codes = iter([123456, 654321])
    monkeypatch.setattr(flow.secrets, "randbelow", lambda limit: next(codes))
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    application = await send_for_review(client, ids, application, headers)
    await approve(client, ids, application)
    old_code = await otp(factory)
    wrong = "000000" if old_code != "000000" else "111111"
    for _ in range(5):
        assert (
            await client.post("/onboarding/me/verify", headers=headers, json={"code": wrong})
        ).status_code == 422
    assert (
        await client.post("/onboarding/me/verify", headers=headers, json={"code": old_code})
    ).status_code == 429
    assert (await client.post("/onboarding/me/resend", headers=headers)).status_code == 429
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        row.otp_sent_at = flow.now() - timedelta(minutes=2)
        await session.commit()
    assert (await client.post("/onboarding/me/resend", headers=headers)).status_code == 200
    code = await otp(factory)
    assert code != old_code
    old_result = await client.post(
        "/onboarding/me/verify", headers=headers, json={"code": old_code}
    )
    assert old_result.status_code == 422
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        assert row.otp_attempts == 1
        row.otp_expires_at = flow.now() - timedelta(seconds=1)
        await session.commit()
    assert (
        await client.post("/onboarding/me/verify", headers=headers, json={"code": code})
    ).status_code == 422


async def test_mail_failures_retry_and_old_codes_are_not_sent(onboarding, monkeypatch):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    application = await send_for_review(client, ids, application, headers)
    await approve(client, ids, application)
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")

    def fail(payload):
        raise OSError("temporary provider failure")

    monkeypatch.setattr(mailer, "send_email", fail)
    async with factory() as session:
        assert await mailer.deliver_one(session)
        row = await session.scalar(select(OnboardingMail).order_by(OnboardingMail.created_at))
        assert row.status == "PENDING" and row.attempts == 1
        assert row.last_error == "OSError"
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda payload: sent.append(payload))
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        row.otp_expires_at = flow.now() - timedelta(seconds=1)
        await session.commit()
        await mailer.deliver_one(session)
        mail = await session.scalar(select(OnboardingMail).where(OnboardingMail.kind == "OTP"))
        assert mail.status == "CANCELLED" and mail.encrypted_payload is None
    assert not sent


async def test_legacy_and_admin_paths_cannot_bypass_review(onboarding):
    client, factory, ids, _ = onboarding
    assert (await client.post("/partners/register", json=payload())).status_code == 409
    result = await client.post("/partners", json=payload(), headers=auth(ids, "admin"))
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "PENDING_APPROVAL"
    partner_id = result.json()["id"]
    assert (
        await client.post(f"/partners/{partner_id}/approve", json={}, headers=auth(ids, "admin"))
    ).status_code == 409
    assert (
        await client.post(
            f"/partners/{partner_id}/status", json={"status": "ACTIVE"}, headers=auth(ids, "admin")
        )
    ).status_code == 409
    access = await client.post(
        "/onboarding/access", json={"email": "applicant@example.com", "password": PASSWORD}
    )
    assert access.status_code == 200
    updated = await client.patch(
        f"/partners/{partner_id}",
        json={"primary_contact_email": "different@example.com"},
        headers=auth(ids, "admin"),
    )
    assert updated.status_code == 409


async def test_primary_email_and_account_gate(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        user = await session.get(User, row.applicant_id)
        user.is_active = True
        token = create_access_token(str(user.id))
        await session.commit()
    assert (
        await client.get("/auth/me", headers={"Authorization": "Bearer " + token})
    ).status_code != 200
    application = await send_for_review(client, ids, application, headers)
    result = await client.patch(
        f"/partners/{application['partner_id']}",
        headers=auth(ids, "admin"),
        json={"capability_codes": ["SYSTEM_INTEGRATOR"]},
    )
    assert result.status_code == 409


async def test_resume_rate_limit_and_legal_provisioning(onboarding):
    client, factory, ids, _ = onboarding
    for _ in range(10):
        result = await client.post(
            "/onboarding/access", json={"email": "unknown@example.com", "password": "incorrect"}
        )
        assert result.status_code == 401
    assert (
        await client.post(
            "/onboarding/access", json={"email": "unknown@example.com", "password": "incorrect"}
        )
    ).status_code == 429
    body = {"email": "newlegal@example.com", "full_name": "Legal Reviewer", "password": PASSWORD}
    assert (
        await client.post("/onboarding/reviewers", json=body, headers=auth(ids, "sales"))
    ).status_code == 403
    assert (
        await client.post("/onboarding/reviewers", json=body, headers=auth(ids, "admin"))
    ).status_code == 201


def test_upload_type_checks_and_required_scanning(monkeypatch):
    assert flow.validate_file("company.pdf", PDF) == "application/pdf"
    with pytest.raises(HTTPException):
        flow.validate_file("company.html", PDF)
    monkeypatch.setattr(settings, "CLAMAV_HOST", "")
    with pytest.raises(HTTPException) as error:
        flow.scan_file(PDF)
    assert error.value.status_code == 503
    with pytest.raises(ValueError, match="Configure CLAMAV_HOST"):
        Settings(APP_ENV="development", CLAMAV_HOST="").assert_runtime_requirements()
    Settings(APP_ENV="test", CLAMAV_HOST="").assert_runtime_requirements()


async def test_applicant_download_is_scoped_to_application(onboarding):
    client, factory, ids, _ = onboarding
    first, first_headers = await draft(client)
    first = await upload_all(client, first_headers)
    second, second_headers = await draft(client, email="second@example.com")
    doc = first["documents"][0]
    path = f"/onboarding/me/documents/{doc['id']}/download"
    assert (await client.get(path, headers=first_headers)).status_code == 200
    assert (await client.get(path, headers=second_headers)).status_code == 404


async def test_mail_success_removes_encrypted_payload(onboarding, monkeypatch):
    client, factory, ids, _ = onboarding
    await draft(client)
    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")
    monkeypatch.setattr(mailer, "send_email", lambda payload: sent.append(payload))
    async with factory() as session:
        assert await mailer.deliver_one(session)
        mail = await session.scalar(select(OnboardingMail))
        assert mail.status == "SENT"
        assert mail.encrypted_payload is None
        assert mail.sent_at is not None
    assert sent[0]["to"] == "applicant@example.com"


async def test_gstin_must_match_pan(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    await upload_all(client, headers)
    result = await client.post(
        "/onboarding/me/documents",
        headers=headers,
        data={"kind": "GSTIN", "number": "27ZZZZZ9999Z1Z5"},
        files={"file": ("gstin.pdf", PDF, "application/pdf")},
    )
    assert result.status_code == 201
    assert (await client.post("/onboarding/me/submit", headers=headers)).status_code == 422
