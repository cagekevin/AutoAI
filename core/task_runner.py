import json
import logging
import threading
import importlib
import os
import re
import hashlib
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from core.image_processor import processor 
from core.task_ledger import ledger 

class TaskRunner:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.is_running = False
        self.current_engine = None
        self.lock = threading.Lock()
        
        # ================= 🚀 Mini-Queue Pro 核心状态 =================
        self.day_queue = []          # 大一统队列：白天动态任务与夜间批量任务都在这里排队
        self.current_task = None     # 当前引擎正在执行的"工作铭牌"
        self.total_count = 0         # 本轮总计收到了多少个任务
        self.current_mode = "idle"   # 当前运行模式状态
        self.stop_requested = False  # 防点火预热期的幽灵启动
        
        # [Fix: 新增柔性暂停状态标识，作为主循环水坝的物理开关]
        self.soft_paused = False
        
        # 🔌 开机自启：自动从硬盘读取未完成的残留任务
        self._load_queue_from_disk()
        # ==============================================================

    # ================= 💾 全自动记忆模块 (Auto-Save) =================
    def _load_queue_from_disk(self):
        """开机自动读档：恢复上一次关闭服务器时的排队状态"""
        backup_file = "queue_backup.json"
        if os.path.exists(backup_file):
            try:
                with open(backup_file, "r", encoding="utf-8") as f:
                    self.day_queue = json.load(f)
                    self.total_count = len(self.day_queue)
                if self.day_queue:
                    logging.info(f"💾 [断电恢复] 成功从本地档案中唤醒了 {len(self.day_queue)} 个排队任务！")
            except Exception as e:
                logging.error(f"⚠️ [断电恢复] 档案读取失败，队列重置: {e}")

    def _save_queue_to_disk(self):
        """静默自动存档：调用前必须确保已持有 self.lock"""
        try:
            with open("queue_backup.json", "w", encoding="utf-8") as f:
                json.dump(self.day_queue, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"⚠️ [持久化] 自动保存队列缓存失败: {e}")
    # ==============================================================

    def load_config(self):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def _pre_flight_check(self, config):
        logging.info("🛂 [调度中心] 正在执行引擎起飞前环境安检...")
        assets_dir = os.path.abspath(os.path.join("assets", "references"))
        if not os.path.exists(assets_dir):
            logging.warning(f"⚠️ [安检] 发现缺失核心资源目录，已自动重建: {assets_dir}")
            os.makedirs(assets_dir, exist_ok=True)
            
        proxy = config.get("global_settings", {}).get("network", {}).get("proxy_server", "")
        if proxy and not proxy.startswith("http"):
            raise ValueError(f"代理地址格式异常！必须包含 http:// 前缀。当前错误值: {proxy}")
            
        logging.info("✅ [调度中心] 安检通过！本地 I/O 与网络配置规范无异常。")

    def _standardize_day_prompts(self, raw_prompts, fallback_image="", aspect_ratio="", inject_dna=False):
        """白天版洗菜机：清洗微型语法 [img.jpg]"""
        standardized = []
        for i, p in enumerate(raw_prompts):
            p = p.strip()
            if not p: continue
            match = re.search(r'\[(.*?\.(?:jpg|jpeg|png|webp))\]', p, re.IGNORECASE)
            img_name = match.group(1).strip() if match else fallback_image
            img_path = os.path.abspath(os.path.join("assets", "references", img_name)) if img_name else ""
            clean_text = re.sub(r'\[(.*?\.(?:jpg|jpeg|png|webp))\]', '', p, flags=re.IGNORECASE).strip()

            unique_salt = f"{p}_{time.time()}_{i}"
            
            standardized.append({
                "task_name": f"DayTask_{hashlib.md5(unique_salt.encode()).hexdigest()[:6]}",
                "prompt": clean_text,
                "image_path": img_path,
                "dna_dict": {
                    "Metadata": {"Image_Prompt": clean_text, "Preset_Name": "白天打样", "Preset_Group": "日间手动队列"},
                    "Vault_L_Structure": {"来源引擎": "控制台指令舱"}
                } if inject_dna else {},
                # [Fix: 将前端传来的散装参数标准化打包为 engine_params，与底层引擎的读取规范对齐]
                "engine_params": {
                    "aspect_ratio": aspect_ratio
                }
            })
        return standardized

    def _prepare_night_tasks(self, mode_cfg):
        """夜间版洗菜机：全面接管 Excel 读取与 DNA 匹配"""
        logging.info("☁️ [调度中心] 正在从云端拉取 Excel 超级数据包...")
        try:
            all_sheets = pd.read_excel(mode_cfg.get("data_source_url"), sheet_name=None)
            df_tasks = all_sheets.get('提示词输出', pd.DataFrame()).fillna('')
            df_presets = all_sheets.get('Presets_Vault', pd.DataFrame()).fillna('')
            if df_tasks.empty:
                raise Exception("找不到名为 '提示词输出' 的工作表！请检查表格名称。")
        except Exception as e:
            raise Exception(f"云端读取失败: {e}")

        inject_dna = mode_cfg.get("inject_dna", False)
        
        if inject_dna:
            df_core = all_sheets.get('Dict_Core', pd.DataFrame()).fillna('')
            df_motion = all_sheets.get('Dict_Motion', pd.DataFrame()).fillna('')
            dict_df = pd.concat([df_core, df_motion], ignore_index=True)
        else:
            dict_df = pd.DataFrame()

        standardized = []
        
        for _, row in df_tasks.iterrows():
            prompt = str(row.get('图片提示词', '')).strip()
            if not prompt: continue
                
            raw_task_name = str(row.get('预设名称', '')).strip()
            if not raw_task_name or raw_task_name.lower() == "nan":
                raw_task_name = "Task_" + hashlib.md5(prompt.encode('utf-8')).hexdigest()[:8]
            task_name = re.sub(r'[\\/*?:"<>|]', "_", raw_task_name)

            dna_data = {}
            if inject_dna:
                preset_vault_info = {}
                if not df_presets.empty and raw_task_name:
                    match = df_presets[df_presets['预设名称'] == raw_task_name]
                    if not match.empty:
                        preset_vault_info = {str(k): str(v) for k, v in match.iloc[0].to_dict().items() if str(v).strip()}
                
                matched_tags = []
                if not dict_df.empty:
                    for _, d_row in dict_df.iterrows():
                        en_prompt = next((str(v) for k, v in d_row.items() if "英文" in str(k) or "Prompt" in str(k)), "")
                        if en_prompt and en_prompt.lower() in prompt.lower():
                            matched_tags.append({str(k): str(v) for k, v in d_row.items() if str(v).strip()})
                
                dna_data = {
                    "Metadata": {"Preset_Name": raw_task_name, "Preset_Group": str(row.get('预设分组', '')), "Image_Prompt": prompt, "Video_Prompt": str(row.get('视频提示词', ''))},
                    "Vault_L_Structure": preset_vault_info,
                    "Deep_Dictionary": matched_tags
                }

            # 🌟 核心升级：从 Excel 提取比例列，并注入站点契约解决 Unknown 路径问题
            excel_ratio = str(row.get('画面比例', '')).strip() or "9:16"
            
            standardized.append({
                "task_name": task_name, 
                "prompt": prompt, 
                "image_path": os.path.abspath(os.path.join("assets", "references", str(row.get('图片路径', '')).strip())) if str(row.get('图片路径', '')).strip() else "", 
                "dna_dict": dna_data,
                "target_site": site_name,  # 🌟 必须注入，否则父类下载器找不到对应目录
                "engine_params": {
                    "aspect_ratio": excel_ratio,
                    "burst_count": 8
                }
            })
            
        logging.info(f"✅ [调度中心] 核心数据清洗完毕: 成功解析 {len(standardized)} 条标准流水线任务！")
        return standardized

    # ================= 🚀 动态队列核心操作 =================
    
    def start_day_queue(self, prompts, site_name=None, image_name="", aspect_ratio="", inject_dna=True, auto_start=True):
        """
        全能入队口：支持 Webhook 静默入队 (auto_start=False) 与 UI 点火启动 (auto_start=True)
        默认 inject_dna=True，确保 Webhook 任务默认带标签进 Eagle
        """
        # 1. 物理洗菜：转换为标准任务格式
        new_tasks = self._standardize_day_prompts(prompts, image_name, aspect_ratio, inject_dna) 
        
        with self.lock:
            if new_tasks:
                self.day_queue.extend(new_tasks)
                self.total_count += len(new_tasks)
                self._save_queue_to_disk()  # 💾 自动落盘存档
            
            if not self.day_queue:
                return False, "⚠️ 大厅空空如也，请先添加任务！"
                
            # 🛡️ 核心拦截器：Webhook 专用逻辑
            if not auto_start:
                return True, f"✅ 任务已静默装填 (共 {len(new_tasks)} 个)，等待手动点火。"

            # --- 以下为点火逻辑 (UI 点击启动时触发) ---
            if self.is_running:
                if new_tasks:
                    return True, f"✅ 成功追加 {len(new_tasks)} 个任务到排队序列！"
                else:
                    return False, "⚠️ 引擎已经在运行中，请勿重复点击启动！"
            
            if not site_name:
                return False, "❌ 启动失败：未指定执行引擎（site_name）。"

            self.is_running = True
            self.current_mode = "day"   
            
        # 🚀 引擎开火
        self.executor.submit(self._run_wrapper, site_name, "day")
        return True, "🚀 引擎已点火！开始消费大厅流水线任务。"

    def remove_from_queue(self, target_task_name):
        """精准撤单：同步修正排队数组与历史分母"""
        with self.lock:
            for i, task in enumerate(self.day_queue):
                if task.get("task_name") == target_task_name:
                    removed_task = self.day_queue.pop(i)
                    self.total_count -= 1  
                    self._save_queue_to_disk()  # 💾 自动存档
                    return True, f"已成功撤单: {removed_task.get('prompt')[:10]}..."
            return False, "❌ 操作失败：找不到指定的排队任务（可能刚被引擎接管）。"

    def clear_all_queue(self):
        """一键清场：代替前端疯狂发请求，瞬间归零"""
        with self.lock:
            self.day_queue.clear()
            self.total_count = 0
            self._save_queue_to_disk()  # 💾 自动存档
        return True, "🗑️ 大厅任务已全部清空！"

    def move_task_to_top(self, target_task_name):
        """[Fix: 柔性插队 - 将目标任务物理转移至队列 0 号位，确保下一次必定拉取此任务]"""
        with self.lock:
            for i, task in enumerate(self.day_queue):
                if task.get("task_name") == target_task_name:
                    if i == 0:
                        return True, "🌟 报告：该任务已在火力最前线，无需插队！"
                    moved_task = self.day_queue.pop(i)
                    self.day_queue.insert(0, moved_task)
                    self._save_queue_to_disk()
                    return True, f"🚀 插队成功: {moved_task.get('prompt')[:10]}..."
            return False, "❌ 操作失败：找不到指定的排队任务（可能已进炉子或已撤单）。"

    def toggle_soft_pause(self):
        """[Fix: 柔性暂停 - 反转水坝开关，不杀浏览器，当前任务跑完即悬停]"""
        with self.lock:
            if not self.is_running:
                return False, "⚠️ 拦截：当前没有运行中的流水线，无需暂停！"
            self.soft_paused = not self.soft_paused
            status = "⏸️ 阀门已关：流水线进入柔性暂停（当前图跑完后原地待命）" if self.soft_paused else "▶️ 阀门已开：柔性暂停解除，流水线继续狂奔！"
            return True, status

    def start_task(self, site_name, mode, **kwargs):
        """挂机启动方式（极简互斥版：运行中绝对禁止新模式启动）"""
        with self.lock:
            if self.is_running:
                return False, "⚠️ 拦截：当前已有任务正在运行中！请先点击【🛑 停止】清场后，再启动新模式。"
            
            self.is_running = True
            self.current_mode = mode   
            
        self.executor.submit(self._run_wrapper, site_name, mode, **kwargs)
        return True, f"✅ 任务已推入执行舱 ({site_name} - {mode}模式)"

    # ================= 🚀 终极调度中枢与通用熔断器 =================

    def _run_wrapper(self, site_name, mode, **kwargs):
        self.stop_requested = False  
        logging.info(f"🚀 收到前端指令，正在后台独立舱初始化 [{site_name}] 引擎 (模式: {mode})...")
        try:
            config = self.load_config()
            self._pre_flight_check(config)
            
            if self.stop_requested:
                logging.warning("🛑 预热期拦截：检测到紧急制动指令，已安全终止引擎启动！")
                return
                
            global_cfg = config.get("global_settings", {})
            engine_cfg = config.get("sites", {}).get(site_name, {})
            mode_cfg = engine_cfg.get(f"{mode}_mode", {})

            # 🛠️ 1. 夜间模式数据灌入大一统队列
            if mode == "night":
                night_tasks = self._prepare_night_tasks(mode_cfg)
                with self.lock:
                    # 🪓 柔性追加：绝不清空白天的残留任务，老老实实排在后面！
                    self.day_queue.extend(night_tasks)
                    self.total_count += len(night_tasks)
                    self._save_queue_to_disk()  # 💾 自动存档

            # 🛠️ 2. 挂载引擎模块
            module_name = f"plugins.{site_name}_engine"
            plugin_module = importlib.import_module(module_name)
            
            # 动态拼接类名，例如 "flow" -> "FlowEngine"
            target_class_name = f"{site_name.capitalize()}Engine"
            engine_class = getattr(plugin_module, target_class_name)
            
            # 无参实例化（配合 base_engine 中彻底废弃 config.json 的重构）
            self.current_engine = engine_class()

            # 🛠️ 3. 首次开启浏览器环境
            logging.info("🔗 正在挂载纯净浏览器环境 (Setup)...")
            self.current_engine.setup()  # 删掉括号里的参数

            consecutive_failures = 0

            # 🛠️ 4. 中枢大循环 (The Brain Loop)
            while True:
                if self.stop_requested:
                    logging.info("🛑 中枢收到制动指令，正在中断主循环...")
                    break

                # [Fix: 柔性暂停水坝 - 开启时让线程进入低耗休眠，绝不触碰队列，且保持浏览器存活]
                while getattr(self, 'soft_paused', False) and not self.stop_requested:
                    time.sleep(1)
                
                if self.stop_requested: # 睡眠中被紧急掐断则直接跳出
                    break

                with self.lock:
                    if not self.day_queue:
                        logging.info("🏁 队列已清空，所有任务执行完毕！")
                        break
                    
                    # 安全拿取一个任务
                    current_task_data = self.day_queue.pop(0)
                    self.current_task = current_task_data.get("task_name")
                    self._save_queue_to_disk()  # 💾 自动存档：抽走一个少一个，实时更新硬盘
                    
                    current_idx = self.total_count - len(self.day_queue)
                    logging.info(f"📊 进度: {current_idx}/{self.total_count}")
                    
                if mode == "night":
                    is_done, who_did_it = ledger.check_task_completed(current_task_data.get("prompt"), current_task_data.get("image_path"))
                    if is_done:
                        logging.info(f"⏭️ [智能拦截] 账本核实该任务已由 [{who_did_it}] 完成，直接跳过！")
                        continue 

                logging.info(f"🎯 [中枢分发] 提取任务: {self.current_task}")

                prompt = current_task_data.get("prompt", "")
                raw_image = current_task_data.get("image_path", "")

                try:
                    success, result = self.current_engine.process_single(current_task_data)

                    if success:
                        logging.info(f"✅ [中枢结算] 任务成功，路径: {result}。触发中心记账。")
                        ledger.record_task(prompt, raw_image, "成功", site_name)
                        consecutive_failures = 0 
                    else:
                        raise Exception(f"任务执行失败返回: {result}")

                except Exception as e:
                    consecutive_failures += 1
                    err_msg = str(e)
                    logging.error(f"❌ [异常熔断] 任务崩溃: {err_msg}。触发通用环境净化协议 (掀桌子)!")
                    retries = current_task_data.get("retry_count", 0)
                    if retries < 2:  # 给 2 次复活机会 (总共最多试 3 次)
                        current_task_data["retry_count"] = retries + 1
                        logging.info(f"⚠️ [容错回收] 任务执行中断 (第{retries+1}次重试)，已重新投入排队序列。")
                        with self.lock:
                            self.day_queue.append(current_task_data) # 扔回队尾排队
                            self._save_queue_to_disk()
                    else:
                        logging.error(f"❌ [死信丢弃] 任务连续 3 次硬启动失败，已作为坏死任务从内存彻底抹除！")
                        ledger.record_task(prompt, raw_image, f"失败: {err_msg[:50]}", site_name)
                    
                    
                    if "收到停止指令" in err_msg or self.stop_requested:
                        break

                    try:
                        self.current_engine.teardown()
                    except Exception as td_err:
                        logging.error(f"⚠️ [强制清理] 清理残留进程时遇到阻碍 (可忽略): {td_err}")

                    meltdown_cfg = mode_cfg.get("meltdown_protection", {})
                    max_fails = meltdown_cfg.get("meltdown_failures", 3)
                    sleep_secs = meltdown_cfg.get("meltdown_sleep_seconds", 600)

                    if consecutive_failures >= max_fails:
                        logging.error(f"❌ [极限熔断] 连续 {max_fails} 次硬启动失败！系统强切至 {sleep_secs} 秒静默休眠防封锁...")
                        for _ in range(sleep_secs // 10): 
                            if self.stop_requested: break
                            time.sleep(10)
                        consecutive_failures = 0 

                    if self.stop_requested:
                        break

                    logging.info("🔄 [中枢自愈] 正在重新注入纯净浏览器环境...")
                    try:
                        self.current_engine.setup()  # 删掉括号里的参数
                    except Exception as setup_e:
                        logging.error(f"❌ [中枢自愈] 重建环境失败，流水线致命瘫痪: {setup_e}")
                        break 

        except Exception as e:
            logging.error(f"❌ 调度器捕获到系统级致命异常: {e}")
        finally:
            logging.info("📦 正在通知后台打标车间处理残余图像并安全下班...")
            processor.wait_and_stop()

            if self.current_engine:
                try:
                    self.current_engine.teardown()
                except:
                    pass

            with self.lock:
                self.is_running = False
                self.current_mode = "idle"  
                self.current_engine = None
                self.current_task = None
            logging.info("💤 调度器已完全释放硬件资源，处于空闲待命状态。")

    def stop_task(self):
        with self.lock:
            self.stop_requested = True 
            # [Fix: 强行重置柔性暂停，防止下次点火直接陷入幽灵卡死]
            self.soft_paused = False
            if not self.is_running:
                return False, "当前没有运行中的任务。"
            if self.current_engine:
                self.current_engine.stop_requested = True
            return True, "🛑 已发送停止指令，将在当前节点清理完毕后安全退出。"

    def confirm_resume(self):
        with self.lock:
            if not self.is_running or self.current_engine is None:
                return False, "当前没有等待确认的任务。"
            if hasattr(self.current_engine, 'resume_event'):
                self.current_engine.resume_event.set()
                return True, "▶️ 已发送放行指令，流水线开始狂奔！"
            return False, "引擎不支持手动放行。"

    def sync_cloud_config(self, engine_name):
        """真正的云控核心：拉取表格 Cloud_Config 页的键值对，热更新本地 JSON"""
        with self.lock:
            try:
                logging.info(f"☁️ [云控中心] 正在连接云端表格，拉取 [{engine_name}] 的最新配置...")
                
                local_config = self.load_config()
                url = local_config.get("sites", {}).get(engine_name, {}).get("night_mode", {}).get("data_source_url", "")
                
                if not url:
                    return False, local_config, "❌ 同步失败：本地未配置该引擎的数据源 URL！"

                all_sheets = pd.read_excel(url, sheet_name=None)
                if not all_sheets:
                    return False, local_config, "❌ 同步失败：云端表格内容为空！"

                df_config = all_sheets.get("Cloud_Config")
                if df_config is None or df_config.empty:
                    return False, local_config, "❌ 同步失败：未找到名为 'Cloud_Config' 的工作表！"
                    
                df_config = df_config.fillna('')
                logging.info(f"📄 成功锁定云控表: [Cloud_Config]，正在执行参数热覆写...")

                engine_config = local_config.setdefault("sites", {}).setdefault(engine_name, {})

                def parse_value(val):
                    if isinstance(val, bool): return val
                    if isinstance(val, (int, float)): 
                        return int(val) if val == int(val) else val
                    
                    val_str = str(val).strip()
                    if not val_str: return val_str
                    if val_str.upper() == 'TRUE': return True
                    if val_str.upper() == 'FALSE': return False
                    if val_str.isdigit(): return int(val_str)
                    
                    if ',' in val_str: 
                        return [x.strip() for x in val_str.split(',') if x.strip()]
                    return val_str

                for _, row in df_config.iterrows():
                    key_path = str(row.iloc[0]).strip()
                    raw_value = row.iloc[1]
                    
                    if not key_path or key_path == "参数名 (配置键)" or key_path.startswith("#"):
                        continue
                        
                    parsed_value = parse_value(raw_value)
                    
                    keys = key_path.split('.')
                    if keys[0] == "global_settings":
                        target_dict = local_config 
                    else:
                        target_dict = engine_config 
                        
                    for key in keys[:-1]:
                        target_dict = target_dict.setdefault(key, {})
                    target_dict[keys[-1]] = parsed_value

                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(local_config, f, indent=4, ensure_ascii=False)
                    
                logging.info(f"✅ [云控中心] 本地配置已被云端参数成功覆写！")
                return True, local_config, "✅ 云端配置已成功同步并覆盖本地！"

            except Exception as e:
                logging.error(f"❌ [云控中心] 同步致命异常: {e}")
                return False, self.load_config(), f"同步失败: {str(e)}"

runner = TaskRunner()