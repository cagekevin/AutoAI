import os
import time
import base64
import tempfile

DUMMY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAA6SURBVGhD7cExAQAAAMKg9U9tCy8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgqQBWgAAB2pD5ZAAAAABJRU5ErkJggg==")

def execute_action(page, action, locator, value, pre_wait_s, post_wait_s, ignore_error):
    try:
        if pre_wait_s > 0: page.wait_for_timeout(int(pre_wait_s * 1000))

        if action == "Wait":
            s = float(value) if value else 1.0
            page.wait_for_timeout(int(s * 1000))
            return {"success": True, "msg": f"✅ 等待 {s}s"}
        elif action == "NetIdle":
            page.wait_for_load_state("networkidle", timeout=30000)
            return {"success": True, "msg": f"✅ 网络静默完成"}
        elif action == "Pause":
            print("\n🚨 [停机摇人] 请手动操作后按回车继续...")
            input()
            return {"success": True, "msg": f"✅ 人工干预接管"}
        elif action == "Press":
            page.keyboard.press(value if value else "PageDown")
            return {"success": True, "msg": f"✅ 物理按键 {value}"}

        if not locator: return {"success": False, "msg": f"❌ Locator 不能为空"}
        
        loc = page.locator(locator).first

        # ========================================================
        # 💯 完美还原昨天的神级逻辑：大道至简
        # ========================================================
        if action == "Click":
            loc.click(timeout=3000, force=True)
            
        elif action == "Hover":
            loc.hover(timeout=3000, force=True)
            
        elif action == "Fill":
            val = value if value else "TEST"
            try:
                # 尝试正常填字
                loc.fill(val, timeout=3000)
            except Exception as e:
                # 破甲机制：利用报错实现完美的人类拟真点击
                if "not an <input>" in str(e) or "contenteditable" in str(e):
                    loc.click(timeout=3000, force=True)
                    page.keyboard.insert_text(val)
                else:
                    raise e
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
        return {"success": True, "msg": f"🚀 [豆包] {action} 执行成功"}

    except Exception as e:
        err_msg = str(e).split('\n')[0]
        if ignore_error: return {"success": True, "msg": f"🛡️ [{action}] 静默跳过: {err_msg[:30]}"}
        return {"success": False, "msg": f"❌ 报错: {err_msg}"}