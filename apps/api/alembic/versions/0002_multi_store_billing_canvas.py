"""Add multi-store, billing, canvas, and Instagram columns.

Existing Neon rows stay. Stamp 0001 first, then upgrade to this revision.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_multi_store_billing_canvas"
down_revision = "0001_django_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    store_cols = {col["name"] for col in inspector.get_columns("core_store")}
    if "instagram_connected" not in store_cols:
        op.add_column("core_store", sa.Column("instagram_connected", sa.Boolean(), server_default=sa.false(), nullable=False))
    if "instagram_user_id" not in store_cols:
        op.add_column("core_store", sa.Column("instagram_user_id", sa.String(64), server_default="", nullable=False))
    if "instagram_access_token" not in store_cols:
        op.add_column("core_store", sa.Column("instagram_access_token", sa.Text(), server_default="", nullable=False))
    media_cols = {col["name"] for col in inspector.get_columns("core_mediaasset")}
    if "instagram_id" not in media_cols:
        op.add_column("core_mediaasset", sa.Column("instagram_id", sa.String(255), nullable=True))
        op.create_index("ix_core_mediaasset_instagram_id", "core_mediaasset", ["instagram_id"], unique=True)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE core_store DROP CONSTRAINT IF EXISTS core_store_user_id_key")
        op.execute("ALTER TABLE core_store DROP CONSTRAINT IF EXISTS core_store_user_id_uniq")
    tables = inspector.get_table_names()
    if "hc_account" not in tables:
        op.create_table(
            "hc_account",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth_user.id"), unique=True, nullable=False),
            sa.Column("plan", sa.String(20), server_default="starter", nullable=False),
            sa.Column("stripe_customer_id", sa.String(64), server_default="", nullable=False),
            sa.Column("stripe_subscription_id", sa.String(64), server_default="", nullable=False),
        )
    if "hc_storelayout" not in tables:
        op.create_table(
            "hc_storelayout",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("store_id", sa.Integer(), sa.ForeignKey("core_store.id"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(10), server_default="DRAFT", nullable=False),
            sa.Column("layout_data", sa.JSON(), nullable=True),
            sa.Column("canvas_width", sa.Integer(), server_default="1920", nullable=False),
            sa.Column("canvas_height", sa.Integer(), server_default="1080", nullable=False),
            sa.Column("published_media_id", sa.Uuid(), sa.ForeignKey("core_mediaasset.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("hc_storelayout")
    op.drop_table("hc_account")
