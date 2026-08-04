# CLAUDE.md — AutoAI 多平台生图自动化控制中心

> 本文档是 AI 助手在本项目协作时的**最高行动准则**。所有操作必须遵守，尤其是"改代码前必须与用户确认"这条红线。

---

## 一、项目是什么

一个 **Python + Playwright + FastAPI** 的多平台 AI 绘画自动化控制中心。它通过 CDP 协议接管本机 Chrome，在真实浏览器里自动完成：新建项目 → 切换模式 → 配置参数 → 上传垫图 → 输入提示词 → 发送 → 收割图片 → 打标投递 Eagle 的完整流水线。

> 📌 **当前架构状态（2026-08 重构后）**：仅保留**白天模式**单一执行链路（`start_day_queue` → `_run_wrapper`）。**云端同步与夜间模式已彻底废除**，`config.json` 是唯一数据源。

### 核心目录
```
<项目根>/
├── core/          # 🧠 调度中枢（server/task_runner/ledger/image_processor）
├── plugins/       # ⚔️ 正式引擎（base + flow/jimeng/lovart/doubao）—— 核心战场
├── templates/     # 🖥️ 前端控制台（index.html，被 FastAPI 按目录引用，勿移）
├── tools/         # 🛠️ 辅助工具（DOM 抓取工具、engine_ide、旧版备份、标准化模版）
├── docs/          # 📄 经验文档（抓包经验总结、总结方法、怎么打包）
├── assets/        # 垫图资源（references/ 为参考垫图，前端图库读取）
├── Downloads/     # 产图输出
├── logs/          # 运行日志
├── config.json    # ☝️ 唯一数据源（global_settings 全局配置 + sites 引擎参数）
├── history.db     # 记账（防重复跑图）
├── main.py        # 入口
└── 启动控制台.bat / .ps1 / .command  # 启动脚本
```

### 启动链路
`main.py` → `core/server.py` (FastAPI, 127.0.0.1:8000) → `core/task_runner.py` (调度) → `plugins/*_engine.py` (浏览器)

### 引擎架构（重点）
- `plugins/base_engine.py`：**统帅底盘**，跨平台通用逻辑（CDP 连接、HIL 极简交互层 `_click`/`_fill`/`_hover`、通用下载器、WAF 逃逸、`_smart_upload` 垫图引擎、`_set_params_iteratively` 参数装填、`_security_check` 安检）
- `plugins/{flow,jimeng,lovart,doubao}_engine.py`：**平台专属适配器**，只写该平台的 DOM 选择器和专属交互流程
- 引擎的 `process_single(payload)` 是主流程入口，子类实现 `action_init_workspace` / `action_upload_image` / `action_fill_and_submit` / `action_wait_and_download` 四个钩子

### ☝️ 单一数据源（最高准则）
> **`config.json` 是唯一真相源**。所有全局运行参数（Chrome 路径/端口、代理、Clash、输出目录、图片黑名单、熔断参数）统一放 `global_settings` 段，引擎在 `base_engine.py` 的 `_load_global_config()` 装载为实例属性。**已彻底废除云端同步与夜间模式**，不要再引入任何"云端 Excel / 云控表覆盖本地参数"的逻辑。
- 优先级：`config.json > base_engine.py` 里的 `GLOBAL_*` 硬编码默认值（后者仅作缺省兜底，向后兼容）。
- 改全局配置 = 改 `config.json`，改完即生效；**不要**在代码里新写死全局常量。
- 站点引擎参数放 `sites.<site_name>` 段（当前为空对象，保留结构以便扩展）。

---

## 二、工作范围（你能碰什么）

### ✅ 可以直接做
- **改 CSS 选择器**：`UI` 字典里的定位器、`PARAM_FORMAT`/`PARAM_OPTION_SELECTORS` 映射、`PARAM_ROUTING` 路由
- **阅读/分析**代码、日志、DOM 情报
- **整理**非业务文件（移动 `tools/`、`docs/` 里的工具和文档）
- **修 bug**、性能调优、选择器失效排查
- **自主抓取 DOM 情报**：通过 CDP 连 9222 浏览器，只读方式读取页面 DOM、提取选择器、抓净化 HTML（**只允许读，不允许主动点击/提交/破坏用户页面状态**）

### ⛔ 红线：改代码必须确认
> **凡是涉及修改引擎业务逻辑代码的（不只是选择器），必须先向用户讲清楚"改什么、为什么改、怎么改"，等用户明确同意后再动手。**

这包括但不限于：
- `plugins/*_engine.py` 里的方法逻辑（重写 `_set_params_iteratively`、`_security_check`、`action_*` 钩子等）
- `base_engine.py` 里的通用底盘逻辑
- `core/`、`main.py` 的调度/服务代码
- **新增/删除文件**

### 例外（无需逐条确认）
- 仅替换 `UI` 字典里的**选择器字符串**（CSS 选择器是允许直接改的）
- 移动/删除 `tools/`、`docs/` 里明确无用的文件（用户已授权）

---

## 三、怎么"抓包"获取 DOM 情报（改选择器的前提）

网站前端经常改版导致选择器失效。**永远不要凭空编造选择器**！必须基于真实抓到的 DOM。

### 抓取方式一：AI 自主抓取（首选，推荐）

> 这是本项目的**首选方案**。AI 可以直接通过 CDP 连到正在运行的浏览器（9222 端口，带登录态），自主读取 DOM、找选择器，**无需用户手动操作浏览器**。

**原理**：本项目 Chrome 由 `启动控制台.bat` 用 `--remote-debugging-port=9222` 启动，天然暴露 CDP 接口。AI 用 Playwright 的 `connect_over_cdp("http://127.0.0.1:9222")` 接管，直接执行 JS 读取页面 DOM、提取选择器、抓净化 HTML。

**AI 自主抓包 SOP（写进 AI 的操作流程）：**

1. **连接现有浏览器**（复用，不新开，保持登录态）：
   ```python
   from playwright.sync_api import sync_playwright
   pw = sync_playwright().start()
   browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
   context = browser.contexts[0]
   # 找目标页（用 URL 认路，别用 pages[-1]）
   page = next((p for p in context.pages if "lovart.ai" in p.url), None)
   if page: page.bring_to_front()
   ```

2. **读取整页净化 DOM**（套用油猴 `purifyDOM` 的清洗逻辑）：
   ```python
   html = page.content()
   # 用正则/BeautifulSoup 剥离 script/style/svg 等，只留 data-testid/href/src 等关键属性
   ```

3. **精准提取单个元素**（读指定选择器结构）：
   ```python
   # 例：看模型下拉菜单里有哪些选项、它们的 testid
   nodes = page.locator('[role="menuitem"]').evaluate_all(
       "els => els.map(e => ({text: e.innerText, testid: e.getAttribute('data-testid')}))")
   ```

4. **穿透 Shadow DOM / iframe**（复杂 React 组件用 eval 递归遍历）：
   ```python
   # 递归穿透所有 shadowRoot / contentDocument，拿到带标签的结构
   page.evaluate("""() => {
     const out = [];
     const walk = (root) => {
       root.querySelectorAll('*').forEach(el => {
         if (el.shadowRoot) walk(el.shadowRoot);
         if (el.tagName === 'IFRAME') { try { walk(el.contentDocument); } catch(e){} }
       });
     };
     walk(document);
     return out;
   }""")
   ```

5. **把抓到的净化 HTML 与现有 `UI` 字典比对**，判断选择器是否失效、如何更新。

