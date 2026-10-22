"""Make Instagram ids unique per store instead of globally.

With a global unique index one store importing a post blocked every other store from importing it (and
revealed that the post exists elsewhere). Idempotent: safe on databases created from the current models,
on databases migrated from Django (where the old uniqueness is a named constraint), and when re-run.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_instagram_per_store"
down_revision = "0002_multi_store_billing_canvas"
branch_labels = None
depends_on = None

TABLE = "core_mediaasset"
LOOKUP_INDEX = "ix_core_mediaasset_instagram_id"
PER_STORE_INDEX = "uq_mediaasset_store_instagram"


def _only_instagram(columns) -> bool:
    return list(columns or []) == ["instagram_id"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for constraint in inspector.get_unique_constraints(TABLE):
        if _only_instagram(constraint["column_names"]) and constraint.get("name"):
            op.drop_constraint(constraint["name"], TABLE, type_="unique")

    inspector = sa.inspect(bind)  # constraints may have been backed by indexes: look again
    for index in inspector.get_indexes(TABLE):
        if _only_instagram(index["column_names"]) and index.get("unique"):
            op.drop_index(index["name"], table_name=TABLE)

    names = {index["name"] for index in sa.inspect(bind).get_indexes(TABLE)}
    if LOOKUP_INDEX not in names:
        op.create_index(LOOKUP_INDEX, TABLE, ["instagram_id"], unique=False)
    if PER_STORE_INDEX not in names:
        op.create_index(PER_STORE_INDEX, TABLE, ["store_id", "instagram_id"], unique=True)


def downgrade() -> None:
    names = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if PER_STORE_INDEX in names:
        op.drop_index(PER_STORE_INDEX, table_name=TABLE)
    if LOOKUP_INDEX in names:
        op.drop_index(LOOKUP_INDEX, table_name=TABLE)
    op.create_index(LOOKUP_INDEX, TABLE, ["instagram_id"], unique=True)
