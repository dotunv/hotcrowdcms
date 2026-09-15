from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, Screen, Store, User

PLANS = {
    "starter": {"label": "Starter", "stores": 1, "screens": 2, "instagram_sync": False},
    "pro": {"label": "Pro", "stores": 20, "screens": 50, "instagram_sync": True},
}


def get_or_create_account(db: Session, user: User) -> Account:
    account = db.query(Account).filter(Account.user_id == user.id).one_or_none()
    if account is None:
        account = Account(user_id=user.id, plan="starter")
        db.add(account)
        db.flush()
    if account.plan not in PLANS:
        account.plan = "starter"
    return account


def plan_limits(account: Account) -> dict:
    return PLANS[account.plan if account.plan in PLANS else "starter"]


def assert_can_add_store(db: Session, user: User) -> Account:
    account = get_or_create_account(db, user)
    count = db.query(Store).filter(Store.user_id == user.id).count()
    limit = plan_limits(account)["stores"]
    if count >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"{plan_limits(account)['label']} includes {limit} store{'s' if limit != 1 else ''}. Upgrade to add another.",
        )
    return account


def assert_can_pair_screen(db: Session, user: User, store: Store) -> None:
    account = get_or_create_account(db, user)
    count = db.query(Screen).filter(Screen.store_id == store.id).count()
    limit = plan_limits(account)["screens"]
    if count >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"{plan_limits(account)['label']} includes {limit} screens per store. Upgrade to connect more.",
        )
