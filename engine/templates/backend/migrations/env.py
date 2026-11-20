from alembic import context
from db import METADATA, connect, database_url

if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=METADATA, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with connect().connect() as connection:
        context.configure(connection=connection, target_metadata=METADATA)
        with context.begin_transaction():
            context.run_migrations()
