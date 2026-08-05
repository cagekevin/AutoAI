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
  tabs                    列出所有标签页
  tab <序号>              切换到指定标签页
  ── 读取 / 抓取 ─────────────────────────────
  buttons                 列出页面所有可见按钮（摸结构）
  find <文本>             搜含文本的元素 + 锚点链（找 data-testid）
  state <选择器>          查看某元素当前内容（验证选择器是否生效）
  verify <sel>[; sel...]  批量验证多个选择器命中情况（total/visible）
  html                    抓整页净化 DOM
  shot [路径]             截图当前页面
  frames                  列出页面所有 iframe
  frame <序号> <命令...>  在指定 iframe 内执行 find/state/verify/probe 等
  shadow <选择器>         穿透 Shadow DOM 找元素并列出锚点链
  js <JS代码>             在页面执行任意 JS 并返回结果
  ── 交互操作 ─────────────────────────────
  click <文本>            点击含该文本的按钮（精确匹配）
  select <文本>           同 click
  open-menu <选择器> [click|hover]  展开下拉菜单（默认 hover）
  probe <选择器> [first|last] [click|hover]  模拟引擎式点击并报告点后变化
  wait <选择器> [超时秒]   等元素出现（条件渲染，默认 10s）
  type <文本>|<选择器> <文本>  向输入框打字（拟人延迟）
  upload <选择器> <路径>  上传文件（file_chooser 拦截/set_input_files）
  clear [选择器]          清空输入框（Ctrl+A + Backspace）
  esc [键名]              按键，默认 Esc 关弹窗
  coord <x> <y>           盲点屏幕坐标（收起菜单/弹窗）
  waitimg <选择器> <张数> [超时秒]  等出图（SRC 差集轮询，默认 300s）
  getimg <选择器> [保存目录]  下载命中的真图 URL 到本地
  ── 沉淀 / 流程 ─────────────────────────────
  export-ui [文件名]      把验证过的选择器聚合成引擎 UI 字典 JSON 落盘
  flow <站点> <提示词> [--img 垫图] [--num 张数]  执行站点预设完整流程
  ── 控制 ─────────────────────────────
  help                    显示本帮助
  quit / exit             退出

安全：读类命令（buttons/find/state/verify/html/shot/frames/shadow/js）只读；
     基础交互（click/open-menu/probe）默认只做轻量点击/展开便于排查试探。
     发消息/传图用 type / upload / flow，它们支持完整交互（可真正发送）。