**首选工具 `tools/webctl.py`（通用浏览器交互控制台，推荐）**：
AI 进入 REPL 后像操作浏览器一样**一条条命令连续操作**，完成「认路→摸结构→找锚点→展开菜单→点击验证」完整闭环，**不用自己写 Playwright 代码**。
两种调用方式：
```bash
# ① 交互式（逐条命令，适合一步步探索）
python tools/webctl.py

# ② 脚本化一次性执行（适合 AI 脚本调用，用 | 分隔多条命令）
python tools/webctl.py --run "page|buttons|find 新建项目|state 按钮选择器|quit"
python tools/webctl.py --url https://www.lovart.ai/zh/home --run "page|find 图像|quit"
```
交互内命令（已内化常用操作，全命令见 `webctl.py` help）：
```
open                      连接 9222 已登录浏览器
page                      看当前页面 URL/标题
nav <url|站点名>          导航到 URL 或站点(doubao/lovart/jimeng/flow)
buttons                   列出页面所有可见按钮（摸结构）
find <文本>               搜含文本的元素 + 锚点链（找 data-testid）
open-menu <选择器> [click|hover]   展开下拉菜单（默认 hover）
click <文本>              点击含该文本的按钮（精确 innerText，避开 has-text 冒号坑）
state <选择器>            查看某元素内容（验证选择器是否生效）
verify <sel> [; sel...]   批量验证多个选择器命中情况（total/visible）
type <文本>|<选择器> <文本>  向输入框打字（拟人延迟）
upload <选择器> <路径>    上传文件（file_chooser 拦截/set_input_files）
flow <站点> <提示词> [--img 垫图] [--num 张数]  一键执行站点预设流程
esc [键名]                按键，默认 Esc 关弹窗
clear [选择器]            清空输入框
coord <x> <y>             盲点屏幕坐标（收起菜单/弹窗）
shot [路径]               截图当前页面
waitimg <选择器> <张数> [超时秒]   等出图（SRC 差集轮询）
html                      抓整页净化 DOM
help / quit
```
- 典型用法：`open` → `page` → `buttons` 看有哪些按钮 → `find "新建项目"` 找锚点 → `open-menu 触发器 click` 展开下拉 → `click "2K"` 试点 → `state 按钮选择器` 确认生效。
- **`find` 是找选择器神器**：返回元素及其父级链的 testid/class/id。**`state`/`verify` 是验证神器**：确认改的选择器真的能拿到元素。
- 默认**只读**；`click`/`open-menu`/`type`/`upload`/`flow` 只做轻量交互（不提交表单/不改值/不导航）。
- 前提：Chrome 已带 9222 启动（`启动控制台.bat` 会做）。若报 `ECONNREFUSED`，提示用户先启动项目。
- **排查经验**：
  - 找不到选择器时，先用 `state`/`verify` 逐个验证，别凭空改；命中 0 先确认前置条件（模式/登录/有字/是否要新建项目），见"通用经验：功能面板是条件渲染的"。
  - 用 `flow <站点>` 快速复现站点完整流程；用 `waitimg` 等出图、`shot` 截图看界面、`esc`/`coord` 破盾清弹窗。
  - `--run` 里命令用 `|` 分隔；`verify` 内多个选择器用 `;` 分隔（避免与 `|` 冲突）。

**单命令工具 `tools/dom_sniffer.py`（适合一次性单次抓取，不想进交互时）**：
核心逻辑与 webctl 相同，命令式：
```bash
python tools/dom_sniffer.py --find "Nano Banana"      # 搜文本+锚点链
python tools/dom_sniffer.py --selector '[data-testid="xxx"]'   # 提取元素结构
python tools/dom_sniffer.py --open '触发器' --open-action click --find "图像"   # 展开菜单后找
```

**辅助模块 `tools/win_utf8.py`（无需手动调用）**：
Windows 下让工具输出 UTF-8 中文不乱码。`webctl.py`/`dom_sniffer.py` 已自动集成，AI 无需单独调用。若在非 UTF-8 系统上中文乱码，是终端问题，不影响 AI 拿到的数据。

**什么时候用哪个（决策指引）**：
- 需要**连贯操作**（展开菜单→找→点→验证）→ 用 `webctl`（交互式或 `--run`）
- 只需**一次性抓某个选择器** → 用 `dom_sniffer --find/--selector`
- 两者都会自动处理中文乱码（集成 win_utf8）

**本项目已有的辅助脚本**：`tools/engine_ide.py`、`tools/工具/adapter_*.py` 里有现成的 CDP 连接、DOM 提取、`execute_action` 路由逻辑，AI 可参考或复用其模式。

---

### 抓取方式二：用户手动抓取（备用，需用户配合）

当 AI 无法自主连到浏览器（如浏览器未开 9222、或需要用户特定操作）时，用这套人工流程：

#### 抓取工具
- **`油猴清洗.js`**（`tools/第一步获取数据/`）：Tampermonkey 脚本，页面注入两个悬浮按钮
  - **🌐 全局提取**：抓整页净化 DOM
  - **🎯 局部狙击**：鼠标高亮目标元素，点击抓该元素的净化 HTML
