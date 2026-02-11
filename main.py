from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
import datetime
from datetime import datetime as dt
import os

# --------------------------
# 1. 数据库配置（同步模式）
# --------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 本地开发：SQLite
    SQLALCHEMY_DATABASE_URL = "sqlite:///./monitor.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # 生产环境：PostgreSQL，强制使用 psycopg2-binary
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # 明确指定使用 psycopg2 驱动
    engine = create_engine(
        DATABASE_URL,
        client_encoding="utf8"
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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

# 创建表结构
Base.metadata.create_all(bind=engine)

# --------------------------
# 3. FastAPI 应用与路由
# --------------------------
app = FastAPI()

# 静态文件与模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 数据库会话依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 首页
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 创建告警
@app.post("/alerts/")
def create_alert(
    hostname: str,
    metric: str,
    value: int,
    message: str,
    db: Session = Depends(get_db)
):
    new_alert = Alert(
        hostname=hostname,
        metric=metric,
        value=value,
        message=message
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    
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

# 查询所有告警
@app.get("/alerts/")
def read_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
    
    result = []
    for alert in alerts:
        result.append({
            "id": alert.id,
            "hostname": alert.hostname,
            "metric": alert.metric,
            "value": alert.value,
            "message": alert.message[:50] + "..." if len(alert.message) > 50 else alert.message,
            "created_at": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {
        "count": len(result),
        "alerts": result
    }

# 告警搜索接口
@app.get("/alerts/search")
def search_alerts(
    hostname: str = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Alert)
    
    if hostname:
        query = query.filter(Alert.hostname.like(f"%{hostname}%"))
    
    if start_time:
        start_dt = dt.strptime(start_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at >= start_dt)
    
    if end_time:
        end_dt = dt.strptime(end_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at <= end_dt)
    
    alerts = query.order_by(Alert.created_at.desc()).all()
    
    result = []
    for alert in alerts:
        result.append({
            "id": alert.id,
            "hostname": alert.hostname,
            "metric": alert.metric,
            "value": alert.value,
            "message": alert.message[:50] + "..." if len(alert.message) > 50 else alert.message,
            "created_at": alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {
        "count": len(result),
        "alerts": result
    }

# 暴露 app 实例
app = app