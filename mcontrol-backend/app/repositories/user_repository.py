"""Data access layer for users, refresh tokens, and password reset OTPs."""
from datetime import datetime, timezone
from typing import Any

from supabase import Client


class UserRepository:
    def __init__(self, db: Client):
        self.db = db

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        res = self.db.table("users").select("*").eq("id", user_id).limit(1).execute()
        return res.data[0] if res.data else None

    def get_by_mobile(self, mobile_number: str) -> dict[str, Any] | None:
        res = self.db.table("users").select("*").eq("mobile_number", mobile_number).limit(1).execute()
        return res.data[0] if res.data else None

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        res = self.db.table("users").select("*").eq("email", email).limit(1).execute()
        return res.data[0] if res.data else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        res = self.db.table("users").insert(data).execute()
        return res.data[0]

    def update_password(self, user_id: str, password_hash: str) -> None:
        self.db.table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()

    def update_fcm_token(self, user_id: str, fcm_token: str) -> None:
        self.db.table("users").update({"fcm_token": fcm_token}).eq("id", user_id).execute()

    # -- Refresh tokens ------------------------------------------------------
    def store_refresh_token(self, user_id: str, token_hash: str, expires_at: datetime) -> dict[str, Any]:
        res = self.db.table("refresh_tokens").insert({
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
        }).execute()
        return res.data[0]

    def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        res = (
            self.db.table("refresh_tokens")
            .select("*")
            .eq("token_hash", token_hash)
            .eq("is_revoked", False)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def revoke_refresh_token(self, token_id: str, replaced_by: str | None = None) -> None:
        payload: dict[str, Any] = {"is_revoked": True}
        if replaced_by:
            payload["replaced_by"] = replaced_by
        self.db.table("refresh_tokens").update(payload).eq("id", token_id).execute()

    def revoke_all_refresh_tokens(self, user_id: str) -> None:
        self.db.table("refresh_tokens").update({"is_revoked": True}).eq("user_id", user_id).execute()

    # -- Password reset OTPs --------------------------------------------------
    def store_otp(self, user_id: str, otp_hash: str, expires_at: datetime) -> dict[str, Any]:
        res = self.db.table("password_reset_otps").insert({
            "user_id": user_id,
            "otp_hash": otp_hash,
            "expires_at": expires_at.isoformat(),
        }).execute()
        return res.data[0]

    def get_latest_otp(self, user_id: str) -> dict[str, Any] | None:
        res = (
            self.db.table("password_reset_otps")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_used", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def mark_otp_used(self, otp_id: str) -> None:
        self.db.table("password_reset_otps").update({"is_used": True}).eq("id", otp_id).execute()

    def increment_otp_attempts(self, otp_id: str, attempts: int) -> None:
        self.db.table("password_reset_otps").update({"attempts": attempts}).eq("id", otp_id).execute()
