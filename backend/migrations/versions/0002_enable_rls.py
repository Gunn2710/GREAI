"""enable row level security on Postgres

Supabase exposes every table in the public schema through its auto-generated
Data API (PostgREST) to anyone holding the project's anon key. Enabling RLS
with no policies denies that API all access. The FastAPI backend connects as
the table owner, which bypasses RLS, so the app itself is unaffected.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "profiles", "skills", "words", "items", "user_skills", "cards", "issued_items",
    "attempts", "confusions", "placement_runs", "user_params", "alembic_version",
]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
