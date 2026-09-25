from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Reuse the same DATABASE_URL env var as the app (db.py / db_sql.py),
# instead of hard-coding a connection string in alembic.ini.
if os.environ.get("DATABASE_URL"):
    config_db_url = os.environ["DATABASE_URL"]
    if config_db_url.startswith("postgres://"):
        config_db_url = config_db_url.replace("postgres://", "postgresql://", 1)
    elif config_db_url.startswith("postgresql://") and "+" not in config_db_url.split("://", 1)[0]:
        config_db_url = config_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    config_db_url = None

# Target both the generic `records` table (db_sql.py's Base) and the
# typed role tables (models.py's Base) so autogenerate sees the whole
# schema.
from db_sql import Base as RecordsBase
from models import Base as ModelsBase

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# Both the generic records table and the typed role tables, so
# `alembic revision --autogenerate` sees the full schema.
target_metadata = [RecordsBase.metadata, ModelsBase.metadata]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config_db_url or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    section = config.get_section(config.config_ini_section, {})
    if config_db_url:
        section["sqlalchemy.url"] = config_db_url
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
