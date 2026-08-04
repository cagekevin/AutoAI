import os
import time
import base64
import tempfile
import platform

DUMMY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAA6SURBVGhD7cExAQAAAMKg9U9tCy8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgqQBWgAAB2pD5ZAAAAABJRU5ErkJggg==")

def execute_action(page, action, locator, value, pre_wait_s, post_wait_s, ignore_error, adapter_level="level1"):
    try:
        if pre_wait_s > 0: page.wait_for_timeout(int(pre_wait_s * 1000))

        # 【全局动作】
        if action == "Wait":
            page.wait_for_timeout(int((float(value) if value else 1.0) * 1000))
            return {"success": True, "msg": f"✅ 等待完成"}
        elif action == "NetIdle":
            page.wait_for_load_state("networkidle", timeout=30000)
            return {"success": True, "msg": f"✅ 静默完成"}
        elif action == "Pause":
            input("\n🚨 [人工干预] 请操作后按回车继续...")
            return {"success": True, "msg": f"✅ 干预完毕"}
        elif action == "Press":
            page.keyboard.press(value if value else "PageDown")
            return {"success": True, "msg": f"✅ 按键触发"}

        if not locator: return {"success": False, "msg": f"❌ 缺少 Locator"}
        loc = page.locator(locator).first

        # ========================================================
        # 🎯 确定性武器库：根据传入的 level 精准打击，绝不试错！
        # ========================================================
        if action == "Click":
            if adapter_level == "level1":
                loc.click(timeout=3000)
            elif adapter_level == "level2":
                loc.click(timeout=3000, force=True)
            elif adapter_level == "level3":
                loc.evaluate("el => el.click()")

        elif action == "Hover":
            if adapter_level in ["level1", "level3"]:
                loc.hover(timeout=3000)
            else: # level2
                loc.hover(timeout=3000, force=True)

        elif action == "Fill":
            val = value if value else "TEST"
            if adapter_level == "level1":
                loc.fill(val, timeout=3000)
            elif adapter_level == "level2":
                loc.fill(val, timeout=3000, force=True)
            elif adapter_level == "level3":
                # L3 终极填字：物理对焦 -> 全选清除 -> 盲打 -> 敲击状态锁
                loc.click(timeout=3000, force=True)
                page.keyboard.press("Meta+A" if platform.system() == "Darwin" else "Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.insert_text(val)
                page.keyboard.press("Space")
                page.keyboard.press("Backspace")
        # ========================================================

        elif action == "Upload":
            temp_img = os.path.join(tempfile.gettempdir(), "autoai_dummy.png")
            with open(temp_img, "wb") as f: f.write(DUMMY_PNG)
            try: loc.set_input_files(temp_img, timeout=3000)
            except Exception: page.locator('input[type="file"]').first.set_input_files(temp_img, timeout=3000)
            
        elif action == "Extract":
            attr = value if value else "text"
            res = loc.inner_text(timeout=3000) if attr.lower() in ["text", "innertext"] else loc.get_attribute(attr, timeout=3000)
            return {"success": True, "msg": f"✅ 提取: {str(res)[:30]}..."}

        if post_wait_s > 0: page.wait_for_timeout(int(post_wait_s * 1000))
        return {"success": True, "msg": f"🚀 [{action}|{adapter_level}] 成功"}

    except Exception as e:
        err = str(e).splitlines()[0]
        if ignore_error: return {"success": True, "msg": f"🛡️ 忽略报错: {err[:30]}"}
        return {"success": False, "msg": f"❌ {err}"}