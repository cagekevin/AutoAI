import os
import time
import random
import logging
import platform
import threading
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from typing import TypedDict, Any, List

from playwright.sync_api import sync_playwright
# 请确保你的 core/image_processor.py 依然存在并能正常导入
from core.image_processor import processor 

# =====================================================================
# [全局硬编码区]: 彻底废弃 config.json，单一真相源在此汇聚
# =====================================================================
# 跨平台 Chrome 浏览器可执行文件路径映射表
GLOBAL_CHROME_PATHS = {
    "darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "windows": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
}
# Chrome 用户数据目录路径（用于保持登录态和 Cookie  ）
GLOBAL_USER_DATA_DIR = "./google_chrome_profile"
# 全局代理服务器地址（Clash/Shadowsocks 等）
GLOBAL_PROXY = "http://127.0.0.1:7897"
# Clash API 管理接口地址（用于动态切换节点绕过 WAF）
GLOBAL_CLASH_API = "http://127.0.0.1:9097"
# Clash API 鉴权 Token（若无密码请置空串 ""）
GLOBAL_CLASH_AUTH = "Bearer set-your-secret"
# 统一落盘基准路径：所有引擎产出的图片均收敛至此目录下的子文件夹
GLOBAL_OUTPUT_DIR = "Downloads"

# 🌟 新增：跨平台通用的无效图片特征黑名单 (涵盖垫图、占位图、前端 Blob 本地预览)
GLOBAL_IMAGE_BLACKLIST_REGEX = r'(base64|blob:|loading|placeholder|spinner|/user/|/upload/|/reference/|/source/|/input/)'

# 任务载荷类型定义：描述从调度器下发至引擎的标准化任务结构
class TaskPayload(TypedDict):
    task_name: str        # 任务唯一标识符（通常含 MD5 哈希防重名）
    prompt: str           # AI 生图提示词
    image_path: str       # 垫图本地绝对路径（可选）
    engine_params: dict   # 引擎专属参数集（如 quantity、aspect_ratio、model 等）
    dna_dict: dict        # DNA 元数据字典（用于注入 PNG parameters 字段实现溯源）
    target_site: str      # 目标平台标识（如 "jimeng"、"flow"、"lovart"）

