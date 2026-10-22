"""Django Neon schema baseline.

Existing databases (the old Django tables) are left exactly as they are: nothing is created, altered or
reset. A brand-new empty database gets the application tables created here, so `alembic upgrade head`
works on a fresh Postgres. Later revisions are idempotent and fill in anything missing.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_django_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None

# Tables that make up "an existing HotCrowd database".
APP_TABLES = {"auth_user", "core_store", "core_mediaasset", "core_playlist", "core_screen"}


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if existing & APP_TABLES:
        return  # an existing database: never touch it
    from app.models import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass
