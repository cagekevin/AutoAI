import sqlite3
import threading
import hashlib
import os
import logging
from datetime import datetime

class TaskLedger:
    def __init__(self, db_path="history.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化全局账本数据库，如果不存在则自动创建"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 创建核心台账表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS global_tasks (
                    task_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    image_path TEXT,
                    status TEXT NOT NULL,
                    engine_used TEXT,
                    update_time TEXT
                )
            ''')
            conn.commit()
            conn.close()

    def _generate_task_id(self, prompt, image_path):
        """生成唯一任务指纹：提示词 + 垫图路径 的 MD5"""
        raw_str = f"{str(prompt).strip()}||{str(image_path).strip()}"
        return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

    def check_task_completed(self, prompt, image_path=""):
        """
        查账接口：这个任务（同样的提示词+同样的垫图）以前有没有成功跑完过？
        返回: (是否成功: bool, 是哪个引擎跑的: str)
        """
        task_id = self._generate_task_id(prompt, image_path)
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT status, engine_used FROM global_tasks WHERE task_id = ?', (task_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and "成功" in result[0]:
                return True, result[1]
            return False, ""

    def record_task(self, prompt, image_path, status, engine_used):
        """
        记账接口：引擎跑完后，无论成功失败，向总台账汇报结果
        """
        task_id = self._generate_task_id(prompt, image_path)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 使用 REPLACE 语法：如果 task_id 存在就覆盖更新（比如之前失败了，这次成功了），不存在就插入
            cursor.execute('''
                REPLACE INTO global_tasks (task_id, prompt, image_path, status, engine_used, update_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, prompt, image_path, status, engine_used, now_str))
            conn.commit()
            conn.close()
            logging.info(f"📓 [全局账本] 记录已更新: [{engine_used}] 状态-> {status} | 提示词缩略-> {prompt[:10]}...")

# 实例化全局单例
ledger = TaskLedger()

# ==========================================
# 🧪 沙盒验证测试区 (仅直接运行此文件时触发)
# ==========================================
if __name__ == "__main__":
    # 配置基础日志方便看测试结果
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("====================================")
    print("🛠️ 欢迎来到全局账房沙盒推演系统")
    print("====================================\n")

    test_prompt = "一个赛博朋克武士在雨中"
    test_img = "001.jpg"

    # 1. 模拟 Flow 拿到任务前，先去查账
    is_done, who_did_it = ledger.check_task_completed(test_prompt, test_img)
    print(f"🧐 Flow 查账结果: 此任务是否做过？ -> {is_done}")

    # 2. 模拟即梦跑完了这个任务，并登记造册
    print("\n🚀 模拟 Jimeng 正在疯狂产出...")
    ledger.record_task(test_prompt, test_img, status="全部成功", engine_used="jimeng")
    
    # 3. 模拟 Flow 再次拿到同样的任务（或者第二天再跑这个表格）
    print("\n🧐 第二天，Flow 再次拿到了相同的提示词，再去查账...")
    is_done_again, who_did_it_again = ledger.check_task_completed(test_prompt, test_img)
    
    if is_done_again:
        print(f"✅ 拦截成功！查账发现这个任务已经被 [{who_did_it_again}] 做过了，Flow 将直接跳过！")
    else:
        print("❌ 拦截失败！逻辑有 Bug！")
        
    print("\n🎉 沙盒测试完毕！你可以用 DB 浏览工具查看根目录生成的 history.db 文件。")