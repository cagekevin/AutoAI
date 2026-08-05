# Lovart 平台结构与产图流水线备忘

> 本文档沉淀 Lovart（https://www.lovart.ai）已探明且**实测验证**过的结构。
> 用途：下次排查 / 改选择器直接复用，**别重复探路，别让用户重复解释**。
> 所有选择器均基于真实 DOM + harness 实测验证，非凭空编造。
> 更新日期：2026-08-05

---

## ⭐ 0. 最高准则（动手前必读）

### 0.1 这套代码和 AI 理解的其他东西不一样 —— 链条任何一环不能断

> **这是一个"端到端产图流水线"，每个步骤都依赖前一步，任何一环断了，后面的图就发不出来。**
> 别用"普通自动化脚本"的思维看待它（"这步失败就跳过，继续下一步"）。
> 它是一条必须完整走完的链：**新建项目 → 切模式 → 配参 → 传垫图 → 输词 → 发送 → 等出图 → 下载**。
> 改动前先想清楚：这一步是不是后面产图的**必要前置条件**？漏了它图片能不能出？

### 0.2 软性放行 vs 熔断（关键平衡，务必看懂）

> **部分步骤"偶尔失败"是可以跳过继续的**（配参、垫图等），因为偶尔一次失败大概率是网络抖动，跳过图片照样能出。
> **但连续多次失败就不行**——说明不是偶发，是真问题（选择器失效/网页改版/被风控），必须停下来。

| 失败类型 | 判断 | 处理 |
|---------|------|------|
| **偶发失败**（配参/垫图点一次没命中）| 大概率网络抖动 | ✅ 软性放行：跳过这一步继续，图片还能出 |
| **连续多次失败**（配参/垫图反复失败）| 不是偶发，是真问题 | ❌ 必须熔断/报错/换环境，别硬撑 |
| **核心前置缺失**（没输入框）| 后面发词/发送必失败 | ⛔ 阻塞等人工，加超时跳过 = 图片必然出不来 |

> **为什么**：你实测过——配参/垫图**第一次失败可以成功出图**（网络偶发），但**第二次/第三次还失败就不行**（真故障）。
> 所以引擎对可重试步骤用"软性放行 + 连续失败熔断"，对核心前置用"死等"。

### 0.3 如何写代码（判断改代码的标准）

> **改代码的本质 = 让最终图片能生成，不是为了跳步骤、不是为了堆保护。**

**判断标准：问自己"这个改动是让产图更顺畅，还是跳过步骤导致产图失败？"**

| 场景 | 本质 | 该不该做 |
|------|------|---------|
| 等输入框出现（安检阻塞）| 等产图必需前置条件 | ✅ 保留（没输入框放行也发不了图）|
| 等气泡确认上一发发送成功 | 等发送成功验证 | ✅ 保留 |
| 等图片下载完成 | 等产图结果 | ✅ 保留（超时跳过会丢图）|
| 配参/垫图偶发失败，软性放行 | 容忍网络抖动，图还能出 | ✅ 保留 |
| 配参/垫图连续失败熔断 | 真故障，停下去修 | ✅ 保留 |
| 打字慢、页面刷新耗时 | 真实网页正常节奏 | ✅ 别嫌慢去删 |
| 加超时跳过"没输入框" | **跳核心前置** | ❌ 垃圾，图片发不出来 |
| 为"看着快"删等待 | **变快但变脆** | ❌ 违背"稳就是快"|

> **红线**：任何改动导致图片不能生成，**都是垃圾，禁止**。
> 等待必要前置条件 ≠ 多余保护。前者让产图顺畅，后者破坏产图。

---

## 1. 通用：setup 新建页才能看到窗口

**现象**：日志在走，但 Chrome 上没反应，页面窗口看不到。

**根因**：`connect_over_cdp` 下，**复用已有页面**无论 `bring_to_front()` / `goto` 刷新，都无法把 Chrome 窗口带到前台（窗口被其他程序盖住）；**只有 `new_page()` 新建页面 + `goto` 才能让窗口真实弹出**。

**修复**（`base_engine.py` `setup()`）：
- 去掉复杂的 `target_url`/`clean_url`/`target_page` 寻址和复用分支。
- 总是 `self.page = self.context.new_page()` → `goto(home_url)` → 点新建项目进工作台。
- `teardown()` 补 `self.page.close()`，配合每次新建，避免标签页堆积。
- 删除 `set_viewport_size(1600,1000)` 假视口校准（只改 Playwright 假视口，不改变真实 Chrome 窗口，救不回隐藏窗口）。

