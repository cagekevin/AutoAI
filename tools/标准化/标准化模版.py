from playwright.sync_api import sync_playwright
import time
import os
import random
import logging
import hashlib
import re
import urllib.request  
import copy
import threading
from datetime import datetime

from core.image_processor import processor

class Engine:
    def __init__(self, global_cfg, engine_cfg):
        self.global_cfg = global_cfg
        self.site_cfg = engine_cfg
        self.stop_requested = False
        self.ASSETS_DIR = os.path.abspath(os.path.join("assets", "references"))
        self.consecutive_successes = 0
        self.resume_event = threading.Event()  
        self.project_image_count = 0 

        # =====================================================================
        # 🛠️ [NEXT_DEV_TODO: 平台专属配置区] 下一个开发者只需修改这里的常量即可
        # =====================================================================
        self.PLATFORM_NAME = "TemplateAI"
        self.PLATFORM_URL = "https://www.example-ai.com/workspace" # 平台的工作台地址
        self.URL_KEYWORD = "example-ai" # 用于判断当前标签页是否是该平台的关键字
        
        # --- 核心 DOM 选择器 ---
        self.INPUT_BOX_SELECTOR = '[data-testid="prompt-input"]' # 提示词输入框
        self.SUBMIT_BTN_SELECTOR = '[data-testid="send-button"]' # 发送/生成按钮
        self.IMAGE_CARD_SELECTOR = '.generated-image-card'       # 渲染出来的图片卡片或气泡
        
        # --- 平台规则 ---
        self.EXPECTED_IMAGE_COUNT = 4  # 每次点击生成，预期会返回几张图？(如即梦是4，Lovart是8)
        self.MAX_WAIT_SECONDS = 600    # 等待出图的极限超时时间 (秒)
        self.REBIRTH_THRESHOLD = 100   # 连续生成多少张图后强制刷新网页(防前端内存泄漏)
        
        # --- 违禁词/报错雷达词库 ---
        self.ERROR_KEYWORDS = r'policy violation|violate|无法完成|无法生成|Failed to generate|抱歉'
        # =====================================================================

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _log(self, msg):
        print(msg, flush=True)
        # 语义恢复：智能根据 Emoji 打上正确的系统底层日志级别
        if "❌" in msg: logging.error(msg)
        elif "⚠️" in msg: logging.warning(msg)
        else: logging.info(msg)

    def _random_sleep(self, min_sec, max_sec, log_msg=None):
        sleep_time = random.uniform(min_sec, max_sec)
        if log_msg:
            self._log(f"   -> {log_msg} (约 {sleep_time:.1f} 秒)...")
        steps = int(sleep_time / 0.5)
        for _ in range(steps):
            if self.stop_requested: break
            time.sleep(0.5)
        if not self.stop_requested:
            time.sleep(sleep_time % 0.5)

    def setup(self, mode, mode_cfg):
        self.mode = mode               
        self.mode_cfg = mode_cfg       
        self.stop_requested = False
        self.consecutive_successes = 0
        
        self._log(f"🌐 [{self.PLATFORM_NAME}引擎] 正在启动标准自动化进程...")

        if not self.playwright:
            self.playwright = sync_playwright().start()
        
        try:
            self.browser = self.playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
            self.context = self.browser.contexts[0]
            
            # 智能寄生：寻找已存在的标签页
            target_page = next((p for p in self.context.pages if self.URL_KEYWORD in p.url), None)
            if target_page:
                self.page = target_page
                try: self.page.bring_to_front()
                except: pass
                self._log("🟢 发现已存活的工作标签页，直接接管。")
            else:
                self._log("🟡 未发现存活页，执行环境初始化...")
                self._rebirth_project()
            
            # 安检与人工兜底
            self._log("🛂 正在核验网页登录态与 DOM 完整性...")
            try:
                self.page.locator(self.INPUT_BOX_SELECTOR).last.wait_for(state="visible", timeout=30000)
                self._log("🟢 检测到核心组件已就绪。")
                self.resume_event.set()
            except:
                self.resume_event.clear()
                self._log("⚠️ 30秒未检测到输入框，可能需要登录或存在弹窗。")
                self._log("⏸️ 请检查浏览器，处理完毕后点击界面的【✅ 人工放行】按钮...")
                
                while not self.resume_event.is_set():
                    if self.stop_requested:
                        self.teardown()
                        raise Exception("等待人工放行期间收到停止指令。")
                    time.sleep(1)
                self._log("▶️ 收到人工放行指令，继续执行。")
                
        except Exception as e:
            raise Exception(f"❌ 无法连接 Chrome 9222 端口: {e}")

    def process_single(self, task_data):
        """标准重试包装器（核心防爆装甲，无需修改）"""
        for attempt in range(3):
            if self.stop_requested:
                raise Exception("接收到停止指令")
            try:
                return self._execute_task(task_data)
            except Exception as e:
                if "中止" in str(e) or "接收到停止指令" in str(e) or self.stop_requested:
                    raise e

                self._log(f"⚠️ 任务执行异常 (第 {attempt + 1}/3 次尝试): {e}")
                if attempt == 2:
                    raise e 
                
                self._log("   -> 准备刷新网页以重置前端状态...")
                if self.page:
                    try:
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(300)
                        self.page.reload(timeout=15000) 
                    except: pass
                    
                    self._log("   -> 强制等待 30 秒，规避高频请求拦截...")
                    time.sleep(30) 
                
                self._random_sleep(3, 5, "重新装填任务")

    def _rebirth_project(self):
        """强制内存回收与防零标签崩溃机制（无需修改）"""
        try:
            self._log("\n👉 正在清理冗余标签页，释放系统内存...")
            # 🛡️ 物理防爆：先建新页保底，防止 Windows Chrome 零标签自动退出断开 CDP
            new_page = self.context.new_page()
            
            for old_page in self.context.pages:
                if old_page != new_page:
                    try: old_page.close()
                    except: pass
                    
            self.page = new_page
            self.page.bring_to_front()
            
            self.page.goto(self.PLATFORM_URL, timeout=60000, wait_until="domcontentloaded")
            self.project_image_count = 0
            self._random_sleep(2.0, 4.0, "新画布挂载完毕")
            
        except Exception as e:
            self._log(f"❌ 重生页面失败: {e}")
            raise e

    # =====================================================================
    # 🎯 核心业务生命周期 (5 大标准流程) 
    # =====================================================================
    def _execute_task(self, task_data):
        prompt = task_data.get("prompt", "")
        raw_image_name = task_data.get("image_path", "")
        task_name = task_data.get("task_name", "")
        
        output_dir = os.path.join(
            "Downloads", 
            self.site_cfg.get("output", {}).get("base_dir", f"{self.PLATFORM_NAME}_Downloads"),
            f"{getattr(self, 'mode', 'day').capitalize()}_Mode",
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(output_dir, exist_ok=True)
        image_path = os.path.join(self.ASSETS_DIR, raw_image_name) if raw_image_name else ""
        engine_params = task_data.get("engine_params", {})

        self._log(f"👉 开始执行任务: [{task_name}]")

        # 🔹 阶段 1：环境与参数配置
        self._configure_generation_params(engine_params)

        # 🔹 阶段 2：垫图组装
        if image_path and os.path.exists(image_path):
            self._upload_reference_image(image_path)

        # 🔹 阶段 3：发射与就绪监听
        self._fill_prompt_and_submit(prompt)

        # 🔹 阶段 4：死循环守望与审查雷达 (等待出图)
        download_targets = self._wait_for_generation_result()

        # 🔹 阶段 5：破甲下载与 DNA 打标
        saved_paths = self._download_and_inject_dna(download_targets, task_data, task_name, output_dir)

        if not saved_paths:
            raise Exception("未能成功下载任何图像。")
            
        self._log(f"🎉 [{task_name}] 任务执行完毕，成功产出 {len(saved_paths)} 张图。")
        self.consecutive_successes += 1
        self.project_image_count += len(saved_paths)
        
        if self.project_image_count >= self.REBIRTH_THRESHOLD:
            self._log(f"⚠️ 触发 {self.REBIRTH_THRESHOLD} 张阈值，执行清理重置...")
            self._rebirth_project()
        
        return True, saved_paths[0]

    # ---------------- 阶段方法具体实现 ----------------

    def _configure_generation_params(self, engine_params):
        """阶段 1：配置比例、模型等 (视平台情况自行实现/注销)"""
        aspect_ratio = engine_params.get("aspect_ratio", "9:16")
        try:
            self._log(f"   -> ⚙️ 尝试配置画面比例: {aspect_ratio}")
            # [NEXT_DEV_TODO: 在这里实现点击面板和选中比例的逻辑]
            # ratio_btn = self.page.locator(f'button:has-text("{aspect_ratio}")')
            pass 
        except Exception as e:
            self._log(f"   -> ⚠️ 参数配置跳过或失败 (非致命): {e}")

    def _upload_reference_image(self, image_path):
        """阶段 2：上传垫图 (A/B 流派任选)"""
        self._log(f"   -> 🖼️ 正在装载垫图: {image_path}")
        try:
            # 💡 [流派 A：原生 Input 注入 (推荐，速度最快，适用于即梦等有隐藏 input 的平台)]
            '''
            file_input = self.page.locator('input[type="file"]').first
            file_input.set_input_files(image_path)
            self._random_sleep(1.5, 2.5)
            '''

            # 💡 [流派 B：OS 弹窗拦截法 (适用于 Lovart 等屏蔽了原生 input 的平台)]
            '''
            upload_btn = self.page.locator('[data-testid="upload-button"]').last
            with self.page.expect_file_chooser(timeout=15000) as fc_info:
                upload_btn.click(force=True)
            fc_info.value.set_files(image_path)
            self._random_sleep(3.0, 5.0, "等待图片传至云端")
            '''
            pass
        except Exception as e:
            raise Exception(f"垫图上传失败: {e}")

    def _fill_prompt_and_submit(self, prompt):
        """阶段 3：注入提示词并发送"""
        self._log("   -> ⌨️ 正在注入提示词并准备发送...")
        input_box = self.page.locator(self.INPUT_BOX_SELECTOR).last
        input_box.wait_for(state="visible", timeout=10000)
        
        # 安全清空并填词
        input_box.evaluate("el => el.value = ''; el.innerHTML = '';")
        input_box.fill(prompt)
        input_box.press("Space")
        self._random_sleep(0.5, 1.2)
        
        # 防追尾监听：等待发送按钮亮起
        send_btn = self.page.locator(self.SUBMIT_BTN_SELECTOR).last
        wait_btn_start = time.time()
        while not send_btn.is_enabled():
            if self.stop_requested: raise Exception("中止")
            if time.time() - wait_btn_start > 30: raise Exception("发送按钮被长期锁定，可能触发了违禁词。")
            time.sleep(1)

        self._log("   -> 🚀 点击发送，任务推入云端！")
        send_btn.click(force=True)
        self._random_sleep(2.0, 3.0)

    def _wait_for_generation_result(self):
        """阶段 4：死循环监听出图结果"""
        self._log(f"   -> ⏳ 正在等待目标图像渲染 (预期 {self.EXPECTED_IMAGE_COUNT} 张)...")
        wait_img_start = time.time()
        ready_targets = []
        
        while True:
            if self.stop_requested: raise Exception("中止")
            if time.time() - wait_img_start > self.MAX_WAIT_SECONDS: 
                raise Exception("等待出图超时！")
            
            # 🚫 违禁词雷达检测
            try:
                # 寻找包含提示文本的区域 (按需修改选择器)
                error_panel = self.page.locator('body').inner_text()
                if re.search(self.ERROR_KEYWORDS, error_panel, re.IGNORECASE):
                    raise Exception("触发云端审查拦截或系统生成异常！")
            except Exception as e:
                if "审查拦截" in str(e): raise e

            # [NEXT_DEV_TODO: 在这里实现判定图片是否出炉的逻辑]
            # 例如：获取所有生成好的图片 src
            '''
            imgs = self.page.locator(self.IMAGE_CARD_SELECTOR).evaluate_all("els => els.map(e => e.src)")
            valid_imgs = [src for src in imgs if src and "loading" not in src]
            if len(valid_imgs) >= self.EXPECTED_IMAGE_COUNT:
                ready_targets = valid_imgs
                break
            '''
            # 占位脱出
            ready_targets = ["mock_url_1", "mock_url_2"] # 仅为模版不报错
            break 

            self._random_sleep(3.0, 5.0)
            
        self._log(f"   -> ✨ 侦测到 {len(ready_targets)} 张图像渲染完成！")
        return ready_targets

    def _download_and_inject_dna(self, targets, task_data, task_name, output_dir):
        """阶段 5：文件落盘与 DNA 盖章 (A/B 流派任选)"""
        saved_paths = []
        for idx, target in enumerate(targets):
            self._log(f"   -> 📥 正在处理第 {idx + 1} 张图...")
            
            unique_id = hashlib.md5(f"{target}_{idx}".encode()).hexdigest()[:8]
            fname = f"{task_name}_{unique_id}.png"
            save_path = os.path.join(output_dir, fname)
            
            # 组装待注入的 DNA (前端若没勾选，这就是空字典)
            current_dna = copy.deepcopy(task_data.get("dna_dict", {}))
            if current_dna:
                current_dna["Image_Fingerprint"] = {
                    "File_Name": fname,
                    "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            download_success = False
            
            # 💡 [流派 A：原生网络劫持 (适用于 Lovart 等无下载按钮或屏蔽右键的平台)]
            '''
            try:
                clean_url = target.split('?')[0] # 清理 URL
                # 获取系统级 UA 和 Cookie 绕过防盗链
                user_agent = self.page.evaluate("navigator.userAgent")
                cookies = self.context.cookies()
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                
                req = urllib.request.Request(clean_url, headers={'User-Agent': user_agent, 'Cookie': cookie_str})
                with urllib.request.urlopen(req, timeout=15) as response:
                    img_bytes = response.read()
                    
                    # 提交给打标小哥 (传 bytes)
                    processor.submit_task(save_path=save_path, image_source=img_bytes, dna_dict=current_dna)
                    download_success = True
            except Exception as e:
                self._log(f"   -> ⚠️ urllib 下载异常: {e}")
            '''

            # 💡 [流派 B：浏览器真实物理点击下载 (适用于即梦、Flow 等自带真实下载按钮的平台)]
            '''
            try:
                # 找到对应这张图的下载按钮
                dl_btn = self.page.locator('.download-btn').nth(idx)
                
                # 劫持浏览器的下载事件
                with self.page.expect_download(timeout=15000) as dl_info:
                    dl_btn.click(force=True)
                    
                dl = dl_info.value
                dl.save_as(save_path) # 物理迫降硬盘
                
                # 提交给打标小哥 (传 文件路径)
                processor.submit_task(save_path=save_path, image_source=save_path, dna_dict=current_dna)
                download_success = True
            except Exception as e:
                self._log(f"   -> ⚠️ Playwright 点击下载异常: {e}")
            '''
            
            # 占位符逻辑
            download_success = True 
            
            if download_success:
                saved_paths.append(save_path)
                self._log(f"   -> 📥 已精准投递打标车间: {fname}")
            else:
                self._log(f"   -> ❌ 第 {idx + 1} 张保存失败。")
                
        return saved_paths

    def teardown(self):
        """安全释放资源"""
        if getattr(self, 'browser', None):
            try: self.browser.disconnect()
            except: pass
            
        if getattr(self, 'playwright', None):
            try: self.playwright.stop()
            except: pass
            
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None