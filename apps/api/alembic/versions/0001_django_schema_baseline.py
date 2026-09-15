"""Django Neon schema baseline.

Inspected against the existing Django tables (`auth_user`, `core_store`,
`core_screen`, `core_playlist`, `core_playlistitem`, `core_mediaasset`,
`core_pairingcode`). This revision is a no-op so we never reset production
data. Stamp existing databases with `alembic stamp head`.
"""

revision = "0001_django_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
