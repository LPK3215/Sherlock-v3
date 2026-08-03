import asyncio
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import User
from sqlalchemy import select

async def check():
    await pg_manager.initialize()
    async with pg_manager.get_async_session_context() as s:
        r = await s.execute(select(User).where(User.uid == 'zwj'))
        u = r.scalar_one_or_none()
        if u:
            print(f'uid={u.uid} name={u.username} phone={u.phone_number} hash={u.password_hash[:30]}')
        else:
            print('NOT FOUND')
    await pg_manager.close()

asyncio.run(check())
