import os
import time
import random
import hashlib
from datetime import datetime
from .base_engine import BaseAIEngine, TaskPayload

class DoubaoEngine(BaseAIEngine):
    MAX_WAIT_SEC = 300  

    URL = "https://www.doubao.com/chat/"  

    DEFAULT_PARAMS = {
        "mode": "图像生成"
    }

    PARAM_ROUTING = {
        "aspect_ratio": "ratio_panel_trigger"
    }

    UI = {
        "new_chat_btn": 'a:has-text("新对话"):visible, div:has-text("新对话"):visible',
        "img_mode_btn": 'button[data-skill-id="skill_bar_button_3"]:visible',
        
        "input_box": 'textarea:visible, div[data-slate-editor="true"]:visible',  
        
        # 🎯 核心修复：接管基类的物理失焦逻辑。选完参数后点击输入框，安全收起菜单且不掉模式！
        "defocus_area": 'textarea:visible, div[data-slate-editor="true"]:visible',
        
        "submit_btn": '#flow-end-msg-send:visible',
        
        # 这个选择器本身没问题，只要模式不掉，它就能被精准命中
        "upload_input": 'span:has-text("参考图") input[type="file"]',                          
        "chat_img": 'img[src*="rc_gen_image"]',                        
        "ratio_panel_trigger": 'button:has-text("比例"):visible',

        # 🎯 1. 雷达靶标：用来嗅探图是否生成完毕
        "chat_img": 'img[src*="rc_gen_image"]',  
        
        # 🎯 2. 图像外层大框：兼容最新版的 container-dLabXv 以及旧版的 image-box
        "img_card": 'div[class*="container-dLabXv"], div[class*="image-box-grid-item"]', 
        
         # 🎯 3. 下载按钮交互热区：精准点杀内层 SVG 图标，彻底阻断事件冒泡引发的大图预览！
        "download_btn": '.hover-DQYLdi svg'
    }

    def _switch_work_mode(self, payload: TaskPayload):
        self._log("   -> 🧹 正在创建新对话，清空历史残留...")
        try:
            new_chat = self.page.locator(self.UI["new_chat_btn"]).first
            if new_chat.is_visible(timeout=2000):
                self._click(new_chat)
                time.sleep(1)
        except: pass

        self._log("   -> 🎛️ 正在精准锚定豆包【图像生成】模式...")
        
        # 🎯 暴力防御：前置无脑按 ESC，强制关掉上一轮可能被误触打开的预览大图
        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)
        except: pass
        
        try:
            mode_btn = self.page.locator(self.UI["img_mode_btn"]).first
            if mode_btn.is_visible(timeout=2000):
                self._click(mode_btn)
                time.sleep(0.5)
        except Exception as e:
            self._log(f"   -> ⚠️ 模式锚定跳过: {str(e)[:30]}")

    def _set_params_iteratively(self, payload: TaskPayload):
        # 🎯 修复2：强制擦除防抖记忆。因豆包发完图会掉模式，必须保证每次都重新选参！
        self.last_params = None  
        super()._set_params_iteratively(payload) 

    def action_upload_image(self, payload: TaskPayload):
        self._smart_upload(payload, upload_style="input")

    def action_fill_and_submit(self, payload: TaskPayload):
        self.pre_srcs = set()
        try:
            # 获取当前屏幕上所有的旧图长链接
            old_srcs = self.page.locator(self.UI["chat_img"]).evaluate_all("els => els.map(e => e.src)")
            
            # 🎯 核心修复：把旧图也提纯为短指纹 core_id，加入拦截黑名单！
            for raw_src in old_srcs:
                if raw_src:
                    core_id = raw_src.split("?")[0].split("/")[-1].split("~")[0]
                    self.pre_srcs.add(core_id)
        except: pass

        # 1. 填词（目标已锁定为可见的富文本框或输入框）
        # 🎯 修复1：废除父类的全选删除，只温柔点击聚焦后打字，坚决保护已在框内的参数标签！
        target_input = self.page.locator(self.UI["input_box"]).first
        self._click(target_input)
        self.page.keyboard.type(payload["prompt"], delay=random.randint(20, 50))
        time.sleep(0.5)
        
        # 2. 提交
        self._click(self.UI["submit_btn"])

        # 3. 清理上一轮的垫图缓存状态
        self.cached_img_path = None
    def action_wait_and_download(self, payload: TaskPayload):
        target_num = int(payload.get("engine_params", {}).get("quantity", 1)) 
        self._log(f"   -> ⏳ 启动出图雷达 (目标: {target_num} 张, 熔断: {self.MAX_WAIT_SEC}s)...")
        
        start_time = time.time()
        new_urls = {}  # 🌟 即梦同款：使用字典防重，Key存指纹，Value存原图链接
        
        # ==========================================
        # 第一阶段：指纹雷达监听 (坚决保留假图过滤)
        # ==========================================
        while time.time() - start_time < self.MAX_WAIT_SEC:
            if self.stop_requested: raise Exception("收到中止指令")
            
            current_srcs = self.page.locator(self.UI["chat_img"]).evaluate_all("els => els.map(e => e.src)")
            for raw_src in current_srcs:
                if not raw_src or "data:image" in raw_src or "loading" in raw_src or "avatar" in raw_src: 
                    continue
                
                # 💡 提取纯净核心 ID 作为防重 Key 和制导坐标（防 CSS 解析崩溃）
                core_id = raw_src.split("?")[0].split("/")[-1].split("~")[0]
                
                if core_id not in getattr(self, 'pre_srcs', set()) and core_id not in new_urls:
                    new_urls[core_id] = raw_src  
                    self._log(f"   -> 📡 截获真图指纹: {core_id[-15:]}")  
            
            if len(new_urls) >= target_num: break  
            time.sleep(2)  
            
        if len(new_urls) < target_num: 
            raise Exception("出图超时或云端错误，未凑齐目标数量")

        out_dir = self._get_download_dir(payload)  
        saved_count = 0
        
        self._log("   -> 📥 侦测到前端已渲染，启动宽窄屏自适应物理截获...")
        
        # ==========================================
        # 第二阶段：原生 filter 定位 + 盲狙悬停菜单
        # ==========================================
        for core_id, raw_src in new_urls.items():
            fname = f"EGL_{payload['task_name']}_{hashlib.md5(core_id.encode()).hexdigest()[:6]}.png"  
            save_path = os.path.join(out_dir, fname)
            
            # 🌟 单图 3 次重试护航
            for attempt in range(3):
                try: 
                    # 💡 魔法制导：用 UI 字典里的大框，反查内部含有该图 core_id 的唯一卡片
                    card = self.page.locator(self.UI["img_card"]).filter(has=self.page.locator(f'img[src*="{core_id}"]')).first
                    
                    # 滚屏并悬停大框
                    card.scroll_into_view_if_needed()
                    self._human_pause()
                    self._hover(card)
                    
                    time.sleep(1) # 强制给前端悬停动画留出淡入时间
                    
                    # 💡 终极解法：无视有没有“下载”文字，下载键永远是最后一个交互热区！
                    dl_btn = card.locator(self.UI["download_btn"]).last
                    
                    if self.download_via_browser(dl_btn, save_path, payload, fname):
                        saved_count += 1
                        break  
                    else:
                        self._log(f"   -> ⚠️ 第 {attempt+1} 次下载无响应，准备重试...")
                        
                except Exception as e:
                    self._log(f"   -> ⚠️ 单张图交互第 {attempt+1} 次失败: {str(e)[:50]}...")
                    
                finally:
                    # 🌟 即梦精髓：退刀步，打断 React 组件的悬停死锁
                    self.page.mouse.move(0, 0)  
                time.sleep(1) 
                
        if saved_count == 0:
            raise Exception("极端异常：发现图但全部保存失败，强制交由中枢重启！")