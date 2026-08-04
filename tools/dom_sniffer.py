#!/usr/bin/env python3
"""
🛸 DOM Sniffer — AI 自主抓取 DOM 选择器工具

作用：AI 通过 CDP 连到正在运行的 Chrome (9222)，只读抓取页面 DOM，
     提取稳定选择器锚点，供 AI 判断现有 UI 选择器是否失效、如何更新。

用法（在 G:\AutoAI_01 下，用 venv 的 python 跑）：
    python tools/dom_sniffer.py                     # 抓当前 lovart 页整页净化 DOM
    python tools/dom_sniffer.py --url lovart.ai     # 抓指定站点匹配页
    python tools/dom_sniffer.py --selector [data-testid="xxx"]   # 提取指定元素结构
    python tools/dom_sniffer.py --find "Nano Banana"            # 搜索含该文本的元素及锚点
    python tools/dom_sniffer.py --find "参考图" --depth 3       # 向上取父级深度
    # —— 展开下拉菜单后再抓（hover/click 弹出的菜单）——
    python tools/dom_sniffer.py --open '[data-testid="param-btn"]' --find "2K"
    python tools/dom_sniffer.py --open '.menu-trigger' --open-action click --find "Nano Banana"

⚠️ 安全：默认【只读】。--open 仅做【展开菜单】的轻量交互（hover/click 触发器），
   绝不提交/改值/导航/下载。展开后菜单选项的抓取仍是只读的。
"""
import argparse
import re
import sys
import json
import io

# 强制 UTF-8 输出（避免 Windows 控制台中文乱码）
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright


CDP_URL = "http://127.0.0.1:9222"

# 清洗：剥离视觉/逻辑垃圾标签
DROP_TAGS = {"meta", "link", "noscript", "canvas", "video", "audio", "iframe", "script", "style"}
# 保留的关键属性（找选择器锚点用）
KEEP_ATTRS = ["id", "class", "data-testid", "href", "src", "type", "name", "placeholder", "role", "aria-label"]

# Tailwind 样式类（净化时剔除，避免污染 class）
_TW = r"\b(sm:|md:|lg:|xl:|2xl:|hover:|focus:|active:|group-[a-z]+:)?(flex|grid|hidden|block|inline|absolute|relative|fixed|inset-\S+|w-\S+|h-\S+|m[trblxy]?-\S+|p[trblxy]?-\S+|bg-\S+|text-\S+|border\S*|rounded\S*|shadow\S*|opacity-\S+|z-\S+|gap-\S+|items-\S+|justify-\S+|leading-\S+|font-\S+|tracking-\S+|transition\S*|transform\S*|cursor-\S+|overflow-\S+)\b"
TW_RE = re.compile(_TW)


def _find_page(browser):
    """用 URL 认路找目标页（追踪导弹：不信任 pages[-1]）。"""
    ctx = browser.contexts[0]
    pages = ctx.pages
    if not pages:
        return None
    for p in pages:
        if p.url and "http" in p.url and "chrome://" not in p.url and "about:" not in p.url:
            return p
    return pages[0]


def purify_dom(raw_html):
    """纯前端清洗逻辑的 Python 版：剥离垃圾标签，保留选择器关键属性。"""
    # 简易实现：用正则剥掉 script/style
    html = re.sub(r"<(script|style|noscript|meta|link)[^>]*>.*?</\1>", "", raw_html, flags=re.S | re.I)
    html = re.sub(r"<(script|style|noscript|meta|link)[^>]*>", "", html, flags=re.I)
    # 压缩空白
    html = re.sub(r">\s+<", "><", html)
    html = re.sub(r"\s{2,}", " ", html)
    return html[:20000]  # 截断防爆


def get_purified_page(page):
    """整页净化 DOM。"""
    html = page.content()
    return purify_dom(html)


def get_element_snapshot(page, selector):
    """提取指定 selector 命中的元素结构（含关键属性）。"""
    script = """
    (sel) => {
      const els = document.querySelectorAll(sel);
      return Array.from(els).slice(0, 20).map(el => {
        const obj = {};
        for (const a of el.attributes) {
          if (["id","data-testid","href","src","type","name","placeholder","role","aria-label","data-state","aria-haspopup"].includes(a.name)) {
            obj[a.name] = a.value;
          }
        }
        if (el.className && typeof el.className === "string") obj.class = el.className;
        const txt = (el.innerText || "").trim().slice(0, 50);
        if (txt) obj.text = txt;
        obj.tag = el.tagName.toLowerCase();
        return obj;
      });
    }
    """
    return page.evaluate(script, selector)


