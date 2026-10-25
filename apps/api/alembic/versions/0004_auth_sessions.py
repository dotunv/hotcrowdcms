"""Server-side login sessions, so logout can revoke tokens.

Idempotent: databases created from the current models already have the table.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_auth_sessions"
down_revision = "0003_instagram_per_store"
branch_labels = None
depends_on = None

TABLE = "auth_session"
INDEX = "ix_auth_session_user_id"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )
    if INDEX not in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, ["user_id"])


def downgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
