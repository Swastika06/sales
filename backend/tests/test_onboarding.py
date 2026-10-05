"""Onboarding API tests use isolated storage, mail delivery, and a disposable database."""

import json
import re
from datetime import timedelta
from uuid import UUID, uuid4

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
from app.models.partner import Country, PartnerType
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
            for code in ["TCG_ADMIN", "TCG_LEGAL", "TCG_SALES", "TCG_FINANCE", "PARTNER_ADMIN"]
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


async def emailed_password(factory, application_id, kind):
    async with factory() as session:
        mail = await session.scalar(
            select(OnboardingMail).where(
                OnboardingMail.application_id == UUID(application_id), OnboardingMail.kind == kind
            )
        )
        data = json.loads(flow.mail_cipher().decrypt(mail.encrypted_payload.encode()))
        assert "#token=" not in data["body"]
        password = re.search(r"password: ([^\s]+)", data["body"]).group(1)
        assert password not in mail.encrypted_payload
        return password


async def test_workflow_activation_and_replay(onboarding):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    password = await emailed_password(factory, application["id"], "ONBOARDING_PASSWORD")
    access = await client.post(
        "/onboarding/access", json={"email": "applicant@example.com", "password": password}
    )
    assert access.status_code == 200
    assert (
        await client.post(
            "/onboarding/access", json={"email": "applicant@example.com", "password": PASSWORD}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/auth/token", data={"username": "applicant@example.com", "password": password}
        )
    ).status_code == 401
    blocked = await client.post(
        f"/partners/{application['partner_id']}/approve", json={}, headers=auth(ids, "admin")
    )
    assert blocked.status_code == 409
    application = await send_for_review(client, ids, application, headers)
    result = await approve(client, ids, application)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "COMPLETED"
    assert "access_password_hash" not in result.json()
    assert (await client.get("/onboarding/me", headers=headers)).status_code == 401
    assert (
        await client.post(
            "/onboarding/access", json={"email": "applicant@example.com", "password": password}
        )
    ).status_code == 401
    temporary = await emailed_password(factory, application["id"], "PARTNER_PASSWORD")
    assert temporary != password
    login = await client.post(
        "/auth/token", data={"username": "applicant@example.com", "password": temporary}
    )
    assert login.status_code == 200, login.text
    restricted = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (await client.get("/auth/me", headers=restricted)).json()["must_change_password"]
    assert (await client.get("/partners", headers=restricted)).status_code == 403
    wrong = await client.post(
        "/auth/change-password",
        headers=restricted,
        json={"current_password": "wrong", "new_password": PASSWORD},
    )
    assert wrong.status_code == 401
    same = await client.post(
        "/auth/change-password",
        headers=restricted,
        json={"current_password": temporary, "new_password": temporary},
    )
    assert same.status_code == 422
    short = await client.post(
        "/auth/change-password",
        headers=restricted,
        json={"current_password": temporary, "new_password": "short"},
    )
    assert short.status_code == 422
    changed = await client.post(
        "/auth/change-password",
        headers=restricted,
        json={"current_password": temporary, "new_password": PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    full = {"Authorization": "Bearer " + changed.json()["access_token"]}
    assert not (await client.get("/auth/me", headers=full)).json()["must_change_password"]
    assert (await client.get("/auth/me", headers=restricted)).status_code == 401
    assert (
        await client.post(
            "/auth/token", data={"username": "applicant@example.com", "password": temporary}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/auth/token", data={"username": "applicant@example.com", "password": PASSWORD}
        )
    ).status_code == 200


async def test_onboarding_password_expiry_and_no_reset(onboarding):
    client, factory, _, _ = onboarding
    data = payload()
    data.pop("password")
    result = await client.post("/onboarding/applications", json=data)
    assert result.status_code == 201, result.text
    application = result.json()["application"]
    password = await emailed_password(factory, application["id"], "ONBOARDING_PASSWORD")
    headers = {"X-Application-Token": result.json()["token"]}
    assert (
        await client.post(
            "/onboarding/access", json={"email": "applicant@example.com", "password": password}
        )
    ).status_code == 200
    assert (await client.post("/onboarding/me/resend", headers=headers)).status_code == 409
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        assert (
            timedelta(days=4, hours=23)
            < flow.aware(row.access_expires_at) - flow.now()
            <= timedelta(days=5)
        )
        row.access_expires_at = flow.now() - timedelta(seconds=1)
        await session.commit()
    assert (
        await client.post(
            "/onboarding/access", json={"email": "applicant@example.com", "password": password}
        )
    ).status_code == 401
    assert (await client.get("/onboarding/me", headers=headers)).status_code == 401


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
    async with factory() as session:
        row = await session.get(OnboardingApplication, UUID(application["id"]))
        row.status = "PENDING_EMAIL_VERIFICATION"
        row.reviewed_revision = row.revision
        await flow.queue_otp(session, row)
        await session.commit()
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


async def test_mail_failures_retry_and_stale_passwords_are_not_sent(onboarding, monkeypatch):
    client, factory, ids, _ = onboarding
    application, headers = await draft(client)
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")

    def fail(payload):
        raise OSError("temporary provider failure")

    monkeypatch.setattr(mailer, "send_email", fail)
    async with factory() as session:
        assert await mailer.deliver_one(session)
        row = await session.scalar(select(OnboardingMail))
        assert row.status == "PENDING" and row.attempts == 1
        assert row.last_error == "OSError"
        row.available_at = flow.now() - timedelta(seconds=1)
        await session.commit()
    application = await send_for_review(client, ids, application, headers)
    await approve(client, ids, application)
    sent = []
    monkeypatch.setattr(mailer, "send_email", lambda payload: sent.append(payload))
    async with factory() as session:
        assert await mailer.deliver_one(session)
        old = await session.scalar(
            select(OnboardingMail).where(OnboardingMail.kind == "ONBOARDING_PASSWORD")
        )
        assert old.status == "CANCELLED" and old.encrypted_payload is None
        assert await mailer.deliver_one(session)
        partner_mail = await session.scalar(
            select(OnboardingMail).where(OnboardingMail.kind == "PARTNER_PASSWORD")
        )
        assert partner_mail.status == "SENT" and partner_mail.encrypted_payload is None
    assert len(sent) == 1
    assert "Partner Portal password" in sent[0]["body"]


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
    async with factory() as session:
        application = await session.scalar(
            select(OnboardingApplication).where(
                OnboardingApplication.partner_id == UUID(partner_id)
            )
        )
        application_id = str(application.id)
    password = await emailed_password(factory, application_id, "ONBOARDING_PASSWORD")
    access = await client.post(
        "/onboarding/access", json={"email": "applicant@example.com", "password": password}
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


@pytest.mark.parametrize("role", ["TCG_FINANCE", "TCG_SALES", "TCG_LEGAL", "TCG_ADMIN"])
async def test_admin_staff_invitation_and_first_login(onboarding, monkeypatch, role):
    client, factory, ids, _ = onboarding
    body = {"email": "newstaff@example.com", "full_name": "New Staff", "role_code": role}
    for actor in ["sales", "legal"]:
        assert (
            await client.post("/staff-users", json=body, headers=auth(ids, actor))
        ).status_code == 403
        assert (await client.get("/staff-users", headers=auth(ids, actor))).status_code == 403
        assert (await client.get("/staff-users/roles", headers=auth(ids, actor))).status_code == 403
    result = await client.post("/staff-users", json=body, headers=auth(ids, "admin"))
    assert result.status_code == 201, result.text
    target = result.json()
    assert target["roles"] == [role]
    assert target["must_change_password"] and target["is_active"]
    assert not target["is_superuser"] and target["partner_id"] is None
    assert target["mail_status"] == "PENDING"
    assert "hashed_password" not in target and "password" not in target
    assert (
        await client.post("/staff-users", json=body, headers=auth(ids, "admin"))
    ).status_code == 409
    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")
    monkeypatch.setattr(mailer, "send_email", lambda payload: sent.append(payload))
    async with factory() as session:
        row = await session.scalar(
            select(OnboardingMail).where(OnboardingMail.user_id == UUID(target["id"]))
        )
        assert row.application_id is None
        assert await mailer.deliver_one(session)
        assert row.status == "SENT" and row.encrypted_payload is None
    assert sent[0]["to"] == body["email"]
    password = re.search(r"password: ([^\s]+)", sent[0]["body"]).group(1)
    login = await client.post("/auth/token", data={"username": body["email"], "password": password})
    assert login.status_code == 200, login.text
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (await client.get("/staff-users", headers=headers)).status_code == 403
    assert (await client.get("/auth/me", headers=headers)).json()["must_change_password"]
    changed = await client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": password, "new_password": PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    full = {"Authorization": "Bearer " + changed.json()["access_token"]}
    assert not (await client.get("/auth/me", headers=full)).json()["must_change_password"]
    if role == "TCG_FINANCE":
        assert (await client.get("/deals", headers=full)).status_code == 200
        rejected = await client.post(
            f"/deals/{uuid4()}/reject", headers=full, json={"reason": "Unauthorized finance change"}
        )
        revised = await client.post(f"/quotes/{uuid4()}/revise", headers=full)
        assert rejected.status_code == 403 and revised.status_code == 403
    assert (await client.get("/staff-users", headers=full)).status_code == (
        200 if role == "TCG_ADMIN" else 403
    )
    assert (await client.get("/auth/me", headers=headers)).status_code == 401
    assert (
        await client.post("/auth/token", data={"username": body["email"], "password": password})
    ).status_code == 401
    assert (
        await client.post("/auth/token", data={"username": body["email"], "password": PASSWORD})
    ).status_code == 200


async def test_staff_role_validation_and_legal_shortcut(onboarding):
    client, factory, ids, _ = onboarding
    headers = auth(ids, "admin")
    roles = await client.get("/staff-users/roles", headers=headers)
    assert {row["code"] for row in roles.json()} == {
        "TCG_ADMIN",
        "TCG_FINANCE",
        "TCG_SALES",
        "TCG_LEGAL",
    }
    body = {"email": "newstaff@example.com", "full_name": "New Staff", "role_code": "PARTNER_ADMIN"}
    assert (await client.post("/staff-users", json=body, headers=headers)).status_code == 422
    body["role_code"] = "TCG_FINANCE"
    body["password"] = PASSWORD
    assert (await client.post("/staff-users", json=body, headers=headers)).status_code == 422
    result = await client.post(
        "/onboarding/reviewers",
        headers=headers,
        json={"email": "newlegal@example.com", "full_name": "New Legal"},
    )
    assert result.status_code == 201, result.text
    async with factory() as session:
        target = await session.get(User, UUID(result.json()["id"]))
        assert target.must_change_password and target.roles[0].code == "TCG_LEGAL"
        assert await session.scalar(
            select(OnboardingMail).where(OnboardingMail.user_id == target.id)
        )


async def test_staff_invitation_retry_and_stale_cancellation(onboarding, monkeypatch):
    client, factory, ids, _ = onboarding
    result = await client.post(
        "/staff-users",
        headers=auth(ids, "admin"),
        json={
            "email": "finance@example.com",
            "full_name": "Finance User",
            "role_code": "TCG_FINANCE",
        },
    )
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")

    def fail(payload):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(mailer, "send_email", fail)
    async with factory() as session:
        assert await mailer.deliver_one(session)
        row = await session.scalar(select(OnboardingMail))
        assert row.status == "PENDING" and row.attempts == 1
        assert row.last_error == "OSError" and row.encrypted_payload
        row.available_at = flow.now() - timedelta(seconds=1)
        target = await session.get(User, UUID(result.json()["id"]))
        target.must_change_password = False
        await session.commit()
        assert await mailer.deliver_one(session)
        assert row.status == "CANCELLED" and row.encrypted_payload is None


async def test_admin_can_reissue_pending_staff_invitation(onboarding, monkeypatch):
    client, factory, ids, _ = onboarding
    admin = auth(ids, "admin")
    result = await client.post(
        "/staff-users",
        headers=admin,
        json={
            "email": "finance@example.com",
            "full_name": "Finance User",
            "role_code": "TCG_FINANCE",
        },
    )
    target_id = result.json()["id"]
    path = f"/staff-users/{target_id}/invitation"
    async with factory() as session:
        old_mail = await session.scalar(select(OnboardingMail))
        old_payload = json.loads(flow.mail_cipher().decrypt(old_mail.encrypted_payload.encode()))
        old_password = re.search(r"password: ([^\s]+)", old_payload["body"]).group(1)
    assert (await client.post(path, headers=auth(ids, "sales"))).status_code == 403
    issued = await client.post(path, headers=admin)
    assert issued.status_code == 200 and issued.json()["mail_status"] == "PENDING"
    assert (
        await client.post(
            "/auth/token", data={"username": "finance@example.com", "password": old_password}
        )
    ).status_code == 401
    sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "test.invalid")
    monkeypatch.setattr(mailer, "send_email", lambda payload: sent.append(payload))
    async with factory() as session:
        assert await mailer.deliver_one(session)
        old = await session.get(OnboardingMail, old_mail.id)
        assert old.status == "CANCELLED" and old.encrypted_payload is None
        assert await mailer.deliver_one(session)
    assert len(sent) == 1
    password = re.search(r"password: ([^\s]+)", sent[0]["body"]).group(1)
    assert password != old_password
    login = await client.post(
        "/auth/token", data={"username": "finance@example.com", "password": password}
    )
    assert login.status_code == 200
    restricted = {"Authorization": "Bearer " + login.json()["access_token"]}
    changed = await client.post(
        "/auth/change-password",
        headers=restricted,
        json={"current_password": password, "new_password": PASSWORD},
    )
    assert changed.status_code == 200
    assert (await client.post(path, headers=admin)).status_code == 409
