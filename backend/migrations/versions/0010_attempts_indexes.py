"""attempts indexes: one user's answers by date, and the answer to an item

The new (user_id, created_at) index covers everything the old user_id index
did, so that one is dropped.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_attempts_user_id_created_at', 'attempts', ['user_id', 'created_at'])
    op.create_index('ix_attempts_item_id', 'attempts', ['item_id'])
    op.drop_index('ix_attempts_user_id', table_name='attempts')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_index('ix_attempts_user_id', 'attempts', ['user_id'])
    op.drop_index('ix_attempts_item_id', table_name='attempts')
    op.drop_index('ix_attempts_user_id_created_at', table_name='attempts')