- **`Cookie 极速提取器.txt`**：bookmarklet，一键复制网站 Cookie
- **`网页清洗.html`**：DOM 净化舱

#### 抓取流程
1. 装油猴脚本（刷新目标网页后右上角出现按钮）
2. 抓**整页** → 点"🌐 全局提取"；抓**单个元素/下拉菜单** → 点"🎯 局部狙击"后点目标
3. 自动下载 `情报_*.txt`（含净化 HTML + 给 AI 的系统提示词）
4. 用户把 txt 内容贴给 AI，AI 与现有选择器比对

### 目标元素清单（Lovart 为例，常抓这 5 大模块）
1. **新建项目按钮** → 主页卡片
2. **模式切换**（Agent/图像）→ 触发按钮 + 选项菜单
3. **参数面板**（比例/分辨率/模型）→ 触发按钮 + 下拉菜单选项
4. **垫图上传** → 上传按钮 + 上传菜单/input
5. **发送/收割** → 输入框 + 发送按钮 + 生成后的气泡/图片

### AI 找选择器：从 DOM 到稳定定位的决策链

拿到净化 HTML 后，按这个顺序判断用哪个锚点（也是给 AI 的执行规则）：

1. **先找 `data-testid`** —— 有就直接用（如 `[data-testid="agent-mode-switch-option-image"]`）。这是最稳的。
2. **没 testid**，找稳定的 `id` / 唯一 `class`（如 `#agent-image-generator-prompt`）。
3. **只有文字**：用 `:has-text("文案")` 模糊包含 + 判断是否唯一。**若文案会撞车**（短词、数字、含子串关系），必须配 testid 或属性。
4. **判断作用域**：
   - 目标是"点开面板的按钮"还是"面板里的选项"？路径要分清（先点触发器，再选选项）。
   - 元素在 Shadow DOM / iframe 里吗？在的话要用 eval 穿透取结构，或确认 Playwright 能否直接命中选择器。
5. **判断唯一性**：页面同 testid 有多个时（如多个气泡、多个按钮），想清楚用 `.first` 还是 `.last`。

**AI 自主抓包的自我检查**：
- 抓到的选择器**是从真实 DOM 里读出来的**，不是 AI 自己编的。
- 关键交互（模式切换、参数面板、上传、发送）都验证过元素存在且可见。
- 若某个元素抓不到，**不要瞎猜**——把抓到的净化 HTML 和相关上下文反馈给用户，请求补充情报。

---

### 选择器设计原则（来自实战文档）

**定位锚点选择（优先级从高到低）：**
1. **优先 `data-testid`**：工程师留的后门，最稳定（如 `data-testid="lovart-nav-create-project"`）
2. **次选稳定 `class` / `id`**：如 `#agent-image-generator-prompt`
3. **无稳定锚点时**：用**多重属性兜底组合**（多个属性同时命中，减少误配）
   - 例：`div[aria-haspopup="dialog"]:has-text("参考图")`（属性 + 文本双保险）
4. **最后才考虑 XPath**：且**永远不要用长路径 XPath**（`//html/body/div[2]/...`）——前端加个横幅/弹窗，DOM 平移就全崩

**文本匹配陷阱：**
- **慎用单字/短数字模糊匹配**：`has-text("0")` 会误点 "100%"（`100%` 里含 `0`）
- **文本匹配用 `:has-text()` 模糊包含**，别用 `exact=True`（会被空格/换行/span 拆分坑死）
- **短文本/数字尽量配 `data-testid` 或唯一 class**，别裸靠文本
- **子串冲突**：`has-text("Nano Banana 2")` 会误中 `Nano Banana 2 Lite`，要精确项就用唯一 testid 或加正则锚定

**可见性与多元素：**
- **响应式双套 DOM**：移动端按钮可能 `display:none` 藏在前面，`first` 会抓到隐身节点 → 加 **`:visible`** 过滤 CSS 隐藏的废弃节点
- **`.first` vs `.last`**：同 testid 有多个时想清楚取哪个（发送按钮通常 `.last` 是激活的那个；气泡取最新的用 `.last`）
- **`:has-text` + `:visible` 可叠加**：`button:has-text("参考图"):visible`
- **警惕 `.count()` 假象**：DOM 节点存在 ≠ 可见/可点，count 增加可能是骨架屏/占位符，**判图别靠数节点，靠 SRC 差集**
- **功能面板是条件渲染的**：切对模式/填了字/已登录才出现（见"通用经验：功能面板是条件渲染的"）。找不到先满足前置条件再验证。

