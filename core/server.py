import os
import json
import logging
import asyncio
import shutil
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AutoAI Control Center")

# ================= 🚀 新增：解除 CORS 跨域封锁 =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源（本地开发最省事），或者填入 "chrome-extension://你的插件ID"
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有请求方法 (POST, GET 等)
    allow_headers=["*"],  # 允许所有请求头
)

# ================= 🚀 核心优化：网络层强缓存压制 =================
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/Downloads/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response

# ================= 🚀 日志喇叭 =================
class WebSocketLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.websockets = []
        self.main_loop = None

    def emit(self, record):
        log_entry = self.format(record)
        if self.main_loop and self.main_loop.is_running():
            # [Fix: 浅拷贝遍历，防止 WebSocket 断开时修改列表导致迭代器崩溃]
            for ws in self.websockets.copy():
                try:
                    asyncio.run_coroutine_threadsafe(ws.send_text(log_entry), self.main_loop)
                except Exception:
                    pass

# 🛡️ [Fix: 日志健壮性] 在创建文件日志前物理确保 logs 目录存在，杜绝 FileNotFoundError 导致整个服务器无法启动
os.makedirs("logs", exist_ok=True)

ws_handler = WebSocketLogHandler()
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    handlers=[logging.FileHandler("logs/sys_logs.log"), logging.StreamHandler(), ws_handler])

# ================= 🚀 召唤大管家 =================
from core.task_runner import runner

os.makedirs("assets/references", exist_ok=True)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

os.makedirs("Downloads", exist_ok=True)
app.mount("/Downloads", StaticFiles(directory="Downloads"), name="Downloads")

templates = Jinja2Templates(directory="templates")

# ================= 🚀 数据传输模型 =================
class DayModeRequest(BaseModel):
    engine: str
    prompts: List[str]
    image_name: str = ""
    image_names: List[str] = []
    aspect_ratio: str = ""
    inject_dna: bool = False

class RemoveTaskRequest(BaseModel):
    task_name: str

class TaskActionRequest(BaseModel):
    task_name: str

# [新增：Webhook 专属包裹]
class WebhookPayload(BaseModel):
    payload: str

# ================= 🚀 核心 API 路由 =================

@app.get("/")
async def get_index(request: Request):
    with open("config.json", "r", encoding="utf-8") as f:
        config_str = f.read()
    return templates.TemplateResponse(request, "index.html", {"config_str": config_str})

@app.get("/api/status")
async def get_status():
    return {
        "is_running": runner.is_running,
        "current_mode": getattr(runner, 'current_mode', 'idle'),  
        "current_task": getattr(runner, 'current_task', None), 
        "queue_count": len(getattr(runner, 'day_queue', [])), 
        "total_history": getattr(runner, 'total_count', 0)   
    }

@app.get("/api/queue")
async def get_queue():
    return {
        "current_task": getattr(runner, 'current_task', None),
        "pending": getattr(runner, 'day_queue', [])
    }

@app.post("/api/start_day_mode")
def start_day(req: DayModeRequest):
    # 兼容：image_names 优先（多图），缺省回退到旧的单图 image_name
    image_names = req.image_names or ([req.image_name] if req.image_name else [])
    success, msg = runner.start_day_queue(
        prompts=req.prompts, 
        site_name=req.engine, 
        image_name=image_names[0] if image_names else "",
        image_names=image_names,
        aspect_ratio=req.aspect_ratio, 
        inject_dna=req.inject_dna
    )
    return {"status": "success" if success else "error", "msg": msg}

@app.post("/api/remove_task")
def remove_task(req: RemoveTaskRequest):
    success, msg = runner.remove_from_queue(req.task_name)
    return {"status": "success" if success else "error", "msg": msg}

@app.post("/api/clear_queue")
def clear_queue():
    success, msg = runner.clear_all_queue()
    return {"status": "success" if success else "error", "msg": msg}

@app.post("/api/stop")
async def stop_all():
    success, msg = runner.stop_task()
    return {"status": "success" if success else "error", "msg": msg}

@app.post("/api/confirm_resume")
async def confirm():
    success, msg = runner.confirm_resume()
    return {"status": "success" if success else "error", "msg": msg}

@app.get("/api/images")
async def get_images():
    path = "assets/references"
    imgs = [f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    return {"status": "success", "images": imgs}

@app.post("/api/upload")
def upload_image(file: UploadFile = File(...)):
    try:
        file_path = f"assets/references/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        return {"status": "error", "msg": f"上传失败: {e}"}

@app.post("/api/save_config")
async def save_config(new_config: dict):
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        return {"status": "success", "msg": "配置保存成功！"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_handler.websockets.append(websocket)
    ws_handler.main_loop = asyncio.get_running_loop()
    try:
        while True: await websocket.receive_text()
    except:
        if websocket in ws_handler.websockets: ws_handler.websockets.remove(websocket)

@app.post("/api/move_to_top")
async def move_to_top(req: TaskActionRequest):
    success, msg = runner.move_task_to_top(req.task_name)
    return {"status": "success" if success else "error", "msg": msg}

@app.post("/api/toggle_pause")
async def toggle_pause():
    success, msg = runner.toggle_soft_pause()
    return {"status": "success" if success else "error", "msg": msg}

# ================= 🚀 Webhook 接收专线 (导演分镜流入口) =================
@app.post("/api/batch_generate")
async def batch_generate(req: WebhookPayload):
    try:
        # 1. 解析 Chrome 插件丢过来的 JSON 字符串
        prompts_list = json.loads(req.payload)
        
        # 2. 提取所有的英文 prompt (加了一层 isinstance 安全防护，防脏数据)
        only_prompts = [item.get("prompt") for item in prompts_list if isinstance(item, dict) and item.get("prompt")]
        
        if not only_prompts:
            return {"status": "error", "msg": "未在 payload 中提取到任何合法的 prompt 字段！"}
            
        # 3. 完美复用现有的排队系统，开始让 Python 排队干活！
        success, msg = runner.start_day_queue(
            prompts=only_prompts,
            auto_start=False     # 🛡️ 安全插销：仅入队，坚决不点火！
        )
        
        return {"status": "success", "msg": f"已静默送入大厅！请在控制台核验后手动启动。({msg})"}
    except json.JSONDecodeError:
        return {"status": "error", "msg": "Python解析 JSON 失败，请检查大模型吐出的是否是纯正 JSON 数组"}
    except Exception as e:
        return {"status": "error", "msg": f"批量入库失败: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)