---

## 2. 核心 URL 与模式

| 项 | 值 |
|----|----|
| 主页 | `https://www.lovart.ai/zh/home` |
| 工作台画布 | `https://www.lovart.ai/canvas?projectId=xxx`（`URL_CANVAS = **/canvas?projectId=**`）|
| 模式切换按钮 | `button[data-testid="agent-mode-switch-trigger"]`（**下拉切换型**）|
| 目标模式选项 | `[data-testid="agent-mode-switch-option-image"]` / `-agent` / `-chat` |

> **前置条件**：必须先切【图像生成】模式，否则参数面板 / 上传 / 出图都不渲染。
> 模式切换用 harness 时先 `state mode_btn` 看当前模式，别默认一定在图像模式。

---

## 3. 引擎 `UI` 字典（当前已用、实测命中）

```python
UI = {
    "new_proj_btn": 'a[data-testid="lovart-nav-create-project"], a[href*="newProject=true"]:visible',
    "mode_btn": 'button[data-testid="agent-mode-switch-trigger"]',
    "mode_option": '[data-testid="agent-mode-switch-option-image"], [data-testid="agent-mode-switch-option-agent"], [data-testid="agent-mode-switch-option-chat"]',
    "param_panel_trigger": 'button[data-testid="agent-image-generator-multi-params-button"]',
    "model_btn": 'button[data-testid="generator-model-button"], button[data-testid="agent-generator-model-button"]',
    "defocus_area": '#agent-chat-title',
    "upload_btn": '.no-scrollbar div[aria-haspopup="dialog"]:has-text("参考图")',
    "local_upload_option": 'span.lo-menu-item-text:has-text("从本地上传图片"), button:has-text("从本地上传")',
    "input_box": '#agent-image-generator-prompt',
    "submit_btn": '[data-testid="agent-image-generator-submit-button"], [data-testid="agent-send-button"]',
    "bubble": '[data-testid="agent-message"]',
    "bubble_img": 'img.object-cover, img.ant-image-img',
    "canvas_clean_img": '.tl-canvas img[src*="{file_id}"]',
}
```

---

## 4. 逐步骤专题（每个产图环节单独讲清）

### 4.1 步骤①：新建项目（可选）
- **入口**：从主页点"新建项目"进工作台（`new_proj_btn`），只有 Lovart 需要。
- **关键**：`action_init_workspace` 里 `self.last_params = None` + `self.cached_img_path = None` **强制参数+垫图失忆**。
  - **为什么**：新建画布后，页面参数面板/垫图状态重置，旧记忆会误触发"防抖跳过配参"或"垫图复用"导致失败。必须失忆，强制下轮重配。
  - **教训**：别以为"参数防抖能跨画布生效"，换画布必须失忆。

### 4.2 步骤②：切模式（前置）
- **按钮**：`mode_btn`（下拉切换型），目标 `mode_option`。
- **防抖**：`_switch_work_mode` 用 `re.search(target_mode, 按钮文字)` 判断当前是否已是目标模式，是就跳过。`target_mode = "图像|Image"`（`|` 是正则"或"）。
- **异常处理**：切模式失败走**软性放行**（只记日志不阻断）——因为可能本来就在目标模式。

### 4.3 步骤③：配参（可重试，偶发失败可跳过）
- **逻辑**：`_set_params_iteratively` 点开参数面板 → 选比例/分辨率/模型 → 收起。
- **防抖**：`last_params` 与上一轮一致就跳过 UI 点击（**只对同一画布连续任务有效**）。
- **偶发失败**：单个参数没点中 → 软性放行跳过（`all_success=False` → `last_params=None` 强制下轮重配）。
  - **为什么能跳过**：参数偶尔没配上，图片照样能出（只是比例/分辨率不理想），网络抖动导致。
- **连续失败**：多次配参都失败 → `last_params=None`，下轮强制重配；若持续失败触发熔断，说明选择器失效/改版，需探路更新。
- **模型 data-testid 含斜杠**：`get_by_test_id(f"generator-model-option-{slug}")`，slug 如 `vertex/nano-banana-2`，testid 故意含 `/`，反直觉但必须这么写。

