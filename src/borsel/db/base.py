"""SQLAlchemy declarative base for all ORM models."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared base class for all Borsel Handler ORM models.

    Every model module should import this class and inherit from it:

        from borsel.db.base import Base

        class MyModel(Base):
            __tablename__ = "my_table"
            ...
    """

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)
