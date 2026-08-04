import os
import time
import random
import platform
import re
from datetime import datetime
from .base_engine import BaseAIEngine, TaskPayload

class FlowEngine(BaseAIEngine):
    """
    Google Flow 平台专属适配器 (HIL 极简交互层 + 老代码灵魂版)。
    """
    FORCE_NEW_PAGE = False  
    MAX_WAIT_SEC = 300  
    
    DEFAULT_PARAMS = {
        "quantity": "4",
        "aspect_ratio": "9:16"
    }
    
    URL = "https://labs.google/fx/tools/flow"  
    URL_CANVAS = "**/project/**"  
    
    UI = {
        "new_proj_btn": 'button.jsIRVP, button:has-text("New project")', 
        "input_box": 'div[role="textbox"][contenteditable="true"]',  
        "submit_btn": 'button:has(i:has-text("arrow_forward"))',  
        "upload_btn": 'button:has(i:text-is("add"))',  
        
        # 🌟 终极修复：只找下拉菜单(menuitem)里的上传按钮，彻底屏蔽页面上其他同名的“错误按钮”！
        "local_upload_option": '[role="menuitem"]:has-text("Upload"), [role="menuitem"]:has-text("上传")',  
        
        "scroller": 'div[data-testid="virtuoso-scroller"]',  
        "tile": 'div[data-tile-id]',  
        "popups": ['button:has-text("Dismiss")', 'button:has-text("关闭")']  
    }

    def _set_params_iteratively(self, payload: TaskPayload):
        params = {**self.DEFAULT_PARAMS, **payload.get("engine_params", {})}
        quantity = str(params.get("quantity"))
        q_str = f"x{quantity}" if not quantity.startswith('x') else quantity
        aspect_ratio = str(params.get("aspect_ratio"))
        
        try:
            self._log(f"   -> ⚙️ 正在装填数量: {q_str}")
            self._click('button[aria-haspopup="menu"]:has-text("Nano")')
            self._click(f'button[role="tab"]:has-text("{q_str}")')
            self._log(f"      ✅ 数量装填成功。")
        except Exception as e:
            self._log(f"      ⚠️ 数量装填异常 (非致命): {str(e)[:40]}")
        finally:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)

        try:
            self._log(f"   -> 📐 正在装填画幅: {aspect_ratio}")
            self._click('button[aria-haspopup="menu"]:has-text("Nano")')
            self._click(f'button:has-text("{aspect_ratio}")', index="last")
            self._log(f"      ✅ 画幅装填成功。")
        except Exception as e:
            self._log(f"      ⚠️ 画幅装填异常 (非致命): {str(e)[:40]}")
        finally:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)

    def action_upload_image(self, payload: TaskPayload):
        img_path = payload.get("image_path")
        if not img_path: return
        
        # 1 & 2: 战前物理核验与幽灵防范
        is_reuse = False
        cached_id = getattr(self, 'cached_tile_id', None)
        
        if img_path == getattr(self, 'cached_img_path', None):
            if cached_id and self.page.locator(f'div[data-tile-id="{cached_id}"]').count() > 0:
                is_reuse = True
                self._log("   -> 🧠 物理核验通过，瓷砖依然存活，开启防抖极速复用模式。")
            else:
                self._log("   -> 👻 发现幽灵垫图，前端已清理该瓷砖，强制洗白大脑重传。")
                self.cached_img_path = None  # 逼迫父类重新物理上传
                self.cached_tile_id = None

        try: pre_first_id = self.page.locator(f'{self.UI["scroller"]} {self.UI["tile"]}').first.get_attribute('data-tile-id', timeout=1000)
        except: pre_first_id = "nothing_here"

        # 3. 呼叫父类传图（父类会根据刚刚的 cached_img_path 决定真传还是跳过）
        self._smart_upload(payload, upload_style="os_dialog")
        
        # 如果父类因为致命原因放弃了垫图（比如按钮被死锁挡住），直接撤退防报错
        if not getattr(self, 'cached_img_path', None):
            return

        # 4. 时间线精准分流
        target_tile_id = None
        if not is_reuse:
            self._log("   -> ⏳ 垫图已发往云端，动态监听渲染状态...")
            try:
                js_check_id = f"() => {{ const el = document.querySelector('{self.UI['scroller']} {self.UI['tile']}'); return el && el.getAttribute('data-tile-id') !== '{pre_first_id}'; }}"
                self.page.wait_for_function(js_check_id, timeout=40000)
                
                target_tile_id = self.page.locator(f'{self.UI["scroller"]} {self.UI["tile"]}').first.get_attribute('data-tile-id')
                self.cached_tile_id = target_tile_id  # 写入瓷砖记忆神经元
                self._log(f"   -> 📡 捕获新垫图 ID: {target_tile_id[:8]}，准备执行装填...")
            except Exception as e:
                self._log(f"   -> ⚠️ 垫图渲染超时或交互异常: {e}")
                return # 没拿到 ID 无法装填，直接放弃垫图发纯文字
        else:
            target_tile_id = self.cached_tile_id
            self._log(f"   -> ⚡ 提取已缓存垫图 ID: {target_tile_id[:8]}，跳过等待...")

        # 5. 雷打不动的“扣扳机”：只要拿到合法 ID，立刻执行精准点击装填
        if target_tile_id:
            added = False
            for _ in range(10):
                try:
                    active_tile = self.page.locator(f'div[data-tile-id="{target_tile_id}"]').last
                    self._hover(active_tile)
                    
                    more_btn = active_tile.locator('button:has(i:text-is("more_vert")), button[aria-haspopup="menu"]')
                    self._click(more_btn, timeout=1000)
                    self._click('text=/Add to prompt|添加到提示|添加到/i', timeout=1000)
                    
                    added = True
                    self._log("   -> ✅ 成功点击 Add to prompt，垫图已完美送入炮膛！")
                    break
                except: pass
                self.page.keyboard.press("Escape")
                time.sleep(1)
                
            if not added:
                self._log("   -> ⚠️ 垫图入框辅助点击彻底失败 (非致命，但影响出图效果)")

    def action_fill_and_submit(self, payload: TaskPayload):
        if not getattr(self, 'waf_probe_attached', False):
            self.page.on("response", lambda res: setattr(self, 'waf_intercept_count', getattr(self, 'waf_intercept_count', 0) + 1) if res.status in [403, 429] and "google" in res.url else None)
            self.waf_probe_attached = True

        self.pre_ids = set(self.page.locator(self.UI["tile"]).evaluate_all("els => els.map(e => e.getAttribute('data-tile-id'))"))
        self.waf_intercept_count = 0 
        
        self._fill(self.UI["input_box"], payload["prompt"])
        self._click(self.UI["submit_btn"])

    def action_wait_and_download(self, payload: TaskPayload):
        target_num = int(payload.get("engine_params", {}).get("quantity", 4)) 
        self._log(f"   -> ⏳ 启动 ID 差集雷达 (目标: {target_num} 张)...")
        
        start_time = time.time()
        new_ids = set()
        seen_timestamps = {} 
        
        while time.time() - start_time < self.MAX_WAIT_SEC:
            if self.stop_requested: raise Exception("收到中止指令")
            
            if getattr(self, 'waf_intercept_count', 0) >= target_num:
                self._escape_waf_via_clash()
                raise Exception("触发 WAF 封锁")
                
            current_ids = set(self.page.locator(self.UI["tile"]).evaluate_all("els => els.map(e => e.getAttribute('data-tile-id'))"))
            new_ids = current_ids - self.pre_ids
            if len(new_ids) >= target_num: break
            time.sleep(2)
            
        if len(new_ids) < target_num: raise Exception("出图超时")

        out_dir = self._get_download_dir(payload)
        saved_count = 0
        
        for tid in new_ids:
            for attempt in range(3):
                try:  
                    tile = self.page.locator(f'div[data-tile-id="{tid}"]').last
                    tile.locator('img[alt*="生成"], img[alt*="Generated"], img[alt*="generated"]').first.wait_for(state="visible", timeout=60000)
                    
                    if tid not in seen_timestamps:
                        seen_timestamps[tid] = time.time()
                    elapsed = time.time() - seen_timestamps[tid]
                    if elapsed < 8.0:
                        self._log(f"   -> ⏳ 图 [{tid[-6:]}] 渲染冷却中，强制等待 {8.0 - elapsed:.1f} 秒以保证画质...")
                        time.sleep(8.0 - elapsed)

                    self.page.evaluate('const sc = document.querySelector(`div[data-testid="virtuoso-scroller"]`); if(sc) sc.scrollTo(0, 0);')
                    
                    self._hover(tile)
                    more_btn_selector = 'button:has(i:text-is("more_vert")), button:has(i:has-text("more_vert")), button[aria-haspopup="menu"]'
                    self._click(tile.locator(more_btn_selector))
                    
                    fname = f"{payload['task_name']}_{tid.replace('fe_id_', '')[:6]}.png"
                    save_path = os.path.join(out_dir, fname)
                    
                    with self.page.expect_download(timeout=30000) as dl_info:
                        dl_btn = self.page.locator('div[role="menuitem"], button[role="menuitem"]').filter(has_text=re.compile("Download|下载", re.IGNORECASE))
                        self._click(dl_btn) 
                        try:
                            std_btn = self.page.locator('div[role="menuitem"], button[role="menuitem"]').filter(has_text=re.compile("Standard|1k|Default|标准|原始尺寸", re.IGNORECASE)).first
                            if std_btn.is_visible(timeout=1000):
                                self._click(std_btn)
                        except: pass
                    
                    dl_info.value.save_as(save_path)
                    self._log(f"   -> 📥 [物理截获] 成功落盘: {fname}")
                    
                    import threading
                    threading.Thread(target=self._sync_to_eagle, args=(save_path, None, payload, fname)).start()

                    saved_count += 1
                    self.last_saved_path = save_path
                    break
                except Exception as e:
                    self._log(f"   -> ⚠️ 单张图交互异常: {str(e)[:50]}")
                finally:
                    self.page.keyboard.press("Escape")
                time.sleep(1)
                
        if saved_count == 0: raise Exception("全军覆没，重启引擎")