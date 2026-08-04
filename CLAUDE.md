# CLAUDE.md — AutoAI 多平台生图自动化控制中心

> 本文档是 AI 助手在本项目协作时的**最高行动准则**，核心两条：**AI 负责把引擎选择器写好，让人能自己挂机；改代码逻辑前必须与用户确认**。

---

## 一、项目是什么

Python + Playwright + FastAPI 的多平台 AI 绘画自动化控制中心，通过 CDP 接管本机 Chrome，自动跑完整流水线：新建项目 → 切模式 → 配参 → 传垫图 → 输词 → 发送 → 收割 → 打标投递 Eagle。

- **架构（2026-08 后）**：仅白天模式单一链路（`start_day_queue` → `_run_wrapper`）。云端同步/夜间模式已彻底废除。
- **链路**：`main.py` → `core/server.py`(8000) → `core/task_runner.py` → `plugins/*_engine.py`。
- **引擎架构**：`base_engine.py` 是统帅底盘（CDP、HIL 交互层 `_click`/`_fill`/`_hover`、下载器、WAF 逃逸、`_smart_upload`、`_set_params_iteratively`、`_security_check`）；`plugins/{flow,jimeng,lovart,doubao}_engine.py` 只写 DOM 选择器和专属流程。入口 `process_single(payload)`，子类实现 `action_init_workspace`/`action_upload_image`/`action_fill_and_submit`/`action_wait_and_download` 四钩子。
- **单一数据源（最高准则）**：所有全局参数（Chrome 路径/端口、代理、Clash、输出目录、黑名单、熔断）统一放 `config.json → global_settings`，引擎在 `base_engine.py` 的 `_load_global_config()` 装载，优先级 `config.json > GLOBAL_*` 硬编码兜底。**改全局配置就改 config.json，别在代码里写死常量。**

核心目录：`core/` 调度中枢、`plugins/` 引擎（核心战场）、`templates/` 前端、`tools/` 辅助工具、`docs/` 经验文档、`assets/` 垫图、`Downloads/` 产出、`logs/` 日志、`config.json` 唯一数据源、`history.db` 记账。

---

## 二、项目目标与 AI 角色定位（最重要）

> **最终形态 = 批量重复挂机产图**：引擎一键跑通某平台流水线，调度器批量投喂任务，浏览器日夜挂机收割。
> **AI 不是产图机器，是探路者**：核心交付物不是"让 webctl 一键出图"，而是**把平台的 DOM 探清楚、每个交互验证成稳定选择器、写进引擎 `UI` 字典和 `action_*` 钩子**，让引擎能稳定重复执行。挂机是引擎的事，探路和落选择器是 AI 的事。

### 2.1 AI 的职责
- **探路**：用 `tools/webctl.py` 连 9222 浏览器，走通"认路→摸结构→找锚点→展开菜单→点击验证"闭环。
- **落选择器**：把验证过的选择器写回引擎 `UI` 字典、`PARAM_OPTION_SELECTORS`、`PARAM_ROUTING`、`action_*` 钩子。
- **巡检**：引擎失效时（改版/条件渲染变化）重新探路、更新选择器。
- **不做的**：不追求一键产图（`flow` 仅探路辅助）；不每次手动点；不凭空编选择器。

### 2.2 探路 ↔ 引擎 UI 字典对应（心智模型）
探路产出的每个选择器，都要落到引擎消费它的 key（`base_engine.py` 通过 `self.UI["xxx"]` 读）：
- **模式切换**：`mode_btn`、`mode_option`
- **参数面板**：`param_panel_trigger`、`PARAM_OPTION_SELECTORS`、`PARAM_ROUTING`、`defocus_area`
- **垫图**：`upload_input`/`upload_btn`/`local_upload_option`/`close_preview_btn`
- **输入/安检**：`input_box`（`_security_check` 靠它判登录态）
- **新建项目**：`new_proj_btn` + `URL`/`URL_HOME`/`URL_CANVAS`
- **弹窗清理**：`popups`；四个 `action_*` 钩子里的具体选择器

> 探路时就要想：这选择器对应引擎哪个 key？在引擎 HIL 下（`_click` = `wait_for(visible)` + `click(force=True)`，取 `.first`/`.last`）会不会失效？**要经得起引擎式点击，而不是只在 webctl 里看着命中。**

