import hmac
import json
from hashlib import sha256

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.plans import PLANS, get_or_create_account, plan_limits

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    plan: str = "pro"


def _billing_out(account) -> dict:
    limits = plan_limits(account)
    return {
        "plan": account.plan,
        "label": limits["label"],
        "stores": limits["stores"],
        "screens": limits["screens"],
        "instagram_sync": limits["instagram_sync"],
        "stripe_configured": bool(settings.stripe_secret_key and settings.stripe_price_pro),
        "plans": [
            {"id": key, "label": value["label"], "stores": value["stores"], "screens": value["screens"]}
            for key, value in PLANS.items()
        ],
    }


@router.get("")
def get_billing(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = get_or_create_account(db, user)
    db.commit()
    return _billing_out(account)


@router.post("/checkout")
def checkout(body: CheckoutBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.plan != "pro":
        raise HTTPException(status_code=400, detail="Only the Pro plan can be purchased.")
    account = get_or_create_account(db, user)
    if settings.stripe_secret_key and settings.stripe_price_pro:
        success = f"{settings.public_web_url.rstrip('/')}/billing?checkout=success"
        cancel = f"{settings.public_web_url.rstrip('/')}/billing?checkout=cancel"
        data = {
            "mode": "subscription",
            "line_items[0][price]": settings.stripe_price_pro,
            "line_items[0][quantity]": 1,
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": str(user.id),
            "metadata[user_id]": str(user.id),
        }
        if account.stripe_customer_id:
            data["customer"] = account.stripe_customer_id
        else:
            data["customer_email"] = user.email
        response = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=data,
            auth=(settings.stripe_secret_key, ""),
            timeout=20,
        )
        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="Stripe checkout could not start.")
        session = response.json()
        db.commit()
        return {"url": session.get("url")}
    if not settings.debug:
        raise HTTPException(status_code=400, detail="Stripe is not configured.")
    account.plan = "pro"
    db.commit()
    return {"url": None, "plan": "pro"}


@router.post("/portal")
def portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = get_or_create_account(db, user)
    if not settings.stripe_secret_key or not account.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on this account yet.")
    response = httpx.post(
        "https://api.stripe.com/v1/billing_portal/sessions",
        data={
            "customer": account.stripe_customer_id,
            "return_url": f"{settings.public_web_url.rstrip('/')}/billing",
        },
        auth=(settings.stripe_secret_key, ""),
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail="Could not open the billing portal.")
    db.commit()
    return {"url": response.json().get("url")}


def _valid_stripe_signature(payload: bytes, header: str) -> bool:
    if not settings.stripe_webhook_secret or not header:
        return False
    items = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp = items.get("t")
    signature = items.get("v1")
    if not timestamp or not signature:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(settings.stripe_webhook_secret.encode(), signed, sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    payload = await request.body()
    if settings.stripe_webhook_secret and not _valid_stripe_signature(payload, stripe_signature or ""):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    event = json.loads(payload or b"{}")
    kind = event.get("type")
    obj = event.get("data", {}).get("object", {})
    user_id = None
    if kind == "checkout.session.completed":
        user_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
        customer = obj.get("customer") or ""
        subscription = obj.get("subscription") or ""
        if user_id:
            user = db.get(User, int(user_id))
            if user:
                account = get_or_create_account(db, user)
                account.plan = "pro"
                if customer:
                    account.stripe_customer_id = str(customer)
                if subscription:
                    account.stripe_subscription_id = str(subscription)
                db.commit()
    if kind in {"customer.subscription.deleted", "customer.subscription.canceled"}:
        customer = obj.get("customer")
        if customer:
            from app.models import Account

            account = db.query(Account).filter(Account.stripe_customer_id == str(customer)).one_or_none()
            if account:
                account.plan = "starter"
                db.commit()
    return {"ok": True}
