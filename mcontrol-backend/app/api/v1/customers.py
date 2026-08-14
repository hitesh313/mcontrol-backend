from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.repositories.contact_repository import ContactRepository
from app.schemas.common import MessageResponse
from app.schemas.contact import ContactCreate, ContactResponse, ContactUpdate
from app.services.contact_service import ContactService

router = APIRouter(prefix="/customers", tags=["Customers"])


def _service(db: DbSession) -> ContactService:
    return ContactService(ContactRepository(db, "customers"))


@router.get("", response_model=list[ContactResponse])
def list_customers(current_user: CurrentUser, db: DbSession, active_only: bool = True):
    return _service(db).list(current_user["id"], active_only)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_customer(payload: ContactCreate, current_user: CurrentUser, db: DbSession):
    return _service(db).create(current_user["id"], payload)


@router.get("/{customer_id}", response_model=ContactResponse)
def get_customer(customer_id: str, current_user: CurrentUser, db: DbSession):
    return _service(db).get(customer_id, current_user["id"])


@router.patch("/{customer_id}", response_model=ContactResponse)
def update_customer(customer_id: str, payload: ContactUpdate, current_user: CurrentUser, db: DbSession):
    return _service(db).update(customer_id, current_user["id"], payload)


@router.delete("/{customer_id}", response_model=MessageResponse)
def delete_customer(customer_id: str, current_user: CurrentUser, db: DbSession):
    _service(db).delete(customer_id, current_user["id"])
    return MessageResponse(message="Customer deactivated")