### 2.3 探路产出清单
- [ ] `UI` 字典各 key 选择器都基于真实 DOM
- [ ] 关键交互选择器在引擎式点击下验证过（`.first`/`.last`、可见性、遮挡）
- [ ] 四个 `action_*` 流程走通、每步有验证
- [ ] `URL` 系列认路正确（含 iframe/新标签页）
- [ ] 条件渲染元素的前置条件探明白（切模式/登录/填字/新建）

---

## 三、工作范围与红线

### ✅ 可直接做
- **改 CSS 选择器**（`UI` 字典、`PARAM_FORMAT`/`PARAM_OPTION_SELECTORS`/`PARAM_ROUTING` 映射）
- **自主探路（抓 DOM + 点击验证）**：允许轻量点击（点开面板/展开菜单/试点按钮）确认选择器可用；**禁止破坏性操作**（不真提交发消息、不删改数据、不批量操作、不随意导航）。验证完还原界面状态（Esc/盲点收起）。
- 读代码/日志/DOM、整理 `tools/`/`docs/` 无用文件、修 bug、性能调优、选择器失效排查。

### ⛔ 红线：改代码必须确认
> 改引擎业务逻辑代码（不只是选择器），必须先讲清"改什么、为什么改、怎么改"，**等用户同意再动手**。包括：`plugins/*_engine.py` 方法逻辑（`_set_params_iteratively`/`_security_check`/`action_*`）、`base_engine.py` 底盘、`core/`/`main.py`、新增/删除文件。

> 🧠 **为什么守这条红线：AI 缺网页操作常识。** 教训：AI 探路时"参数选择器没抓到"就喊"网站改版要改代码"，其实**只是没点开参数按钮、下拉菜单没展开**，选择器根本没坏。**AI 分不清"元素没出现（条件渲染）"和"元素真没了（改版）"**，放任瞎改会把引擎改崩。用户有网页常识，能一眼看出"这是没点开面板，不是改版"。

### ⚠️ 排查纪律：选择器命中 0，先怀疑前置条件
**永远先怀疑前置条件，别急着改选择器：**
1. 切对模式了吗？（未切"图像生成"，参数面板/上传/出图都不存在）
2. 点开面板了吗？（参数选项在下拉菜单里，没展开当然命中 0）
3. 登录了吗？（未登录锁工作台，面板不渲染）
4. 填字了吗？（发送按钮随输入渲染）
5. 要先"新建项目"吗？（Lovart 等要先进工作台）
6. 是 iframe/Shadow DOM 里的元素吗？（要穿透才能命中）

**排除所有前置条件后**才能怀疑改版。判断"改版要改选择器"必须**给证据链**（真实 DOM + 失效依据）反馈用户，**等确认再改**。能靠补前置交互解决的别改选择器，更别改逻辑。

### 例外（无需逐条确认）
- 仅替换 `UI` 字典选择器字符串（但先走完排查纪律，确认确实要改）
- 移动/删除 `tools/`、`docs/` 里明确无用的文件

---

## 四、AI 怎么探路

> 探路 = **抓 DOM（摸结构）+ 点击验证（确认引擎下能用）**。只抓不点，验证不了交互；只点不抓，就是瞎点。**永远不要凭空编选择器**，必须基于真实 DOM 且关键交互实测点击验证。

### 方式一：AI 自主探路（首选）
Chrome 由启动脚本带 `--remote-debugging-port=9222` 启动，AI 用 Playwright `connect_over_cdp` 直接接管（复用登录态），无需用户操作。

**SOP：**
1. **连接现有浏览器**（用 URL 认路，别用 `pages[-1]`）：
   ```python
   from playwright.sync_api import sync_playwright
   pw = sync_playwright().start()
   browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
   context = browser.contexts[0]
   page = next((p for p in context.pages if "目标站" in p.url), None)
   if page: page.bring_to_front()
   ```
2. **抓净化 DOM**：`html = page.content()`，剥掉 script/style/svg，只留 data-testid/href/src 关键属性。
3. **精准提元素**：`page.locator('[role="menuitem"]').evaluate_all("els => els.map(e => ({text:e.innerText, testid:e.getAttribute('data-testid')}))")`
4. **穿透 Shadow DOM/iframe**（复杂 React 用 eval 递归遍历 shadowRoot/contentDocument）。
5. **点击验证（关键）**：用 webctl 的 `click`/`open-menu`/`type` 对锚点做轻量交互，确认在引擎式点击下真能命中、展开；验证完 Esc/盲点还原。
6. **比对 `UI` 字典**：确认选择器对应引擎哪个 key（见 2.2）。

