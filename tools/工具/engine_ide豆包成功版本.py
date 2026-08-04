import json
import tempfile
import os
import time
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------
# 🛠️ AutoAI 首席架构师特供：V18 跨次元跃迁版
# (多标签页跨域打击 / SPA无缝支持 / 极致容错)
# ---------------------------------------------------------

CONFIG_FILE = "engine_config.json"
DUMMY_PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

def execute_action(page, action, locator, value, pre_wait_s, post_wait_s, ignore_error):
    try:
        # 秒级单位转换
        if pre_wait_s > 0: page.wait_for_timeout(int(pre_wait_s * 1000))

        if action == "Wait":
            s = float(value) if value else 1.0
            page.wait_for_timeout(int(s * 1000))
            return {"success": True, "msg": f"✅ 等待 {s}s"}
        elif action == "NetIdle":
            page.wait_for_load_state("networkidle", timeout=30000)
            return {"success": True, "msg": f"✅ 网络静默完成"}
        elif action == "Pause":
            print("\n🚨 [停机摇人] 请在浏览器手动操作后，在终端按回车继续...")
            input()
            return {"success": True, "msg": f"✅ 人工干预接管完毕"}
        elif action == "Press":
            page.keyboard.press(value if value else "PageDown")
            return {"success": True, "msg": f"✅ 物理按键 [{value}]"}

        if not locator: return {"success": False, "msg": f"❌ 缺少 Locator 特征码"}
        
        loc = page.locator(locator).first

        if action == "Click":
            loc.click(timeout=3000, force=True)
        elif action == "Hover":
            loc.hover(timeout=3000, force=True)
        elif action == "Fill":
            try:
                loc.fill(value if value else "TEST", timeout=3000)
            except Exception as e:
                if "not an <input>" in str(e) or "contenteditable" in str(e):
                    # 破甲机制：Div 伪装的输入框，先点击聚焦，再用键盘物理敲入！
                    loc.click(timeout=3000, force=True)
                    page.keyboard.insert_text(value if value else "TEST")
                else:
                    raise e
        elif action == "Upload":
            temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
            with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
            try:
                loc.set_input_files(temp_img, timeout=3000)
            except Exception:
                # 穿透机制：无视前端拖拽区遮罩，强行寻找隐藏的原生 input[type="file"]
                page.locator('input[type="file"]').first.set_input_files(temp_img, timeout=3000)
        elif action == "Extract":
            attr = value if value else "src"
            res_data = loc.inner_text(timeout=3000) if attr.lower() in ["text", "innertext"] else loc.get_attribute(attr, timeout=3000)
            return {"success": True, "msg": f"✅ 成功提取战利品: {str(res_data)[:30]}..."}

        if post_wait_s > 0: page.wait_for_timeout(int(post_wait_s * 1000))
        return {"success": True, "msg": f"✅ [{action}] 完美触发"}

    except Exception as e:
        err_msg = str(e).split('\n')[0]
        if ignore_error: return {"success": True, "msg": f"🛡️ [{action}] 触发柔性屏障，已静默跳过"}
        return {"success": False, "msg": f"❌ {err_msg}"}

