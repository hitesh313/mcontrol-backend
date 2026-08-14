from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.repositories.contact_repository import ContactRepository
from app.schemas.common import MessageResponse
from app.schemas.contact import ContactCreate, ContactResponse, ContactUpdate
from app.services.contact_service import ContactService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


def _service(db: DbSession) -> ContactService:
    return ContactService(ContactRepository(db, "suppliers"))


@router.get("", response_model=list[ContactResponse])
def list_suppliers(current_user: CurrentUser, db: DbSession, active_only: bool = True):
    return _service(db).list(current_user["id"], active_only)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: ContactCreate, current_user: CurrentUser, db: DbSession):
    return _service(db).create(current_user["id"], payload)


@router.get("/{supplier_id}", response_model=ContactResponse)
def get_supplier(supplier_id: str, current_user: CurrentUser, db: DbSession):
    return _service(db).get(supplier_id, current_user["id"])


@router.patch("/{supplier_id}", response_model=ContactResponse)
def update_supplier(supplier_id: str, payload: ContactUpdate, current_user: CurrentUser, db: DbSession):
    return _service(db).update(supplier_id, current_user["id"], payload)


@router.delete("/{supplier_id}", response_model=MessageResponse)
def delete_supplier(supplier_id: str, current_user: CurrentUser, db: DbSession):
    _service(db).delete(supplier_id, current_user["id"])
    return MessageResponse(message="Supplier deactivated")
