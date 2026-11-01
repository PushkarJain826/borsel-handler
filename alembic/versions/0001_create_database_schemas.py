"""Create initial database schemas

Revision ID: 0001_create_database_schemas
Revises: 
Create Date: 2026-11-02 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001_create_database_schemas"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Creation order for the seven logical schemas
CREATE_SCHEMAS = [
    "reference",
    "market",
    "corporate",
    "ingestion",
    "quality",
    "fundamentals",
    "system",
]

# Drop order in reverse dependency hierarchy
DROP_SCHEMAS = [
    "system",
    "fundamentals",
    "quality",
    "corporate",
    "market",
    "ingestion",
    "reference",
]


def upgrade() -> None:
    for schema in CREATE_SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def downgrade() -> None:
    for schema in DROP_SCHEMAS:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} RESTRICT")
