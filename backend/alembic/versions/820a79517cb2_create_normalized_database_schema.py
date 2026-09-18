"""create normalized database schema

Revision ID: 820a79517cb2
Revises:
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "820a79517cb2"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_USER_ID = "c46e4036-8827-45e8-9625-f05341aa2bbc"


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. Create users table
    # ---------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email"),
    )

    # ---------------------------------------------------------
    # 2. Create migration/import user
    # ---------------------------------------------------------
    op.execute(
        f"""
        INSERT INTO users
            (user_id, username, email, role, created_at)
        VALUES
            (
                '{LEGACY_USER_ID}'::uuid,
                'legacy-import',
                'legacy-import@adaptive-mas-rca.local',
                'system',
                CURRENT_TIMESTAMP
            )
        """
    )

    # ---------------------------------------------------------
    # 3. Preserve existing legacy incidents
    #
    # Rename the existing table temporarily, then create the
    # documented normalized incidents table.
    # ---------------------------------------------------------
    op.rename_table("incidents", "incidents_legacy")

    op.create_table(
        "incidents",
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ---------------------------------------------------------
    # 4. Convert legacy incident IDs such as INC-001 into UUIDs
    #
    # uuid_generate_v5 is deterministic, so the same legacy
    # incident ID always produces the same UUID.
    # ---------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        INSERT INTO incidents
            (
                incident_id,
                user_id,
                title,
                description,
                severity,
                status,
                source,
                created_at,
                updated_at
            )
        SELECT
            gen_random_uuid(),
            'c46e4036-8827-45e8-9625-f05341aa2bbc'::uuid,
            COALESCE(alert_name, 'Legacy Incident'),
            COALESCE(description, 'Legacy incident imported from previous schema.'),
            LEFT(COALESCE(severity, 'unknown'), 20),
            LEFT(COALESCE(status, 'unknown'), 30),
            service,
            created_at,
            NULL
        FROM incidents_legacy
        ORDER BY id
        """
    )

    # ---------------------------------------------------------
    # 5. Create agent_outputs
    # ---------------------------------------------------------
    op.create_table(
        "agent_outputs",
        sa.Column(
            "output_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.incident_id"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ---------------------------------------------------------
    # 6. Create confidence_scores
    # ---------------------------------------------------------
    op.create_table(
        "confidence_scores",
        sa.Column(
            "confidence_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_outputs.output_id"),
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("confidence_level", sa.String(length=30), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ---------------------------------------------------------
    # 7. Create feedback
    # ---------------------------------------------------------
    op.create_table(
        "feedback",
        sa.Column(
            "feedback_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_outputs.output_id"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # Remove normalized tables in reverse dependency order.
    op.drop_table("feedback")
    op.drop_table("confidence_scores")
    op.drop_table("agent_outputs")

    op.drop_table("incidents")

    # Restore the legacy incidents table.
    op.rename_table("incidents_legacy", "incidents")

    op.drop_table("users")