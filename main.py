import os
import uvicorn

def init_environment():
    """
    环境预热：系统启动前，物理创建所有必须的基建目录，
    彻底杜绝因为找不到文件夹导致的报错。
    """
    directories = [
        "logs",
        "assets/references",
        "Downloads",
        "core",
        "plugins" 
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

if __name__ == "__main__":
    # 1. 预建目录
    init_environment()
    
    # 2. 打印启动横幅
    print("=================================================================")
    print("🚀 AutoAI Control Center - 极简单机产图兵工厂已就绪")
    print("🌐 调度面板请在浏览器中访问: http://127.0.0.1:8000")
    print("🛑 停止程序请直接在此窗口按 Ctrl+C")
    print("=================================================================\n")
    
    # 3. 启动 FastAPI 服务器
    # 这里的 "core.server:app" 指的是读取 core 文件夹下 server.py 里的 app 对象
    uvicorn.run("core.server:app", host="127.0.0.1", port=8000, reload=False, access_log=False)