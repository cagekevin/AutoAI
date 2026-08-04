import queue
import threading
import logging
import json
import io
import os
from PIL import Image
from PIL.PngImagePlugin import PngInfo

class ImageProcessor:
    def __init__(self):
        # 建立线程安全的任务传送带
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.lock = threading.Lock()

    def start(self):
        """启动后台贴标线程"""
        with self.lock:
            if not self.is_running:
                self.is_running = True
                # daemon=True 表示当主程序崩溃时，它不会阻止程序退出
                self.worker_thread = threading.Thread(target=self._process_worker, daemon=True, name="ImageProcessor-Worker")
                self.worker_thread.start()
                logging.info("🏭 [独立打标车间] 异步图像处理后台线程已启动！")

    def _process_worker(self):
        """后台静默打工小哥的死循环"""
        while True:
            # 从传送带拿任务，如果没有就会在这里安静地挂起（不占CPU）
            task = self.task_queue.get()
            
            # 收到毒药丸（None），准备下班
            if task is None: 
                self.task_queue.task_done()
                break
            
            save_path, image_source, dna_dict = task
            try:
                metadata = PngInfo()
                if dna_dict:
                    # 移除 ensure_ascii=False，强制 JSON 转义中文为 \uXXXX 格式的纯 ASCII
                    metadata.add_text("parameters", json.dumps(dna_dict))

                # 💡 核心：如果传入的是纯内存流(bytes)，直接使用 BytesIO
                if isinstance(image_source, bytes):
                    img = Image.open(io.BytesIO(image_source))
                else:
                    # 🪓 剃刀终极版：彻底杜绝 Windows 文件占用锁！
                    # 一次性将硬盘文件吸入内存变 bytes，瞬间物理释放文件句柄！
                    with open(image_source, "rb") as f:
                        file_bytes = f.read()
                    img = Image.open(io.BytesIO(file_bytes))

                # 💡 核心：因为文件连接已彻底断开，此时同名覆盖写入 100% 安全！
                img.save(save_path, pnginfo=metadata)
                
                # ====================================================
                # 🦅 [融入点] Eagle 双写同步引擎 (零依赖原生 HTTP)
                # ====================================================
                if dna_dict:
                    try:
                        import urllib.request
                        
                        # 1. 解析 DNA 提取 Eagle 需要的标签和注释
                        meta = dna_dict.get("Metadata", {})
                        dicts = dna_dict.get("Deep_Dictionary", [])
                        
                        eagle_annotation = meta.get("Image_Prompt", "")
                        eagle_tags = []
                        
                        # 把分组作为标签
                        if meta.get("Preset_Group") and meta.get("Preset_Group") != "nan":
                            eagle_tags.append(meta.get("Preset_Group"))
                        
                        # 把特征词典里的中文词汇全部作为标签
                        for d in dicts:
                            name = d.get("Disp (中文名)") or d.get("命中词") or ""
                            if name and name != "nan":
                                eagle_tags.append(name)
                        
                        # 2. 组装发给 Eagle 的数据包 (必须使用绝对路径)
                        eagle_payload = {
                            "path": os.path.abspath(save_path),
                            "name": os.path.basename(save_path),
                            "annotation": eagle_annotation,
                            "tags": eagle_tags
                        }
                        
                        # 3. 呼叫 Eagle 本地 API
                        req = urllib.request.Request(
                            'http://localhost:41595/api/item/addFromPath', 
                            data=json.dumps(eagle_payload).encode('utf-8'),
                            headers={'Content-Type': 'application/json'}
                        )
                        with urllib.request.urlopen(req, timeout=3) as response:
                            eagle_res = json.loads(response.read().decode('utf-8'))
                            if eagle_res.get("status") == "success":
                                logging.info(f"   -> 🦅 [Eagle 同步] 已成功归档并注入搜索标签！")
                            else:
                                logging.warning(f"   -> 🦅 [Eagle 警告] Eagle 返回失败: {eagle_res}")
                                
                    except Exception as eagle_err:
                        # 柔性降级：哪怕 Eagle 没开，或者同步失败，绝对不能影响主流程的运行！
                        logging.warning(f"   -> 🦅 [Eagle 旁路异常] 推送失败 (Eagle是否未打开?): {eagle_err}")
                # ====================================================

                # [Fix: 修复白天模式下打标车间假报"DNA已注入"的日志逻辑缺陷]
                if dna_dict:
                    logging.info(f"   -> 🧬 [后台静默落库] 极速写入完成，DNA已注入: {os.path.basename(save_path)}")
                else:
                    logging.info(f"   -> 💾 [后台静默落库] 极速写入完成，纯净出图: {os.path.basename(save_path)}")

            except Exception as e:
                logging.error(f"   -> ⚠️ [后台车间报错] 图像处理/写入失败 ({os.path.basename(save_path)}): {e}")
            finally:
                # 无论成功失败，告诉传送带：这个任务干完了
                self.task_queue.task_done()

    def submit_task(self, save_path, image_source, dna_dict=None):
        """
        前台引擎专用 API：把任务扔上传送带，秒脱手
        """
        if not self.is_running:
            self.start()
        # 将任务打包放进队列
        self.task_queue.put((save_path, image_source, dna_dict))

    def wait_and_stop(self):
        """
        🪓 剃刀修复：优雅等待（放弃杀线程）
        """
        if self.is_running:
            logging.info("🏭 [独立打标车间] 正在确认传送带上的余留图片已全部注入 DNA...")
            self.task_queue.join() # 极其简单：只要等到队列空了就行，打工小哥继续回去睡觉，不用杀他。
            logging.info("🏭 [独立打标车间] 所有残余任务清理完毕！")

# 实例化为全局单例，所有引擎共用这一个车间
processor = ImageProcessor()