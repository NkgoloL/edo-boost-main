import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.api.models.db_models import Base
from app.api.core.config import settings

async def init_db():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        print("Creating all tables if they don't exist...")
        # Note: In a real app, we'd use migrations, but for the sandbox
        # and given the alembic driver issue, this is a safe way to ensure tables exist.
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialisation complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
