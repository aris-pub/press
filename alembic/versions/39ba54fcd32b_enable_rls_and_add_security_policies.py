"""Enable RLS and add security policies

Revision ID: 39ba54fcd32b
Revises: 3f51169c08c8
Create Date: 2026-02-12 13:53:23.954509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39ba54fcd32b'
down_revision: Union[str, Sequence[str], None] = '3f51169c08c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable Row Level Security (RLS) on all tables.

    This migration enables RLS to satisfy Supabase security requirements.
    Since the application connects as the 'postgres' superuser role (via service key),
    it automatically bypasses RLS. This protects against unauthorized access via
    Supabase client (anon/authenticated roles) while maintaining app functionality.

    No policies are added - all access via anon/authenticated roles is blocked.
    """
    # Enable RLS on all user tables
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subjects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scrolls ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Disable Row Level Security on all tables."""
    op.execute("ALTER TABLE tokens DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scrolls DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subjects DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
