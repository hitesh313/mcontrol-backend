"""
Generic repository for 'suppliers' and 'customers' tables — they are
structurally identical, so one parameterized repository avoids duplication.
"""
from typing import Any

from supabase import Client


class ContactRepository:
    def __init__(self, db: Client, table: str):
        assert table in ("suppliers", "customers")
        self.db = db
        self.table = table

    def list_for_user(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        query = self.db.table(self.table).select("*").eq("user_id", user_id)
        if active_only:
            query = query.eq("is_active", True)
        res = query.order("created_at", desc=True).execute()
        return res.data

    def get_by_id(self, contact_id: str, user_id: str) -> dict[str, Any] | None:
        res = (
            self.db.table(self.table)
            .select("*")
            .eq("id", contact_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.db.table(self.table).insert(data).execute()
        return res.data[0]

    def update(self, contact_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        res = (
            self.db.table(self.table)
            .update(data)
            .eq("id", contact_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def soft_delete(self, contact_id: str, user_id: str) -> None:
        self.db.table(self.table).update({"is_active": False}).eq("id", contact_id).eq(
            "user_id", user_id
        ).execute()
