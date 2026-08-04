// ==UserScript==
// @name         🛸 DOM 极简空投舱 (大模型喂饭版)
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  右上角悬浮按钮：🌐全局提取 + 🎯局部狙击。快捷键备用 Alt+1 / Alt+2。
// @author       AutoAI 首席架构师
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ==========================================
    // 🧠 核心洗脱引擎 (锁死最优策略)
    // ==========================================
    function purifyDOM(rawHtml) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(rawHtml, 'text/html');
        const root = doc.body || doc.documentElement;

        // 1. 斩杀视觉与逻辑垃圾
        ['meta', 'link', 'noscript', 'canvas', 'video', 'audio', 'iframe', 'script', 'style'].forEach(tag =>
            doc.querySelectorAll(tag).forEach(el => el.remove())
        );

        const twRegex = /\b(sm:|md:|lg:|xl:|2xl:|hover:|focus:|active:|group-[a-z]+:)?(flex|grid|hidden|block|inline|absolute|relative|fixed|inset-\S+|w-\S+|h-\S+|m[trblxy]?-\S+|p[trblxy]?-\S+|bg-\S+|text-\S+|border\S*|rounded\S*|shadow\S*|opacity-\S+|z-\S+|gap-\S+|items-\S+|justify-\S+|leading-\S+|font-\S+|tracking-\S+|transition\S*|transform\S*|cursor-\S+|overflow-\S+)\b/g;
        const keepAttributes = ['id', 'class', 'href', 'src', 'type', 'name', 'value', 'placeholder', 'role'];

        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null, false);
        let node; const nodesToProcess = [];
        while (node = walker.nextNode()) nodesToProcess.push(node);

        for (let i = 0; i < nodesToProcess.length; i++) {
            let el = nodesToProcess[i];
            if (el.nodeType === Node.TEXT_NODE) {
                el.nodeValue = el.nodeValue.replace(/\s+/g, ' ').trim();
                continue;
            }
            if (el.tagName.toLowerCase() === 'svg') {
                const rep = doc.createElement('svg'); rep.setAttribute('data-icon', 'svg-placeholder');
                el.replaceWith(rep); continue;
            }
            if (el.hasAttribute('src') && el.getAttribute('src').startsWith('data:image')) el.setAttribute('src', '[Base64 Omitted]');

            if (el.hasAttribute('class')) {
                let cls = el.getAttribute('class').replace(twRegex, '').replace(/\s+/g, ' ').trim();
                if (cls) el.setAttribute('class', cls); else el.removeAttribute('class');
            }
            Array.from(el.attributes).forEach(attr => {
                if (!keepAttributes.includes(attr.name) && !attr.name.startsWith('data-') && !attr.name.startsWith('aria-')) el.removeAttribute(attr.name);
            });
        }

        // 2. 修剪空壳
        function pruneEmpty(n) {
            Array.from(n.children).forEach(pruneEmpty);
            if (!['img', 'input', 'br', 'hr', 'svg', 'textarea', 'button'].includes(n.tagName.toLowerCase()) && n.children.length === 0 && !n.textContent.trim()) {
                if (!n.hasAttribute('id') && !n.className && !Array.from(n.attributes).some(a => a.name.startsWith('data-'))) n.remove();
            }
        }
        pruneEmpty(root);

        return root.innerHTML.replace(/\n\s*\n/g, '\n').replace(/ {4,}/g, '  ').trim();
    }

    // ==========================================
    // 📦 组装与空投下载
    // ==========================================
    function downloadDrop(fileName, cleanedHtml, isPartial = false) {
        if (!fileName) return;
        const safeName = fileName.replace(/[\\/:*?"<>|]/g, '_');

        const systemPrompt = `[系统最高指令：前端自动化防御与规避法则]
你现在是一名顶尖的 Playwright 自动化架构专家。请基于下方提供的 DOM 结构编写代码。
注意：以下 DOM 是我通过特定算法【极度净化】后的骨架，去除了所有样式垃圾。

【战术法则】：
1. 🛡️ 警惕乱码属性，优先寻找稳定的 \`data-*\` 属性或模糊匹配 (\`[class*="xxx"]\`)。
2. 🛡️ 涉及点击动作时，务必考虑使用 \`force=True\` 暴力破甲。
3. ⚠️ 如果在 DOM 中无法找到合理的锚点，绝对不要胡乱编造选择器！请停止输出并要求我提供原始源码。

============= [当前步骤状态：${safeName}] =============\n\`\`\`html\n`;

        const finalContent = systemPrompt + cleanedHtml + "\n```\n";

        const blob = new Blob([finalContent], { type: "text/plain;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `情报_${isPartial ? '局部_' : '全局_'}${safeName}.txt`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    // ==========================================
    // 🎮 武器控制器 (全局监听)
    // ==========================================
    let sniperMode = false;
    let lastHighlighted = null;

    // 🌐 全局提取函数 (供按钮调用)
    function doGlobalExtract() {
        if (sniperMode) return;
        const stepName = prompt("🌐 [全网页洗脱提取]\n请输入当前步骤的名称 (如: 步骤1-初始状态):", "步骤X-全局状态");
        if (stepName) {
            const cleaned = purifyDOM(document.body.outerHTML);
            downloadDrop(stepName, cleaned, false);
        }
    }

    // 🎯 切换狙击模式函数 (供按钮调用)
    function toggleSniper() {
        sniperMode = !sniperMode;
        if (sniperMode) {
            document.body.style.cursor = 'crosshair';
            console.log("🎯 狙击模式开启！请点击目标下拉菜单...");
        } else {
            document.body.style.cursor = 'auto';
            if (lastHighlighted) lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
            console.log("⏹️ 狙击模式已取消。");
        }
    }

    // 🎛️ 注入悬浮按钮 (右上角固定)
    function injectButtons() {
        if (document.getElementById('dom-sniffer-toolbar')) return;
        const toolbar = document.createElement('div');
        toolbar.id = 'dom-sniffer-toolbar';
        toolbar.style.cssText = 'position:fixed;top:12px;right:12px;z-index:2147483647;display:flex;flex-direction:column;gap:6px;font-family:system-ui,sans-serif;';
        const mkBtn = (label, color, fn) => {
            const b = document.createElement('button');
            b.textContent = label;
            b.style.cssText = `padding:8px 14px;font-size:13px;font-weight:600;color:#fff;background:${color};border:none;border-radius:6px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3);white-space:nowrap;`;
            b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); fn(); });
            return b;
        };
        toolbar.appendChild(mkBtn('🌐 全局提取', '#2563eb', doGlobalExtract));
        toolbar.appendChild(mkBtn('🎯 局部狙击', '#dc2626', toggleSniper));
        document.body.appendChild(toolbar);
    }

    // 页面加载完成且 body 存在时注入按钮
    if (document.body) {
        injectButtons();
    } else {
        window.addEventListener('DOMContentLoaded', injectButtons);
    }

    // 拦截点击事件 (狙击模式下专用)
    document.addEventListener('click', function(e) {
        if (!sniperMode) return;
        e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();

        // 解除高亮
        if (lastHighlighted) {
            lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
            lastHighlighted = null;
        }
        sniperMode = false;
        document.body.style.cursor = 'auto';

        // 提取被击中元素的 HTML
        const targetHtml = e.target.outerHTML;
        const stepName = prompt("🎯 [局部狙击成功]\n请输入下拉菜单/元素的步骤名称 (如: 步骤2-选尺寸):", "步骤X-下拉菜单");
        if (stepName) {
            const cleaned = purifyDOM(targetHtml);
            downloadDrop(stepName, cleaned, true);
        }
    }, true);

    // 鼠标移动高亮 (狙击模式下专用)
    document.addEventListener('mouseover', function(e) {
        if (!sniperMode) return;
        if (lastHighlighted && lastHighlighted !== e.target) {
            lastHighlighted.style.outline = lastHighlighted.dataset.oldOutline || '';
        }
        lastHighlighted = e.target;
        if (!e.target.dataset.oldOutline) e.target.dataset.oldOutline = e.target.style.outline || '';
        e.target.style.outline = '3px solid #F44336';
        e.stopPropagation();
    }, true);

    // 快捷键监听
    window.addEventListener('keydown', (e) => {
        // 🚀 Alt + 1：全局无脑提取
        if (e.altKey && (e.code === 'Digit1' || e.key === '1')) {
            e.preventDefault(); e.stopImmediatePropagation();
            doGlobalExtract();
        }

        // 🎯 Alt + 2：下拉菜单/局部狙击提取
        if (e.altKey && (e.code === 'Digit2' || e.key === '2')) {
            e.preventDefault(); e.stopImmediatePropagation();
            toggleSniper();
        }
    }, true);

})();