def find_text_anchors(page, keyword, depth):
    """在页面里找含指定文本的元素，向上取父级，收集稳定锚点。"""
    script = """
    (args) => {
      const kw = args.kw, depth = args.depth;
      const results = [];
      // 只搜叶子/短文本节点，避免父容器长文本噪音
      const nodes = document.querySelectorAll('button,a,span,div,li,[role="menuitem"],[role="tab"],[data-testid]');
      nodes.forEach(el => {
        const t = (el.innerText || "").trim();
        // 必须是精准短文本（≤25字符）且含关键词；过滤掉超长父容器
        if (t && t.length <= 25 && t.includes(kw)) {
          const chain = [];
          let cur = el;
          for (let i = 0; i <= depth && cur; i++) {
            const cls = (typeof cur.className === "string" ? cur.className : "")
              .split(" ")
              .filter(c => c && !/^(w-|h-|m[trblxy]?-|p[trblxy]?-|bg-|text-|border|rounded|shadow|opacity-|z-|gap-|flex|grid|absolute|relative|fixed|inline|block|hidden|items-|justify-|leading-|font-|tracking-|transition|transform|cursor-|overflow-|duration-|ease-|min-|max-|size-|nowrap|whitespace|break-|outline-|select-|list-|grid-|col-|row-)/.test(c))
              .join(" ").slice(0, 80);
            chain.push({
              tag: cur.tagName.toLowerCase(),
              testid: cur.getAttribute("data-testid") || "",
              cls: cls,
              text: (cur.innerText || "").trim().slice(0, 30),
              id: cur.id || ""
            });
            cur = cur.parentElement;
          }
          results.push(chain);
        }
      });
      return results.slice(0, 12);
    }
    """
    return page.evaluate(script, {"kw": keyword, "depth": depth})


def open_menu(page, selector, action):
    """展开下拉菜单：hover 或 click 触发器，等菜单渲染。只做展开，不提交不改值。"""
    loc = page.locator(selector).last
    loc.scroll_into_view_if_needed(timeout=5000)
    if action == "click":
        loc.click(timeout=8000, force=True)
    else:  # 默认 hover（Radix 等组件 hover 弹菜单）
        loc.hover(timeout=8000, force=True)
    # 物理等菜单动画渲染（React 挂载）
    page.wait_for_timeout(1200)


def main():
    ap = argparse.ArgumentParser(description="DOM Sniffer — AI 自主抓取选择器")
    ap.add_argument("--url", default="lovart.ai", help="目标站点关键词（用于认路找页）")
    ap.add_argument("--selector", help="提取指定 CSS 选择器命中的元素")
    ap.add_argument("--find", help="在页面搜索含该文本的元素")
    ap.add_argument("--depth", type=int, default=2, help="find 模式向上取父级深度")
    ap.add_argument("--open", help="先展开这个触发器（hover/click）弹出下拉菜单，再抓选项")
    ap.add_argument("--open-action", choices=["hover", "click"], default="hover",
                    help="展开方式，默认 hover（有些网站是 click 才弹菜单）")
    args = ap.parse_args()

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        page = _find_page(browser)
        if not page:
            print("❌ 未找到可用页面，请确认 Chrome 已带 9222 启动。")
            return 1

        print(f"📍 认路页面: {page.url}")

        # 可选：先展开下拉菜单，再抓取（hover/click 弹出的菜单）
        if args.open:
            try:
                open_menu(page, args.open, args.open_action)
                print(f"✅ 已展开触发器 [{args.open}] ({args.open_action})，等待菜单渲染...")
            except Exception as e:
                print(f"⚠️ 展开菜单失败（可能不是 hover/click 触发，或选择器不对）: {e}")
                print("   提示：可换 --open-action click，或用 --find 确认触发器选择器。")

        if args.selector:
            snaps = get_element_snapshot(page, args.selector)
            print("\n=== 元素快照 ===")
            print(json.dumps(snaps, ensure_ascii=False, indent=2))
        elif args.find:
            res = find_text_anchors(page, args.find, args.depth)
            print(f"\n=== 搜索「{args.find}」的锚点链 ===")
            if not res:
                print("未找到。提示：菜单可能没展开，或用 --open 先弹出下拉菜单。")
            for i, chain in enumerate(res):
                print(f"\n--- 命中 {i+1} ---")
                print(json.dumps(chain, ensure_ascii=False, indent=2))
        else:
            html = get_purified_page(page)
            print("\n=== 整页净化 DOM (前 20000 字符) ===")
            print(html)

        print("\n✅ 抓取完成。请将此输出与现有 UI 选择器比对。")
        return 0
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        print("提示：请确认 Chrome 已用 --remote-debugging-port=9222 启动（启动控制台.bat 会这样做）。")
        return 1
    finally:
        try:
            pw.stop()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
