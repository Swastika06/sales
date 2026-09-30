"""Isolated SQL/API workflows. PostgreSQL DDL/triggers are tested by the migration harness."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.commercial import CommercialTermVersion, OpportunityParticipant, Organization
from app.models.identity import Permission, Role, User
from app.models.partner import Partner, PartnerType
from app.models.pricing import Product, ProductPrice, Sku
from app.models.sales import Order


@compiles(JSONB, "sqlite")
def sqlite_json(element, compiler, **kw):
    return "JSON"


@pytest.fixture
async def workflow():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enforce_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        tcg = Organization(identifier="TCG_INTERNAL", legal_name="TCG", is_internal=True)
        org = Organization(identifier="partner-1", legal_name="Multi-capability partner")
        other_org = Organization(identifier="partner-2", legal_name="Other partner")
        types = [
            PartnerType(code=code, name=code)
            for code in ["RESELLER", "REFERRAL", "SYSTEM_INTEGRATOR"]
        ]
        permission = Permission(code="sales.manage", description="Manage sales")
        role = Role(code="PARTNER_ADMIN", name="Partner admin", permissions=[permission])
        admin = User(
            email="admin@example.com",
            full_name="Admin",
            hashed_password="unused",
            is_superuser=True,
            roles=[],
        )
        session.add_all([tcg, org, other_org, admin, *types, role])
        await session.flush()

        def partner(o, email):
            return Partner(
                organization_id=o.id,
                company_name=o.legal_name,
                company_email=email,
                primary_contact_name="Contact",
                primary_contact_email=email,
                partner_type_id=types[0].id,
                capabilities=types,
                status="ACTIVE",
            )

        p = partner(org, "partner@example.com")
        other = partner(other_org, "other@example.com")
        session.add_all([p, other])
        await session.flush()
        member = User(
            email="member@example.com",
            full_name="Member",
            hashed_password="unused",
            partner_id=p.id,
            roles=[role],
        )
        outsider = User(
            email="outsider@example.com",
            full_name="Outsider",
            hashed_password="unused",
            partner_id=other.id,
            roles=[role],
        )
        null_user = User(
            email="null@example.com", full_name="Null", hashed_password="unused", roles=[role]
        )
        product = Product(code="MCUBE", name="mcube", owner_organization_id=tcg.id)
        session.add_all([member, outsider, null_user, product])
        await session.flush()
        sku = Sku(
            product_id=product.id,
            code="LICENSE",
            name="License",
            category="LICENSE",
            unit="license",
        )
        session.add(sku)
        await session.flush()
        session.add(
            ProductPrice(sku_id=sku.id, amount=Decimal("100000"), effective_from=date(2020, 1, 1))
        )
        session.add(
            CommercialTermVersion(
                engagement_model="REFERRAL",
                scope="DEFAULT",
                status="APPROVED",
                effective_from=date(2020, 1, 1),
                parameters={"referral_rate": "10"},
            )
        )
        await session.commit()
        ids = {
            "admin": admin.id,
            "member": member.id,
            "outsider": outsider.id,
            "null": null_user.id,
            "partner": p.id,
            "org": org.id,
            "other_org": other_org.id,
            "tcg": tcg.id,
            "product": product.id,
            "sku": sku.id,
        }
    state = {"user": ids["admin"]}

    async def database():
        async with factory() as session:
            yield session

    async def current_user(session: AsyncSession = Depends(get_db)):
        return await session.get(User, state["user"])

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client, ids, state, factory
    app.dependency_overrides.clear()
    await engine.dispose()


async def request(client, method, path, body=None, status=200):
    response = await client.request(method, path, json=body)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def new_deal(client, ids, model="DIRECT"):
    return await request(
        client,
        "POST",
        "/deals",
        dict(
            engagement_model=model,
            partner_id=str(ids["partner"]) if model != "DIRECT" else None,
            product_id=str(ids["product"]),
            name="Customer project",
            estimated_value="100000",
            customer={"name": f"Customer {uuid4()}", "country_code": "IN"},
        ),
        201,
    )


async def approve(client, deal):
    await request(client, "POST", f"/deals/{deal['id']}/submit")
    return await request(client, "POST", f"/deals/{deal['id']}/approve")


async def new_quote(client, ids, deal, finalize=True):
    quote = await request(client, "POST", "/quotes", {"opportunity_id": deal["id"]}, 201)
    quote = await request(
        client, "POST", f"/quotes/{quote['id']}/items", {"sku_id": str(ids["sku"]), "quantity": "1"}
    )
    if finalize:
        quote = await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "FINAL"})
    return quote


async def terms(client, deal, parameters, status=200):
    term = await request(
        client,
        "POST",
        "/commercial/terms",
        dict(
            expected_version=deal["commercial_version"],
            engagement_model=deal["engagement_model"],
            scope="OPPORTUNITY",
            opportunity_id=deal["id"],
            effective_from="2020-01-01",
            parameters=parameters,
        ),
        201,
    )
    await request(
        client,
        "POST",
        f"/commercial/terms/{term['id']}/approve",
        {"expected_version": deal["commercial_version"]},
        status,
    )
    return await request(client, "GET", f"/deals/{deal['id']}")


async def test_direct_deal_quote_accept_order_preserves_snapshot(workflow):
    client, ids, state, factory = workflow
    deal = await approve(client, await new_deal(client, ids))
    quote = await new_quote(client, ids, deal)
    assert quote["partner_id"] is None
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"})
    order = await request(
        client,
        "POST",
        "/orders",
        dict(
            quote_id=quote["id"],
            billing_name="Customer",
            billing_address="Customer billing address",
            billing_email="billing@example.com",
        ),
        201,
    )
    assert Decimal(order["total"]) == 100000
    async with factory() as session:
        stored = await session.get(Order, UUID(order["id"]))
        assert stored.quote_snapshot["total"] == "100000.00"
        assert stored.quote_snapshot["commercial_snapshot_id"]
    state["user"] = ids["null"]
    assert await request(client, "GET", "/deals") == []
    assert await request(client, "GET", "/quotes") == []
    assert await request(client, "GET", "/orders") == []
    await request(client, "GET", f"/deals/{deal['id']}", status=404)


async def test_referral_forecast_conversion_idempotency_and_visibility(workflow):
    client, ids, state, _ = workflow
    state["user"] = ids["member"]
    deal = await new_deal(client, ids, "REFERRAL")
    state["user"] = ids["admin"]
    structure = await request(client, "GET", f"/commercial/opportunities/{deal['id']}")
    eligible = dict(
        component_ids=[structure["components"][0]["id"]],
        amount="80000",
        discounts="Net",
        taxes="Excluded",
        vendor_charges="Excluded",
        credits="Agreed adjustment",
        refunds="Agreed adjustment",
    )
    deal = await terms(
        client,
        deal,
        dict(eligibility=eligible, settlement_policy="Pay on signed conversion; adjust refunds"),
    )
    deal = await approve(client, deal)
    quote = await new_quote(client, ids, deal)
    frozen = (await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots"))[0]
    assert Decimal(frozen["payload"]["result"]["commission_expense"]) == 8000
    assert await request(client, "GET", "/commercial/commissions") == []
    # Bid win without conversion does not accrue.
    await request(
        client,
        "POST",
        f"/deals/{deal['id']}/stage",
        dict(stage="WON", actual_contract_value="100000", actual_close_date="2026-09-30"),
    )
    assert await request(client, "GET", "/commercial/commissions") == []
    body = dict(
        expected_version=deal["commercial_version"],
        snapshot_id=frozen["id"],
        evidence="Verified customer project contract",
        actual_eligibility=eligible,
    )
    first = await request(
        client, "POST", f"/commercial/opportunities/{deal['id']}/conversion", body
    )
    second = await request(
        client, "POST", f"/commercial/opportunities/{deal['id']}/conversion", body
    )
    assert first["accrual"]["id"] == second["accrual"]["id"]
    state["user"] = ids["member"]
    assert await request(client, "GET", "/quotes") == []
    assert await request(client, "GET", "/orders") == []
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"}, 404)
    own = await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots")
    assert "payload" not in own[0]
    assert Decimal(own[0]["own_entitlement"]) == 8000
    assert len(await request(client, "GET", "/commercial/commissions")) == 1
    await request(client, "GET", "/commercial/agreements", status=403)
    state["user"] = ids["outsider"]
    await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots", status=404)
    assert await request(client, "GET", "/commercial/commissions") == []
    state["user"] = ids["admin"]
    accrual = first["accrual"]["id"]
    payment = dict(expected_version=0, payment_reference="PAY-001", amount="8000")
    await request(client, "POST", f"/commercial/commissions/{accrual}/payments", payment, 201)
    await request(client, "POST", f"/commercial/commissions/{accrual}/payments", payment, 201)
    ledger = (await request(client, "GET", "/commercial/commissions"))[0]
    assert ledger["status"] == "PAID" and len(ledger["payments"]) == 1
    await request(
        client,
        "POST",
        f"/commercial/commissions/{accrual}/adjustments",
        dict(event_key="CREDIT-001", amount="-500", reason="Agreed refund"),
        201,
    )
    ledger = (await request(client, "GET", "/commercial/commissions"))[0]
    assert Decimal(ledger["amount"]) == 8000 and Decimal(ledger["net_accrued"]) == 7500


async def test_referral_finalization_requires_explicit_eligibility(workflow):
    client, ids, _, _ = workflow
    deal = await approve(client, await new_deal(client, ids, "REFERRAL"))
    quote = await new_quote(client, ids, deal, False)
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "FINAL"}, 422)


async def test_overlapping_terms_and_stale_versions(workflow):
    client, ids, _, _ = workflow
    deal = await new_deal(client, ids)
    updated = await terms(client, deal, {"discount_percentage": "0"})
    await terms(client, updated, {"discount_percentage": "5"}, 409)
    await request(
        client,
        "POST",
        "/commercial/terms",
        dict(
            expected_version=deal["commercial_version"],
            engagement_model="DIRECT",
            scope="OPPORTUNITY",
            opportunity_id=deal["id"],
            effective_from="2020-01-01",
            parameters={"fixed_unit_price": "100"},
        ),
        409,
    )


async def test_reseller_only_contract_buyer_can_accept(workflow):
    client, ids, state, factory = workflow
    deal = await new_deal(client, ids, "RESELLER")
    deal = await terms(client, deal, {"fixed_unit_price": "80000", "wholesale_value": "80000"})
    deal = await approve(client, deal)
    quote = await new_quote(client, ids, deal)
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"}, 403)
    async with factory() as session:
        session.add(
            OpportunityParticipant(
                opportunity_id=UUID(deal["id"]),
                organization_id=ids["other_org"],
                capability="RESELLER",
                access_level="COMMERCIAL",
            )
        )
        await session.commit()
    state["user"] = ids["outsider"]
    assert len(await request(client, "GET", "/deals")) == 1
    assert await request(client, "GET", "/quotes") == []
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"}, 403)
    state["user"] = ids["member"]
    visible = await request(client, "GET", "/quotes")
    assert len(visible) == 1 and "parameters" not in visible[0]["items"][0]["pricing_snapshot"]
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"})


async def test_tier_contracts_removed(workflow):
    client, _, _, _ = workflow
    options = await request(client, "GET", "/partners/registration-options")
    assert "partner_tiers" not in options
    await request(client, "GET", "/pricing/configuration", status=404)


def configuration(structure, deal):
    from app.schemas.commercial import ComponentInput, ParticipantInput

    return dict(
        expected_version=structure["commercial_version"],
        engagement_model=deal["engagement_model"],
        partner_id=deal["partner_id"],
        responsible_user_id=None,
        participants=[
            {k: p[k] for k in ParticipantInput.model_fields} for p in structure["participants"]
        ],
        roles=[
            dict(
                organization_id=next(
                    p["organization_id"]
                    for p in structure["participants"]
                    if p["id"] == r["participant_id"]
                ),
                role=r["role"],
                scope=r["scope"],
                primary=r["is_primary"],
            )
            for r in structure["roles"]
        ],
        components=[
            {k: c[k] for k in ComponentInput.model_fields} for c in structure["components"]
        ],
    )


async def test_si_explicit_roles_allocation_and_contract_acceptance(workflow):
    client, ids, state, _ = workflow
    deal = await new_deal(client, ids, "SYSTEM_INTEGRATOR")
    await request(client, "POST", f"/deals/{deal['id']}/submit")
    await request(client, "POST", f"/deals/{deal['id']}/approve", status=422)
    structure = await request(client, "GET", f"/commercial/opportunities/{deal['id']}")
    body = configuration(structure, deal)
    for role in ["CUSTOMER_RELATIONSHIP_OWNER", "BIDDER", "CONTRACTING_SELLER", "DELIVERY_LEAD"]:
        body["roles"].append(
            dict(organization_id=str(ids["org"]), role=role, scope="OPPORTUNITY", primary=True)
        )
    structure = await request(client, "PUT", f"/commercial/opportunities/{deal['id']}", body)
    contract = await request(
        client,
        "POST",
        "/commercial/contracts",
        dict(
            expected_version=structure["commercial_version"],
            opportunity_id=deal["id"],
            seller_organization_id=str(ids["tcg"]),
            buyer_organization_id=str(ids["org"]),
            kind="PROJECT",
        ),
        201,
    )
    deal = await request(client, "GET", f"/deals/{deal['id']}")
    deal = await terms(
        client,
        deal,
        dict(
            customer_value="200000",
            fixed_unit_price="60000",
            allocation_method="PERCENT",
            tcg_percentage="30",
            pool=dict(
                name="Whole-project services",
                component_ids=[structure["components"][0]["id"]],
                gross_amount="200000",
                residual_beneficiary_id=str(ids["org"]),
            ),
        ),
    )
    # The failed approval left the opportunity submitted.
    deal = await request(client, "POST", f"/deals/{deal['id']}/approve")
    quote = await request(
        client, "POST", "/quotes", dict(opportunity_id=deal["id"], contract_id=contract["id"]), 201
    )
    await request(
        client, "POST", f"/quotes/{quote['id']}/items", dict(sku_id=str(ids["sku"]), quantity="1")
    )
    quote = await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "FINAL"})
    assert Decimal(quote["total"]) == 60000
    frozen = (await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots"))[0]
    assert Decimal(frozen["payload"]["result"]["partner_entitlement"]) == 140000
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"}, 403)
    state["user"] = ids["member"]
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"})


async def test_accepted_structure_requires_amendment_and_reapproval(workflow):
    client, ids, _, _ = workflow
    deal = await approve(client, await new_deal(client, ids))
    quote = await new_quote(client, ids, deal)
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "ACCEPTED"})
    structure = await request(client, "GET", f"/commercial/opportunities/{deal['id']}")
    body = configuration(structure, deal)
    await request(client, "PUT", f"/commercial/opportunities/{deal['id']}", body, 409)
    body["amendment_reason"] = "Agreed delivery ownership amendment"
    await request(client, "PUT", f"/commercial/opportunities/{deal['id']}", body)
    changed = await request(client, "GET", f"/deals/{deal['id']}")
    assert changed["approval_status"] == "DRAFT"
    frozen = (await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots"))[0]
    assert Decimal(frozen["payload"]["result"]["tcg_entitlement"]) == 100000
    await request(client, "PUT", f"/commercial/opportunities/{deal['id']}", body, 409)


async def test_draft_price_cannot_finalize_after_changed_terms(workflow):
    client, ids, _, _ = workflow
    deal = await approve(client, await new_deal(client, ids))
    quote = await new_quote(client, ids, deal, False)
    changed = await terms(client, deal, {"fixed_unit_price": "80000"})
    assert changed["approval_status"] == "DRAFT"
    await approve(client, changed)
    await request(client, "POST", f"/quotes/{quote['id']}/status", {"status": "FINAL"}, 409)


async def test_vendor_contract_document_and_referral_attachments_private(workflow):
    from app.models.commercial import VendorAgreement
    from app.models.content import Document

    client, ids, state, factory = workflow
    deal = await new_deal(client, ids, "REFERRAL")
    async with factory() as session:
        document = Document(
            title="Private vendor agreement",
            category="OTHER",
            visibility="ALL_PARTNERS",
            created_by_id=ids["admin"],
        )
        session.add(document)
        await session.flush()
        session.add(
            VendorAgreement(
                provider_organization_id=ids["other_org"],
                buyer_organization_id=ids["tcg"],
                billing_basis="Usage",
                charge_model="USAGE",
                effective_from=date(2020, 1, 1),
                document_id=document.id,
            )
        )
        await session.commit()
        document_id = str(document.id)
    state["user"] = ids["member"]
    assert await request(client, "GET", "/documents") == []
    await request(client, "GET", f"/documents/{document_id}/download", status=404)
    await request(client, "GET", f"/deals/{deal['id']}/attachments", status=404)
    await request(client, "GET", f"/deals/{deal['id']}/attachments/{uuid4()}/download", status=404)


async def test_lost_referral_with_conversion_does_not_accrue(workflow):
    client, ids, _, _ = workflow
    deal = await new_deal(client, ids, "REFERRAL")
    structure = await request(client, "GET", f"/commercial/opportunities/{deal['id']}")
    eligible = dict(
        component_ids=[structure["components"][0]["id"]],
        amount="80000",
        discounts="Net",
        taxes="Excluded",
        vendor_charges="Excluded",
        credits="Adjust",
        refunds="Adjust",
    )
    deal = await terms(client, deal, dict(eligibility=eligible, referral_rate="0"))
    deal = await approve(client, deal)
    await new_quote(client, ids, deal)
    frozen = (await request(client, "GET", f"/commercial/opportunities/{deal['id']}/snapshots"))[0]
    assert Decimal(frozen["payload"]["result"]["commission_expense"]) == 0
    await request(
        client,
        "POST",
        f"/deals/{deal['id']}/stage",
        dict(stage="LOST", lost_reason="Project cancelled"),
    )
    result = await request(
        client,
        "POST",
        f"/commercial/opportunities/{deal['id']}/conversion",
        dict(
            expected_version=deal["commercial_version"],
            snapshot_id=frozen["id"],
            evidence="Prior project evidence",
            actual_eligibility=eligible,
        ),
    )
    assert result["accrual"] is None
    assert await request(client, "GET", "/commercial/commissions") == []
