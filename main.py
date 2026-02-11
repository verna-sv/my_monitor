from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, or_, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
import datetime
from datetime import datetime as dt

# 1. 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./monitor.db"
# 新增 check_same_thread=False 解决SQLite线程问题
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. 定义数据表结构
class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String)
    metric = Column(String)
    value = Column(Integer)
    message = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

# 3. 创建数据库表
Base.metadata.create_all(bind=engine)

# 4. 创建FastAPI应用
app = FastAPI()

# 静态文件和模板配置
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 5. 根路径：返回前端页面
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 依赖函数：获取数据库连接
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 6. 创建告警接口
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

# 7. 查询所有告警接口
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

# 阶段二新增：告警搜索接口
@app.get("/alerts/search")
def search_alerts(
    hostname: str = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db)
):
    # 初始化查询
    query = db.query(Alert)
    
    # 1. 主机名模糊搜索
    if hostname:
        query = query.filter(Alert.hostname.like(f"%{hostname}%"))
    
    # 2. 时间范围筛选
    if start_time:
        # 转换前端传入的 datetime-local 格式（YYYY-MM-DDTHH:MM）为 datetime 对象
        start_dt = dt.strptime(start_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at >= start_dt)
    
    if end_time:
        end_dt = dt.strptime(end_time, "%Y-%m-%dT%H:%M")
        query = query.filter(Alert.created_at <= end_dt)
    
    # 执行查询并按时间倒序排序
    alerts = query.order_by(Alert.created_at.desc()).all()
    
    # 格式化返回结果
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
    app=app