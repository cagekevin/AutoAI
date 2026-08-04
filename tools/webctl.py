#!/usr/bin/env python3
"""
🖥️ webctl — 通用浏览器交互控制台（REPL）

用途：AI 或人通过它连到正在运行的 Chrome (9222)，像操作浏览器一样
     一条条输入命令，完成「认路 → 摸结构 → 找锚点 → 展开菜单 → 点击验证」的完整闭环。
     通用无站点依赖，对接任何网站都能用，不用重复写 Playwright 代码。

用法：python tools/webctl.py            # 进入交互（输入 help 查看，quit 退出）
     python tools/webctl.py --run "page|buttons|find 新建项目|quit"    # 脚本化一次性执行，命令用 | 分隔
     python tools/webctl.py --url <URL> --run "page|quit"              # 先导航再执行

命令总览（完整版与 cmd_help 一致）：
  ── 连接 / 导航 ─────────────────────────────
  open                    连接 9222 浏览器
  page                    看当前页面 URL / 标题
  nav <url|站点名>        导航到 URL 或站点(doubao/lovart/jimeng/flow)
  ── 读取 / 抓取 ─────────────────────────────
  buttons                 列出页面所有可见按钮（摸结构）
  find <文本>             搜含文本的元素 + 锚点链（找 data-testid）
  state <选择器>          查看某元素当前内容（验证选择器是否生效）
  verify <sel>[; sel...]  批量验证多个选择器命中情况（total/visible）
  html                    抓整页净化 DOM
  shot [路径]             截图当前页面
  ── 交互操作 ─────────────────────────────
  click <文本>            点击含该文本的按钮（精确匹配）
  select <文本>           同 click
  open-menu <选择器> [click|hover]  展开下拉菜单（默认 hover）
  type <文本>|<选择器> <文本>  向输入框打字（拟人延迟）
  upload <选择器> <路径>  上传文件（file_chooser 拦截/set_input_files）
  clear [选择器]          清空输入框（Ctrl+A + Backspace）
  esc [键名]              按键，默认 Esc 关弹窗
  coord <x> <y>           盲点屏幕坐标（收起菜单/弹窗）
  waitimg <选择器> <张数> [超时秒]  等出图（SRC 差集轮询，默认 300s）
  ── 一键流程 ─────────────────────────────
  flow <站点> <提示词> [--img 垫图] [--num 张数]  执行站点预设完整流程
  ── 控制 ─────────────────────────────
  help                    显示本帮助
  quit / exit             退出

安全：读类命令（buttons/find/state/verify/html/shot）只读；
     基础交互（click/open-menu）默认只做轻量点击/展开便于排查试探。
     发消息/传图用 type / upload / flow，它们支持完整交互（可真正发送）。
"""
import os
import re
import sys
import time
import argparse
from functools import wraps
from playwright.sync_api import sync_playwright

# Windows 控制台 UTF-8 修复（避免中文乱码）
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import win_utf8
    win_utf8.ensure_utf8_console()
except Exception:
    pass

CDP_URL = "http://127.0.0.1:9222"

# 只保留非样式特征 class（找锚点时过滤 Tailwind/框架样式噪音）
_SKIP_CLS = re.compile(
    r"^(w-|h-|m[trblxy]?-|p[trblxy]?-|bg-|text-|border|rounded|shadow|opacity-|z-|gap-|flex|grid|"
    r"absolute|relative|fixed|inline|block|hidden|items-|justify-|leading-|font-|tracking-|transition|"
    r"transform|cursor-|overflow-|duration-|ease-|min-|max-|size-|nowrap|whitespace|break-|outline-|"
    r"select-|list-|grid-|col-|row-)"
)

def _clean_cls(cls: str) -> str:
    """清理并过滤无用的样式 class"""
    return " ".join(c for c in (cls or "").split() if c and not _SKIP_CLS.match(c))[:80]


# ---------- 装饰器 ----------
def require_page(func):
    """确保在执行命令前已连接并获取到有效页面"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.page:
            print("⚠️ 尚未连接，先输入 open")
            return
        return func(self, *args, **kwargs)
    return wrapper

def catch_error(prefix="❌ 执行异常"):
    """统一的异常捕获机制，减少冗余 try/except"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                print(f"{prefix}: {str(e)[:100]}")
        return wrapper
    return decorator