# =====================================================================
# [司令部]: 核心装甲底盘与通用武器库
# =====================================================================
class BaseAIEngine:
    """
    AI 生图引擎的统帅大脑，包揽所有跨平台共性逻辑。
    """
    
    def __init__(self):
        # ================== [运行时状态] ==================
        self.stop_requested = False          # 全局制动标志位（用于紧急中止任务）
        self.resume_event = threading.Event() # 人工放行事件锁（安检失败时阻塞等待人工干预）
        self.consecutive_successes = 0       # 连续成功计数器（用于熔断策略判断）
        self.cached_img_path = None          # 垫图缓存路径（避免重复上传同一张垫图）
        self.last_params = None              # 上次配参快照（用于防抖，相同参数跳过重复点击）
        
        # ================== [Playwright 实例引用] ==================
        self.playwright = None               # Playwright 客户端实例
        self.browser = None                  # Chromium 浏览器连接对象
        self.context = None                  # 浏览器上下文（含 Cookie/Storage）
        self.page = None                     # 当前工作标签页

    def _log(self, msg: str):
        """统一日志输出通道：同时打印至控制台并写入 logging 模块"""
        print(msg, flush=True)
        if "❌" in msg: logging.error(msg)
        elif "⚠️" in msg: logging.warning(msg)
        else: logging.info(msg)

    # ---------------------------------------------------------
    # [武器库 1]: 拟人微操发生器
    # ---------------------------------------------------------
    def _human_pause(self, action_type="click"):
        """
        模拟人类操作的自然随机延迟，规避网站反自动化检测。
        """
        delays = {"click": (0.3, 0.8), "type": (0.8, 1.5), "upload": (1.5, 3.0)}
        min_s, max_s = delays.get(action_type, (0.5, 1.0))
        time.sleep(random.uniform(min_s, max_s))

    # =========================================================
    # 🌟 [极简交互层 HIL] 内置拟人呼吸感与 React 水合等待 (新增)
    # =========================================================
    def _click(self, selector_or_locator, index="first", force=True, timeout=10000):
        """带拟人停顿的安全点击，支持 css selector 字符串或 Locator 对象"""
        self._human_pause("click")  # 动作前缓冲：防封锁
        
        target = self.page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
        target = target.first if index == "first" else target.last
        
        target.wait_for(state="visible", timeout=timeout)
        target.click(force=force)
        
        time.sleep(random.uniform(0.8, 1.5)) # 动作后缓冲：等 React 动画/弹窗

    def _fill(self, selector_or_locator, text: str, index="first"):
        """带拟人打字速度的安全输入"""
        self._click(selector_or_locator, index=index)
        cmd_key = "Meta+A" if platform.system().lower() == "darwin" else "Control+A"
        self.page.keyboard.press(cmd_key)
        self.page.keyboard.press("Backspace")
        self.page.keyboard.type(text, delay=random.randint(2, 5))
        time.sleep(random.uniform(0.5, 1.0))

    def _hover(self, selector_or_locator, index="first", timeout=10000):
        """带呼吸感的安全悬停"""
        target = self.page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
        target = target.first if index == "first" else target.last
        
        target.scroll_into_view_if_needed()
        self.page.mouse.move(0, 0)
        time.sleep(0.3)
        target.hover(timeout=timeout)
        time.sleep(random.uniform(0.5, 1.0)) # 等悬停菜单弹出
    # =========================================================

    # ---------------------------------------------------------
    # [武器库 2]: 通用战前清扫 (已替换为 HIL)
    # ---------------------------------------------------------
    def _clear_popups(self, popup_selectors: List[str]):
        if not getattr(self, 'page', None) or not popup_selectors: return
        for sel in popup_selectors:
            try:
                elem = self.page.locator(sel).first
                if elem.is_visible(timeout=500):
                    self._log(f"   -> 🧹 发现视野障碍，执行物理清障...")
                    self._click(elem, timeout=1000)
            except: pass

    # ---------------------------------------------------------
    # [武器库 2.5]: 通用模式切换器 (基于DOM视觉记忆的绝对防御版)
    # ---------------------------------------------------------
    def _switch_work_mode(self, payload: TaskPayload):
        # 修复：先尝试从 payload 获取，如果没有，再尝试从子类的默认参数获取
        default_mode = getattr(self, 'DEFAULT_PARAMS', {}).get("mode")
        target_mode = payload.get("engine_params", {}).get("mode", default_mode)
        
        if not target_mode or not hasattr(self, 'UI') or "mode_btn" not in self.UI: return

        self._log(f"   -> 🎛️ 正在核验并校准工作模式至: [{target_mode}]...")
        
        try:
            # 1. 强制寻找触发按钮（去掉软弱的 is_visible，找不到直接引发 except 熔断）
            mode_trigger = self.page.locator(self.UI["mode_btn"]).last
            mode_trigger.wait_for(state="visible", timeout=15000) # 给 15 秒加载时间
            
            # 2. 视觉记忆防抖：使用正则看一眼当前按钮文字。如果是目标模式，立刻跳过
            if re.search(str(target_mode), mode_trigger.inner_text(), re.I):
                self._log("      ✅ [防抖] 视觉核验通过，当前已是目标模式，无需点击。")
                return
            
            # 3. 必须切换：点开菜单
            self._click(mode_trigger, index="last")
            
            # 4. 精准寻找目标选项并点击
            option_selector = self.UI.get("mode_option", 'div, button, span, [role="menuitem"], [role="tab"]')
            target_option = self.page.locator(option_selector).filter(has_text=re.compile(str(target_mode), re.I)).last
            self._click(target_option, index="last")
            
            self._log("      ✅ 点击执行完毕，强制静默 3s 等待前端 React 重绘...")
            time.sleep(3)
            
            # 5. 动作后校验：再看一眼，确保真的切过去了，没被网页吞点击
            if not re.search(str(target_mode), mode_trigger.inner_text(), re.I):
                self._log(f"      ⚠️ 点击了选项但按钮文字未变，疑似遭拦截。触发软性放行。")
                return
                
        except Exception as e:
            # 贯彻流水线哲学：软性放行，仅记录日志，绝不阻断任务
            self._log(f"      ⚠️ 模式切换发生异常，执行软性放行 (可能导致后续无法垫图): {e}")

    # ---------------------------------------------------------
    # [武器库 3]: 独立重置配参引擎 (已替换为 HIL)
    # ---------------------------------------------------------
    def _set_params_iteratively(self, payload: TaskPayload):
        default_params = getattr(self, 'DEFAULT_PARAMS', {})
        raw_params = {**default_params, **payload.get("engine_params", {})}
        
        if not hasattr(self, 'UI'): return

        format_dict = getattr(self, 'PARAM_FORMAT', {}) 
        routing_map = getattr(self, 'PARAM_ROUTING', {})
        ignore_keys = getattr(self, 'IGNORE_UI_PARAMS', [])

        # 1. 参数提纯：只保留真正需要去 UI 面板里点击的参数
        ui_params = {k: v for k, v in raw_params.items() if k not in ignore_keys}

        # 2. 绝对防抖：拿提纯后的 UI 参数与大脑记忆比对
        if getattr(self, 'last_params', None) == ui_params:
            self._log("   -> ⚡ 参数配置与上一轮完全一致，触发防抖，跳过 UI 交互。")
            return

        self._log("   -> ⚙️ 启动标准化智能路由参数装填...")
        all_success = True  # 事务状态标志

        for key, val in ui_params.items():
            trigger_key = routing_map.get(key, "param_panel_trigger")
            if trigger_key not in self.UI: continue
            
            target_text = format_dict.get(key, "{}").format(val)
            
            try:
                # 依然保持跨平台最稳的"点开 -> 选中 -> 收起"闭环操作
                self._click(self.UI[trigger_key], index="last")
                
                custom_selectors = getattr(self, 'PARAM_OPTION_SELECTORS', {})
                base_locator_str = custom_selectors.get(key, 'button, div, span, [role="tab"], [role="menuitem"]')
                
                param_btn = self.page.locator(base_locator_str).filter(has_text=re.compile(re.escape(str(target_text)), re.I)).last
                self._click(param_btn, index="last")
                self._log(f"      ✅ 选中参数: {target_text}")
                
                if "defocus_area" in self.UI:
                    self._click(self.UI["defocus_area"])
                else:
                    self.page.keyboard.press("Escape")
                    self.page.mouse.click(0, 0)
                self._human_pause()
                
            except Exception as e:
                self._log(f"      ⚠️ 参数 [{target_text}] 匹配失败，跳过。")
                all_success = False  # 遇到任何一个报错，这单的记忆就判定为脏数据

        # 3. 事务提交：全对才写入大脑，否则物理失忆
        if all_success:
            self.last_params = ui_params
        else:
            self.last_params = None

    # ---------------------------------------------------------
    # [武器库 4]: 双流派通用垫图引擎 (已替换为 HIL，彻底根治过快问题)
    # ---------------------------------------------------------
    def _smart_upload(self, payload: TaskPayload, upload_style="input"):
        img_path = payload.get("image_path")

        if not img_path or not os.path.exists(img_path):
            if getattr(self, 'cached_img_path', None) and hasattr(self, 'UI') and "close_preview_btn" in self.UI:
                try:
                    btn = self.page.locator(self.UI["close_preview_btn"]).first
                    if btn.is_visible(timeout=500): self._click(btn)
                    self._log("   -> 🧹 清理上一轮残存的垫图面板。")
                except: pass
            self.cached_img_path = None  
            return
            
        if not hasattr(self, 'UI'): return
        
        if img_path == self.cached_img_path:
            # 修复 Bug 1：既然触发了防抖复用，绝不能去点击 X 删除按钮
            self._log("   -> 🧠 触发垫图记忆，保留当前垫图，跳过物理上传。")
            return

        # 修复 Bug 2：如果走到这里，说明要传【新图】。必须先检查并清理【旧图】防止堆叠
        if getattr(self, 'cached_img_path', None) and "close_preview_btn" in self.UI:
            try:
                btn = self.page.locator(self.UI["close_preview_btn"]).first
                if btn.is_visible(timeout=500): 
                    self._click(btn)
                    self._log("   -> 🧹 已物理清理上一单的旧垫图，为新图腾出空间。")
            except: pass

        self._log(f"   -> 🖼️ 正在装载新垫图...")
        try:
            if upload_style == "input" and "upload_input" in self.UI:
                self.page.locator(self.UI["upload_input"]).first.set_input_files(img_path)
                
            elif upload_style == "os_dialog" and "upload_btn" in self.UI:
                if "local_upload_option" in self.UI:
                    # 🌟 极简 HIL 替换：不再需要满篇的 wait_for 和 sleep，_click 一句话搞定所有微操
                    self._click(self.UI["upload_btn"], index="first")
                    with self.page.expect_file_chooser() as fc:
                        self._click(self.UI["local_upload_option"], index="first")
                    fc.value.set_files(img_path)  
                else:
                    with self.page.expect_file_chooser() as fc:
                        self._click(self.UI["upload_btn"], index="first")
                    fc.value.set_files(img_path)  
                    
            self._human_pause("upload")  
            self.cached_img_path = img_path  
        except Exception as e:
            # 贯彻流水线哲学：找不到传图按钮或传图失败时，直接放弃传图，强行往下发词
            self._log(f"   -> ⚠️ 垫图装载失败或无入口，忽略垫图强制执行放行: {e}")
            self.cached_img_path = None # 清空残存记忆，防止下一单误判

    # ---------------------------------------------------------
    # [武器库 4.5]: 全局通用真实图片嗅探器
    # ---------------------------------------------------------
    def _extract_valid_image_url(self, image_locators):
        """
        核心战术组件：统一用全局黑名单过滤掉垫图、本地预览和加载动画，精准提取唯一纯净的真图 URL。
        """
        if not image_locators or image_locators.count() == 0:
            return None
            
        for i in range(image_locators.count()):
            img_node = image_locators.nth(i)
            # 兼容处理：尝试获取 src 或 data-src
            src = img_node.evaluate("el => el.src || el.getAttribute('data-src')") or ""
            
            # 核心过滤：必须是 http 开头，且绝对不能命中全局黑名单
            if src and src.startswith('http') and not re.search(GLOBAL_IMAGE_BLACKLIST_REGEX, src, re.I):
                return src
                
        return None

    # ---------------------------------------------------------
    # [武器库 5]: 统一安检与放行门
    # ---------------------------------------------------------
    def _security_check(self):
        self._log("🛂 正在核验网页登录态与 DOM 完整性...")
        
        if hasattr(self, 'UI') and "popups" in self.UI:
            self._log("   -> 🧹 安检前置：清扫潜在的弹窗遮挡物...")
            self._clear_popups(self.UI["popups"])
            
        try:
            input_selector = self.UI.get("input_box", "textarea")  
            self.page.locator(input_selector).first.wait_for(state="visible", timeout=30000)
            self._log("🟢 检测到核心组件已就绪。")
            self.resume_event.set()  
        except:
            self.resume_event.clear()  
            self._log("⚠️ 30秒未检测到输入框，可能需要登录或存在弹窗拦截。")
            self._log("⏸️ 请人工处理浏览器当前页面，完毕后点击控制台的【✅ 人工放行】...")
            
            while not self.resume_event.is_set():
                if self.stop_requested: raise Exception("人工放行期间收到中止指令。")
                time.sleep(1)
            self._log("▶️ 收到放行指令，引擎恢复运转。")

    # ---------------------------------------------------------
    # [LIFECYCLE 1]: 底层环境挂载
    # ---------------------------------------------------------
    def setup(self):
        self.stop_requested = False  
        sys_os = platform.system().lower()
        chrome_path = GLOBAL_CHROME_PATHS.get(sys_os, "")
        abs_profile = os.path.abspath(GLOBAL_USER_DATA_DIR) if GLOBAL_USER_DATA_DIR else ""
        
        args = f'--remote-debugging-port=9222 --user-data-dir="{abs_profile}"'
        if GLOBAL_PROXY: args += f' --proxy-server={GLOBAL_PROXY}'

        if chrome_path:
            import socket
            port_in_use = False
            try:
                with socket.create_connection(("127.0.0.1", 9222), timeout=1):
                    port_in_use = True
            except OSError:
                pass

            if port_in_use:
                self._log("   -> ♻️ 进程防碰撞拦截：Chrome (9222) 稳固运行中，直接复用。")
            else:
                try:
                    self._log(f"🚀 [底盘点火] 拉起独立 Chrome...")
                    if sys_os == "darwin": os.system(f"open -n -a '{chrome_path}' --args {args}")
                    elif sys_os == "windows": os.system(f'start "" "{chrome_path}" {args}')
                except: pass

        if not self.playwright: self.playwright = sync_playwright().start()  
        
        max_retries = 15
        for i in range(max_retries):
            try:
                self.browser = self.playwright.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
                self._log("   -> 🟢 CDP 底层调试接口已连通！")
                break
            except Exception as e:
                if i == max_retries - 1:
                    raise Exception("致命错误: Chrome 启动超时或 9222 端口被僵尸进程占用。请在任务管理器中强制结束所有 chrome.exe 后重试！")
                self._log(f"   -> ⏳ 等待 Chrome 引擎冷启动就绪 (耗时 {i+1}s)...")
                time.sleep(1)
        self.context = self.browser.contexts[0]  
        
        self._log("👉 [基建] 正在寻址或部署工作阵地...")
        target_url = getattr(self, 'URL_CANVAS', getattr(self, 'URL', ""))
        clean_url = target_url.replace("*", "").split("?")[0] if target_url else "UNKNOWN"  
        target_page = next((p for p in self.context.pages if clean_url in p.url), None)  
        
        if target_page and not getattr(self, 'FORCE_NEW_PAGE', False):
            self.page = target_page
            try: self.page.bring_to_front()
            except: pass
        else:
            self.page = self.context.new_page() if getattr(self, 'FORCE_NEW_PAGE', False) else (self.context.pages[0] if len(self.context.pages) > 0 else self.context.new_page())
            self.page.bring_to_front()
            try: self.page.evaluate("window.onbeforeunload = null")  
            except: pass
            
            home_url = getattr(self, 'URL_HOME', getattr(self, 'URL', ""))
            if home_url: self.page.goto(home_url, timeout=60000)  
            
            if hasattr(self, 'UI') and "new_proj_btn" in self.UI:
                self._click(self.UI["new_proj_btn"])  # 🌟 已替换为 HIL
                if hasattr(self, 'URL_CANVAS'):
                    self.page.wait_for_url(self.URL_CANVAS, timeout=30000)  
            time.sleep(3)  
        
        self._security_check()  

    # ---------------------------------------------------------
    # [LIFECYCLE 2]: 绝对防弹的 8 步主流程
    # ---------------------------------------------------------
    def process_single(self, payload: TaskPayload) -> bool:
        if self.stop_requested: raise Exception("中止")
            
        if hasattr(self, 'UI') and "popups" in self.UI:
            self._clear_popups(self.UI["popups"])
        
        self._switch_work_mode(payload)
        self._set_params_iteratively(payload)
        
        self.action_upload_image(payload)
        self.action_fill_and_submit(payload)
        self.action_wait_and_download(payload)
        
        self.consecutive_successes += 1
        rel_path = getattr(self, 'last_saved_path', '').replace(os.getcwd() + os.sep, '')
        return True, rel_path

    def _get_download_dir(self, payload: TaskPayload) -> str:
        site_name = payload.get("target_site", "Unknown").capitalize()
        out_dir = os.path.join(GLOBAL_OUTPUT_DIR, f"{site_name}_Downloads", datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    # ---------------------------------------------------------
    # [LIFECYCLE 3]: 安全清场
    # ---------------------------------------------------------
    def teardown(self):
        self._log("🧹 [引擎待命] 任务清空，关闭当前标签页防堆积，切断 CDP。")
        if getattr(self, 'page', None):
            try: 
                self.page.evaluate("window.onbeforeunload = null")  
            except: pass
        if getattr(self, 'browser', None):
            try: self.browser.disconnect()  
            except: pass
        if getattr(self, 'playwright', None):
            try: self.playwright.stop()  
            except: pass
        self.page = None; self.context = None; self.browser = None; self.playwright = None  
        self.cached_img_path = None  
        self.last_params = None      

    # =====================================================================
    # [HOOKS]: 子类契约
    # =====================================================================
    def action_init_workspace(self): raise NotImplementedError
    def action_upload_image(self, payload: TaskPayload): raise NotImplementedError
    def action_fill_and_submit(self, payload: TaskPayload): raise NotImplementedError
    def action_wait_and_download(self, payload: TaskPayload): raise NotImplementedError

    # =====================================================================
    # [DOWNLOADERS & EAGLE]: 下载器与旁路打标
    # =====================================================================
    def _sync_to_eagle(self, file_path: str, raw_data: bytes, payload: TaskPayload, fname: str):
        dna_dict = dict(payload.get("dna_dict", {}))  
        if dna_dict:
            dna_dict["Image_Fingerprint"] = {"File_Name": fname, "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        try: processor.submit_task(save_path=file_path, image_source=raw_data or file_path, dna_dict=dna_dict)
        except Exception as e: self._log(f"   -> ⚠️ 打标投递失败: {e}")

    def download_via_browser(self, trigger_locator, save_path: str, payload: TaskPayload, fname: str) -> bool:
        try:
            with self.page.expect_download(timeout=30000) as dl_info:  
                self._click(trigger_locator) # 🌟 HIL：下载按钮也完美切入安全点击
            dl_info.value.save_as(save_path)  
            self._log(f"   -> 📥 [物理截获] 成功落盘: {fname}")
            threading.Thread(target=self._sync_to_eagle, args=(save_path, None, payload, fname)).start()
            return True
        except Exception as e:
            self._log(f"   -> ⚠️ 物理下载超时或被网页拦截 (跳过此图): {e}")
            return False  

    def download_via_network(self, url: str, save_path: str, payload: TaskPayload, fname: str) -> bool:
        try:
            user_agent = self.page.evaluate("navigator.userAgent")  
            cookies = self.context.cookies()  
            req = urllib.request.Request(url, headers={'User-Agent': user_agent, 'Cookie': "; ".join([f"{c['name']}={c['value']}" for c in cookies]), 'Referer': self.page.url})
            with urllib.request.urlopen(req, timeout=30) as res: img_bytes = res.read()  
            self._log(f"   -> 📥 [网络渗透] 成功落盘: {fname}")
            threading.Thread(target=self._sync_to_eagle, args=(save_path, img_bytes, payload, fname)).start()
            return True
        except Exception as e:
            self._log(f"   -> ⚠️ 网络裸下超时或被拒绝 (跳过此图): {e}")
            return False  

    def _escape_waf_via_clash(self) -> bool:
        if not GLOBAL_CLASH_API: return False  
        try:
            headers = {"Authorization": GLOBAL_CLASH_AUTH} if GLOBAL_CLASH_AUTH else {}
            
            req = urllib.request.Request(f"{GLOBAL_CLASH_API}/proxies", headers=headers)
            data = json.loads(urllib.request.urlopen(req, timeout=3).read().decode('utf-8'))
            
            proxies_data = data.get('proxies', {})
            
            target_group = "GLOBAL"  
            for group_name in proxies_data.keys():
                if any(k in group_name.upper() for k in ["机场", "PROXY", "节点", "NODE", "SELECT", "NINJA"]):
                    target_group = group_name
                    break
            
            if target_group not in proxies_data:
                self._log(f"❌ [WAF逃逸] 找不到有效的策略组，当前尝试组: {target_group}")
                return False

            all_nodes = proxies_data[target_group].get('all', [])  
            current_node = proxies_data[target_group].get('now', "")  
            
            escape_nodes = [
                n for n in all_nodes 
                if any(k in n.upper() for k in ["美国", "US", "美", "台湾", "TW", "日本", "JP", "日"]) 
                and n != current_node
            ]
            
            if escape_nodes:
                next_node = random.choice(escape_nodes)  
                switch_req = urllib.request.Request(
                    f"{GLOBAL_CLASH_API}/proxies/{urllib.parse.quote(target_group)}", 
                    data=json.dumps({"name": next_node}).encode('utf-8'), 
                    headers=headers, method='PUT'
                )
                urllib.request.urlopen(switch_req, timeout=3)
                self._log(f"🛡️ [WAF逃逸] 探测到云端封锁，已强行热切节点至: {next_node}")
                return True
                
        except Exception as e:
            self._log(f"⚠️ [WAF逃逸] 节点切换链路异常 (非致命): {e}")
            
        return False