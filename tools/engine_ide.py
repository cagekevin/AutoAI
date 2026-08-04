import os
import time
import json
import base64
import tempfile
import platform
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------
# 👑 AutoAI 首席架构师特供：全域雷达·终极融合版
# (抗干扰寻址 / 深层锚点抓取 / 阶梯武器分发)
# ---------------------------------------------------------

CONFIG_FILE = "engine_config.json"
DUMMY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAA6SURBVGhD7cExAQAAAMKg9U9tCy8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgqQBWgAAB2pD5ZAAAAABJRU5ErkJggg==")

# =========================================================
# ⚔️ 武器库：最终的三阶梯武器库版本
# (L1豆包原版 / L2纯净标准版 / L3 Lovart破甲版)
# =========================================================
def execute_action(page, action, locator, value, pre_wait_s, post_wait_s, ignore_error, adapter_level="level1"):
    try:
        if pre_wait_s > 0: page.wait_for_timeout(int(pre_wait_s * 1000))

        if action == "Wait":
            page.wait_for_timeout(int((float(value) if value else 1.0) * 1000))
            return {"success": True, "msg": f"✅ 等待 {value}s"}
        elif action == "NetIdle":
            page.wait_for_load_state("networkidle", timeout=30000)
            return {"success": True, "msg": f"✅ 网络静默完成"}
        elif action == "Pause":
            print("\n🚨 [停机摇人] 请手动操作后，在终端按回车...")
            input()
            return {"success": True, "msg": f"✅ 人工干预完毕"}
        elif action == "Press":
            page.keyboard.press(value if value else "PageDown")
            return {"success": True, "msg": f"✅ 物理按键 [{value}]"}

        if not locator: return {"success": False, "msg": f"❌ 缺少 Locator"}
        
        # --- 🌟 补回：原生等待与 Iframe 穿透兜底 ---
        loc = page.locator(locator).first
        try:
            # 强制让底层引擎死盯 3 秒，等元素挂载，完美解决 L3 的 JS 瞬间报错问题
            loc.wait_for(state="attached", timeout=3000)
        except Exception:
            # 如果主页面 3 秒没出来，下潜到 Iframe 里找（找回老版本的跨域能力）
            for frame in page.frames:
                try:
                    floc = frame.locator(locator).first
                    floc.wait_for(state="attached", timeout=1000)
                    loc = floc
                    break
                except Exception:
                    continue

        # ==========================================
        # 🟢 L1: 豆包原版 (你的最爱：自带 force=True 与智能降级)
        # ==========================================
        if adapter_level == "level1":
            if action == "Click":
                loc.click(timeout=3000, force=True)
            elif action == "Hover":
                loc.hover(timeout=3000, force=True)
            elif action == "Fill":
                try:
                    loc.fill(value if value else "TEST", timeout=3000)
                except Exception as e:
                    if "not an <input>" in str(e) or "contenteditable" in str(e):
                        loc.click(timeout=3000, force=True)
                        page.keyboard.insert_text(value if value else "TEST")
                    else:
                        raise e
            elif action == "Upload":
                temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
                with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
                try: loc.set_input_files(temp_img, timeout=3000)
                except Exception: page.locator('input[type="file"]').first.set_input_files(temp_img, timeout=3000)

        # ==========================================
        # 🟡 L2: 纯净标准版 (不用 force，专治 force=True 误点遮罩的奇葩网页)
        # ==========================================
        elif adapter_level == "level2":
            if action == "Click": loc.click(timeout=3000)
            elif action == "Hover": loc.hover(timeout=3000)
            elif action == "Fill": loc.fill(value if value else "TEST", timeout=3000)
            elif action == "Upload":
                temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
                with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
                loc.set_input_files(temp_img, timeout=3000)

        # ==========================================
        # 🔴 L3: Lovart 破甲版 (纯底层事件分发)
        # ==========================================
        elif adapter_level == "level3":
            if action == "Click":
                try: loc.focus(timeout=500)
                except: pass
                loc.evaluate("""el => {
                    const opts = {bubbles: true, cancelable: true, pointerId: 1};
                    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(t => el.dispatchEvent(new window[t.includes('pointer') ? 'PointerEvent' : 'MouseEvent'](t, opts)));
                }""")
            elif action == "Hover":
                loc.hover(timeout=3000, force=True)
            elif action == "Fill":
                try: loc.focus(timeout=500)
                except: pass
                loc.click(timeout=1000, force=True)
                page.keyboard.press("Meta+A" if platform.system() == "Darwin" else "Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.insert_text(value if value else "TEST")
            elif action == "Upload":
                temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
                with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
                try: loc.set_input_files(temp_img, timeout=3000)
                except Exception: page.locator('input[type="file"]').first.set_input_files(temp_img, timeout=3000)

        # --- 提取动作 (通用) ---
        if action == "Extract":
            attr = value if value else "text"
            res_data = loc.inner_text(timeout=3000) if attr.lower() in ["text", "innertext"] else loc.get_attribute(attr, timeout=3000)
            return {"success": True, "msg": f"✅ 提取战利品: {str(res_data)[:30]}..."}

        if post_wait_s > 0: page.wait_for_timeout(int(post_wait_s * 1000))
        return {"success": True, "msg": f"✅ [{action}|{adapter_level}] 触发成功"}

    except Exception as e:
        err_msg = str(e).split('\n')[0]
        if ignore_error: return {"success": True, "msg": f"🛡️ 已静默跳过报错: {err_msg[:30]}"}
        return {"success": False, "msg": f"❌ {err_msg}"}


# =========================================================
# 🖥️ 核心主程序：前后端通信枢纽
# =========================================================
def run_ide():
    with sync_playwright() as p:
        print("⏳ 正在附身浏览器...")
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            print(f"❌ 附身失败，请检查 9222 端口: {e}")
            return

        context = browser.contexts[0]
        
        ui_script = r"""
        (() => {
            if (window.__autoai_injected) return;
            window.__autoai_injected = true;

            const isTop = (window.top === window.self);

            // ==========================================
            // 📡 模块 1：跨域通信与全维事件监听
            // ==========================================
            let isPicking = false; 
            let isGrabbing = false; 
            let lastHighlighted = null;
            window.activePickInput = null; 

            window.addEventListener('message', (e) => {
                if (e.data && e.data.type === 'IDE_STATE_UPDATE') {
                    isPicking = e.data.isPicking;
                    isGrabbing = e.data.isGrabbing;
                    if (!isPicking && !isGrabbing && lastHighlighted) {
                        lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                        lastHighlighted = null;
                    }
                }
                if (isTop && e.data && e.data.type === 'IDE_ELEMENT_PICKED') {
                    if (window.activePickInput) {
                        window.activePickInput.value = e.data.locator;
                        const runBtn = window.activePickInput.closest('.macro-step').querySelector('.btn-run-single');
                        window.activePickInput = null;
                        if (document.getElementById('btn-pick').innerText !== '🎯 狙击') {
                            document.getElementById('btn-pick').click(); 
                        }
                        ideLog(`🎯 [跨域穿透] 预装填完毕，自动开火！`);
                        if (runBtn) runBtn.click();
                    } else {
                        addStep('Click', e.data.locator);
                        ideLog(`🎯 [跨域穿透] 捕获来自 Iframe 的元素`);
                        if (document.getElementById('btn-pick').innerText !== '🎯 狙击') {
                            document.getElementById('btn-pick').click();
                        }
                    }
                }
                if (isTop && e.data && e.data.type === 'IDE_TEXT_GRABBED') {
                    navigator.clipboard.writeText(e.data.text).then(() => ideLog(`✅ [跨域抓文] 成功`));
                    if (document.getElementById('btn-grab').innerText !== '🧲 抓文') {
                        document.getElementById('btn-grab').click();
                    }
                }
            });

            function broadcastState() {
                if (!isTop) return;
                document.querySelectorAll('iframe').forEach(f => {
                    try { f.contentWindow.postMessage({ type: 'IDE_STATE_UPDATE', isPicking, isGrabbing }, '*'); } catch(err) {}
                });
            }

            // 🌟 强力深层锚点定位器生成逻辑 🌟
            function generateLocator(el) {
                let dimensions = [];

                // ==========================================
                // 维度 1：🥇 金牌特征 (唯一ID、四大前端框架测试标签)
                // ==========================================
                const testIds = ['data-testid', 'data-test-id', 'data-cy', 'data-qa', 'data-spm']; // spm是阿里系常用
                for (let attr of testIds) {
                    if (el.hasAttribute(attr)) {
                        dimensions.push(`${el.tagName.toLowerCase()}[${attr}="${el.getAttribute(attr)}"]`);
                        break;
                    }
                }
                if (el.id && !/\d{3,}/.test(el.id) && el.id.length < 50) {
                    dimensions.push(`#${el.id}`);
                }

                // ==========================================
                // 维度 2：🥈 智能标签特化解析 (语义与Role)
                // ==========================================
                let tagName = el.tagName.toLowerCase();
                let semanticSel = tagName;
                
                // 抓取无障碍 Role (如 div[role="button"])
                let role = el.getAttribute('role');
                if (role) semanticSel += `[role="${role}"]`;

                // 链接与图片特化抓取
                if (tagName === 'a' && el.getAttribute('href') && !el.getAttribute('href').startsWith('javascript:')) {
                    if(el.getAttribute('href').length < 50) semanticSel += `[href="${el.getAttribute('href')}"]`;
                }
                if (tagName === 'img' && el.getAttribute('alt')) {
                    semanticSel += `[alt="${el.getAttribute('alt').replace(/"/g, '\\"')}"]`;
                }

                // 常规稳定属性
                const stableAttrs = ['name', 'placeholder', 'type', 'aria-label', 'title', 'value'];
                let hasStableAttr = false;
                for (let attr of stableAttrs) {
                    if (el.hasAttribute(attr) && el.getAttribute(attr).length < 50) {
                        semanticSel += `[${attr}="${el.getAttribute(attr).replace(/"/g, '\\"')}"]`;
                        hasStableAttr = true;
                    }
                }
                if (hasStableAttr || role || tagName === 'a' || tagName === 'img') {
                    dimensions.push(semanticSel);
                }

                // ==========================================
                // 维度 3：🥉 文本双绝杀 (精确全匹配 + 模糊包含)
                // ==========================================
                let text = (el.textContent || '').trim().split('\n')[0].trim();
                if (text && text.length < 30 && ['button', 'a', 'span', 'label', 'div', 'li'].includes(tagName)) {
                    let escapedText = text.replace(/"/g, '\\"');
                    // 绝杀1: 必须一字不差 (防误点)
                    dimensions.push(`${tagName}:text-is("${escapedText}")`);
                    // 绝杀2: 只要包含就行 (防前后加空格/图标)
                    dimensions.push(`${tagName}:has-text("${escapedText}")`);
                }

                // ==========================================
                // 维度 4：🛡️ 柔性层级结构 (防中间插广告/新容器)
                // ==========================================
                let classPath = [];
                let currNode = el;
                let depth = 0;
                while (currNode && currNode.nodeType === Node.ELEMENT_NODE && currNode.tagName !== 'BODY' && currNode.tagName !== 'HTML' && depth < 3) {
                    let sel = currNode.tagName.toLowerCase();
                    let validClass = Array.from(currNode.classList).find(c => !/\d/.test(c) && c.length > 3 && c.length < 25 && !['flex', 'block', 'hidden', 'active'].includes(c));
                    if (validClass) sel += `.${validClass}`;
                    
                    let sib = currNode, nth = 1;
                    while ((sib = sib.previousElementSibling)) {
                        if (sib.nodeType === Node.ELEMENT_NODE && sib.tagName === currNode.tagName) nth++;
                    }
                    if (nth > 1) sel += `:nth-of-type(${nth})`;
                    
                    classPath.unshift(sel);
                    currNode = currNode.parentNode;
                    depth++;
                }
                if (classPath.length > 0) dimensions.push(classPath.join(' > '));

                // ==========================================
                // 维度 5：🕸️ XPath 绝对引擎底层寻址
                // ==========================================
                let xpath = '';
                let xNode = el;
                while (xNode && xNode.nodeType === Node.ELEMENT_NODE) {
                    let xName = xNode.tagName.toLowerCase();
                    let sib = xNode, nth = 1;
                    while ((sib = sib.previousElementSibling)) {
                        if (sib.nodeType === Node.ELEMENT_NODE && sib.tagName === xNode.tagName) nth++;
                    }
                    let xIndex = nth > 1 ? `[${nth}]` : '';
                    if (xNode.tagName === 'HTML') {
                        xpath = '//html' + xpath;
                        break;
                    } else if (xNode.tagName === 'BODY') {
                        xpath = '/body' + xpath;
                        xNode = xNode.parentNode;
                    } else {
                        xpath = '/' + xName + xIndex + xpath;
                        xNode = xNode.parentNode;
                    }
                }
                if (xpath) dimensions.push(`xpath=${xpath}`);

                // ==========================================
                // 维度 6：⛓️ Playwright 原生 nth-child 纯物理坐标
                // ==========================================
                let physPath = [];
                let currPhys = el;
                while (currPhys && currPhys.nodeType === Node.ELEMENT_NODE && currPhys.tagName !== 'BODY' && currPhys.tagName !== 'HTML') {
                    let sel = currPhys.tagName.toLowerCase();
                    let sib = currPhys, nth = 1;
                    while ((sib = sib.previousElementSibling)) {
                        if (sib.nodeType === Node.ELEMENT_NODE) nth++;
                    }
                    sel += `:nth-child(${nth})`;
                    physPath.unshift(sel);
                    currPhys = currPhys.parentNode;
                }
                dimensions.push(physPath.join(' > '));

                // ==========================================
                // 万剑归宗：去重、拼接、OR 连接！
                // ==========================================
                let uniqueDimensions = [...new Set(dimensions)];
                return uniqueDimensions.map(d => d + " >> visible=true").join(', ');
            }

            // 👻 核心防污染：拦截前置事件
            const freezeEvent = (e) => {
                if (isPicking) {
                    if (isTop && e.target.closest('#autoai-ide-panel')) return;
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                }
            };
            document.addEventListener('mousedown', freezeEvent, true);
            document.addEventListener('pointerdown', freezeEvent, true);
            document.addEventListener('mouseup', freezeEvent, true);

            document.addEventListener('mouseover', (e) => {
                if (!isPicking && !isGrabbing) return;
                if (isTop && e.target.closest('#autoai-ide-panel')) return; 
                if (lastHighlighted && lastHighlighted !== e.target) {
                    lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                }
                lastHighlighted = e.target;
                if (!e.target.dataset.oldOutline) e.target.dataset.oldOutline = e.target.style.outline || '';
                e.target.style.outline = isPicking ? '3px solid #9C27B0' : '3px dashed #E91E63'; 
                e.stopPropagation();
            }, true);

            document.addEventListener('click', (e) => {
                if (!isPicking && !isGrabbing) return;
                if (isTop && e.target.closest('#autoai-ide-panel')) return;
                e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); 

                if (lastHighlighted) {
                    lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
                    lastHighlighted = null;
                }

                if (isGrabbing) {
                    let text = e.target.innerText || "";
                    if (isTop) {
                        isGrabbing = false;
                        document.getElementById('btn-grab').style.background = '#E91E63';
                        document.getElementById('btn-grab').innerText = '🧲 抓文';
                        navigator.clipboard.writeText(text).then(() => ideLog(`✅ [抓文] 成功`));
                        broadcastState();
                    } else {
                        window.top.postMessage({ type: 'IDE_TEXT_GRABBED', text: text }, '*');
                    }
                    return;
                }

                if (isPicking) {
                    let loc = generateLocator(e.target);
                    if (isTop) {
                        if (window.activePickInput) {
                            window.activePickInput.value = loc;
                            const runBtn = window.activePickInput.closest('.macro-step').querySelector('.btn-run-single');
                            window.activePickInput = null;
                            
                            isPicking = false;
                            document.getElementById('btn-pick').style.background = '#9C27B0';
                            document.getElementById('btn-pick').innerText = '🎯 狙击';
                            broadcastState();
                            
                            ideLog(`🎯 预装填完毕，自动开火！`);
                            if (runBtn) runBtn.click();
                        } else {
                            isPicking = false;
                            document.getElementById('btn-pick').style.background = '#9C27B0';
                            document.getElementById('btn-pick').innerText = '🎯 狙击';
                            addStep('Click', loc); 
                            ideLog(`🎯 [锁定] 积木生成完毕`);
                            broadcastState();
                        }
                    } else {
                        window.top.postMessage({ type: 'IDE_ELEMENT_PICKED', locator: loc }, '*');
                    }
                }
            }, true);

            // ==========================================
            // 🎨 模块 2：IDE 面板渲染
            // ==========================================
            if (!isTop) return; 

            window.__ide_cmd = null;
            window.__ide_save = null;
            window.__ide_res = null;

            function initPanel() {
                if (document.getElementById('autoai-ide-panel')) return;

                const panel = document.createElement('div');
                panel.id = 'autoai-ide-panel';
                panel.style.cssText = 'position: fixed; left: 10px; top: 10px; width: 480px; height: 550px; max-height: 95vh; display: flex; flex-direction: column; background: #121212; border-radius: 6px; z-index: 2147483647; font-family: monospace; box-shadow: 0 4px 20px rgba(0,0,0,0.8); border: 1px solid #333; overflow: hidden; resize: both;';
                
                panel.innerHTML = `
                    <div id="ide-drag-handle" style="cursor: move; background: #1e1e1e; padding: 6px 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #000; user-select: none;">
                        <div style="display: flex; gap: 6px;">
                            <button id="btn-add-step" style="background: #2196F3; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 13px; font-weight: bold;">➕ 加空块</button>
                            <button id="btn-pick" style="background: #9C27B0; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 13px; font-weight: bold;" title="Alt+Q">🎯 盲狙</button>
                            <button id="btn-grab" style="background: #E91E63; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 13px; font-weight: bold;" title="Alt+W">🧲 抓文</button>
                        </div>
                        <div style="display: flex; gap: 6px;">
                            <button id="btn-run-all" style="background: #FF9800; border: none; padding: 4px 10px; color: white; cursor: pointer; border-radius: 3px; font-size: 13px; font-weight: bold;">▶️ 全跑</button>
                            <button id="btn-save" style="background: #4CAF50; border: none; padding: 4px 10px; color: white; cursor: pointer; border-radius: 3px; font-size: 13px; font-weight: bold;">💾 存盘</button>
                        </div>
                    </div>
                    
                    <div id="steps-container" style="flex: 1; overflow-y: auto; padding: 6px; background: #161616; display: flex; flex-direction: column; gap: 4px;"></div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; background: #1e1e1e; padding: 4px 8px; border-top: 1px solid #333;">
                        <span style="font-size: 12px; color: #888; font-weight: bold;">日志 (全域雷达已挂载)</span>
                        <div style="display: flex; gap: 6px;">
                            <button id="btn-clear-log" style="background: transparent; color: #F44336; border: 1px solid #F44336; border-radius: 3px; padding: 2px 6px; font-size: 12px; cursor: pointer;">🗑️ 清空</button>
                            <button id="btn-copy-log" style="background: transparent; color: #2196F3; border: 1px solid #2196F3; border-radius: 3px; padding: 2px 6px; font-size: 12px; cursor: pointer;">📋 复制</button>
                        </div>
                    </div>
                    <div id="ide-log" style="font-size: 12px; color: #00E676; background: #0a0a0a; padding: 6px 8px; height: 110px; flex-shrink: 0; overflow-y: auto; margin: 0; box-sizing: border-box;">&gt; 🟢 极速雷达与破甲底盘就绪！</div>
                `;
                document.body.appendChild(panel);

                window.ideLog = (msg) => { 
                    const logBox = document.getElementById('ide-log');
                    logBox.innerHTML += '<br>&gt; ' + msg; 
                    logBox.scrollTop = logBox.scrollHeight;
                };

                const updateStepNumbers = () => {
                    document.querySelectorAll('.macro-step').forEach((el, index) => {
                        const badge = el.querySelector('.step-idx');
                        if (badge) badge.innerText = index + 1;
                    });
                };

                const setActiveStep = (stepDiv) => {
                    document.querySelectorAll('.macro-step').forEach(el => {
                        el.style.border = '1px solid #333';
                        el.style.boxShadow = 'none';
                        el.querySelector('.step-idx').style.background = '#444';
                        el.querySelector('.step-idx').style.color = '#fff';
                    });
                    if (stepDiv) {
                        stepDiv.style.border = '1px solid #00E676';
                        stepDiv.style.boxShadow = '0 0 8px rgba(0, 230, 118, 0.2)';
                        stepDiv.querySelector('.step-idx').style.background = '#00E676';
                        stepDiv.querySelector('.step-idx').style.color = '#000';
                    }
                };

                const saveStateToLocal = () => {
                    const container = document.getElementById('steps-container');
                    container.querySelectorAll('input').forEach(el => {
                        if(el.type === 'checkbox') el.defaultChecked = el.checked;
                        else el.setAttribute('value', el.value);
                    });
                    container.querySelectorAll('select').forEach(el => {
                        el.querySelectorAll('option').forEach(opt => {
                            if(opt.value === el.value) opt.setAttribute('selected', 'selected');
                            else opt.removeAttribute('selected');
                        });
                    });
                    localStorage.setItem('autoai_ide_backup', container.innerHTML);
                };

                const restoreStateFromLocal = () => {
                    const backup = localStorage.getItem('autoai_ide_backup');
                    if (backup) {
                        document.getElementById('steps-container').innerHTML = backup;
                        updateStepNumbers();
                    }
                };
                restoreStateFromLocal();

                document.getElementById('steps-container').addEventListener('input', saveStateToLocal);
                document.getElementById('steps-container').addEventListener('change', saveStateToLocal);
                document.getElementById('steps-container').addEventListener('click', (e) => {
                    const stepDiv = e.target.closest('.macro-step');
                    if (stepDiv && e.target.tagName !== 'BUTTON') setActiveStep(stepDiv);
                });

                const dragHandle = document.getElementById('ide-drag-handle');
                let isDragging = false, offsetX, offsetY;
                dragHandle.addEventListener('mousedown', (e) => {
                    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT') return;
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

                window.addStep = (action = 'Click', loc = '') => {
                    const id = 'step-' + Date.now();
                    const html = `
                        <div class="macro-step" data-id="${id}" style="background: #222; border: 1px solid #333; padding: 6px; border-radius: 4px; transition: all 0.2s;">
                            <div style="display: flex; gap: 6px; align-items: center; margin-bottom: 4px;">
                                <div class="step-idx" style="background: #444; color: #fff; width: 18px; height: 18px; border-radius: 50%; font-size: 11px; display: flex; justify-content: center; align-items: center; font-weight: bold; flex-shrink: 0;">0</div>
                                
                                <select class="step-adapter" style="background: #111; color: #00E676; border: 1px solid #444; padding: 2px 4px; border-radius: 3px; font-size: 12px; font-weight: bold;">
                                    <option value="level1">🟢 L1</option>
                                    <option value="level2">🟡 L2</option>
                                    <option value="level3">🔴 L3</option>
                                </select>

                                <select class="step-action" style="background: #333; color: #fff; border: 1px solid #444; padding: 2px 4px; border-radius: 3px; font-size: 12px; width: 60px;">
                                    <option value="Click" ${action==='Click'?'selected':''}>点击</option>
                                    <option value="Hover" ${action==='Hover'?'selected':''}>悬停</option>
                                    <option value="Fill" ${action==='Fill'?'selected':''}>填字</option>
                                    <option value="Upload" ${action==='Upload'?'selected':''}>传图</option>
                                    <option value="Extract" ${action==='Extract'?'selected':''}>提取</option>
                                    <option value="Wait" ${action==='Wait'?'selected':''}>等待</option>
                                    <option value="NetIdle" ${action==='NetIdle'?'selected':''}>静默</option>
                                    <option value="Pause" ${action==='Pause'?'selected':''}>人工</option>
                                    <option value="Press" ${action==='Press'?'selected':''}>按键</option>
                                </select>
                                <input class="step-memo" placeholder="备注..." style="flex: 1; background: #3b3a20; color: #ffd700; border: 1px solid #666; padding: 2px 6px; font-size: 12px; border-radius: 3px;">
                                
                                <div style="display: flex; gap: 2px;">
                                    <button class="btn-up" style="background: #333; border: 1px solid #444; border-radius: 2px; cursor: pointer; padding: 1px 4px; font-size: 10px;">▲</button>
                                    <button class="btn-down" style="background: #333; border: 1px solid #444; border-radius: 2px; cursor: pointer; padding: 1px 4px; font-size: 10px;">▼</button>
                                    <button class="btn-del" style="background: transparent; color: #F44336; border: none; cursor: pointer; padding: 1px 4px; font-size: 12px;">✖</button>
                                </div>
                            </div>
                            <div class="step-body" style="display: flex; flex-direction: column; gap: 4px; padding-left: 24px;">
                                <div style="display: flex; gap: 4px;">
                                    <button class="btn-card-pick" style="background: #9C27B0; color: white; border: none; border-radius: 3px; padding: 2px 8px; font-size: 11px; cursor: pointer; font-weight: bold;" title="选好武器后，点我去装填目标">🎯定标</button>
                                    <input class="step-loc" value='${loc.replace(/'/g, "&#39;")}' placeholder="Locator" style="flex: 1; background: #000; color: #00FF00; border: 1px solid #444; padding: 2px 6px; font-size: 11px; font-family: monospace; border-radius: 2px;">
                                    <input class="step-val" placeholder="参数" style="width: 70px; background: #000; color: #fff; border: 1px solid #444; padding: 2px 6px; font-size: 12px; border-radius: 2px;">
                                </div>
                                <div style="display: flex; gap: 8px; align-items: center; background: #1a1a1a; padding: 2px 6px; border-radius: 3px;">
                                    <span style="font-size: 11px; color: #888;">前(s)</span>
                                    <input class="step-pre" type="number" step="0.1" value="0" style="width: 35px; background: #000; color: #888; border: 1px solid #333; font-size: 11px; text-align: center;">
                                    <span style="font-size: 11px; color: #888;">后(s)</span>
                                    <input class="step-post" type="number" step="0.1" value="0" style="width: 35px; background: #000; color: #888; border: 1px solid #333; font-size: 11px; text-align: center;">
                                    
                                    <label style="font-size: 11px; color: #FF9800; cursor: pointer; display: flex; align-items: center; margin-left: 4px;">
                                        <input type="checkbox" class="step-ignore" style="margin:0 2px 0 0;"> 忽略
                                    </label>
                                    <div style="flex: 1;"></div>
                                    <button class="btn-run-single" style="background: #2E7D32; color: #fff; border: none; cursor: pointer; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">🧪 试跑</button>
                                </div>
                            </div>
                        </div>
                    `;
                    document.getElementById('steps-container').insertAdjacentHTML('beforeend', html);
                    updateStepNumbers(); 
                    const newStep = document.getElementById('steps-container').lastElementChild;
                    setActiveStep(newStep);
                    saveStateToLocal();
                    
                    const container = document.getElementById('steps-container');
                    container.scrollTop = container.scrollHeight;
                };

                const runStep = async (stepDiv) => {
                    window.__ide_res = null;
                    window.__ide_cmd = {
                        adapter: stepDiv.querySelector('.step-adapter').value, 
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

                window.addEventListener('keydown', (e) => {
                    if (e.altKey && (e.code === 'KeyQ' || e.key.toLowerCase() === 'q' || e.key === 'œ')) {
                        e.preventDefault(); e.stopImmediatePropagation(); 
                        document.getElementById('btn-pick').click();
                    }
                    if (e.altKey && (e.code === 'KeyW' || e.key.toLowerCase() === 'w' || e.key === '∑')) {
                        e.preventDefault(); e.stopImmediatePropagation();
                        document.getElementById('btn-grab').click();
                    }
                    if (e.altKey && (e.code === 'KeyS' || e.key.toLowerCase() === 's' || e.key === 'ß')) {
                        e.preventDefault(); e.stopImmediatePropagation();
                        let activeStep = null;
                        document.querySelectorAll('.macro-step').forEach(el => {
                            if (el.style.border.includes('0E676') || el.style.border.includes('0, 230, 118')) activeStep = el;
                        });
                        if (!activeStep) {
                            const steps = document.querySelectorAll('.macro-step');
                            if (steps.length > 0) activeStep = steps[steps.length - 1];
                        }
                        if (activeStep) {
                            const runBtn = activeStep.querySelector('.btn-run-single');
                            if (runBtn) runBtn.click();
                        } else {
                            ideLog('⚠️ 无可用积木试跑！');
                        }
                    }
                }, true);

                panel.addEventListener('click', async (e) => {
                    if (e.target.classList.contains('btn-card-pick')) {
                        const stepDiv = e.target.closest('.macro-step');
                        setActiveStep(stepDiv);
                        window.activePickInput = stepDiv.querySelector('.step-loc');
                        isPicking = true;
                        isGrabbing = false;
                        document.getElementById('btn-pick').style.background = '#F44336';
                        document.getElementById('btn-pick').innerText = '⏹️ 停';
                        broadcastState();
                        ideLog("🎯 幽灵涂层开启，请点击网页目标完成装填！");
                    }

                    if (e.target.id === 'btn-pick') {
                        isPicking = !isPicking;
                        isGrabbing = false; 
                        window.activePickInput = null;
                        e.target.style.background = isPicking ? '#F44336' : '#9C27B0';
                        e.target.innerText = isPicking ? '⏹️ 停' : '🎯 盲狙';
                        document.getElementById('btn-grab').style.background = '#E91E63';
                        document.getElementById('btn-grab').innerText = '🧲 抓文';
                        broadcastState(); 
                        ideLog(isPicking ? "🎯 狙击雷达开启，全域扫描中..." : "⏹️ 雷达关闭。");
                    }
                    if (e.target.id === 'btn-grab') {
                        isGrabbing = !isGrabbing;
                        isPicking = false; 
                        window.activePickInput = null;
                        e.target.style.background = isGrabbing ? '#F44336' : '#E91E63';
                        e.target.innerText = isGrabbing ? '⏹️ 停' : '🧲 抓文';
                        document.getElementById('btn-pick').style.background = '#9C27B0';
                        document.getElementById('btn-pick').innerText = '🎯 盲狙';
                        broadcastState(); 
                        ideLog(isGrabbing ? "🧲 抓取雷达开启，全域扫描中..." : "⏹️ 抓取关闭。");
                    }
                    
                    if (e.target.id === 'btn-add-step') addStep();
                    
                    if (e.target.classList.contains('btn-del')) {
                        e.target.closest('.macro-step').remove();
                        updateStepNumbers();
                        saveStateToLocal();
                    }
                    
                    if (e.target.classList.contains('btn-up')) {
                        const step = e.target.closest('.macro-step');
                        if (step.previousElementSibling) {
                            step.parentNode.insertBefore(step, step.previousElementSibling);
                            updateStepNumbers();
                            saveStateToLocal();
                        }
                    }
                    
                    if (e.target.classList.contains('btn-down')) {
                        const step = e.target.closest('.macro-step');
                        if (step.nextElementSibling) {
                            step.parentNode.insertBefore(step.nextElementSibling, step);
                            updateStepNumbers();
                            saveStateToLocal();
                        }
                    }

                    if (e.target.classList.contains('btn-run-single')) {
                        const stepDiv = e.target.closest('.macro-step');
                        setActiveStep(stepDiv);
                        ideLog(`&gt; 执行 [${stepDiv.querySelector('.step-idx').innerText}]...`);
                        ideLog((await runStep(stepDiv)).msg);
                    }

                    if (e.target.id === 'btn-run-all') {
                        const steps = document.querySelectorAll('.macro-step');
                        ideLog("▶️ 开始全跑...");
                        for (let i = 0; i < steps.length; i++) {
                            setActiveStep(steps[i]);
                            const res = await runStep(steps[i]);
                            ideLog(`[步${i+1}] ` + res.msg);
                            if(!res.success) break;
                        }
                    }

                    if (e.target.id === 'btn-clear-log') {
                        document.getElementById('ide-log').innerHTML = '&gt; 🟢 日志已清空';
                    }

                    if (e.target.id === 'btn-copy-log') {
                        const logs = document.getElementById('ide-log').innerText;
                        navigator.clipboard.writeText(logs).then(() => {
                            e.target.innerText = '✅ 搞定';
                            setTimeout(() => e.target.innerText = '📋 复制', 2000);
                        });
                    }

                    if (e.target.id === 'btn-save') {
                        let sequence = [];
                        document.querySelectorAll('.macro-step').forEach(stepDiv => {
                            sequence.push({
                                "adapter": stepDiv.querySelector('.step-adapter').value,
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
                        ideLog("💾 正在向后端交接情报...");
                        while (!window.__ide_res) { await new Promise(r => setTimeout(r, 100)); }
                        ideLog(window.__ide_res.msg);
                        window.__ide_res = null;
                    }
                });
            }

            setInterval(() => { if (document.body && !document.getElementById('autoai-ide-panel')) initPanel(); }, 1000);
            initPanel();
        })();
        """
        
        context.add_init_script(ui_script)
        
        if len(context.pages) > 0:
            try: context.pages[0].evaluate(ui_script)
            except: pass

        print("\n" + "=".rjust(50, "="))
        print("🚀 [全域雷达版] 引擎启动成功")
        print("👉 10s深水扫描 | 阶梯防御击穿 | 防动态ID抓取")
        print("=".rjust(50, "=") + "\n")

        while True:
            try:
                if not context.pages:
                    time.sleep(0.1)
                    continue
                
                target_page = context.pages[-1]

                for sender_page in context.pages:
                    if sender_page.is_closed(): continue
                    
                    save_data = sender_page.evaluate("window.__ide_save")
                    if save_data:
                        sender_page.evaluate("window.__ide_save = null")
                        try:
                            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                                json.dump({"target_url": target_page.url, "sequence": save_data}, f, ensure_ascii=False, indent=4)
                            res = {"success": True, "msg": f"💾 存档安全落盘于 {CONFIG_FILE}"}
                        except Exception as e:
                            res = {"success": False, "msg": f"❌ 存盘失败: {str(e)}"}
                        sender_page.evaluate("res => { window.__ide_res = res; }", res)

                    cmd = sender_page.evaluate("window.__ide_cmd")
                    if cmd:
                        sender_page.evaluate("window.__ide_cmd = null")
                        res = execute_action(
                            target_page, 
                            cmd["action"], 
                            cmd["locator"], 
                            cmd["value"], 
                            cmd["pre_wait_s"], 
                            cmd["post_wait_s"], 
                            cmd["ignore_error"],
                            cmd.get("adapter", "level1") 
                        )
                        sender_page.evaluate("res => { window.__ide_res = res; }", res)
                        
            except Exception:
                pass
            time.sleep(0.1)

if __name__ == "__main__":
    run_ide()