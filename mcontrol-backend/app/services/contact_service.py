from app.repositories.contact_repository import ContactRepository
from app.schemas.contact import ContactCreate, ContactUpdate
from app.utils.exceptions import NotFoundError


class ContactService:
    def __init__(self, repo: ContactRepository):
        self.repo = repo

    def list(self, user_id: str, active_only: bool = True):
        return self.repo.list_for_user(user_id, active_only)

    def get(self, contact_id: str, user_id: str):
        contact = self.repo.get_by_id(contact_id, user_id)
        if not contact:
            raise NotFoundError(f"{self.repo.table[:-1].capitalize()} not found")
        return contact

    def create(self, user_id: str, payload: ContactCreate):
        data = payload.model_dump()
        data["user_id"] = user_id
        return self.repo.create(data)

    def update(self, contact_id: str, user_id: str, payload: ContactUpdate):
        self.get(contact_id, user_id)  # 404 if not owned/found
        data = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not data:
            return self.get(contact_id, user_id)
        return self.repo.update(contact_id, user_id, data)

    def delete(self, contact_id: str, user_id: str):
        self.get(contact_id, user_id)
        self.repo.soft_delete(contact_id, user_id)
