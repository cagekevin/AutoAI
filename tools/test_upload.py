from playwright.sync_api import sync_playwright
from PIL import Image
import os
import time

# 1. 动态生成一张 64x64 的假图用于测试 (纯红色)
test_img_path = os.path.abspath("fake_test_64.png")
print("🎨 正在生成测试图片...")
Image.new('RGB', (64, 64), color='red').save(test_img_path)
print(f"✅ 图片已就绪: {test_img_path}")

print("\n🔌 正在连接到本地 Chrome (9222端口)...")
with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
        context = browser.contexts[0]
        
        # 寻找包含 flow 的标签页
        page = None
        for p_tab in context.pages:
            if "flow" in p_tab.url.lower():
                page = p_tab
                break
                
        if not page:
            print("❌ 没找到 Flow 的标签页，请先在浏览器里打开 Flow 页面！")
            exit()
            
        print(f"✅ 成功锁定页面: {page.title()}")
        page.bring_to_front()

        # ==========================================
        # 🕵️‍♂️ 核心侦查：全页面扫描隐藏的 input[type="file"]
        # ==========================================
        print("\n🕵️‍♂️ 正在扫描 DOM 树底层的上传接口...")
        
        # 获取页面上所有 type="file" 的 input
        file_inputs = page.locator('input[type="file"]')
        count = file_inputs.count()
        
        if count > 0:
            print(f"🎯 破案了！页面上潜伏着 {count} 个隐藏的 input[type=\"file\"] 标签。")
            
            # 尝试直接把假图塞进第一个接口
            print("💉 尝试执行降维打击，直接向底层标签注入文件...")
            try:
                # set_input_files 是 Playwright 的神技，它无视 CSS 的 display:none 或 visibility:hidden
                file_inputs.first.set_input_files(test_img_path)
                print("✅ 注入成功！快看一眼浏览器，看看 UI 有没有反应（比如出现了红色的垫图预览）。")
                
                # 挂起 10 秒让你观察
                time.sleep(10)
            except Exception as e:
                print(f"❌ 注入失败了，可能前端加了严格的事件拦截: {e}")
        else:
            print("🤔 居然没找到？Google Flow 的前端工程师可能用了纯粹的 HTML5 DataTransfer (拖拽API) 绘制，完全抛弃了 input 标签！")
            print("💡 如果是这种情况，我们就不能用 set_input_files，必须用 js 模拟 drag-and-drop 事件了。")
            
    except Exception as e:
        print(f"❌ 运行报错: {e}")
    finally:
        # 清理测试图片
        if os.path.exists(test_img_path):
            os.remove(test_img_path)