**首选工具 `tools/webctl.py`（通用浏览器控制台）**：像操作浏览器一样一条条命令操作，走完探路闭环，不用写 Playwright 代码。
```bash
python tools/webctl.py                                   # 交互式
python tools/webctl.py --run "page|buttons|find 新建项目|quit"   # 脚本化，命令用 | 分隔
```
常用命令：`open`/`page`/`nav`/`buttons`/`find <文本>`（找锚点链）/`open-menu <sel> [click|hover]`/`click <文本>`/`state <sel>`/`verify <sel>[;sel...]`/`type`/`upload`/`esc`/`clear`/`coord`/`shot`/`waitimg <sel> <张数>`/`html`/`flow <站> <词> [--img][--num]`/`help`/`quit`。
- `find` 是找锚点神器（返回 testid/class/id 父级链）；`state`/`verify` 是验证神器。
- 默认读为主 + 轻量交互验证；`--run` 用 `|` 分隔，`verify` 内用 `;` 分隔。

**单命令工具 `tools/dom_sniffer.py`**（一次性抓取）：
```bash
python tools/dom_sniffer.py --find "Nano Banana"
python tools/dom_sniffer.py --selector '[data-testid="xxx"]'
python tools/dom_sniffer.py --open '触发器' --open-action click --find "图像"
```
- 连贯操作用 webctl；只抓单个选择器用 dom_sniffer。两者都集成 `win_utf8` 处理中文乱码。

### 方式二：用户协助提供 DOM（备用）
AI 无法连浏览器时，用户装 `油猴清洗.js`（`tools/第一步获取数据/`）抓整页/局部净化 DOM，或用 `Cookie 极速提取器.txt`、`网页清洗.html`，下载 `情报_*.txt` 贴给 AI 比对。

### 目标元素清单（Lovart 为例，常抓 5 大模块）
新建项目按钮 → 模式切换（Agent/图像）→ 参数面板（比例/分辨率/模型）→ 垫图上传 → 发送/收割（输入框+发送钮+生成气泡/图片）

---

## 五、改代码的核心经验（实战铁律）

> 完整血泪史见 `docs/抓包经验总结.txt`。以下铁律改任何引擎代码都必须遵守。

### 铁律 1：物理降维，别信标准 API
React/Vue 用虚拟 DOM，`loc.fill()` 会被清空。输入框可能是 `div[contenteditable="true"]`。正确连招：`click(force=True)` → `Ctrl+A` → `Backspace` → `keyboard.type()`/`insert_text()`。`try: loc.fill() except: 降级物理键盘`。

### 铁律 2：UI 是幻觉，遮挡要强攻
透明遮罩/悬浮面板/没收起的下拉会挡目标。用 `click(force=True)` 无视遮挡。`attached` 比 `visible` 抗遮挡，但若 `visible`+force 实测稳定就用它。**展开面板后习惯 `Escape` + `mouse.click(10,10)` 盲点破盾**。

### 铁律 3：状态感知，别线性流水线
网页有记忆，上次停某模式这次别死脑筋去切。操作前 `is_visible()` 嗅探，门开着就跨过。非关键 UI 动作套 `try...except: pass`。

### 通用经验：功能面板是条件渲染的（Mode-First）
面板/按钮要先满足前置条件才渲染：先切模式才有参数面板；发送按钮随输入渲染；未登录锁工作台；有的站要先"新建项目"。**别一口气猛点，操作间停 1s**（React 水合延迟）。排查找不到先确认前置条件，别急着改选择器。

### 铁律 4：出图用 SRC 差集，别数节点
现代框架先渲染 Base64 骨架屏，`count()` 增加可能是假图。做法：初始提真实 http URL 存 `Set A`，出图后存 `Set B`，`B - A` 才是真图。配合黑名单正则（`base_engine.py` 的 `_extract_valid_image_url`，可在 config.json `image_blacklist` 调）：`(base64|blob:|loading|placeholder|spinner|/user/|/upload/|/reference/|/source/|/input/)`，只认 `/generator/` 真图路径。

### 铁律 5：幽灵标签页，URL 认路
CDP 接管时 `pages[-1]` 可能拿到扩展/空白页。遍历所有页用 `url` 认路，找到后 `bring_to_front()`。

