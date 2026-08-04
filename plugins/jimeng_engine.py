import os
import time
import random
import re
import hashlib
from datetime import datetime
from .base_engine import BaseAIEngine, TaskPayload

class JimengEngine(BaseAIEngine):
    """
    即梦（Jimeng）平台专属适配器 (HIL 极简交互层版)。
    """
    MAX_WAIT_SEC = 300  

    URL = "https://jimeng.jianying.com/ai-tool/image/generate"  
    
    # 🌟 默认参数兜底
    DEFAULT_PARAMS = {
        "mode": "图片生成",
        "model": "4.6",        # 默认回落至 4.6 模型
        "aspect_ratio": "9:16"
    }

    # 🌟 核心修复 1：参数路由映射。告诉大脑，选 model 时该点哪个按钮！
    PARAM_ROUTING = {
        "model": "model_trigger",              # 设模型 -> 点第二个下拉框
        "aspect_ratio": "param_panel_trigger"  # 设比例 -> 点第三个按钮
    }

    UI = {
        "input_box": 'div.ProseMirror[role="textbox"]',  
        "upload_input": 'input[type="file"]',  
        
        # 🌟 核心修复 2：使用 nth-child 精准解绑“双胞胎”下拉框
        # 第 1 个元素是【创作类型】，如：Agent/图片生成/视频生成
        "mode_btn": 'div.toolbar-settings-content-AqQb52 > div.toolbar-select-DS5gGq:nth-child(1)', 
        "mode_option": '.lv-select-option', 

        # 第 2 个元素是【模型选择】，如：图片 4.7/图片 4.6
        "model_trigger": 'div.toolbar-settings-content-AqQb52 > div.toolbar-select-DS5gGq:nth-child(2)',

        # 第 3 个元素是【比例与画质选项】
        "param_panel_trigger": 'div.toolbar-settings-content-AqQb52 > button.toolbar-button-pEFNv9',  
        
        # 新增：失焦安全区，确保点完下拉菜单后能安全收起
       "defocus_area": 'div.ProseMirror[role="textbox"]',

        "ref_item_container": 'div[class*="reference-item"]',
        "remove_ref_btn": 'div[class*="remove-button"]',
        "submit_btn": 'button[class*="submit-button-"]:visible',  
        "img_card": 'img[data-apm-action="ai-generated-image-record-card"]',  
    }

    

    def action_upload_image(self, payload: TaskPayload):
        img_path = payload.get("image_path")
        
        # 🛡️ 换图清理防御：仅在需要更换新图时，执行“Hover 逼出 -> 点击销毁”连招
        if img_path and os.path.exists(img_path) and img_path != getattr(self, 'cached_img_path', None):
            if getattr(self, 'cached_img_path', None):
                self._log("   -> 🧹 探测到换图请求，启动两段式破甲清场...")
                try:
                    ref_item = self.page.locator(self.UI["ref_item_container"]).first
                    if ref_item.count() > 0:
                        # 第一步：物理悬停，逼出隐藏的删除按钮
                        self._hover(ref_item) 
                        # 第二步：精准点击暴露出来的叉号
                        remove_btn = ref_item.locator(self.UI["remove_ref_btn"]).first
                        self._click(remove_btn, timeout=2000)
                        self._log("   -> 💥 旧垫图已成功被物理销毁。")
                except Exception as e:
                    self._log(f"   -> ⚠️ 清障交互异常 (可能已无残留): {str(e)[:30]}")

        # 清场完毕，调用父类执行 input 塞图动作与记忆装填
        self._smart_upload(payload, upload_style="input")

    def action_fill_and_submit(self, payload: TaskPayload):
        self.history_srcs = set()  
        try:
            pre_srcs = self.page.locator(self.UI["img_card"]).evaluate_all("els => els.map(e => e.getAttribute('src'))")
            self.history_srcs = set([s.split('~tplv-')[0] for s in pre_srcs if s])  
        except: pass  

        # 🌟 即梦基于 ProseMirror，保留你之前专门清空 innerHTML 的特殊逻辑
        input_box = self.page.locator(self.UI["input_box"]).first
        input_box.evaluate("el => el.innerHTML = ''")  
        
        # 🌟 HIL 替换：安全点击后打字
        self._click(input_box) 
        self.page.keyboard.type(payload["prompt"], delay=random.randint(20, 50))  
        time.sleep(random.uniform(0.5, 1.0))

        submit_btn = self.page.locator(self.UI["submit_btn"]).first
        wait_start = time.time()
        while submit_btn.is_disabled():  
            if time.time() - wait_start > 30: raise Exception("发送按钮长期锁定，疑触发屏蔽词")  
            time.sleep(1)
            
        # 🌟 HIL 替换：安全开火
        self._click(submit_btn) 

    def action_wait_and_download(self, payload: TaskPayload):
        target_num = int(payload.get("engine_params", {}).get("quantity", 4))  
        self._log(f"   -> ⏳ 启动 SRC 对比雷达 (目标: {target_num} 张, 熔断: {self.MAX_WAIT_SEC}s)...")
        
        start_time = time.time()
        new_urls = {}  
        
        while time.time() - start_time < self.MAX_WAIT_SEC:
            if self.stop_requested: raise Exception("收到中止指令")
            
            current_srcs = self.page.locator(self.UI["img_card"]).evaluate_all("els => els.map(e => e.getAttribute('src'))")
            for raw_src in current_srcs:
                if not raw_src or "data:image" in raw_src or "loading" in raw_src: continue
                clean_url = raw_src.split('~tplv-')[0]  
                if clean_url not in self.history_srcs and clean_url not in new_urls:
                    new_urls[clean_url] = raw_src  
                    self._log(f"   -> 📡 截获真图指纹: {clean_url[-15:]}")  
            
            if len(new_urls) >= target_num: break  
            time.sleep(2)  
            
        if len(new_urls) < target_num: raise Exception("出图超时或云端错误，未凑齐目标数量")

        out_dir = self._get_download_dir(payload)  
        saved_count = 0
        for clean_url, raw_src in new_urls.items():
            fname = f"EGL_{payload['task_name']}_{hashlib.md5(clean_url.encode()).hexdigest()[:6]}.png"  
            save_path = os.path.join(out_dir, fname)
            
            for attempt in range(3):
                try: 
                    card = self.page.locator(f'img[src="{raw_src}"]').locator('xpath=ancestor::div[contains(@class, "image-card-wrapper")]').first
                    
                    # 🌟 HIL 替换：原来长达 5 行的悬停、退刀步和等待，现在浓缩成了一句话！
                    self._hover(card)
                    
                    dl_btn = card.locator('div[class*="operation-button"]').first  
                    if self.download_via_browser(dl_btn, save_path, payload, fname):
                        saved_count += 1
                        break  
                    else:
                        self._log(f"   -> ⚠️ 第 {attempt+1} 次下载无响应，准备重试...")
                except Exception as e:
                    self._log(f"   -> ⚠️ 单张图交互第 {attempt+1} 次失败: {str(e)[:50]}...")
                finally:
                    self.page.mouse.move(0, 0)  
                time.sleep(1) 
                
        if saved_count == 0:
            raise Exception("极端异常：发现图但全部保存失败，强制交由中枢重启！")