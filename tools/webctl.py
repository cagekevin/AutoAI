#!/usr/bin/env python3
"""
🖥️ webctl — 通用浏览器交互控制台（REPL）

用途：AI 或人通过它连到正在运行的 Chrome (9222)，像操作浏览器一样
     一条条输入命令，完成「认路 → 摸结构 → 找锚点 → 展开菜单 → 点击验证」的完整闭环。
     通用无站点依赖，对接任何网站都能用，不用重复写 Playwright 代码。

用法：python tools/webctl.py
     进入交互后输入命令，输入 help 查看所有命令，quit 退出。

安全：默认只读；click/select/open-menu 只做点击/展开的轻量交互（不提交表单、不导航、不改数据）。
"""
import os
import re
import sys
import time
import argparse
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


def _clean_cls(cls):
    if not cls:
        return ""
    return " ".join(c for c in cls.split() if c and not _SKIP_CLS.match(c))[:80]


class WebCtl:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.page = None

    # ---------- 基础 ----------
    def open(self, args=None):
        if not self.pw:
            self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(CDP_URL)
        self._pick_page()
        print(f"✅ 已连接 9222 浏览器，当前页面: {self.page.url}")
        return True

    def _pick_page(self):
        """追踪导弹：用 URL 认路，不信任 pages[-1]"""
        ctx = self.browser.contexts[0]
        for p in ctx.pages:
            if p.url and p.url.startswith("http") and "chrome://" not in p.url and "about:" not in p.url:
                self.page = p
                return
        self.page = ctx.pages[0] if ctx.pages else None

    def _need_page(self):
        if not self.page:
            print("⚠️ 尚未连接，先输入 open")
            return False
        return True

    # ---------- 看 ----------
    def cmd_page(self, args):
        if not self._need_page():
            return
        print(f"📍 页面: {self.page.url}")
        print(f"  标题: {self.page.title()}")

    def cmd_buttons(self, args):
        """列出页面所有可见按钮文本（摸结构用）"""
        if not self._need_page():
            return
        btns = self.page.locator("button:visible").all()
        seen = []
        for b in btns:
            t = (b.inner_text() or "").strip()
            if t and t not in seen:
                seen.append(t)
        print(f"共 {len(btns)} 个可见按钮，去重后 {len(seen)} 个:")
        for t in seen:
            print(f"  · {t!r}")

    def cmd_find(self, args):
        """搜索含文本的元素 + 父级锚点链"""
        if not self._need_page() or not args:
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
                cls = _clean_cls(n["cls"])
                print(f"  <{n['tag']}> testid={n['testid']!r} id={n['id']!r} cls={cls!r} text={n['text']!r}")

    def cmd_state(self, args):
        """查看某选择器命中的元素当前内容（验证是否生效）"""
        if not self._need_page() or not args:
            print("用法: state <选择器>")
            return
        sel = " ".join(args)
        try:
            loc = self.page.locator(sel)
            n = loc.count()
            if n == 0:
                print(f"「{sel}」命中 0 个")
                return
            for i in range(min(n, 3)):
                el = loc.nth(i)
                info = el.evaluate(
                    "e => ({tag:e.tagName, text:(e.innerText||'').trim().slice(0,40), "
                    "testid:e.getAttribute('data-testid')||'', vis:!!(e.offsetWidth||e.offsetHeight)})"
                )
                print(f"  [{i}] {info}")
        except Exception as e:
            print(f"❌ {str(e)[:100]}")

    def cmd_html(self, args):
        """抓整页净化 DOM（剥掉 script/style）"""
        if not self._need_page():
            return
        html = self.page.content()
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
        html = re.sub(r">\s+<", "><", html)
        print(html[:8000])

    # ---------- 做 ----------
    def cmd_open_menu(self, args):
        """展开下拉菜单：open-menu <选择器> [click|hover]"""
        if not self._need_page() or not args:
            print("用法: open-menu <选择器> [click|hover]")
            return
        action = "hover"
        if len(args) > 1 and args[-1] in ("click", "hover"):
            action = args[-1]
            sel = " ".join(args[:-1])
        else:
            sel = " ".join(args)
        try:
            loc = self.page.locator(sel).last
            loc.scroll_into_view_if_needed(timeout=5000)
            if action == "click":
                loc.click(timeout=8000, force=True)
            else:
                loc.hover(timeout=8000, force=True)
            time.sleep(1.2)
            print(f"✅ 已用 {action} 展开「{sel}」")
        except Exception as e:
            print(f"⚠️ 展开失败: {str(e)[:100]}")

    def cmd_click(self, args):
        """点击含文本的按钮（智能定位：按精确 innerText，避开 has-text 冒号坑）"""
        if not self._need_page() or not args:
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
        """精确文本定位并点击（用于 2K/9:16 这类短文本，用 evaluate 精确匹配）"""
        return self.cmd_click(args)

    # ---------- 控制 ----------
    def cmd_help(self, args):
        print("""
命令用法（通用浏览器控制台）:
  open                      连接 9222 浏览器
  page                      看当前页面 URL/标题
  buttons                   列出页面所有可见按钮（摸结构）
  find <文本>               搜含文本的元素 + 锚点链（找 data-testid）
  open-menu <选择器> [click|hover]   展开下拉菜单（默认 hover）
  click <文本>              点击含该文本的按钮（精确匹配）
  select <文本>             同 click，精确文本点击
  state <选择器>            查看某元素当前内容（验证是否生效）
  html                      抓整页净化 DOM
  help                      显示本帮助
  quit / exit               退出
""")

    def cmd_quit(self, args):
        self.close()
        print("再见。")
        sys.exit(0)

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass
        self.page = self.browser = self.pw = None

    # ---------- 命令路由 ----------
    CMD = {
        "open": "open", "page": "cmd_page", "buttons": "cmd_buttons",
        "find": "cmd_find", "state": "cmd_state", "html": "cmd_html",
        "open-menu": "cmd_open_menu", "click": "cmd_click", "select": "cmd_select",
        "help": "cmd_help", "quit": "cmd_quit", "exit": "cmd_quit",
    }

    def run(self):
        self.cmd_help([])
        while True:
            try:
                raw = input("\nwebctl> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.close()
                print("\n再见。")
                break
            if not raw:
                continue
            parts = raw.split()
            cmd, args = parts[0].lower(), parts[1:]
            mname = self.CMD.get(cmd)
            if not mname:
                print(f"未知命令: {cmd}（输入 help 查看）")
                continue
            fn = getattr(self, mname)
            try:
                fn(args)
            except Exception as e:
                print(f"❌ 命令执行异常: {str(e)[:120]}")


def main():
    ap = argparse.ArgumentParser(description="通用浏览器交互控制台")
    ap.add_argument("--url", help="连上后自动导航到该 URL（可选）")
    ap.add_argument("--run", help="一次性执行命令序列，用 | 分隔，如 --run \"page|buttons|quit\"")
    args = ap.parse_args()

    ctl = WebCtl()
    try:
        ctl.open()
        if args.url:
            ctl.page.goto(args.url, timeout=60000)
            time.sleep(2)
            print(f"已导航到: {ctl.page.url}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("提示：请先用 启动控制台.bat 启动项目（Chrome 带 9222）。")
        return 1

    if args.run:
        # 非交互：一次性执行命令序列
        for line in args.run.split("|"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            mname = ctl.CMD.get(parts[0].lower())
            if not mname:
                print(f"未知命令: {parts[0]}")
                continue
            try:
                getattr(ctl, mname)(parts[1:])
            except Exception as e:
                print(f"❌ {parts[0]} 执行异常: {str(e)[:120]}")
        ctl.close()
        return 0

    ctl.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
