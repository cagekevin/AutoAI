import os
import time
import base64
import tempfile
import platform

DUMMY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAA6SURBVGhD7cExAQAAAMKg9U9tCy8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgqQBWgAAB2pD5ZAAAAABJRU5ErkJggg==")

def execute_action(page, action, locator, value, pre_wait_s, post_wait_s, ignore_error):
    try:
        # 1. 执行前置等待
        if pre_wait_s > 0: page.wait_for_timeout(int(pre_wait_s * 1000))

        # 2. 无需 Locator 的全局动作（完整恢复）
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
            return {"success": True, "msg": f"✅ 人工干预完成"}
        elif action == "Press":
            page.keyboard.press(value if value else "PageDown")
            return {"success": True, "msg": f"✅ 物理按键 {value}"}

        # 3. 必须 Locator 的交互动作
        if not locator: return {"success": False, "msg": f"❌ Locator 不能为空"}
        loc = page.locator(locator).first

        if action == "Click":
            try:
                loc.wait_for(state="attached", timeout=1500)
                try: loc.focus(timeout=500)
                except: pass
                loc.click(timeout=1500, force=True)
            except Exception:
                try:
                    # 💥 破甲：底层触控事件全面模拟
                    loc.evaluate("""el => {
                        const opts = {bubbles: true, cancelable: true, pointerId: 1};
                        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(t => {
                            el.dispatchEvent(new window[t.includes('pointer') ? 'PointerEvent' : 'MouseEvent'](t, opts));
                        });
                    }""")
                except Exception:
                    raise Exception("DOM元素已彻底蒸发，跨域或失焦！")

        elif action == "Hover":
            try: loc.hover(timeout=1500)
            except: loc.hover(timeout=1500, force=True)

        elif action == "Fill":
            val = value if value else "TEST"
            # 💥 破甲：物理键盘逐字强敲
            try:
                try: loc.focus(timeout=500)
                except: pass
                loc.click(timeout=1000, force=True)
            except: pass
            
            page.keyboard.press("Meta+A" if platform.system() == "Darwin" else "Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.1)
            page.keyboard.insert_text(val)
            page.keyboard.press("Space")
            page.keyboard.press("Backspace")

        elif action == "Upload":
            # 💥 破甲：幽灵 input 强行挂载
            temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
            with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
            try:
                loc.set_input_files(temp_img, timeout=3000)
            except Exception:
                page.locator('input[type="file"]').first.set_input_files(temp_img, timeout=3000)

        elif action == "Extract":
            attr = value if value else "text"
            res_data = loc.inner_text(timeout=3000) if attr.lower() in ["text", "innertext"] else loc.get_attribute(attr, timeout=3000)
            return {"success": True, "msg": f"✅ 成功提取 {attr}: {str(res_data)[:30]}..."}

        # 4. 执行后置等待
        if post_wait_s > 0: page.wait_for_timeout(int(post_wait_s * 1000))
        return {"success": True, "msg": f"🚀 [破甲模式] {action} 执行成功"}

    except Exception as e:
        err_msg = str(e).split('\n')[0]
        if ignore_error: return {"success": True, "msg": f"🛡️ [{action}] 报错已静默跳过: {err_msg[:30]}"}
        return {"success": False, "msg": f"❌ {err_msg}"}