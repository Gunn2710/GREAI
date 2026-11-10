"""your sentence: a sentence the student writes with a word to remember it

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'word_sentences',
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('word_id', sa.Integer(), nullable=False),
        sa.Column('sentence', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['word_id'], ['words.id']),
        sa.PrimaryKeyConstraint('user_id', 'word_id'),
    )
    # Like every table (see 0002): no access through Supabase's Data API.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE "word_sentences" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('word_sentences')
