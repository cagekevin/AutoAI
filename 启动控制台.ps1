$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$chromeProfile = "G:\AutoAI_01\google_chrome_profile"
$baseDir = "G:\AutoAI_01"

while ($true) {
    Clear-Host
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                            ║" -ForegroundColor Cyan
    Write-Host "║              🚀 AutoAI 核心总控台 v4.0                     ║" -ForegroundColor White
    Write-Host "║                                                            ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [ 🟢 引擎与运行 ] (自带智能端口清理)" -ForegroundColor Green
    Write-Host "    1. ▶️  全部启动 (挂载现有 Chrome + 拉起后端服务)" -ForegroundColor White
    Write-Host "    2. 🔌 仅启后端 (不打开浏览器，纯净 API 模式)" -ForegroundColor White
    Write-Host ""
    Write-Host "  [ 🛠️ 维护与清理 ]" -ForegroundColor Yellow
    Write-Host "    3. 🧹 日常清场 (一键清空：过期日志 + 断电残留队列)" -ForegroundColor White
    Write-Host "    4. 💣 账本核弹 (物理删除 DB，强制重新跑图)" -ForegroundColor White
    Write-Host ""
    Write-Host "  [ 📊 监控与开发 ]" -ForegroundColor Cyan
    Write-Host "    5. 📡 状态雷达 (秒级自检：产出体积 / 内存 / 服务存活)" -ForegroundColor White
    Write-Host "    6. 💻 Venv终端 (一键进入带虚拟环境的独立 CMD)" -ForegroundColor White
    Write-Host ""
    Write-Host "    0. ❌ 安全退出控制台" -ForegroundColor Red
    Write-Host ""
    Write-Host "──────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    
    $opt = Read-Host "  👉 请输入指令 [0-6] 并按回车"

    switch ($opt) {
        "1" {
            Clear-Host
            Write-Host "┌────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
            Write-Host "│                   🚀  启动全阵列中...                      │" -ForegroundColor Cyan
            Write-Host "└────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
            Write-Host ""
            
            # 智能杀僵尸进程 (无缝熔断在启动里)
            $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
            if ($conn) {
                Write-Host " [*] 发现 8000 端口被残留进程占用，正在静默释放..." -ForegroundColor Yellow
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
            }

            Write-Host " [*] 端口畅通，正在拉起 Chrome 与 Python 后端..." -ForegroundColor Green
            Start-Process $chromePath "--remote-debugging-port=9222 --user-data-dir=$chromeProfile"
            Set-Location $baseDir
            & "venv\Scripts\python.exe" "main.py"
            Read-Host "`n按回车键返回主菜单..."
        }
        "2" {
            Clear-Host
            Write-Host "┌────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
            Write-Host "│                 🔌  挂载纯净后端中...                      │" -ForegroundColor Cyan
            Write-Host "└────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
            Write-Host ""

            # 智能杀僵尸进程 
            $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
            if ($conn) {
                Write-Host " [*] 发现 8000 端口被残留进程占用，正在静默释放..." -ForegroundColor Yellow
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
            }

            Write-Host " [*] 端口畅通，正在拉起纯净 API 后端..." -ForegroundColor Green
            Set-Location $baseDir
            & "venv\Scripts\python.exe" "main.py"
            Read-Host "`n按回车键返回主菜单..."
        }
        "3" {
            Clear-Host
            Write-Host "┌────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
            Write-Host "│                   🧹  清空日志与缓存                       │" -ForegroundColor Cyan
            Write-Host "└────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
            Write-Host ""
            if (Test-Path "$baseDir\logs\sys_logs.log") { Clear-Content "$baseDir\logs\sys_logs.log" }
            if (Test-Path "$baseDir\queue_backup.json") { Remove-Item "$baseDir\queue_backup.json" -Force }
            Write-Host "`n ✅ 日志与断电缓存已全部清空！系统恢复纯净状态。" -ForegroundColor Green
            Read-Host "`n按回车键返回主菜单..."
        }
        "4" {
            Clear-Host
            Write-Host "┌────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
            Write-Host "│                   💣  销毁历史账本 DB                      │" -ForegroundColor Cyan
            Write-Host "└────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  [警告] 这将删除防重复记录，历史任务将可重新出图！" -ForegroundColor Red
            $delConfirm = Read-Host "`n  确认物理删除请按 Y，按其他键取消"
            if ($delConfirm -match "^[yY]$") {
                if (Test-Path "$baseDir\history.db") {
                    Remove-Item "$baseDir\history.db" -Force
                    Write-Host "`n  └─ ✅ 历史账本已飞灰湮灭！" -ForegroundColor Green
                } else {
                    Write-Host "`n  └─ ⚠️ 账本原本就不存在。" -ForegroundColor Yellow
                }
            } else {
                Write-Host "`n [*] 已取消销毁操作。" -ForegroundColor Yellow
            }
            Read-Host "`n按回车键返回主菜单..."
        }
        "5" {
            Clear-Host
            Write-Host "┌────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
            Write-Host "│                   📡  状态雷达 & 专项自检                  │" -ForegroundColor Cyan
            Write-Host "└────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
            Write-Host ""

            # 1. 监控随时间膨胀的文件目录
            Write-Host " [1] 📁 产出文件体积检测 (单位: MB)" -ForegroundColor Yellow
            $dlSize = if (Test-Path "$baseDir\Downloads") { [math]::Round((Get-ChildItem "$baseDir\Downloads" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB, 2) } else { 0 }
            $logSize = if (Test-Path "$baseDir\logs") { [math]::Round((Get-ChildItem "$baseDir\logs" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB, 2) } else { 0 }
            $dbSize = if (Test-Path "$baseDir\history.db") { [math]::Round((Get-Item "$baseDir\history.db").Length / 1MB, 2) } else { 0 }
            $refSize = if (Test-Path "$baseDir\assets\references") { [math]::Round((Get-ChildItem "$baseDir\assets\references" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB, 2) } else { 0 }
            
            Write-Host "  -> 📥 Downloads (落盘产出图): $dlSize MB" -ForegroundColor Green
            Write-Host "  -> 🖼️ References (上传垫图集): $refSize MB" -ForegroundColor Green
            Write-Host "  -> 📝 Logs (运行与报错日志): $logSize MB" -ForegroundColor Green
            Write-Host "  -> 📓 history.db (防重复账本): $dbSize MB" -ForegroundColor Green

            $os = Get-CimInstance Win32_OperatingSystem
            Write-Host "`n [2] 🧠 物理内存占用状态" -ForegroundColor Yellow
            Write-Host "  -> 剩余 $([math]::Round($os.FreePhysicalMemory / 1MB, 2)) GB / 共 $([math]::Round($os.TotalVisibleMemorySize / 1MB, 2)) GB" -ForegroundColor Green

            # 2. 瞬间微服务探测
            Write-Host "`n [3] 🔌 核心微服务连通性雷达" -ForegroundColor Yellow
            $ports = netstat -ano
            
            if ($ports -match ":8000\s+.*LISTENING") { Write-Host "  -> ⚡ FastAPI (8000): 存活" -ForegroundColor Green } else { Write-Host "  -> 💤 FastAPI (8000): 未启动" -ForegroundColor DarkGray }
            if ($ports -match ":9222\s+.*LISTENING") { Write-Host "  -> 🐛 Chrome CDP (9222): 连通" -ForegroundColor Green } else { Write-Host "  -> 💤 Chrome CDP (9222): 端口空闲" -ForegroundColor DarkGray }
            if ($ports -match ":41595\s+.*LISTENING") { Write-Host "  -> 🦅 Eagle 打标 (41595): 连通" -ForegroundColor Green } else { Write-Host "  -> ⚠️ Eagle 打标 (41595): 未开 (旁路降级中)" -ForegroundColor Yellow }
            if ($ports -match ":9097\s+.*LISTENING") { Write-Host "  -> 🛡️ Clash 逃逸 (9097): 连通" -ForegroundColor Green } else { Write-Host "  -> ⚠️ Clash 逃逸 (9097): 未检测到" -ForegroundColor Yellow }

            Read-Host "`n>>> 扫描完毕！按回车键返回主菜单..."
        }
        "6" {
            $venvScript = Join-Path -Path $baseDir -ChildPath "venv\Scripts\activate.bat"
            if (Test-Path $venvScript) {
                Start-Process cmd "/k cd /d `"$baseDir`" && call `"$venvScript`""
            } else {
                Write-Host "`n ❌ 找不到虚拟环境 (venv)！请检查项目目录。" -ForegroundColor Red
                Start-Sleep -Seconds 2
            }
        }
        "0" {
            Write-Host "`n 👋 拜拜！已安全退出控制台。" -ForegroundColor Cyan
            Start-Sleep -Seconds 1
            exit
        }
        default {
            Write-Host "`n ❌ 无效选项，请重新输入。" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}