**写进 `UI` 字典时的组合惯例：**
- 允许写**逗号分隔的多选择器兜底**：`[data-testid="xxx"], [data-testid="yyy"]`（一个失效另一个顶上）
- 允许 `:has-text()`、`:visible`、`:last` 等伪类混用

---

## 四、改代码的核心经验（从 docs 提取的实战铁律）

> 完整血泪史见 `docs/抓包经验总结.txt`。以下是最核心的、改任何引擎代码都必须遵守的铁律：

### 铁律 1：物理降维打击，别信标准 API
现代前端（React/Vue）用虚拟 DOM 和合成事件，`loc.fill()` 填完会被状态管理器清空。
- 输入框可能是 `div[contenteditable="true"]` 伪装的，不是 `<input>`
- **正确连招**：`click(force=True)` 夺取光标 → `Ctrl+A` 全选 → `Backspace` 删除 → `keyboard.type()`/`insert_text()` 硬敲
- 用 `try: loc.fill() except: 降级物理键盘`

### 铁律 2：UI 都是幻觉，遮挡必须强攻
- 透明 Placeholder 遮罩、悬浮参数面板、忘了收起的下拉菜单会挡住目标
- `state="attached"`（只要在源码里就抓）比 `state="visible"`（被遮挡 1px 就超时）更抗遮挡；但若 `visible` + `click(force=True)` 在当前引擎实测稳定，**不必强行改成 attached**——以实测稳定为准，两种都可用。
- 关键防御手段是 `click(force=True)` 无视遮挡，以及点击前先定位到目标本身
- **点完展开面板后，养成习惯敲 `Escape` + 屏幕角落 `mouse.click(10, 10)` 盲点一枪**，物理破盾

### 铁律 3：状态感知，不要线性流水线
网页有记忆（Cookie/LocalStorage），上次停在某模式，这次别死脑筋去切。
- **操作前先 `is_visible()` 嗅探**：门开着就跨过去，没开再动手
- 非关键 UI 过渡动作套 `try...except: pass`，别让一个小按钮崩掉整个链路

### 通用经验：功能面板是条件渲染的（Mode-First）
很多面板/按钮不是一开始就在，要先满足前置条件才渲染/激活：
- **先切模式，才有参数面板**：豆包/即梦/Lovart 等必须先选"图像生成"进入对应工作台，比例/模型/上传/出图才出现。未切模式或未登录时这些全为 0，别误判选择器失效。
- **发送按钮随输入渲染**：输入框为空时不渲染/禁用发送按钮，填字后才出现。
- **未登录锁工作台**：很多面板要登录态才渲染，未登录只弹"登录以解锁"。
- **有的站要先"新建项目"**：Lovart 等从主页点"新建项目"进工作台后，参数面板/上传才可用。
- **别一口气猛点，操作间停 1s 左右**：前端 React 渲染/水合有延迟，上一步刚点完，下一步元素还没就位。每个动作后 `time.sleep(1)` 左右，网站反应没那么快。

**落地**：流程顺序先 `_switch_work_mode` 切模式 → 再填参数 → 后 `keyboard.type(prompt)` → 再 `_click(submit_btn)`；涉及"新建项目"的站点先点新建。**排查找不到时先确认模式/登录/有字/是否要新建项目，别急着改选择器。**

### 铁律 4：出图用"SRC 集合差集"，别数 DOM 节点
- 现代框架先渲染 Base64 骨架屏占位，`locator.count()` 增加可能是假图
- **正确做法**：初始提取所有真实 `http` URL 存 `Set A`；出图后提取存 `Set B`；`Set B - Set A` 剩下的才是真图
- 配合黑名单正则过滤（项目实现在 `base_engine.py` 的 `_extract_valid_image_url`，正则可在 `config.json → global_settings.image_blacklist` 调）：`(base64|blob:|loading|placeholder|spinner|/user/|/upload/|/reference/|/source/|/input/)`，只认 `/generator/` 等真图路径

