import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
url=os.environ['DATABASE_URL']
# MySQL 应用连接采用 READ COMMITTED；本地 SQLite 开发/测试不支持该级别，按方言默认
opts={'pool_pre_ping':True} if url.startswith('sqlite') else {'pool_pre_ping':True,'isolation_level':'READ COMMITTED'}
engine=create_engine(url,**opts)
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
def session():
    with Session() as db:
        try:yield db
        except Exception:db.rollback();raise
