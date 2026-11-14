"""coach agent: actions on coach replies, coach notes, and daily AI usage

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('coach_messages', sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_table(
        'coach_notes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coach_notes_user_id', 'coach_notes', ['user_id'])
    op.create_table(
        'ai_usage',
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('requests', sa.Integer(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('cache_read_tokens', sa.Integer(), nullable=False),
        sa.Column('cache_write_tokens', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'day'),
    )
    # Like every table (see 0002): no access through Supabase's Data API.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE "coach_notes" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "ai_usage" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_usage')
    op.drop_index('ix_coach_notes_user_id', table_name='coach_notes')
    op.drop_table('coach_notes')
    op.drop_column('coach_messages', 'actions')
