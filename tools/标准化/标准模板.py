import os
import time
import re
import hashlib
from .base_engine import BaseAIEngine, TaskPayload

# =====================================================================
# [标准模板引擎]: 仅提供配置坐标与核心 4 步动作，其余全交由大管家
# =====================================================================
class StandardEngine(BaseAIEngine):
    
    # ================== [系统级配置] ==================
    FORCE_NEW_PAGE = False       # 是否强制新开干净标签页
    MAX_WAIT_SEC = 300           # 兜底死线：5分钟不报错最高宪法
    
    # ================== [大管家参数解析配置] ==================
    DEFAULT_PARAMS = {"aspect_ratio": "1:1"}  # 兜底参数（前端没传时生效）
    IGNORE_UI_PARAMS = ["quantity"]           # 仅用于内部逻辑，不让大管家去网页上瞎点的参数
    PARAM_FORMAT = {}                         # 参数文本转换器（例如 {"quantity": "x{}"}）
    PARAM_ROUTING = {}                        # 专属面板路由（不填则全去点 UI["param_panel_trigger"]）
    PARAM_OPTION_SELECTORS = {}               # 限定 CSS 查找范围（防同名误点）
    
    # ================== [页面坐标雷达 (必须替换为你网站的)] ==================
    URL = "https://www.example-ai.com/create"
    UI = {
        "input_box": 'textarea[placeholder="Enter prompt"]',
        "submit_btn": 'button.generate-btn',
        "upload_input": 'input[type="file"]',   # 垫图输入框 (流派 A 用)
        "param_panel_trigger": 'button.settings',
        "result_img": 'img.final-output',       # 生成的最终图片
        "dl_btn": 'button.download-btn'         # 下载按钮 (流派 A 用)
    }

    # ================== [必须实现的 4 个动作钩子] ==================

    def action_init_workspace(self):
        """1. 战前准备：关闭弹窗、清空画布等（如不需要直接 pass）"""
        pass

    def action_upload_image(self, payload: TaskPayload):
        """2. 上传垫图：直接调父类武器"""
        # upload_style="input" (无感注入) 或 "os_dialog" (弹窗点击)
        self._smart_upload(payload, upload_style="input")

    def action_fill_and_submit(self, payload: TaskPayload):
        """3. 填词并开火"""
        input_box = self.page.locator(self.UI["input_box"]).first
        input_box.fill(payload["prompt"])
        self._human_pause("type")
        
        self.page.locator(self.UI["submit_btn"]).first.click()
        self._human_pause("click")

    def action_wait_and_download(self, payload: TaskPayload):
        """4. 监听与下载：贯彻【单图防弹 + 兜底宪法】"""
        target_num = int(payload.get("engine_params", {}).get("quantity", 1))
        out_dir = self._get_download_dir(payload)
        
        # 1. 监听渲染完毕
        imgs = self.page.locator(self.UI["result_img"])
        imgs.first.wait_for(state="visible", timeout=self.MAX_WAIT_SEC * 1000)
        
        saved_count = 0
        
        # 2. 循环下载（套上 3 次单图重试护甲）
        for i in range(min(imgs.count(), target_num)):
            img_node = imgs.nth(i)
            src = img_node.evaluate("el => el.src")
            fname = f"EGL_{payload['task_name']}_{i}.png"
            save_path = os.path.join(out_dir, fname)
            
            for attempt in range(3):
                try:
                    # 如果有下载按钮，用流派 A：
                    # dl_btn = img_node.locator('xpath=..').locator(self.UI["dl_btn"])
                    # if self.download_via_browser(dl_btn, save_path, payload, fname):
                    
                    # 如果只能直接抓 URL，用流派 B：
                    if self.download_via_network(src, save_path, payload, fname):
                        saved_count += 1
                        self.last_saved_path = save_path
                        break
                except Exception as e:
                    self._log(f"   -> ⚠️ 第 {attempt+1} 次下载异常: {e}")
                time.sleep(1)
                
        # 3. 终极结算
        if saved_count == 0:
            raise Exception("死线已到，全军覆没，交由大管家掀桌子！")