def run_ide():
    with sync_playwright() as p:
        print("⏳ 正在附身...")
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"❌ 附身失败，请检查 9222 端口是否开启: {e}")
            return

        context = browser.contexts[0]
        
        ui_script = r"""
        (() => {
            if (window.top !== window.self) return; 
            if (window.__autoai_ide_running) return;
            window.__autoai_ide_running = true;

            window.__ide_cmd = null;
            window.__ide_save = null;
            window.__ide_res = null;

            function initPanel() {
                if (document.getElementById('autoai-ide-panel')) return;

                const panel = document.createElement('div');
                panel.id = 'autoai-ide-panel';
                panel.style.cssText = 'position: fixed; left: 10px; top: 10px; width: 480px; height: 550px; max-height: 95vh; display: flex; flex-direction: column; background: #121212; border-radius: 8px; z-index: 2147483647; font-family: monospace; box-shadow: 0 4px 20px rgba(0,0,0,0.8); border: 1px solid #444; overflow: hidden; resize: both;';
                
                panel.innerHTML = `
                    <div id="ide-drag-handle" style="cursor: move; background: #222; padding: 8px 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #000; user-select: none;">
                        <div style="display: flex; gap: 8px;">
                            <button id="btn-pick" style="background: #9C27B0; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;" title="抓结构(点谁就生成一块积木)">🎯 狙击</button>
                            <button id="btn-grab" style="background: #E91E63; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;" title="抓纯文本(点谁就自动提纯文案进剪贴板)">🧲 抓文</button>
                            <button id="btn-add-step" style="background: #2196F3; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;">➕ 加块</button>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button id="btn-run-all" style="background: #FF9800; border: none; padding: 4px 12px; color: white; cursor: pointer; border-radius: 4px; font-size: 13px; font-weight: bold;">▶️ 全跑</button>
                            <button id="btn-save" style="background: #4CAF50; border: none; padding: 4px 12px; color: white; cursor: pointer; border-radius: 4px; font-size: 13px; font-weight: bold;">💾 存盘</button>
                        </div>
                    </div>
                    
                    <div id="steps-container" style="flex: 1; overflow-y: auto; padding: 10px; background: #1a1a1a;"></div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; background: #222; padding: 6px 10px; border-top: 1px solid #333; border-bottom: 1px solid #000;">
                        <span style="font-size: 12px; color: #aaa; font-weight: bold;">运行日志</span>
                        <div style="display: flex; gap: 8px;">
                            <button id="btn-clear-log" style="background: transparent; color: #F44336; border: 1px solid #F44336; border-radius: 3px; padding: 2px 8px; font-size: 12px; cursor: pointer;">🗑️ 清空</button>
                            <button id="btn-copy-log" style="background: transparent; color: #2196F3; border: 1px solid #2196F3; border-radius: 3px; padding: 2px 8px; font-size: 12px; cursor: pointer;">📋 复制</button>
                        </div>
                    </div>
                    <div id="ide-log" style="font-size: 12px; color: #00E676; background: #000; padding: 8px 10px; height: 130px; flex-shrink: 0; overflow-y: auto; margin: 0; box-sizing: border-box;">&gt; 🟢 系统就绪！</div>
                `;
                document.body.appendChild(panel);

                const dragHandle = document.getElementById('ide-drag-handle');
                let isDragging = false, offsetX, offsetY;
                dragHandle.addEventListener('mousedown', (e) => {
                    isDragging = true;
                    offsetX = e.clientX - panel.getBoundingClientRect().left;
                    offsetY = e.clientY - panel.getBoundingClientRect().top;
                });
                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    panel.style.left = (e.clientX - offsetX) + 'px';
                    panel.style.top = (e.clientY - offsetY) + 'px';
                });
                document.addEventListener('mouseup', () => { isDragging = false; });

                document.getElementById('btn-copy-log').addEventListener('click', () => {
                    const logs = document.getElementById('ide-log').innerText;
                    navigator.clipboard.writeText(logs).then(() => {
                        const btn = document.getElementById('btn-copy-log');
                        btn.innerText = '✅ 搞定';
                        setTimeout(() => btn.innerText = '📋 复制', 2000);
                    });
                });
                
                document.getElementById('btn-clear-log').addEventListener('click', () => {
                    document.getElementById('ide-log').innerHTML = '&gt; 🟢 日志已清空';
                });

                const ideLog = (msg) => { 
                    const logBox = document.getElementById('ide-log');
                    logBox.innerHTML += '<br>&gt; ' + msg; 
                    logBox.scrollTop = logBox.scrollHeight;
                };

                function generateLocator(el) {
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        if (el.placeholder) return `${el.tagName.toLowerCase()}[placeholder="${el.placeholder}"] >> visible=true`;
                    }
                    let path = []; let current = el;
                    while (current && current.nodeType === Node.ELEMENT_NODE && current.tagName !== 'BODY' && current.tagName !== 'HTML') {
                        let selector = current.tagName.toLowerCase();
                        let sib = current, nth = 1;
                        while (sib = sib.previousElementSibling) {
                            if (sib.nodeType === Node.ELEMENT_NODE) nth++;
                        }
                        selector += `:nth-child(${nth})`;
                        path.unshift(selector);
                        current = current.parentNode;
                    }
                    return path.join(' > ') + " >> visible=true";
                }

                let isPicking = false; 
                let isGrabbing = false; 
                let lastHighlighted = null;

                document.addEventListener('mouseover', (e) => {
                    if (!isPicking && !isGrabbing) return;
                    if (e.target.closest('#autoai-ide-panel')) return; 
                    if (lastHighlighted) lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                    lastHighlighted = e.target;
                    e.target.dataset.oldOutline = e.target.style.outline;
                    e.target.style.outline = isPicking ? '3px solid #9C27B0' : '3px dashed #E91E63'; 
                    e.stopPropagation();
                }, true);

                document.addEventListener('click', (e) => {
                    if (!isPicking && !isGrabbing) return;
                    if (e.target.closest('#autoai-ide-panel')) return;
                    e.preventDefault(); e.stopPropagation();

                    if (lastHighlighted) {
                        lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                        lastHighlighted = null;
                    }

                    if (isGrabbing) {
                        isGrabbing = false;
                        document.getElementById('btn-grab').style.background = '#E91E63';
                        document.getElementById('btn-grab').innerText = '🧲 抓文';
                        
                        let text = e.target.innerText || "";
                        text = text.split('\n').map(s => s.trim()).filter(s => s.length > 0).join(', ');
                        navigator.clipboard.writeText(text).then(() => {
                            ideLog(`✅ [抓文成功] 已存入剪贴板: ${text.substring(0, 40)}${text.length > 40 ? '...' : ''}`);
                        });
                        return;
                    }

                    if (isPicking) {
                        isPicking = false;
                        document.getElementById('btn-pick').style.background = '#9C27B0';
                        document.getElementById('btn-pick').innerText = '🎯 狙击';
                        addStep('Click', generateLocator(e.target)); 
                        ideLog(`🎯 [锁定] 已生成积木。`);
                    }
                }, true);

                const addStep = (action = 'Click', loc = '') => {
                    const id = 'step-' + Date.now();
                    const html = `
                        <div class="macro-step" data-id="${id}" style="background: #252525; border: 1px solid #444; padding: 10px; margin-bottom: 8px; border-radius: 6px; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">
                            
                            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 4px;">
                                <button class="btn-fold" style="background: transparent; border: none; color: #888; cursor: pointer; font-size: 14px; padding: 0 4px;" title="展开/收起">🔽</button>
                                <select class="step-action" style="background: #333; color: #fff; border: 1px solid #555; padding: 4px 6px; border-radius: 4px; font-size: 13px; width: 75px; font-weight: bold;">
                                    <option value="Click" ${action==='Click'?'selected':''}>点击</option>
                                    <option value="Hover" ${action==='Hover'?'selected':''}>悬停</option>
                                    <option value="Fill" ${action==='Fill'?'selected':''}>填字</option>
                                    <option value="Upload" ${action==='Upload'?'selected':''}>传图</option>
                                    <option value="Wait" ${action==='Wait'?'selected':''}>等待</option>
                                    <option value="NetIdle" ${action==='NetIdle'?'selected':''}>静默</option>
                                    <option value="Extract" ${action==='Extract'?'selected':''}>提取</option>
                                    <option value="Pause" ${action==='Pause'?'selected':''}>人工</option>
                                    <option value="Press" ${action==='Press'?'selected':''}>按键</option>
                                </select>
                                <input class="step-memo" placeholder="📝 灵魂备注 (给大模型的留言)" style="flex: 1; background: #3b3a20; color: #ffd700; border: 1px solid #8a8000; padding: 4px 8px; font-size: 13px; border-radius: 4px;">
                                
                                <div style="display: flex; gap: 4px;">
                                    <button class="btn-up" title="上移" style="background: #333; border: 1px solid #555; border-radius: 3px; cursor: pointer; font-size: 12px; padding: 2px 4px;">⬆️</button>
                                    <button class="btn-down" title="下移" style="background: #333; border: 1px solid #555; border-radius: 3px; cursor: pointer; font-size: 12px; padding: 2px 4px;">⬇️</button>
                                    <button class="btn-del" title="删除" style="background: transparent; color: #F44336; border: none; cursor: pointer; font-size: 14px; padding: 2px 4px;">❌</button>
                                </div>
                            </div>

                            <div class="step-body" style="display: flex; flex-direction: column; gap: 8px; padding-left: 28px; margin-top: 8px;">
                                <div style="display: flex; gap: 6px;">
                                    <input class="step-loc" value='${loc.replace(/'/g, "&#39;")}' placeholder="定位器 (Locator)" style="flex: 1; background: #111; color: #00FF00; border: 1px solid #555; padding: 4px 8px; font-size: 12px; font-family: monospace; border-radius: 3px;">
                                    <input class="step-val" placeholder="参数" style="width: 100px; background: #111; color: #fff; border: 1px solid #555; padding: 4px 8px; font-size: 13px; border-radius: 3px;">
                                </div>
                                <div style="display: flex; gap: 10px; align-items: center; background: #1e1e1e; padding: 4px 8px; border-radius: 4px;">
                                    <span style="font-size: 12px; color: #aaa;">前等(s)</span>
                                    <input class="step-pre" type="number" step="0.1" value="0" style="width: 45px; background: #111; color: #aaa; border: 1px solid #444; font-size: 12px; padding: 2px 4px; text-align: center; border-radius: 3px;">
                                    <span style="font-size: 12px; color: #aaa;">后等(s)</span>
                                    <input class="step-post" type="number" step="0.1" value="0" style="width: 45px; background: #111; color: #aaa; border: 1px solid #444; font-size: 12px; padding: 2px 4px; text-align: center; border-radius: 3px;">
                                    
                                    <label style="font-size: 12px; color: #FF9800; cursor: pointer; display: flex; align-items: center; margin-left: 10px;" title="遇到找不到元素的报错时，静默跳过">
                                        <input type="checkbox" class="step-ignore" style="margin:0 4px 0 0;"> 🛡️ 忽略报错
                                    </label>
                                    
                                    <div style="flex: 1;"></div>
                                    <button class="btn-run-single" style="background: #2E7D32; color: #fff; border: none; cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">🧪 试跑此步</button>
                                </div>
                            </div>
                        </div>
                    `;
                    document.getElementById('steps-container').insertAdjacentHTML('beforeend', html);
                };

                const runStep = async (stepDiv) => {
                    window.__ide_res = null;
                    window.__ide_cmd = {
                        action: stepDiv.querySelector('.step-action').value,
                        locator: stepDiv.querySelector('.step-loc').value,
                        value: stepDiv.querySelector('.step-val').value,
                        pre_wait_s: parseFloat(stepDiv.querySelector('.step-pre').value) || 0,
                        post_wait_s: parseFloat(stepDiv.querySelector('.step-post').value) || 0,
                        ignore_error: stepDiv.querySelector('.step-ignore').checked
                    };
                    while (!window.__ide_res) { await new Promise(r => setTimeout(r, 100)); }
                    let res = window.__ide_res;
                    window.__ide_res = null;
                    return res;
                };

                panel.addEventListener('click', async (e) => {
                    if (e.target.id === 'btn-pick') {
                        isPicking = !isPicking;
                        isGrabbing = false; 
                        e.target.style.background = isPicking ? '#F44336' : '#9C27B0';
                        e.target.innerText = isPicking ? '⏹️ 停' : '🎯 狙击';
                        document.getElementById('btn-grab').style.background = '#E91E63';
                        document.getElementById('btn-grab').innerText = '🧲 抓文';
                        if (!isPicking && lastHighlighted) lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                        ideLog(isPicking ? "🎯 [雷达激活] 点击网页元素，自动生成积木。" : "⏹️ 雷达关闭。");
                    }
                    
                    if (e.target.id === 'btn-grab') {
                        isGrabbing = !isGrabbing;
                        isPicking = false; 
                        e.target.style.background = isGrabbing ? '#F44336' : '#E91E63';
                        e.target.innerText = isGrabbing ? '⏹️ 停' : '🧲 抓文';
                        document.getElementById('btn-pick').style.background = '#9C27B0';
                        document.getElementById('btn-pick').innerText = '🎯 狙击';
                        if (!isGrabbing && lastHighlighted) lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                        ideLog(isGrabbing ? "🧲 [抓取激活] 点击下拉框，自动提取文本进剪贴板。" : "⏹️ 抓取关闭。");
                    }

                    if (e.target.id === 'btn-add-step') addStep();
                    
                    if (e.target.classList.contains('btn-del')) e.target.closest('.macro-step').remove();
                    
                    if (e.target.classList.contains('btn-fold')) {
                        const body = e.target.closest('.macro-step').querySelector('.step-body');
                        const isHidden = body.style.display === 'none';
                        body.style.display = isHidden ? 'flex' : 'none';
                        e.target.innerText = isHidden ? '🔽' : '🔼';
                    }

                    if (e.target.classList.contains('btn-up')) {
                        const step = e.target.closest('.macro-step');
                        if (step.previousElementSibling) step.parentNode.insertBefore(step, step.previousElementSibling);
                    }

                    if (e.target.classList.contains('btn-down')) {
                        const step = e.target.closest('.macro-step');
                        if (step.nextElementSibling) step.parentNode.insertBefore(step.nextElementSibling, step);
                    }
                    
                    if (e.target.classList.contains('btn-run-single')) {
                        const stepDiv = e.target.closest('.macro-step');
                        ideLog(`&gt; 执行: [${stepDiv.querySelector('.step-action').value}]...`);
                        ideLog((await runStep(stepDiv)).msg);
                    }

                    if (e.target.id === 'btn-run-all') {
                        const steps = document.querySelectorAll('.macro-step');
                        ideLog("▶️ 开始行云流水般的全自动试跑...");
                        for (let i = 0; i < steps.length; i++) {
                            const res = await runStep(steps[i]);
                            ideLog(`[步${i+1}] ` + res.msg);
                            if(!res.success) break;
                        }
                    }

                    if (e.target.id === 'btn-save') {
                        let sequence = [];
                        document.querySelectorAll('.macro-step').forEach(stepDiv => {
                            sequence.push({
                                "action": stepDiv.querySelector('.step-action').value,
                                "locator": stepDiv.querySelector('.step-loc').value,
                                "value": stepDiv.querySelector('.step-val').value,
                                "pre_wait_s": parseFloat(stepDiv.querySelector('.step-pre').value) || 0,
                                "post_wait_s": parseFloat(stepDiv.querySelector('.step-post').value) || 0,
                                "ignore_error": stepDiv.querySelector('.step-ignore').checked,
                                "memo": stepDiv.querySelector('.step-memo').value
                            });
                        });
                        
                        window.__ide_res = null;
                        window.__ide_save = sequence;
                        ideLog("💾 正在向后端物理交接情报...");
                        while (!window.__ide_res) { await new Promise(r => setTimeout(r, 100)); }
                        ideLog(window.__ide_res.msg);
                        window.__ide_res = null;
                    }
                });
            }

            // 支持 SPA 动态路由加载
            setInterval(() => { if (document.body && !document.getElementById('autoai-ide-panel')) initPanel(); }, 1000);
            initPanel();
        })();
        """
        
        context.add_init_script(ui_script)
        
        # 初始注入
        for page in context.pages:
            try: page.evaluate(ui_script)
            except: pass

        print("\n" + "=".rjust(50, "="))
        print("🚀 V18 跨次元终极装甲 启动！")
        print("👉 支持多标签页跃迁，支持 SPA 热更新，解决一切遮罩。")
        print("=".rjust(50, "=") + "\n")

        # 【核心突破】：神级多标签页监听环 (Multi-Tab Polling)
        while True:
            try:
                # 防御：如果没有打开的网页，就稍微睡一会儿，防止死循环崩盘
                if not context.pages:
                    time.sleep(0.1)
                    continue
                
                # 【目标执行页】：永远只操作你眼睛正看着的、最新弹出的那个标签页！
                target_page = context.pages[-1]

                # 【信号接收站】：巡视所有可能挂着面板的页面
                for sender_page in context.pages:
                    if sender_page.is_closed(): continue
                    
                    # 查收存盘请求
                    save_data = sender_page.evaluate("window.__ide_save")
                    if save_data:
                        sender_page.evaluate("window.__ide_save = null")
                        try:
                            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                                json.dump({"target_url": target_page.url, "sequence": save_data}, f, ensure_ascii=False, indent=4)
                            res = {"success": True, "msg": f"💾 情报已安全存入 {CONFIG_FILE}"}
                        except Exception as e:
                            res = {"success": False, "msg": f"❌ 存盘失败: {str(e)}"}
                        sender_page.evaluate("res => { window.__ide_res = res; }", res)

                    # 查收动作请求
                    cmd = sender_page.evaluate("window.__ide_cmd")
                    if cmd:
                        sender_page.evaluate("window.__ide_cmd = null")
                        # 物理隔离：接收指令的可能在 A 页面，但执行动作绝对是在最新的 target_page！
                        res = execute_action(
                            target_page, cmd["action"], cmd["locator"], cmd["value"], 
                            cmd["pre_wait_s"], cmd["post_wait_s"], cmd["ignore_error"]
                        )
                        # 执行完，把结果传回给发指令的旧页面
                        sender_page.evaluate("res => { window.__ide_res = res; }", res)
                        
            except Exception:
                pass # 遇到页面刚刚刷新/跳转时的瞬间抛错，直接静默吞掉，维持稳定
            
            time.sleep(0.1)

if __name__ == "__main__":
    run_ide()