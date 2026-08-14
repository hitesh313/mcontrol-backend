"""
Supabase client singleton.
Uses the SERVICE ROLE key because all authorization/user-scoping is enforced
in the application layer (see repositories — every query is filtered by
user_id). The service role key must NEVER be shipped to the Flutter client;
it lives only in this backend's environment.
"""
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