### 铁律 5：幽灵标签页，追踪导弹式接管
- CDP 接管时 `context.pages[-1]` 可能拿到扩展隐藏页/空白页
- **遍历所有标签页，用 `url` 认路**，找到目标后必须 `page.bring_to_front()`

### 铁律 6：网络空闲是谎言
- 商业站挂满埋点/心跳脚本，`networkidle` 永远等不到
- **只等 `domcontentloaded` 或 `commit`**，盯 UI：下一步要操作的元素 visible 就直接强攻

### 铁律 7：React 水合延迟
- 按钮空壳已渲染但 onClick 还没绑定时，点上去没反应
- **核心路由跳转后，物理硬等 1~2 秒**（`wait_for_timeout(2000)`），让 JS 事件挂载完再点

### 铁律 8：上传垫图用 `file_chooser` 拦截
- 现代前端（Ant Design 等）出于安全，不会把真实 `input[type="file"]` 写死在页面里，只有真实点击上传按钮才动态生成；直接 `set_input_files` 底层传文件会被丢弃
- **正确做法**：模拟真人点 UI 上传按钮，同时用 Playwright 黑科技 `with page.expect_file_chooser() as fc:`，在系统文件选择框弹出的半空拦截，再 `fc.value.set_files(本地路径)` 硬塞
- 若是原生隐藏 `input`（如即梦），可尝试直接 `set_input_files`，失败再降级到 file_chooser

---

## 五、核心心法：稳，就是快（Slow is Fast）

> **这是本项目的最高原则，所有代码改动都必须围绕它。**

在网站发提示词/执行自动化时：
- **宁可慢，不可错**。一次稳健的成功，远胜十次快速但失败的尝试。
- **不要激进提速**。拟人延迟、缓冲等待是必要的——它们让行为像真人，防封号、防 WAF。**"快"不等于减少等待，而是减少返工。**
- 网站自动化 80% 的时间是在和前端框架、异步渲染、遮挡层、状态残留斗智斗勇。**每一步都走稳，整体才最快。**
- 改代码时，不要为了"看着快"而删掉必要的 `time.sleep` / 随机延迟 / `_human_pause`。这些是防封和稳定的护身符。
- 遇到选择器失效 → 先抓 DOM 情报，确认了再改，**不要瞎猜、不要拍脑袋**。

### 与用户协作的节奏
1. 收到任务 → 先分析，说清楚你的理解和方案
2. **要改代码 → 先讲清楚改哪、怎么改 → 等用户确认**
3. 能靠改 CSS 选择器解决的，不动代码逻辑
4. 改完 → 检查 lint → 让用户测试 → 根据结果迭代

---

## 六、启动与测试

```bash
# Windows
启动控制台.bat

# macOS
./启动控制台.command        # 或直接
python3 main.py

# 或直接（通用）
python3 main.py
```
- **必须用 `python3`，不要用 `python`**：系统默认 `python` 可能是 Python 2.7，会导致类型注解/TypedDict 编译失败。
- 控制台：http://127.0.0.1:8000
- 日志实时推送到前端终端，也落在 `logs/sys_logs.log`
- 测试出问题时，把**报错日志**和**DOM 情报**一起贴给 AI，不要只贴报错
- 若在 Mac 上运行：Chrome 路径、调试端口等由 `config.json → global_settings.chrome` 控制（默认 `debug_port: 9222`）。

---

## 七、快速自查清单（改引擎代码前过一遍）
- [ ] 选择器是基于真实抓取的 DOM 吗？还是我编的？
- [ ] 要改的是**代码逻辑**还是**选择器**？代码逻辑必须确认。
- [ ] 全局参数有没有写死？**应放 `config.json → global_settings`，由 `_load_global_config()` 读**。
- [ ] 有没有引入云端同步/夜间模式？**这两者已彻底废除，不要再加回来**。
- [ ] 输入框处理用了物理键盘降级吗？
- [ ] 展开面板后记得 Esc + 盲点破盾吗？
- [ ] 出图判定用了 SRC 差集 + 黑名单过滤吗？
- [ ] 标签页用 URL 认路 + bring_to_front 了吗？
- [ ] 上传垫图用 `expect_file_chooser` 拦截了吗（还是裸 `set_input_files`）？
- [ ] 会不会因为删掉等待导致"变快但变脆"？
