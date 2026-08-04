# CLAUDE.md — AutoAI 多平台生图自动化控制中心

> 本文档是 AI 助手在本项目协作时的**最高行动准则**。所有操作必须遵守，尤其是"改代码前必须与用户确认"这条红线。

---

## 一、项目是什么

一个 **Python + Playwright + FastAPI** 的多平台 AI 绘画自动化控制中心。它通过 CDP 协议接管本机 Chrome，在真实浏览器里自动完成：新建项目 → 切换模式 → 配置参数 → 上传垫图 → 输入提示词 → 发送 → 收割图片 → 打标投递 Eagle 的完整流水线。

### 核心目录（已整理）
```
G:\AutoAI_01\
├── core/          # 🧠 调度中枢（server/task_runner/ledger/image_processor）
├── plugins/       # ⚔️ 正式引擎（base + flow/jimeng/lovart/doubao）—— 核心战场
├── templates/     # 🖥️ 前端控制台（index.html，被 FastAPI 按目录引用，勿移）
├── tools/         # 🛠️ 辅助工具（DOM 抓取工具、engine_ide、旧版备份、标准化模版）
├── docs/          # 📄 经验文档（抓包经验总结、总结方法、怎么打包）
├── assets/        # 垫图资源
├── Downloads/     # 产图输出
├── logs/          # 运行日志
├── config.json    # 站点配置（含云控 Excel 地址）
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

---

## 二、工作范围（你能碰什么）

### ✅ 可以直接做
- **改 CSS 选择器**：`UI` 字典里的定位器、`PARAM_FORMAT`/`PARAM_OPTION_SELECTORS` 映射、`PARAM_ROUTING` 路由
- **阅读/分析**代码、日志、DOM 情报
- **整理**非业务文件（移动 `tools/`、`docs/` 里的工具和文档）
- **修 bug**、性能调优、选择器失效排查

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

### 抓取工具
项目里有专门的抓 DOM 工具（在 `tools/第一步获取数据/`）：
- **`油猴清洗.js`**：Tampermonkey 油猴脚本，页面上注入两个悬浮按钮
  - **🌐 全局提取**：抓整个页面净化后的 DOM（右上角按钮）
  - **🎯 局部狙击**：开启后鼠标高亮目标元素，点击即抓该元素的净化 HTML
- **`Cookie 极速提取器.txt`**：bookmarklet，一键复制网站 Cookie
- **`网页清洗.html`**：DOM 净化舱

### 抓取流程
1. **装油猴脚本**：把 `油猴清洗.js` 装进 Tampermonkey（刷新目标网页后右上角出现按钮）
2. **定位目标**：在 Lovart 等目标网页，按需抓取
   - 抓**整页骨架** → 点"🌐 全局提取"
   - 抓**某个具体元素/下拉菜单** → 点"🎯 局部狙击"后点目标
3. **导出情报**：自动下载 `情报_*.txt`，内容含净化 HTML + 给 AI 的系统提示词
4. **把情报内容贴给 AI**，由 AI 与现有选择器比对，判断是否失效、如何更新

### 目标元素清单（Lovart 为例，常抓这 5 大模块）
1. **新建项目按钮** → 主页卡片
2. **模式切换**（Agent/图像）→ 触发按钮 + 选项菜单
3. **参数面板**（比例/分辨率/模型）→ 触发按钮 + 下拉菜单选项
4. **垫图上传** → 上传按钮 + 上传菜单/input
5. **发送/收割** → 输入框 + 发送按钮 + 生成后的气泡/图片

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
- **不要迷信 `state="visible"`**（被遮挡 1px 就超时）。改用 `state="attached"`（只要在源码里就抓）
- 配合 `click(force=True)` 无视遮挡
- **点完展开面板后，养成习惯敲 `Escape` + 屏幕角落 `mouse.click(10, 10)` 盲点一枪**，物理破盾

### 铁律 3：状态感知，不要线性流水线
网页有记忆（Cookie/LocalStorage），上次停在某模式，这次别死脑筋去切。
- **操作前先 `is_visible()` 嗅探**：门开着就跨过去，没开再动手
- 非关键 UI 过渡动作套 `try...except: pass`，别让一个小按钮崩掉整个链路

### 铁律 4：出图用"SRC 集合差集"，别数 DOM 节点
- 现代框架先渲染 Base64 骨架屏占位，`locator.count()` 增加可能是假图
- **正确做法**：初始提取所有真实 `http` URL 存 `Set A`；出图后提取存 `Set B`；`Set B - Set A` 剩下的才是真图
- 配合黑名单正则过滤：`(base64|loading|placeholder|/user/|/upload/)`，只认 `/generator/` 等真图路径

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
# 或直接
venv\Scripts\activate && python main.py
```
- 控制台：http://127.0.0.1:8000
- 日志实时推送到前端终端，也落在 `logs/sys_logs.log`
- 测试出问题时，把**报错日志**和**DOM 情报**一起贴给 AI，不要只贴报错

---

## 七、快速自查清单（改引擎代码前过一遍）
- [ ] 选择器是基于真实抓取的 DOM 吗？还是我编的？
- [ ] 要改的是**代码逻辑**还是**选择器**？代码逻辑必须确认。
- [ ] 输入框处理用了物理键盘降级吗？
- [ ] 展开面板后记得 Esc + 盲点破盾吗？
- [ ] 出图判定用了 SRC 差集 + 黑名单过滤吗？
- [ ] 标签页用 URL 认路 + bring_to_front 了吗？
- [ ] 上传垫图用 `expect_file_chooser` 拦截了吗（还是裸 `set_input_files`）？
- [ ] 会不会因为删掉等待导致"变快但变脆"？
