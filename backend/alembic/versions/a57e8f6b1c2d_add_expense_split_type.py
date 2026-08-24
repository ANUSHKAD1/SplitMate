"""add expense split type

Revision ID: a57e8f6b1c2d
Revises: 29cb0be6d981
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a57e8f6b1c2d"
down_revision: Union[str, Sequence[str], None] = "29cb0be6d981"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column(
            "split_type",
            sa.String(length=20),
            server_default=sa.text("'equal'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_expenses_split_type_valid",
        "expenses",
        "split_type IN ('equal', 'custom')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_expenses_split_type_valid", "expenses", type_="check")
    op.drop_column("expenses", "split_type")