class WebCtl:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.page = None
        
        # 注册各站点的预设流程
        self._FLOWS = {
            "doubao": self._flow_doubao,
            # "lovart": self._flow_lovart,   
            # "jimeng": self._flow_jimeng,
        }
        self._init_commands()

    def _init_commands(self):
        """注册所有可用命令到路由字典"""
        self.CMD = {
            "open": self.cmd_open, "page": self.cmd_page, "buttons": self.cmd_buttons, 
            "nav": self.cmd_nav, "find": self.cmd_find, "state": self.cmd_state, 
            "verify": self.cmd_verify, "html": self.cmd_html, "open-menu": self.cmd_open_menu, 
            "click": self.cmd_click, "select": self.cmd_select, "type": self.cmd_type, 
            "upload": self.cmd_upload, "flow": self.cmd_flow, "esc": self.cmd_esc, 
            "clear": self.cmd_clear, "coord": self.cmd_coord, "shot": self.cmd_shot, 
            "waitimg": self.cmd_waitimg, "help": self.cmd_help, "quit": self.cmd_quit, 
            "exit": self.cmd_quit,
        }

    # ---------- 基础 ----------
    @catch_error("❌ 连接失败")
    def cmd_open(self, args=None):
        if not self.pw:
            self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(CDP_URL)
        self._pick_page()
        
        if not self.page:
            print("✅ 已连接 9222 浏览器，但未找到可用的 http 页面。可先导航或在浏览器打开网站。")
        else:
            print(f"✅ 已连接 9222 浏览器，当前页面: {self.page.url}")
        return True

    def _pick_page(self):
        """追踪导弹：用 URL 认路，不信任 pages[-1]"""
        for p in self.browser.contexts[0].pages:
            if p.url and p.url.startswith("http") and "chrome://" not in p.url and "about:" not in p.url:
                self.page = p
                return
        self.page = self.browser.contexts[0].pages[0] if self.browser.contexts[0].pages else None

    # ---------- 看 ----------
    @require_page
    def cmd_page(self, args):
        print(f"📍 页面: {self.page.url}\n  标题: {self.page.title()}")

    @require_page
    @catch_error("❌ 导航失败")
    def cmd_nav(self, args):
        if not args:
            print("用法: nav <url> 或 nav <站点名(doubao/lovart/jimeng/flow)>")
            return
            
        presets = {
            "doubao": "https://www.doubao.com/chat/",
            "lovart": "https://www.lovart.ai/zh/home",
            "jimeng": "https://jimeng.jianying.com/ai-tool/image/generate",
            "flow": "https://flow.bytedance.com/",
        }
        url = presets.get(args[0].lower(), args[0])
        self.page.goto(url, timeout=60000)
        time.sleep(2)
        print(f"🧭 已导航到: {self.page.url}")

    @require_page
    def cmd_buttons(self, args):
        btns = self.page.locator("button:visible").all()
        seen = []
        for b in btns:
            if (t := (b.inner_text() or "").strip()) and t not in seen:
                seen.append(t)
                
        print(f"共 {len(btns)} 个可见按钮，去重后 {len(seen)} 个:")
        for t in seen:
            print(f"  · {t!r}")

    @require_page
    def cmd_find(self, args):
        if not args:
            print("用法: find <文本>")
            return
            
        kw = " ".join(args)
        res = self.page.evaluate(
            """(kw) => {
                const results = [];
                const nodes = document.querySelectorAll('button,a,span,div,li,[role="menuitem"],[role="tab"],[data-testid]');
                nodes.forEach(el => {
                    const t = (el.innerText || "").trim();
                    if (t && t.length <= 25 && t.includes(kw)) {
                        const chain = [];
                        let cur = el;
                        for (let i = 0; i <= 3 && cur; i++) {
                            chain.push({
                                tag: cur.tagName.toLowerCase(),
                                testid: cur.getAttribute("data-testid") || "",
                                cls: (typeof cur.className === "string" ? cur.className : ""),
                                text: (cur.innerText || "").trim().slice(0, 30),
                                id: cur.id || ""
                            });
                            cur = cur.parentElement;
                        }
                        results.push(chain);
                    }
                });
                return results.slice(0, 10);
            }""",
            kw,
        )
        if not res:
            print(f"未找到含「{kw}」的短文本元素。")
            return
            
        for i, chain in enumerate(res):
            print(f"\n--- 命中 {i+1} ---")
            for n in chain:
                print(f"  <{n['tag']}> testid={n['testid']!r} id={n['id']!r} cls={_clean_cls(n['cls'])!r} text={n['text']!r}")

    @require_page
    @catch_error("❌ 获取状态失败")
    def cmd_state(self, args):
        if not args:
            print("用法: state <选择器>")
            return
            
        sel = " ".join(args)
        loc = self.page.locator(sel)
        
        if (n := loc.count()) == 0:
            print(f"「{sel}」命中 0 个")
            return
            
        for i in range(min(n, 3)):
            info = loc.nth(i).evaluate(
                "e => ({tag:e.tagName, text:(e.innerText||'').trim().slice(0,40), "
                "testid:e.getAttribute('data-testid')||'', vis:!!(e.offsetWidth||e.offsetHeight)})"
            )
            print(f"  [{i}] {info}")

    @require_page
    @catch_error("❌ 输入失败")
    def cmd_type(self, args):
        if not args:
            print("用法: type <文本> 或 type <选择器> <文本>")
            return
            
        first = args[0]
        looks_selector = any(c in first for c in "#.[:>,=\"'")
        
        if looks_selector and len(args) >= 2:
            target = self.page.locator(first).first
            text = " ".join(args[1:])
        else:
            target = self.page.locator("textarea:visible, input[type=text]:visible, div[contenteditable=true]:visible").first
            text = " ".join(args)
            
        try:
            target.wait_for(state="visible", timeout=8000)
            target.click(force=True)
        except Exception as e:
            print(f"⚠️ 定位/聚焦输入框异常: {str(e)[:80]}")
            
        time.sleep(0.3)
        self.page.keyboard.type(text, delay=30)
        time.sleep(0.5)
        print(f"⌨️ 已输入: {text!r}")

    @require_page
    def cmd_upload(self, args):
        if len(args) < 2:
            print("用法: upload <选择器> <本地文件绝对路径>")
            return
            
        sel, path = args[0], args[1]
        if not os.path.exists(path):
            print(f"❌ 文件不存在: {path}")
            return
            
        try:
            loc = self.page.locator(sel).first
            if loc.count() > 0:
                loc.set_input_files(path)
                print(f"📤 已通过 set_input_files 上传: {os.path.basename(path)}")
                return
        except Exception:
            pass
            
        try:
            print("⏳ 尝试 file_chooser 拦截...")
            with self.page.expect_file_chooser(timeout=8000) as fc:
                self.page.locator(sel).first.click(force=True)
            fc.value.set_files(path)
            print(f"📤 已通过 file_chooser 上传: {os.path.basename(path)}")
        except Exception as e:
            print(f"❌ 上传失败: {str(e)[:100]}")

    @require_page
    @catch_error("❌ 按键失败")
    def cmd_esc(self, args):
        key = args[0] if args else "Escape"
        self.page.keyboard.press(key)
        time.sleep(0.5)
        print(f"⌨️ 已按 <{key}>")

    @require_page
    @catch_error("❌ 清空失败")
    def cmd_clear(self, args):
        sel = args[0] if args else "textarea:visible, input[type=text]:visible, div[contenteditable=true]:visible"
        loc = self.page.locator(sel).first
        loc.wait_for(state="visible", timeout=5000)
        loc.click(force=True)
        
        cmd = "Meta+A" if sys.platform.startswith("darwin") else "Control+A"
        self.page.keyboard.press(cmd)
        self.page.keyboard.press("Backspace")
        time.sleep(0.3)
        print(f"🧹 已清空输入框: {sel}")

    @require_page
    @catch_error("❌ 点击失败")
    def cmd_coord(self, args):
        if len(args) < 2:
            print("用法: coord <x> <y>（屏幕坐标）")
            return
        x, y = int(args[0]), int(args[1])
        self.page.mouse.click(x, y)
        time.sleep(0.5)
        print(f"🎯 已点击坐标 ({x}, {y})")

    @require_page
    @catch_error("❌ 截图失败")
    def cmd_shot(self, args):
        path = args[0] if args else os.path.join("Downloads", f"webctl_{int(time.time())}.png")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.page.screenshot(path=path)
        print(f"📸 截图已保存: {path}")

    @require_page
    def cmd_waitimg(self, args):
        if len(args) < 2:
            print("用法: waitimg <选择器> <目标张数> [超时秒]")
            return
            
        sel = args[0]
        try:
            target = int(args[1])
        except ValueError:
            print("❌ 目标张数需为数字")
            return
            
        timeout = int(args[2]) if len(args) > 2 and args[2].isdigit() else 300
        start_time = time.time()
        seen = {}
        
        print(f"⏳ 等待出图: 目标 {target} 张，超时 {timeout}s，监听 {sel}...")
        while time.time() - start_time < timeout:
            try:
                srcs = self.page.locator(sel).evaluate_all("els => els.map(e => e.src || e.getAttribute('data-src') || '')")
                for s in srcs:
                    if s and "data:image" not in s and "loading" not in s:
                        seen[s] = seen.get(s, 0) + 1
                if len(seen) >= target:
                    print(f"✅ 已出现 {len(seen)} 张真图：")
                    for s in seen:
                        print(f"   - {s[:100]}")
                    return
            except Exception:
                pass
            time.sleep(2)
        print(f"⚠️ 超时，仅出现 {len(seen)} 张（不足 {target} 张）")

    # ---------------------------------------------------------
    # [预设流程]：把站点常用操作序列内化，一条命令走完整流程
    # ---------------------------------------------------------
    def cmd_flow(self, args):
        if not args:
            print("用法: flow <站点名> <提示词> [--img <垫图路径>] [--num <张数>]")
            return
            
        site = args[0].lower()
        if site not in self._FLOWS:
            print(f"❌ 未知站点流程: {site}，可用: {list(self._FLOWS.keys())}")
            return
            
        # 优化参数解析逻辑
        prompt_parts, img_path, num = [], None, 1
        it = iter(args[1:])
        for t in it:
            if t == "--img":
                img_path = next(it, None)
            elif t == "--num":
                num = int(next(it, 1))
            else:
                prompt_parts.append(t)
                
        prompt = " ".join(prompt_parts)
        if not prompt:
            print("❌ 请提供提示词")
            return
            
        print(f"🎬 执行 [{site}] 流程: 提示词={prompt!r} 垫图={img_path} 数量={num}")
        try:
            self._FLOWS[site](prompt=prompt, img_path=img_path, num=num)
        except Exception as e:
            print(f"❌ 流程执行异常: {str(e)[:150]}")

    def _ensure_site_page(self, site, url):
        """确保当前 page 是目标站点页；否则导航过去（复用登录态）。"""
        if not self.page and not self.cmd_open():
            raise Exception("无法连接浏览器")
        if site not in (self.page.url or ""):
            self.cmd_nav([url])
            time.sleep(3)

    def _flow_doubao(self, prompt, img_path, num):
        """豆包完整流程，逐步验证：每步确认成功才进下一步，失败明确报出。"""
        self._ensure_site_page("doubao.com", "https://www.doubao.com/chat/")
        page = self.page
        ok_all = True

        # ── 步骤1：选择【图像生成】模式，验证输入框/工作台就位 ──
        print("   [1/4] 🎛️ 选择【图像生成】模式...")
        try:
            mode_btn = page.locator('button[data-skill-id="skill_bar_button_3"]:visible').first
            mode_btn.wait_for(state="visible", timeout=8000)
            mode_btn.click(force=True)
            time.sleep(2)
            # 验证：输入框是否出现（模式切换后工作台应有可输入框）
            if page.locator("textarea:visible").first.count() > 0:
                print("       ✅ 模式已切换，工作台就位")
            else:
                print("       ⚠️ 点了模式但未见输入框，可能未登录/被弹窗拦截")
                ok_all = False
        except Exception as e:
            print(f"       ❌ 图像生成模式切换异常: {str(e)[:80]}")
            ok_all = False

        # ── 步骤2：上传垫图（如有）并验证 ──
        if img_path:
            print(f"   [2/4] 🖼️ 上传垫图: {img_path}")
            try:
                up = page.locator('span:has-text("参考图") input[type="file"]').first
                if up.count() > 0:
                    up.set_input_files(img_path)
                    time.sleep(2)
                    # 验证：上传后垫图缩略是否出现（用参考图区域的可见元素判断）
                    ok_up = page.locator('img[src*="blob"], img[src*="data:"], [class*="preview"]').first.count() > 0
                    if ok_up:
                        print("       ✅ 垫图已上传")
                    else:
                        print("       ⚠️ 垫图已塞但未见预览，可能上传失败")
                        ok_all = False
                else:
                    print("       ❌ 未找到上传入口（未登录/未进入图像模式）")
                    ok_all = False
            except Exception as e:
                print(f"       ❌ 上传失败: {str(e)[:80]}")
                ok_all = False
        else:
            print("   [2/4] 🖼️ 无垫图，跳过")

        # ── 步骤3：填入提示词，验证发送按钮出现 ──
        print("   [3/4] ⌨️ 填入提示词...")
        try:
            ta = page.locator("textarea:visible").first
            ta.wait_for(state="visible", timeout=8000)
            ta.click(force=True)
            page.keyboard.type(prompt, delay=30)
            time.sleep(0.8)
            if page.locator("#flow-end-msg-send:visible").first.count() > 0:
                print("       ✅ 已填词，发送按钮就位")
            else:
                print("       ⚠️ 已填词但发送按钮未出现（可能输入框没拿到文字）")
                ok_all = False
        except Exception as e:
            print(f"       ❌ 填词失败: {str(e)[:80]}")
            ok_all = False

        # ── 步骤4：发送，并验证出图 ──
        print(f"   [4/4] 🚀 发送，等待出图（目标 {num} 张）...")
        try:
            send = page.locator("#flow-end-msg-send:visible").first
            send.wait_for(state="visible", timeout=8000)
            send.click(force=True)
            print("       ✅ 已发送，开始监听出图...")
            self.cmd_waitimg(['img[src*="rc_gen_image"]', str(num), "120"])
        except Exception as e:
            print(f"       ❌ 发送按钮未出现（可能未登录或无输入）: {str(e)[:80]}")
            ok_all = False

        print("─" * 40)
        if ok_all:
            print(f"🎯 [{self.page.url and 'doubao'}] 流程全部步骤验证通过")
        else:
            print(f"⚠️ [{self.page.url and 'doubao'}] 流程有步骤未通过，请检查上面 ❌/⚠️")

    @require_page
    def cmd_verify(self, args):
        if not args:
            print("用法: verify <选择器> 或 verify <选择器1> ; <选择器2> ...")
            return
            
        sels = [s.strip() for s in " ".join(args).split(";") if s.strip()]
        print(f"验证 {len(sels)} 个选择器：")
        
        for sel in sels:
            try:
                loc = self.page.locator(sel)
                total = loc.count()
                vis = sum(1 for i in range(total) if loc.nth(i).is_visible())
                
                mark = "✅" if vis > 0 else ("⚠️" if total > 0 else "❌")
                first_info = ""
                
                if total > 0:
                    try:
                        first_info = loc.nth(0).evaluate(
                            "e => ({tag:e.tagName, testid:e.getAttribute('data-testid')||'', "
                            "cls:(typeof e.className==='string'?e.className.slice(0,40):'')})"
                        )
                    except Exception:
                        pass
                        
                print(f"  {mark} total={total:3d} visible={vis:3d}  {sel}")
                if first_info:
                    print(f"       first -> {first_info}")
            except Exception as e:
                print(f"  ❌ {sel}  异常: {str(e)[:80]}")
                
        print("  ℹ️  若发送/提交按钮命中 0，先往输入框打字再验证（很多站空输入不渲染发送按钮）。")

    @require_page
    def cmd_html(self, args):
        html = self.page.content()
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
        html = re.sub(r">\s+<", "><", html)
        print(html[:8000])

    # ---------- 做 ----------
    @require_page
    @catch_error("⚠️ 展开失败")
    def cmd_open_menu(self, args):
        if not args:
            print("用法: open-menu <选择器> [click|hover]")
            return
            
        # 解析动作：仅当最后一个是显式的 click/hover 关键字时才作为动作，其余全是选择器
        if len(args) > 1 and args[-1] in ("click", "hover"):
            action = args[-1]
            sel = " ".join(args[:-1])
        else:
            action = "hover"
            sel = " ".join(args)
        
        loc = self.page.locator(sel).last
        loc.scroll_into_view_if_needed(timeout=5000)
        
        if action == "click":
            loc.click(timeout=8000, force=True)
        else:
            loc.hover(timeout=8000, force=True)
            
        time.sleep(1.2)
        print(f"✅ 已用 {action} 展开「{sel}」")

    @require_page
    def cmd_click(self, args):
        if not args:
            print("用法: click <文本>")
            return
            
        kw = " ".join(args)
        clicked = self.page.evaluate(
            """(kw) => {
                const els = Array.from(document.querySelectorAll('button,a,[role="button"],[role="menuitem"]'));
                const t = els.find(e => (e.innerText||'').trim() === kw);
                if (t) { t.click(); return {ok:true, tag:t.tagName}; }
                // 模糊匹配
                const f = els.filter(e => (e.innerText||'').trim().includes(kw));
                if (f.length) { f[0].click(); return {ok:true, tag:f[0].tagName, matched:f.length}; }
                return {ok:false};
            }""",
            kw,
        )
        if clicked.get("ok"):
            print(f"✅ 点击了含「{kw}」的元素 (<{clicked['tag']}>)")
        else:
            print(f"❌ 未找到含「{kw}」的可点击元素")

    def cmd_select(self, args):
        return self.cmd_click(args)

    # ---------- 控制 ----------
    def cmd_help(self, args=None):
        print("""
命令用法（通用浏览器控制台）:
  open                      连接 9222 浏览器
  page                      看当前页面 URL/标题
  nav <url|站点名>          导航到 URL 或站点(doubao/lovart/jimeng/flow)
  buttons                   列出页面所有可见按钮（摸结构）
  find <文本>               搜含文本的元素 + 锚点链（找 data-testid）
  open-menu <选择器> [click|hover]   展开下拉菜单（默认 hover）
  click <文本>              点击含该文本的按钮（精确匹配）
  select <文本>             同 click，精确文本点击
  state <选择器>            查看某元素当前内容（验证是否生效）
  verify <选择器> [; 选择器...]  批量验证多个选择器命中情况（total/visible）
  type <文本> | type <选择器> <文本>  向输入框打字（拟人延迟）
  upload <选择器> <本地文件路径>      上传文件（file_chooser 拦截/set_input_files）
  flow <站点名> <提示词> [--img 垫图] [--num 张数]  执行站点预设流程
  esc [键名]                按键，默认 Esc 关弹窗
  clear [选择器]            清空输入框（Ctrl+A+Backspace）
  coord <x> <y>             盲点屏幕坐标（收起菜单/弹窗）
  shot [路径]               截图当前页面
  waitimg <选择器> <张数> [超时秒]   等出图（SRC 差集轮询，默认300s）
  html                      抓整页净化 DOM
  help                      显示本帮助
  quit / exit               退出
""")

    def cmd_quit(self, args=None):
        self.close()
        print("再见。")
        sys.exit(0)

    def close(self):
        try:
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except Exception:
            pass
        finally:
            self.page = self.browser = self.pw = None

    # ---------- 命令路由 ----------
    def exec_line(self, line):
        """执行单条命令字符串（REPL 与 --run 共用）。"""
        if not (line := line.strip()):
            return
            
        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]
        
        if handler := self.CMD.get(cmd):
            try:
                handler(args)
            except Exception as e:
                print(f"❌ {cmd} 执行内部异常: {str(e)[:120]}")
        else:
            print(f"未知命令: {cmd}（输入 help 查看）")

    def run(self):
        self.cmd_help()
        while True:
            try:
                raw = input("\nwebctl> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.close()
                print("\n再见。")
                break
            self.exec_line(raw)


def main():
    ap = argparse.ArgumentParser(description="通用浏览器交互控制台")
    ap.add_argument("--url", help="连上后自动导航到该 URL（可选）")
    ap.add_argument("--run", help="一次性执行命令序列，用 | 分隔，如 --run \"page|buttons|quit\"")
    args = ap.parse_args()

    ctl = WebCtl()
    try:
        ctl.cmd_open()
        if args.url and ctl.page:
            ctl.page.goto(args.url, timeout=60000)
            time.sleep(2)
            print(f"已导航到: {ctl.page.url}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("提示：请先用 启动控制台.bat 启动项目（Chrome 带 9222）。")
        return 1

    if args.run:
        for line in args.run.split("|"):
            ctl.exec_line(line)
        ctl.close()
        return 0

    ctl.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())