### 4.4 步骤④：传垫图（可重试，偶发失败可跳过）
- **逻辑**：`_smart_upload` 走 `os_dialog` 上传（`expect_file_chooser` 拦截）。
- **偶发失败**：找不到传图按钮 / 上传失败 → 软性放行，忽略垫图强制发词（`self.cached_img_path = None`）。
  - **为什么能跳过**：偶尔一次垫图没传上，图片还能出（只是没垫图参考），网络抖动导致。
- **连续失败**：多次上传都失败 → 说明上传入口/选择器出问题，需探路确认。
- **8 连发特殊**：每发发送后 `cached_img_path = None` 洗白，下一发重新上传同一张垫图。**故意不复用**——因为复用要处理"上一发垫图是否被平台吃掉、要不要清旧图"的复杂状态，直接传 8 次最省心，不赌缓存状态。

### 4.5 步骤⑤：输词
- **输入框**：`#agent-image-generator-prompt`（`input_box`）。
- **打字**：`_fill` 逐字符打字（每字符 2-5ms），真实网页正常节奏，别嫌慢去优化。
- **前置**：输入框必须存在，否则发送按钮不激活。

### 4.6 步骤⑥：发送（必须确认成功）
- **按钮**：`submit_btn`，随输入渲染，填字后才可点。
- **等按钮可用**：死等 `is_disabled()` 变 false（上限 90s）。
- **发送后必做**：等气泡出现 = **验证上一发发送成功**（发送成功就产生新气泡）。必须确认上一发发出去了才发下一个，否则第一次没发出后面全乱套。
  - **替代方案**（如果气泡不好用）：也可以用"发送键是否可点击"作为发送成功的标志。但**优先用等气泡**，这是现行已验证方案。

### 4.7 步骤⑦：等出图（收割）
- **气泡生命周期**：
  1. 发送后立即出现气泡 `data-testid="agent-message"`（**还没真图**）。
  2. 生成中：气泡内只有模型图标 `.../web/generator/nbp.svg`（`h-3 w-3 opacity-40` 小图标 = loading）。
  3. 生成完成：气泡内 `nbp.svg` 被替换成真图 `<img>`，`src` 变为 `.../artifacts/generator/xxx.png?...`。
- **判断出图**：不是看气泡数量，而是**看气泡内是否出现真图 src**（`/generator/` 路径）。
- **1 个气泡 = 1 张真图**：别理解成气泡里有多张图并存（那是误抓中间态）。
- **区分技巧**：`bubble_img` 用 `img.object-cover`——**生成中**气泡没有 `object-cover` 图（只有 `nbp.svg` 小图标，`h-3 w-3 opacity-40`，**非 object-cover**），**生成完**才有 → 天然区分"生成中 / 已出图"。
  - 占位图标虽也在 `/web/generator/` 路径下，但**无 `object-cover` class**，不会误匹配。
- **收割机制**：`pending_bubbles` 存气泡 data-testid（值都是 `agent-message`，不唯一）→ `locator` 实际命中整个消息区 → 扫 `img.object-cover` → `_extract_valid_image_url` 靠 src 路径判断真图（`/generator/` 真图 + 黑名单排除垫图等）。**收割靠真图 src，不靠精确定位单个气泡**。
  - **AI 别纠结"气泡 data-testid 是否唯一"**：实测抓到 4 个气泡 data-testid 都是 `agent-message`（不唯一），但这套收集 + 收割逻辑**代码验证走得通**。遇到想不通就先信它是对的，别去改。
- **扫描节奏**：池子有未出图气泡就**心跳休眠 25~35 秒**再扫——**Lovart 生成慢（高峰期一张图甚至 1 小时），排队挂机**，宽幅休眠是等待节奏 + 防封，别嫌慢删。

### 4.8 步骤⑧：下载（等结果，别跳）
- **高清原图**：真图 `img` 的 `src` 可能带 `?x-oss-process=image/resize,w_512`（缩略图参数），但引擎 `clean_url = raw_url.split('?')[0]` **去掉 query 再下载**，所以**落盘的是高清原图**，不是 512 小图。
- **下载等待**：`download_via_network` 有超时重试（3 次）。**别加"跳过下载"的保护**——那样丢图，图片出不来。

---

## 5. 8 连发 40 秒间隔根因（已修复）