"""
import os
import re
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
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

# 锚点记忆存储路径（跨会话持久化，探到的稳定锚点下次自动复用）
_ANCHOR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".webctl_anchors.json")

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

# Radix/复合框架生成带冒号的 id（如 #radix-:r3f:），Playwright CSS 里冒号需转义
_ID_COLON_RE = re.compile(r'(#[^ \t\r\n,>+~]+)')

def _norm_selector(sel: str) -> str:
    """标准化选择器，解决探路常见坑：
    1. `:has-text(中文)` 无引号 → 自动补成 `:has-text("中文")`（Playwright 要求字符串参数）
    2. id 里的冒号（#radix-:r3f:）→ 转义为 \\: （否则被当伪类解析失败）
    """
    if not sel:
        return sel

    def fix_has_text(m):
        # :has-text(xxx) 或 :has-text( xxx ) → :has-text("xxx")；已带引号则跳过
        inner = m.group(1)
        if inner.strip().startswith(('"', "'")):
            return f':has-text({inner.strip()})'
        return f':has-text("{inner.strip()}")'
    sel = re.sub(r':has-text\(\s*([^()]*?)\s*\)', fix_has_text, sel)

    def fix_id_colon(m):
        # 对 # 开头的片段，把裸冒号转义为 \\: （但不破坏已有的 \\:）
        part = m.group(1)
        part = re.sub(r'(?<!\\):', r'\\:', part)
        return part
    sel = _ID_COLON_RE.sub(fix_id_colon, sel)
    return sel


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
        # 锚点记忆表：ui/anchor 收集的稳定锚点，按名称复用（跨会话持久化，迭代复用）
        self.anchors = self._load_anchors()
        
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
            # ---- 探路增强 ----
            "probe": self.cmd_probe, "wait": self.cmd_wait,
            "frames": self.cmd_frames, "frame": self.cmd_frame,
            "shadow": self.cmd_shadow, "js": self.cmd_js,
            "tabs": self.cmd_tabs, "tab": self.cmd_tab,
            "export-ui": self.cmd_export_ui, "getimg": self.cmd_getimg,
            "ui": self.cmd_ui, "anchor": self.cmd_anchor,
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

    @catch_error("❌ 标签页操作失败")
    def cmd_tabs(self, args):
        """列出当前 context 所有标签页，供 tab 切换认路。"""
        pages = self.browser.contexts[0].pages
        cur = getattr(self, 'page', None)
        print(f"共 {len(pages)} 个标签页:")
        for i, p in enumerate(pages):
            mark = " 👈 当前" if p == cur else ""
            try:
                title = p.title()
            except Exception:
                title = "?"
            print(f"  [{i}] {title!r}\n      {p.url}{mark}")

    @catch_error("❌ 切换失败")
    def cmd_tab(self, args):
        """切换到指定序号的标签页：tab <序号>"""
        if not args:
            print("用法: tab <序号>（先用 tabs 看序号）")
            return
        try:
            idx = int(args[0])
        except ValueError:
            print(f"❌ 序号需为数字: {args[0]}")
            return
        pages = self.browser.contexts[0].pages
        if idx >= len(pages):
            print(f"❌ 序号 {idx} 越界，共 {len(pages)} 个")
            return
        self.page = pages[idx]
        try:
            self.page.bring_to_front()
        except Exception:
            pass
        print(f"✅ 已切到标签页 [{idx}]: {self.page.url}")

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
            
        raw = " ".join(args)
        sel = _norm_selector(self._resolve_anchor(raw)) if (" " not in raw) else _norm_selector(raw)
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

    @require_page
    @catch_error("❌ 下载失败")
    def cmd_getimg(self, args):
        """getimg <选择器> [保存目录]：把命中的真实图片 URL 下载到本地（收割）。"""
        if not args:
            print("用法: getimg <选择器> [保存目录]")
            return
        sel = _norm_selector(args[0])
        out_dir = args[1] if len(args) > 1 else os.path.join("Downloads", "webctl_images")
        os.makedirs(out_dir, exist_ok=True)

        srcs = self.page.locator(sel).evaluate_all(
            "els => els.map(e => e.src || e.getAttribute('data-src') || '')"
        )
        # 过滤：只留 http 真图，去掉 data: 内联与黑名单占位
        blacklist = re.compile(r"(base64|blob:|loading|placeholder|spinner|/user/|/upload/|/reference/|/source/|/input/)", re.I)
        valid = [s for s in dict.fromkeys(srcs) if s and s.startswith("http") and not blacklist.search(s)]
        if not valid:
            print(f"❌ 「{sel}」未找到 http 真图 URL（命中 {len(srcs)} 个原始 src）")
            return
        print(f"⬇️ 发现 {len(valid)} 张真图，开始下载到 {out_dir} ...")
        user_agent = self.page.evaluate("navigator.userAgent")
        cookies = self.context_cookies()
        for i, url in enumerate(valid):
            fname = f"{int(time.time())}_{i}.jpg"
            save_path = os.path.join(out_dir, fname)
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": user_agent,
                    "Cookie": cookies,
                    "Referer": self.page.url,
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                with open(save_path, "wb") as f:
                    f.write(data)
                print(f"  ✅ [{i+1}/{len(valid)}] {fname}  {url[:90]}")
            except Exception as e:
                print(f"  ⚠️ [{i+1}/{len(valid)}] 下载失败: {str(e)[:60]}  {url[:90]}")
        print(f"📦 完成，保存目录: {out_dir}")

    def context_cookies(self):
        """取当前 context 的 Cookie 串（供下载带登录态）。"""
        try:
            cookies = self.browser.contexts[0].cookies()
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        except Exception:
            return ""

    @require_page
    @catch_error("❌ 导出失败")
    @require_page
    @catch_error("❌ 收集 UI 失败")
    def cmd_ui(self, args):
        """ui：扫描当前页，收集可见可交互元素的稳定锚点，存进记忆表 self.anchors。
        切对模式后参数按钮（比例/模型/风格/上传/发送）是稳定不变的，一次收集、后续按名复用。
        之后命令里用锚点名（如 click 比例 / open-menu 模型）即可自动定位。
        """
        nodes = self.page.evaluate(
            """() => {
                const out = {};
                const els = document.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="tab"],select');
                els.forEach(el => {
                    // 只看可见元素
                    const r = el.getBoundingClientRect();
                    const vis = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
                    if (!vis) return;
                    const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                    if (!text) return;
                    // 只取短文本（按钮/选项），跳过冗长描述
                    const key = text.split('\\n')[0].trim().slice(0, 12);
                    if (!key) return;
                    // 保留最短文本，避免父元素覆盖子元素
                    if (!(key in out) || text.length < out[key].text.length) {
                        const c = typeof el.className === 'string' ? el.className : '';
                        out[key] = { text, tag: el.tagName.toLowerCase(), cls: c.slice(0, 60) };
                    }
                });
                return out;
            }"""
        )
        if not nodes:
            print("⚠️ 当前页未找到可见的可交互文本元素。可能未切到正确模式/未登录。")
            return
        print(f"✅ 收集到 {len(nodes)} 个稳定锚点，已存入记忆表（后续 click/open-menu/state 可直接用锚点名）：")
        for key, info in nodes.items():
            # 生成可复用的选择器：优先 has-text 文本锚定（比动态 class 稳）
            sel = f'button:has-text("{key}"), a:has-text("{key}")'
            self.anchors[key] = sel
            print(f"  「{key}」 <- {sel}")
        self._save_anchors()
        print(f"  💾 已持久化到 {_ANCHOR_FILE}（下次启动自动复用，不用重新探）")
        print("  用法示例: click 比例 | open-menu 模型 | state 风格")
        print("  手动补充/覆盖用: anchor <名称> <选择器>")

    def _load_anchors(self) -> dict:
        """加载持久化的锚点表，实现跨会话迭代复用。"""
        try:
            if os.path.exists(_ANCHOR_FILE):
                with open(_ANCHOR_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_anchors(self):
        """把锚点表写入磁盘，供下次会话复用（迭代式探路的关键）。"""
        try:
            with open(_ANCHOR_FILE, "w", encoding="utf-8") as f:
                json.dump(self.anchors, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ 锚点持久化失败: {str(e)[:60]}")

    @catch_error("❌ 添加锚点失败")
    def cmd_anchor(self, args):
        """anchor <名称> <选择器>：手动把稳定锚点加入记忆表并持久化。"""
        if len(args) < 2:
            print("用法: anchor <名称> <选择器>")
            return
        name, sel = args[0], _norm_selector(" ".join(args[1:]))
        self.anchors[name] = sel
        self._save_anchors()
        print(f"✅ 已记住锚点: 「{name}」-> {sel}（已持久化）")

    def _resolve_anchor(self, target: str) -> str:
        """若 target 命中了记忆的锚点名，返回其选择器；否则原样返回（视为选择器或文本）。"""
        if target in self.anchors:
            return self.anchors[target]
        return target

    def cmd_export_ui(self, args):
        """export-ui [文件名]：把当前页探路验证过的选择器聚合成引擎 UI 字典 JSON 落盘。
        收集：当前页面所有含 data-testid 的元素 + 用户已通过 state/verify 确认的选择器。
        简单起见，收集所有带 data-testid 的元素并给建议 key（按文案）。
        """
        fname = args[0] if args else os.path.join("Downloads", "webctl_ui_export.json")
        os.makedirs(os.path.dirname(fname) or ".", exist_ok=True)

        # 收集所有 data-testid 元素
        nodes = self.page.evaluate(
            """() => {
                const out = {};
                document.querySelectorAll('[data-testid]').forEach(el => {
                    const tid = el.getAttribute('data-testid');
                    if (!tid || tid in out) return;
                    const text = (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30);
                    const tag = el.tagName.toLowerCase();
                    out[tid] = { tag, text };
                });
                return out;
            }"""
        )
        if not nodes:
            print("⚠️ 当前页未找到任何 data-testid 元素。可先 find/state 探到选择器后，再 export-ui 收集。")
            return

        # 组织成引擎 UI 字典风格：建议 key = 文本短名（英文/拼音不易，这里用 text 截断）
        ui = {}
        for tid, info in nodes.items():
            key = f"testid_{tid.split('_')[-1]}" if tid else f"el_{len(ui)}"
            ui[key] = f'[data-testid="{tid}"]'
        payload = {"_note": "由 webctl export-ui 生成，key 为建议值，请按引擎实际 UI 字典 key 重命名", "ui": ui}
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"✅ 已导出 {len(ui)} 个 data-testid 选择器到 {fname}")
        print("   请按 base_engine.py 的 UI key（mode_btn/param_panel_trigger/upload_input/input_box/new_proj_btn/popups...）重命名后使用")

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
            
        sels = [_norm_selector(s.strip()) for s in " ".join(args).split(";") if s.strip()]
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

    @require_page
    @catch_error("❌ 穿透失败")
    def cmd_shadow(self, args):
        """shadow <选择器>：穿透 Shadow DOM / iframe 递归找含该文本的元素，列出锚点链。"""
        if not args:
            print("用法: shadow <文本>（递归穿透所有 shadowRoot / contentDocument 找含文本元素）")
            return
        kw = " ".join(args)
        res = self.page.evaluate(
            """(kw) => {
                const results = [];
                const walk = (root) => {
                    root.querySelectorAll('button,a,span,div,li,[role="menuitem"],[role="tab"],[data-testid]').forEach(el => {
                        const t = (el.innerText || "").trim();
                        if (t && t.length <= 40 && t.includes(kw)) {
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
                    root.querySelectorAll('*').forEach(el => {
                        if (el.shadowRoot) walk(el.shadowRoot);
                        if (el.tagName === 'IFRAME') { try { walk(el.contentDocument); } catch(e){} }
                    });
                };
                walk(document);
                return results.slice(0, 10);
            }""",
            kw,
        )
        if not res:
            print(f"未在 Shadow DOM/iframe 中找到含「{kw}」的元素。")
            return
        for i, chain in enumerate(res):
            print(f"\n--- 命中 {i+1} ---")
            for n in chain:
                print(f"  <{n['tag']}> testid={n['testid']!r} id={n['id']!r} cls={_clean_cls(n['cls'])!r} text={n['text']!r}")

    @require_page
    @catch_error("❌ JS 执行失败")
    def cmd_js(self, args):
        """js <JS代码>：在页面执行任意 JS，返回 JSON 序列化结果（探结构/穿透用）。"""
        if not args:
            print("用法: js <JS代码>（如 js \"Array.from(document.querySelectorAll('*')).length\"）")
            return
        code = " ".join(args)
        ret = self.page.evaluate(code)
        if isinstance(ret, (dict, list)):
            print(json.dumps(ret, ensure_ascii=False, indent=2)[:8000])
        else:
            print(ret)

    @require_page
    @catch_error("❌ 取 frame 失败")
    def cmd_frames(self, args):
        """frames：列出页面所有 iframe（含名字/url/序号），供 frame <序号> 用。"""
        fs = self.page.frames
        print(f"共 {len(fs)} 个 frame:")
        for i, f in enumerate(fs):
            mark = " (主frame)" if f == self.page.main_frame else ""
            try:
                u = f.url
            except Exception:
                u = "?"
            print(f"  [{i}] {u}{mark}")

    @require_page
    @catch_error("❌ frame 内操作失败")
    def cmd_frame(self, args):
        """frame <序号> <子命令...>：在指定 iframe 内执行 find/state/verify/probe/click。"""
        if len(args) < 2:
            print("用法: frame <序号> <find/state/verify/probe/click/buttons/...> <参数>")
            return
        try:
            idx = int(args[0])
        except ValueError:
            print(f"❌ frame 序号需为数字: {args[0]}")
            return
        fs = self.page.frames
        if idx >= len(fs):
            print(f"❌ frame 序号 {idx} 越界，共 {len(fs)} 个")
            return
        f = fs[idx]
        sub_cmd, sub_args = args[1].lower(), args[2:]
        print(f"▶️ 在 frame [{idx}] {f.url[:80]} 内执行 {sub_cmd}")

        if sub_cmd == "find":
            if not sub_args:
                print("用法: frame <n> find <文本>")
                return
            kw = " ".join(sub_args)
            res = f.evaluate(
                """(kw) => {
                    const results = [];
                    document.querySelectorAll('button,a,span,div,li,[role="menuitem"],[role="tab"],[data-testid]').forEach(el => {
                        const t = (el.innerText || "").trim();
                        if (t && t.length <= 25 && t.includes(kw)) {
                            const chain = [];
                            let cur = el;
                            for (let i = 0; i <= 3 && cur; i++) {
                                chain.push({tag: cur.tagName.toLowerCase(), testid: cur.getAttribute("data-testid")||"", cls:(typeof cur.className==="string"?cur.className:""), text:(cur.innerText||"").trim().slice(0,30), id:cur.id||""});
                                cur = cur.parentElement;
                            }
                            results.push(chain);
                        }
                    });
                    return results.slice(0, 8);
                }""",
                kw,
            )
            if not res:
                print(f"frame 内未找到含「{kw}」的元素。")
                return
            for i, chain in enumerate(res):
                print(f"\n--- 命中 {i+1} ---")
                for n in chain:
                    print(f"  <{n['tag']}> testid={n['testid']!r} id={n['id']!r} cls={_clean_cls(n['cls'])!r} text={n['text']!r}")
        elif sub_cmd == "state":
            if not sub_args:
                print("用法: frame <n> state <选择器>")
                return
            sel = _norm_selector(" ".join(sub_args))
            loc = f.locator(sel)
            n = loc.count()
            if n == 0:
                print(f"frame 内「{sel}」命中 0")
                return
            for i in range(min(n, 3)):
                info = loc.nth(i).evaluate(
                    "e => ({tag:e.tagName, text:(e.innerText||'').trim().slice(0,40), "
                    "testid:e.getAttribute('data-testid')||'', vis:!!(e.offsetWidth||e.offsetHeight)})"
                )
                print(f"  [{i}] {info}")
        elif sub_cmd == "verify":
            sels = [_norm_selector(s.strip()) for s in " ".join(sub_args).split(";") if s.strip()]
            for sel in sels:
                try:
                    loc = f.locator(sel)
                    total = loc.count()
                    vis = sum(1 for i in range(total) if loc.nth(i).is_visible())
                    mark = "✅" if vis > 0 else ("⚠️" if total > 0 else "❌")
                    print(f"  {mark} total={total:3d} visible={vis:3d}  {sel}")
                except Exception as e:
                    print(f"  ❌ {sel} 异常: {str(e)[:60]}")
        elif sub_cmd == "probe":
            sel = _norm_selector(" ".join(sub_args)) if sub_args else ""
            if not sel:
                print("用法: frame <n> probe <选择器>")
                return
            loc = f.locator(sel).last
            total = f.locator(sel).count()
            vis = sum(1 for i in range(f.locator(sel).count()) if f.locator(sel).nth(i).is_visible())
            print(f"  命中 total={total} visible={vis}，模拟引擎式点击 .last ...")
            loc.wait_for(state="visible", timeout=8000)
            loc.click(force=True)
            time.sleep(1)
            print(f"  ✅ frame 内引擎式点击成功（已点击「{sel}」的 .last）")
        elif sub_cmd == "click":
            if not sub_args:
                print("用法: frame <n> click <文本>")
                return
            kw = " ".join(sub_args)
            clicked = f.evaluate(
                """(kw) => {
                    const els = Array.from(document.querySelectorAll('button,a,[role="button"],[role="menuitem"]'));
                    const t = els.find(e => (e.innerText||'').trim() === kw);
                    if (t) { t.click(); return {ok:true, tag:t.tagName}; }
                    const m = els.filter(e => (e.innerText||'').trim().includes(kw));
                    if (m.length) { m[0].click(); return {ok:true, tag:m[0].tagName, matched:m.length}; }
                    return {ok:false};
                }""",
                kw,
            )
            print(f"  {'✅ 点击了' if clicked.get('ok') else '❌ 未找到'} <{clicked.get('tag')}> 含「{kw}」")
        elif sub_cmd == "buttons":
            seen = []
            for b in f.locator("button:visible").all():
                if (t := (b.inner_text() or "").strip()) and t not in seen:
                    seen.append(t)
            print(f"  frame 内可见按钮去重 {len(seen)} 个:")
            for t in seen:
                print(f"    · {t!r}")
        else:
            print(f"❌ frame 内不支持子命令: {sub_cmd}（支持 find/state/verify/probe/click/buttons）")

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
            target = " ".join(args[:-1])
        else:
            action = "hover"
            target = " ".join(args)
        # 锚点名复用：无空格的单词若命中锚点表，直接换成已记住的选择器
        sel = _norm_selector(self._resolve_anchor(target)) if (" " not in target) else _norm_selector(target)
        if not sel:
            print("❌ 请提供选择器")
            return
        loc = self.page.locator(sel).last
        loc.scroll_into_view_if_needed(timeout=5000)
        
        if action == "click":
            loc.click(timeout=8000, force=True)
        else:
            loc.hover(timeout=8000, force=True)
            
        time.sleep(1.2)
        print(f"✅ 已用 {action} 展开「{sel}」")

    @require_page
    @catch_error("❌ probe 失败")
    def cmd_probe(self, args):
        """probe <选择器> [first|last] [click|hover]：模拟引擎式点击。
        与引擎 HIL 对齐：wait visible + click force + first/last，点完报告点后 DOM 变化。
        """
        if not args:
            print("用法: probe <选择器> [first|last] [click|hover]")
            return
        # 解析可选参数
        which = "last"
        action = "click"
        sels = []
        for a in args:
            if a in ("first", "last"):
                which = a
            elif a in ("click", "hover"):
                action = a
            else:
                sels.append(a)
        raw = " ".join(sels)
        sel = _norm_selector(self._resolve_anchor(raw)) if (" " not in raw) else _norm_selector(raw)
        if not sel:
            print("❌ 请提供选择器")
            return

        loc_all = self.page.locator(sel)
        total = loc_all.count()
        vis = sum(1 for i in range(total) if loc_all.nth(i).is_visible())
        print(f"🧪 probe「{sel}」: total={total} visible={vis}，用 .{which} + {action} 模拟引擎式操作...")

        target = loc_all.first if which == "first" else loc_all.last
        target.wait_for(state="visible", timeout=8000)

        # 点前快照：记录页面可见文本数（判断点后是否有面板展开/内容变化）
        def snapshot():
            try:
                return self.page.evaluate("document.body ? document.body.innerText.length : 0")
            except Exception:
                return None
        before = snapshot()

        try:
            if action == "hover":
                target.hover(force=True)
            else:
                target.click(force=True)
        except Exception as e:
            print(f"  ⚠️ 引擎式{action}抛出异常（点击可能已生效但元素随后被移除/页面导航）: {str(e)[:60]}")
            return
        time.sleep(1.2)

        after = snapshot()
        if before is None or after is None:
            print(f"  ✅ 引擎式{action}成功（{which}），但页面发生了导航/上下文销毁，无法读取点后 DOM。")
            print(f"  ↳ 若当前 URL 已变化，说明点击触发了跳转；用 page 命令确认。")
            return
        delta = after - before
        print(f"  ✅ 引擎式{action}成功（{which}）。点击前后 body 文本长度变化: {delta:+d}")
        if delta > 50:
            print(f"  ↳ 点后内容显著增加（{delta} 字符），很可能展开了面板/菜单。")
        elif delta == 0:
            print(f"  ↳ 点后无内容变化，可能是收起、无 UI 反应，或点击未生效，需结合 state/verify 复查。")
        else:
            print(f"  ↳ 点后内容减少（{delta} 字符），可能收起了面板或发生了跳转。")

    @require_page
    @catch_error("❌ wait 失败")
    def cmd_wait(self, args):
        """wait <选择器> [超时秒]：等元素出现（条件渲染），默认 10s。"""
        if not args:
            print("用法: wait <锚点名|选择器> [超时秒]")
            return
        raw = args[0]
        sel = _norm_selector(self._resolve_anchor(raw))
        timeout = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        print(f"⏳ 等待「{sel}」出现（超时 {timeout}s）...")
        self.page.locator(sel).first.wait_for(state="visible", timeout=timeout * 1000)
        total = self.page.locator(sel).count()
        print(f"✅ 「{sel}」已出现，命中 {total} 个")

    @require_page
    def cmd_click(self, args):
        """click/select：支持三种目标 —— 锚点名、CSS 选择器、文本。"""
        if not args:
            print("用法: click <锚点名|选择器|文本>")
            return

        raw = " ".join(args)
        # 优先：锚点名复用（如 click 比例）
        if args[0] in self.anchors:
            return self._click_selector(self.anchors[args[0]])
        # 其次：CSS 选择器（含 # . [ : > 等特征）
        looks_selector = any(c in raw for c in "#.[:>=\"'")
        if looks_selector:
            return self._click_selector(raw)
        return self._click_text(raw)

    def _click_selector(self, sel):
        """按 CSS 选择器做引擎式点击（wait visible + click force，取 .last 激活项）。"""
        try:
            sel = _norm_selector(sel)
            loc_all = self.page.locator(sel)
            total = loc_all.count()
            if total == 0:
                print(f"❌ 选择器「{sel}」命中 0")
                return
            target = loc_all.last
            target.wait_for(state="visible", timeout=8000)
            target.click(force=True)
            time.sleep(0.8)
            print(f"✅ 已按选择器点击「{sel}」（命中 {total} 个，点 .last）")
        except Exception as e:
            print(f"❌ 选择器点击失败: {str(e)[:80]}")

    def _click_text(self, kw):
        """按文本匹配点击（精确优先，模糊兜底）。"""
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
  ── 连接 / 导航 ──
  open                      连接 9222 浏览器
  page                      看当前页面 URL/标题
  nav <url|站点名>          导航到 URL 或站点(doubao/lovart/jimeng/flow)
  tabs                      列出所有标签页
  tab <序号>                切换到指定标签页
  ── 读取 / 抓取 ──
  buttons                   列出页面所有可见按钮（摸结构）
  find <文本>               搜含文本的元素 + 锚点链（找 data-testid）
  state <选择器>            查看某元素当前内容（验证是否生效）
  verify <选择器> [; 选择器...]  批量验证多个选择器命中情况（total/visible）
  html                      抓整页净化 DOM
  shot [路径]               截图当前页面
  frames                    列出页面所有 iframe
  frame <序号> <命令...>    在指定 iframe 内执行 find/state/verify/probe/click/buttons
  shadow <文本>             穿透 Shadow DOM / iframe 找元素并列出锚点链
  js <JS代码>               在页面执行任意 JS 并返回结果
  ── 交互操作 ──
  click <选择器|文本>       点选择器(引擎式)或含该文本的按钮
  select <选择器|文本>       同 click
  open-menu <选择器> [click|hover]   展开下拉菜单（默认 hover）
  probe <选择器> [first|last] [click|hover]  模拟引擎式点击并报告点后 DOM 变化
  wait <选择器> [超时秒]     等元素出现（条件渲染，默认 10s）
  type <文本> | type <选择器> <文本>  向输入框打字（拟人延迟）
  upload <选择器> <本地文件路径>      上传文件（file_chooser 拦截/set_input_files）
  clear [选择器]            清空输入框（Ctrl+A+Backspace）
  esc [键名]                按键，默认 Esc 关弹窗
  coord <x> <y>             盲点屏幕坐标（收起菜单/弹窗）
  waitimg <选择器> <张数> [超时秒]   等出图（SRC 差集轮询，默认300s）
  getimg <选择器> [保存目录]  下载命中的真图 URL 到本地
  ── 沉淀 / 流程 ──
  ui                        扫描当前页收集稳定锚点并存记忆表（跨会话复用）
  anchor <名称> <选择器>     手动添加/覆盖稳定锚点
  export-ui [文件名]        把页面 data-testid 聚合成引擎 UI 字典 JSON 落盘
  flow <站点名> <提示词> [--img 垫图] [--num 张数]  快速复现站点流程（仅探路辅助）
  help                      显示本帮助
  quit / exit               退出

提示：
  - 探到稳定锚点后用 ui/anchor 记住，下次启动自动加载复用（click/open-menu/state/probe/wait 直接按锚点名操作），不用重复探。
  - --run 脚本化时命令用 | 分隔；含空格文本可用双引号包裹（自动按引号分组）。
  - 复杂 JS / 引号场景建议用交互式（python tools/webctl.py）。
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
    @staticmethod
    def _split_args(line: str):
        """把命令行按空格分词，但尊重双引号/单引号分组（含空格的文本不会被打散）。"""
        parts = []
        buf = []
        quote = None
        for ch in line:
            if ch in "\"'":
                if quote == ch:
                    quote = None
                elif quote is None:
                    quote = ch
                else:
                    buf.append(ch)
            elif ch.isspace() and quote is None:
                if buf:
                    parts.append("".join(buf))
                    buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf))
        return parts

    def exec_line(self, line):
        """执行单条命令字符串（REPL 与 --run 共用）。"""
        if not (line := line.strip()):
            return
            
        parts = self._split_args(line)
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