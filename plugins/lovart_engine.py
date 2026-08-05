import os
import time
import random
import re
import hashlib
from datetime import datetime
from .base_engine import BaseAIEngine, TaskPayload

class LovartEngine(BaseAIEngine):
    """
    Lovart 平台专属适配器 (HIL 极简交互层版)。
    """
    FORCE_NEW_PAGE = False  
    MAX_PROJECT_IMAGES = 480  
    MAX_WAIT_SEC = 3600  

    DEFAULT_PARAMS = {
        "mode": "图像|Image",
        "aspect_ratio": "9:16", 
        "resolution": "2K", 
        "model": "Nano Banana 2"
    }
    
    PARAM_ROUTING = {
        "model": "model_btn"
    }

    # 参数文本/值 -> DOM 锚点的转换器
    # - model: 模型下拉项的真实 data-testid 后缀 (精确防误配，避免选中 "Nano Banana 2 Lite")
    # - resolution / aspect_ratio: 面板内按钮的展示文本
    PARAM_FORMAT = {
        "model": {
            "Nano Banana 2": "vertex/nano-banana-2",
            "Nano Banana": "vertex/nano-banana",
            "Nano Banana Pro": "vertex/anon-bob",
            "GPT Image 2": "openai/gpt-image-2",
            "GPT Image 1.5": "openai/gpt-image-1-5",
            "GPT Image": "openai/gpt-image-1",
            "Flux 2 Pro": "fal/flux-2-pro",
            "Flux 2 Max": "fal/flux-2-max",
            "Seedream 5.0 Pro": "seedream/seedream-5-0-pro",
            "Seedream 4.5": "seedream/seedream-4-5",
            "Midjourney": "youchuan/midjourney",
            "Ideogram 4": "ideogram/ideogram-v4",
        },
    }

    IGNORE_UI_PARAMS = ["burst_count", "mode"]  

    URL_HOME = "https://www.lovart.ai/zh/home"  
    URL_CANVAS = "**/canvas?projectId=**"  
    
    UI = {
        "new_proj_btn": 'a[data-testid="lovart-nav-create-project"], a[href*="newProject=true"]:visible',
        "mode_btn": 'button[data-testid="agent-mode-switch-trigger"]',
        "mode_option": '[data-testid="agent-mode-switch-option-image"], [data-testid="agent-mode-switch-option-agent"], [data-testid="agent-mode-switch-option-chat"]', 
        "param_panel_trigger": 'button[data-testid="agent-image-generator-multi-params-button"]',
        "model_btn": 'button[data-testid="generator-model-button"], button[data-testid="agent-generator-model-button"]',  
        "defocus_area": '#agent-chat-title',  
        "upload_btn": '.no-scrollbar div[aria-haspopup="dialog"]:has-text("参考图")',
        "local_upload_option": 'span.lo-menu-item-text:has-text("从本地上传图片"), button:has-text("从本地上传")',
        "input_box": '#agent-image-generator-prompt',
        "submit_btn": '[data-testid="agent-image-generator-submit-button"], [data-testid="agent-send-button"]',
        "bubble": '[data-testid="agent-message"]',
        "bubble_img": 'img.object-cover, img.ant-image-img',
        "canvas_clean_img": '.tl-canvas img[src*="{file_id}"]'
    }

    def action_init_workspace(self):
        try:
            self._log("\n👉 [重生] 正在申请全新 Canvas 阵地...")
            self.page.goto(self.URL_HOME, timeout=50000)
            
            # 🌟 HIL 替换：安全点击新建按钮
            self._click(self.UI["new_proj_btn"])
            
            self.page.wait_for_url(self.URL_CANVAS, timeout=50000)
            self.project_image_count = 0  
            self.last_params = None      # 🚀 强制失忆：清空参数防抖记忆
            self.cached_img_path = None  # 🚀 强制失忆：清空垫图缓存记忆
            self.cached_img_paths = []   # 🚀 强制失忆：清空多图垫图缓存记忆
            self._log("   -> ✅ 涅槃成功，全新画布挂载完毕。")
        except Exception as e:
            raise Exception(f"项目涅槃遇阻: {e}")

    def _set_params_iteratively(self, payload: TaskPayload):
        """
        Lovart 专属参数装填 (子类重写，不动基类通用逻辑)。
        分两类处理，代码直白好维护：
          - model:         走 "generator-model-button" 按钮 -> 用精确 data-testid 选中
          - 其他 (分辨率/比例): 走 "multi-params" 按钮 -> 用文本 has_text 精确选中
        """
        default_params = getattr(self, 'DEFAULT_PARAMS', {})
        raw_params = {**default_params, **payload.get("engine_params", {})}

        # 1. 参数提纯：只保留真正需要去 UI 面板里点击的参数
        ignore_keys = set(getattr(self, 'IGNORE_UI_PARAMS', []))
        ui_params = {k: v for k, v in raw_params.items() if k not in ignore_keys}

        # 2. 绝对防抖：与上一轮完全一致则跳过 UI 交互
        if getattr(self, 'last_params', None) == ui_params:
            self._log("   -> ⚡ 参数配置与上一轮完全一致，触发防抖，跳过 UI 交互。")
            return

        self._log("   -> ⚙️ 启动 Lovart 标准化参数装填...")
        all_success = True
        model_map = getattr(self, 'PARAM_FORMAT', {}).get('model', {})

        for key, val in ui_params.items():
            try:
                if key == "model":
                    # --- 模型：精确 data-testid 防误配 (避免选成 "Nano Banana 2 Lite") ---
                    self._click(self.UI["model_btn"], index="last")
                    slug = model_map.get(val)
                    if not slug:
                        self._log(f"      ⚠️ 模型 [{val}] 未配置 PARAM_FORMAT 映射，跳过。")
                        all_success = False
                        self.page.keyboard.press("Escape")
                        continue
                    option = self.page.get_by_test_id(f"generator-model-option-{slug}").last
                    option.wait_for(state="visible", timeout=10000)
                    option.click(force=True)
                    self._log(f"      ✅ 选中模型: {val}")

                else:
                    # --- 分辨率/比例等文本参数：点参数面板，按文本精确选中 ---
                    self._click(self.UI["param_panel_trigger"], index="last")
                    # 文本按钮：分辨率 "512/1K/2K/4K"、比例 "16:9/9:16" 等，无子串冲突
                    option = self.page.locator("button").filter(
                        has_text=re.compile(rf"^\s*{re.escape(str(val))}\s*$", re.I)
                    ).last
                    option.wait_for(state="visible", timeout=10000)
                    option.click(force=True)
                    self._log(f"      ✅ 选中参数: {key} = {val}")

                # 收起面板/弹窗，回到干净画布
                if "defocus_area" in self.UI:
                    self._click(self.UI["defocus_area"])
                else:
                    self.page.keyboard.press("Escape")
                    self.page.mouse.click(0, 0)
                self._human_pause()

            except Exception as e:
                self._log(f"      ⚠️ 参数 [{key}={val}] 配置失败，跳过: {e}")
                all_success = False

        # 3. 事务提交：全对才写入记忆，否则物理失忆 (强制下轮重配)
        self.last_params = ui_params if all_success else None

    def _security_check(self):
        """
        Lovart 专属安检 (子类重写，不动基类通用逻辑)。
        核心放宽点：只要页面存在【Agent 输入框】或【图像模式输入框】任一种，即判定核心组件就绪，
        不再因为停留在 Agent 模式而误报"找不到输入框"卡住人工放行。
        """
        self._log("🛂 正在核验网页登录态与 DOM 完整性...")

        if hasattr(self, 'UI') and "popups" in self.UI:
            self._log("   -> 🧹 安检前置：清扫潜在的弹窗遮挡物...")
            self._clear_popups(self.UI["popups"])

        # Agent 输入框 与 图像模式输入框 任一存在即可
        input_selectors = [
            '#agent-lexical-mention-input',                 # Agent 模式 (Lexical 富文本)
            '[data-testid="agent-message-input"]',          # Agent 模式 (testid 兜底)
            '#agent-image-generator-prompt',                # 图像模式
            '[data-testid="agent-image-generator-prompt"]', # 图像模式 (testid 兜底)
        ]
        ready = False
        for sel in input_selectors:
            try:
                self.page.locator(sel).first.wait_for(state="visible", timeout=8000)
                ready = True
                break
            except Exception:
                continue

        if ready:
            self._log("🟢 检测到核心组件已就绪 (Agent 或 图像模式输入框)。")
            self.resume_event.set()
            return

        self.resume_event.clear()
        self._log("⚠️ 30秒内未检测到 Agent/图像模式输入框，可能需要登录或存在弹窗拦截。")
        self._log("⏸️ 请人工处理浏览器当前页面，完毕后点击控制台的【✅ 人工放行】...")
        while not self.resume_event.is_set():
            if self.stop_requested: raise Exception("人工放行期间收到中止指令。")
            time.sleep(1)
        self._log("▶️ 收到放行指令，引擎恢复运转。")

    def action_upload_image(self, payload: TaskPayload):
        self._smart_upload(payload, upload_style="os_dialog")

    def action_fill_and_submit(self, payload: TaskPayload):
        burst_count = int(payload.get("engine_params", {}).get("burst_count", 8))
        self.bubble_ids = []  
        prev_count = self.page.locator(self.UI["bubble"]).count()  

        self._log(f"   -> 🚀 启动 {burst_count} 连发装填管线...")
        for i in range(burst_count):
            if self.stop_requested: raise Exception("收到中止指令")
            
            # 去除强行洗白大脑的内鬼代码，将垫图全权交由父类智能调度
            self.action_upload_image(payload)
            
            # 🌟 HIL 替换：自带全选清空和拟人延迟的 _fill
            self._fill(self.UI["input_box"], payload["prompt"], index="last")
            self.page.keyboard.press("Space")  # 唤醒 Lovart 的 React 状态
            
            send_btn = self.page.locator(self.UI["submit_btn"]).last  
            wait_btn_start = time.time()
            
            # 🛡️ 装甲升级：用 while True + try 结构，硬抗 React 渲染时的 DOM 脱离报错
            while True:
                if time.time() - wait_btn_start > 90: 
                    raise Exception("发送按钮死锁，疑似垫图卡住 (已达 90 秒红线)")  
                try:
                    # 如果获取不到状态，或者节点正在重绘，这里会抛出异常，走到 except
                    if not send_btn.is_disabled():
                        break  # 按钮终于亮起，跳出循环准备开火
                except Exception:
                    pass  # 忽略瞬间的 DOM 闪烁脱离报错，坚定执行死等策略
                time.sleep(1)
                
            # 🌟 HIL 替换：安全开火
            self._click(send_btn) 
            
            # 🚀 子类专属物理同步：Lovart 点击发送后垫图会被平台吃掉，立刻洗白大脑通知父类
            self.cached_img_path = None
            self.cached_img_paths = []  # 多图垫图一并洗白，下次连发重新上传全部
            
            wait_bubble_start = time.time()
            while time.time() - wait_bubble_start < 40:
                current_count = self.page.locator(self.UI["bubble"]).count()  
                if current_count > prev_count:  
                    current_id = self.page.locator(self.UI["bubble"]).last.get_attribute('data-testid')  
                    if current_id and "PLACEHOLDER" not in current_id:  
                        self.bubble_ids.append(current_id)  
                        prev_count = current_count  
                        break
                time.sleep(1)  

    def action_wait_and_download(self, payload: TaskPayload):
        out_dir = self._get_download_dir(payload)  
        saved_paths = []  
        pending_bubbles = list(self.bubble_ids)  # 建立监控池
        global_start = time.time()

        self._log(f"   -> ⏳ 启动动态监控池，共 {len(pending_bubbles)} 个气泡排队等候结算 (熔断: {self.MAX_WAIT_SEC}s)...")

        # 大轮询启动：只要池子里还有气泡，且没触发全局超时，就继续扫街
        while pending_bubbles and time.time() - global_start < self.MAX_WAIT_SEC:
            if self.stop_requested: raise Exception("收到中止指令")

            # 必须使用 [:] 遍历快照副本，防止因执行 remove 而导致漏扫
            for b_id in pending_bubbles[:]:
                try:
                    my_bubble = self.page.locator(f'[data-testid="{b_id}"]')
                    
                    # 第一层判定：找真图（绝对白名单收割）
                    imgs = my_bubble.locator(self.UI["bubble_img"])
                    raw_url = self._extract_valid_image_url(imgs)
                    
                    # 必须且仅包含 /generator/ 才是目标纯净真图
                    if raw_url and "/generator/" in raw_url:
                        self._log(f"   -> 🎯 气泡 [{b_id[-6:]}] 产出真图，准备收割！")
                        clean_url = raw_url.split('?')[0]  
                        fname = f"EGL_{payload['task_name']}_{hashlib.md5(clean_url.encode()).hexdigest()[:6]}.png"  
                        save_path = os.path.join(out_dir, fname)

                        dl_success = False
                        for attempt in range(3):
                            if self.download_via_network(clean_url, save_path, payload, fname):
                                dl_success = True
                                saved_paths.append(save_path)
                                self.last_saved_path = save_path  
                                break  
                            else:
                                self._log(f"   -> ⚠️ 第 {attempt+1} 次网络下载无响应，准备重试...")
                                time.sleep(1)
                                
                        if dl_success:
                            try:
                                file_id = clean_url.split('/')[-1].split('.')[0] 
                                canvas_img = self.page.locator(self.UI["canvas_clean_img"].format(file_id=file_id)).first
                                self._click(canvas_img)
                                self.page.keyboard.press("Backspace")
                                self.page.keyboard.press("Delete")
                            except: pass
                            
                        # 无论最终下载是否成功，只要拿到 URL，该气泡使命结束，将其判决并踢出池子
                        pending_bubbles.remove(b_id)
                        continue

                    # 第二层判定：找错（物理处决：特定无图文本块）
                    error_node = my_bubble.locator('.cursor-text.select-text')
                    if error_node.count() > 0:
                        self._log(f"   -> 🚫 气泡 [{b_id[-6:]}] 遭遇错误或限制 (DOM拦截)，直接判死刑踢出池子！")
                        pending_bubbles.remove(b_id)
                        continue
                        
                except Exception:
                    # 前端 DOM 刷新重绘可能会瞬间抛出“节点脱离文档”的报错，必须静默无视
                    pass

            # 极速遍历完当前池子一圈后，执行一次整体的宽幅随机心跳休眠
            if pending_bubbles:
                sleep_time = random.uniform(25, 35)
                self._log(f"   -> 💤 池中还剩 {len(pending_bubbles)} 个气泡，进入心跳休眠 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)

        # --------------------- 轮询结束，开始保底结算 ---------------------
        if pending_bubbles:
            self._log(f"   -> ⚠️ {self.MAX_WAIT_SEC} 秒最高死线已到，强行终止轮询，残余的 {len(pending_bubbles)} 个气泡被放弃。")

        if not saved_paths: 
            raise Exception(f"任务全军覆没，交由中枢掀桌！")
        elif len(saved_paths) < len(self.bubble_ids):
            self._log(f"   -> ⚠️ 批次结算完毕 (成功抢救了 {len(saved_paths)}/{len(self.bubble_ids)} 张图)，任务判定及格！")

        self.project_image_count = getattr(self, 'project_image_count', 0) + len(saved_paths)
        self._log(f"📊 当前项目累计图数: {self.project_image_count}/{self.MAX_PROJECT_IMAGES}")

        if self.project_image_count >= self.MAX_PROJECT_IMAGES:
            self._log(f"⚠️ 触发 {self.MAX_PROJECT_IMAGES} 张显存红线！执行防爆重生...")
            self.action_init_workspace()
            self.last_params = None  
            
        return True