**症状**：第一个发出去后，约 50 秒才发第二个；每发之间被拖 40+ 秒。

**根因**：等气泡用 `.agent-chat-message`（**已失效**）→ 气泡数永远 0 → `current_count > prev_count` 永不成立 → 死等满 40 秒超时。

**修复**：`"bubble"` 改为 `'[data-testid="agent-message"]'`，`"bubble_img"` 改为 `'img.object-cover, img.ant-image-img'`。

> 排查时**先怀疑条件渲染/选择器失效**，别急着怀疑"气泡生成慢"（生成不会那么慢）。

---

## 6. 气泡选择器已变更（本次重要发现）

**Lovart 改版后，气泡 DOM 从 class 改成了 data-testid。**

| 项目 | 旧（已失效） | 新（实测命中） |
|------|------------|--------------|
| 气泡元素 | `.agent-chat-message`（class） | `[data-testid="agent-message"]` |
| 气泡内容区 class | — | `empty:hidden` |
| 外层消息容器 | — | `[data-testid="agent-generator-messages"]` |

**后果（重要）**：若仍用 `.agent-chat-message`，`count()` 永远为 0 → 等气泡循环死等 40 秒超时 → **8 连发每发间隔被拖到 44 秒**。必须用 `[data-testid="agent-message"]` 数气泡。

**修复后效果**：气泡发送后立即出现（`data-testid="agent-message"`），所以等气泡会秒过，8 连发自然快速连续。

---

## 7. 引擎里 AI 反直觉的设计（别当 bug 删）

### A. 模型 data-testid 含斜杠
```python
option = self.page.get_by_test_id(f"generator-model-option-{slug}")
# slug = "vertex/nano-banana-2" → testid = "generator-model-option-vertex/nano-banana-2"
```
- Lovart 模型选项 data-testid **故意含斜杠 `/`**，反直觉但必须这么写，别改。

### B. 新建项目强制"参数 + 垫图失忆"
`action_init_workspace` 里 `last_params = None` + `cached_img_path = None`。
- **为什么**：新画布状态重置，旧记忆误触发防抖/垫图复用导致失败。必须失忆。

### C. 参数防抖只对"同一画布连续任务"有效
`_set_params_iteratively` 靠 `last_params` 防抖。换画布/重启必须失忆，否则漏配参数。

### D. `_security_check` 找不到输入框会阻塞等人工放行（本质是必要等待）
- 找不到输入框 → 阻塞等用户点【✅ 人工放行】。
- **本质**：**没有输入框，放行后 `_fill`/`submit` 全失败，图片根本发不出去。** 等的是"输入框出现"这个产图必需前置条件。
- **教训**：**别加超时跳过**。加超时 = 跳核心前置 = 图片发不出来 = 垃圾。

### E. `_click` 的 `force=True`（AI 生成，能用就行）
- base_engine 的 `_click` 用 `click(force=True)` 强制点击。**这段是之前 AI 写的，具体机制不强断言**，但实测能用。别去动它。

### F. 真实网页有正常刷新耗时，别嫌慢
- `_fill` 逐字符打字、`_human_pause`、动作后缓冲——都是真实网页正常节奏。别为"看着快"删等待（变快但变脆）。

---

## 8. harness 探路要点（避免踩坑）

- **必须用 `cmd /c "... < 探路脚本.py"` 重定向喂 stdin**，别用 PowerShell 管道（会插 BOM `U+FEFF` 语法错误）。
- harness `js()` 返回值坑：**别用裸箭头函数**（`()=>x` 返回 `{}`）；用**直接表达式**（如 `document.title`）或**带 `return` 的函数体**（harness 自动包 IIFE）。
- 探路/验证/交互一律用 harness 现成 helper（`js()`/`click_at_xy`/`fill_input`/`press_key`/`capture_screenshot`），**禁止自己写独立探路脚本、禁止造轮子**。
- 运行时：`cmd /c "cd /d g:\AutoAI_01\tools\browser_harness\src && set BU_CDP_URL=http://127.0.0.1:9222 && g:\AutoAI_01\venv\Scripts\python.exe -m browser_harness.run < 探路脚本.py"`

---

## 9. 待办 / 注意

- [ ] `FORCE_NEW_PAGE` 属性已不再被基类使用（子类仍定义），留着无害，暂不动。
