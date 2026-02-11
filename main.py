from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, String, DateTime, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import datetime
from datetime import datetime as dt
import os  # 读取环境变量

# --------------------------
# 1. 数据库配置（异步模式，强制 asyncpg）
# --------------------------
# 从环境变量读取PostgreSQL连接字符串
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 本地开发：使用 SQLite（同步模式）
    from sqlalchemy import create_engine
    SQLALCHEMY_DATABASE_URL = "sqlite:///./monitor.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # 生产环境（Vercel + Neon）：强制使用 asyncpg 异步连接
    # 修复连接字符串前缀：明确指定 asyncpg 驱动
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    if "postgresql://" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # 创建异步引擎，强制指定驱动
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"driver": "asyncpg"}  # 强制使用 asyncpg，避免加载 psycopg2
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=AsyncSession
    )

Base = declarative_base()

# --------------------------
# 2. 数据表模型
# --------------------------
class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String)
    metric = Column(String)
    value = Column(Integer)
    message = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

# --------------------------
# 3. FastAPI 应用与路由
# --------------------------
app = FastAPI()

# 静态文件与模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库会话依赖（异步/同步兼容）
async def get_db():
    if isinstance(engine, create_async_engine):
        async with SessionLocal() as session:
            yield session
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

# 首页
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 创建告警（异步）
@app.post("/alerts/")
async def create_alert(
    hostname: str,
    metric: str,
    value: int,
    message: str,
    db: AsyncSession = Depends(get_db)
):
    new_alert = Alert(
        hostname=hostname,
        metric=metric,
        value=value,
        message=message
    )
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    
    return {
        "success": True,
        "message": "告警记录已保存",
        "alert_id": new_alert.id,
        "data": {
            "hostname": hostname,
            "metric": metric,
            "value": value
        }
    }

# 查询所有告警（异步）
@app.get("/alerts/")
async def read_alerts(db: AsyncSession = Depends(get_db)):
    if isinstance(engine, create_async_engine):
        result = await db.execute(select(Alert).order_by(Alert.created_at.desc()))
        alerts = result.scalars().all()
    else:
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
    
    result_list = []
    for alert in alerts:
        result_list.append({
            "id": alert.id,
            "hostname": alert.hostname,
            "metric": alert.metric,
            "value": alert.value,
            "message": alert.message[:50] + "..." if len(alert.message) > 50 else alert.message,
            "created_at": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {
        "count": len(result_list),
        "alerts": result_list
    }

# 告警搜索接口（异步）
@app.get("/alerts/search")
async def search_alerts(
    hostname: str = None,
    start_time: str = None,
    end_time: str = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Alert)
    
    if hostname:
        query = query.filter(Alert.hostname.like(f"%{hostname}%"))
    
    if start_time:
        start_dt = dt.strptime(start_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at >= start_dt)
    
    if end_time:
        end_dt = dt.strptime(end_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at <= end_dt)
    
    query = query.order_by(Alert.created_at.desc())
    
    if isinstance(engine, create_async_engine):
        result = await db.execute(query)
        alerts = result.scalars().all()
    else:
        alerts = db.query(Alert).from_statement(query).all()
    
    result_list = []
    for alert in alerts:
        result_list.append({
            "id": alert.id,
            "hostname": alert.hostname,
            "metric": alert.metric,
            "value": alert.value,
            "message": alert.message[:50] + "..." if len(alert.message) > 50 else alert.message,
            "created_at": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {
        "count": len(result_list),
        "alerts": result_list
    }

# 关键：暴露 app 实例给 Vercel 运行时
app = app