### 铁律 6：网络空闲是谎言
商业站挂满埋点，`networkidle` 等不到。只等 `domcontentloaded`/`commit`，盯 UI：要操作的元素 visible 就强攻。

### 铁律 7：React 水合延迟
按钮空壳已渲染但 onClick 没绑，点了没反应。核心路由跳转后物理硬等 1~2 秒。

### 铁律 8：上传垫图用 file_chooser 拦截
Ant Design 等不会把真实 `input[type=file]` 写死，直接 `set_input_files` 会被丢弃。正确：模拟真人点上传按钮，用 `with page.expect_file_chooser() as fc:` 半空拦截，`fc.value.set_files(本地路径)`。若是原生隐藏 input（如即梦）可先试 `set_input_files`，失败降级 file_chooser。

### 选择器设计（锚点优先级从高到低）
1. **`data-testid`**（最稳，工程师留的后门）
2. **稳定 `class`/`id`**
3. **多重属性兜底**（如 `div[aria-haspopup="dialog"]:has-text("参考图")`）
4. **最后才 XPath，且绝不用长路径**（`//html/body/div[2]/...`，DOM 平移就崩）

**文本匹配陷阱**：慎用单字/短数字模糊匹配（`has-text("0")` 会误中 "100%"）；用 `:has-text()` 模糊包含，别用 `exact=True`；短文本/数字尽量配 testid 或唯一 class；子串冲突用唯一 testid 锚定。

**可见性/多元素**：响应式双套 DOM 的隐身节点要加 `:visible` 过滤；同 testid 多个想清楚 `.first`/`.last`（发送按钮通常 `.last` 激活）；`:has-text`+`:visible` 可叠加；`.count()` 增加可能是占位符，判图靠 SRC 差集。

**写进 `UI` 字典**：允许逗号分隔多选择器兜底（一个失效另一个顶上）；允许 `:has-text`/`:visible`/`:last` 混用。

---

## 六、核心心法：稳，就是快（Slow is Fast）

> **最高原则，所有改动围绕它。**

- 适用于**引擎挂机**和 **AI 探路**：宁可慢，不可错。探路也每步验证一步，别猛点；探得稳，落对选择器才不用返工。
- 拟人延迟/缓冲等待是护身符，防封号防 WAF。**"快"≠减少等待，而是减少返工**。别为"看着快"删 `time.sleep`/`_human_pause`。
- 遇到选择器失效 → 先抓 DOM 情报确认再改，**不要瞎猜**。

**协作节奏**：收到任务先分析 → 要改代码先讲清等确认 → 能靠改选择器解决的不动逻辑 → 改完查 lint 让用户测试迭代。

---

## 七、启动与测试

```bash
# Windows / macOS
启动控制台.bat  或  ./启动控制台.command  或  python3 main.py
```
- **必须用 `python3`**（系统 `python` 是 2.7，类型注解会编译失败）。
- 控制台：http://127.0.0.1:8000；日志实时推前端终端，也落 `logs/sys_logs.log`。
- 测试出问题，把**报错日志 + DOM 情报**一起贴给 AI，别只贴报错。
- Mac 上 Chrome 路径/端口由 `config.json → global_settings.chrome` 控制（默认 debug_port 9222）。

---

## 八、快速自查清单（改引擎前过一遍）
- [ ] 探路结果沉淀成引擎选择器了吗？（落进 `UI`/`PARAM_OPTION_SELECTORS`/`action_*`，不是只在 webctl 看过）
- [ ] 关键交互选择器在引擎式点击下实测验证过吗？（`.first`/`.last`/遮挡/动画）
- [ ] 选择器基于真实抓取的 DOM，还是我编的？
- [ ] 要改的是代码逻辑还是选择器？逻辑必须确认。
- [ ] 全局参数有没有写死？应放 `config.json → global_settings`。
- [ ] 没引入云端同步/夜间模式？
- [ ] 输入框用物理键盘降级了吗？
- [ ] 展开面板后 Esc + 盲点破盾了吗？
- [ ] 出图判定用 SRC 差集 + 黑名单过滤了吗？
- [ ] 标签页用 URL 认路 + bring_to_front 了吗？
- [ ] 上传用 `expect_file_chooser` 拦截了吗？
- [ ] 会不会因删等待导致"变快但变脆"？
