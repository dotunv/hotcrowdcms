from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_store, get_current_user, list_user_stores, set_store_cookie
from app.models import Store, User
from app.plans import assert_can_add_store, get_or_create_account
from app.routers.auth import StoreOut, _store_out

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])


class StoreCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)


@router.get("")
def list_stores(user: User = Depends(get_current_user), store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    stores = list_user_stores(db, user)
    account = get_or_create_account(db, user)
    db.commit()
    return {
        "plan": account.plan,
        "current_id": store.id,
        "results": [_store_out(item) for item in stores],
    }


@router.post("", response_model=StoreOut)
def create_store(body: StoreCreate, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assert_can_add_store(db, user)
    store = Store(user_id=user.id, business_name=body.business_name.strip())
    db.add(store)
    db.commit()
    db.refresh(store)
    set_store_cookie(response, store.id)
    return _store_out(store)


@router.post("/{store_id}/select", response_model=StoreOut)
def select_store(
    store_id: int,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.id == store_id, Store.user_id == user.id).one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    set_store_cookie(response, store.id)
    return _store_out(store)
