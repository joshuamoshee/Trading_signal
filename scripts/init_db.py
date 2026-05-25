import asyncio
from src.db.models import Base
from src.db.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Schema created")


if __name__ == "__main__":
    asyncio.run(main())