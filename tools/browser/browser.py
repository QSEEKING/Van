"""
浏览器自动化工具 - DEV-003 核心实现

基于 Playwright 提供完整的浏览器自动化能力：
- 页面导航与快照
- 元素交互（点击、输入、悬停等）
- 截图与PDF导出
- JavaScript执行
- 多标签页管理
- 对话框处理
- Cookie管理
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from ..base import BaseTool, ExecutionContext

logger = structlog.get_logger(__name__)

# 延迟导入 Playwright，避免未安装时崩溃
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("playwright_not_available", msg="Install with: pip install playwright && playwright install")


class BrowserAction(Enum):
    """浏览器操作类型"""
    START = "start"
    STOP = "stop"
    OPEN = "open"
    NAVIGATE = "navigate"
    NAVIGATE_BACK = "navigate_back"
    SNAPSHOT = "snapshot"
    SCREENSHOT = "screenshot"
    CLICK = "click"
    TYPE = "type"
    EVAL = "eval"
    EVALUATE = "evaluate"
    RESIZE = "resize"
    CONSOLE_MESSAGES = "console_messages"
    NETWORK_REQUESTS = "network_requests"
    HANDLE_DIALOG = "handle_dialog"
    FILE_UPLOAD = "file_upload"
    FILL_FORM = "fill_form"
    INSTALL = "install"
    PRESS_KEY = "press_key"
    RUN_CODE = "run_code"
    DRAG = "drag"
    HOVER = "hover"
    SELECT_OPTION = "select_option"
    TABS = "tabs"
    WAIT_FOR = "wait_for"
    PDF = "pdf"
    CLOSE = "close"
    COOKIES_GET = "cookies_get"
    COOKIES_SET = "cookies_set"
    COOKIES_CLEAR = "cookies_clear"
    CONNECT_CDP = "connect_cdp"
    LIST_CDP_TARGETS = "list_cdp_targets"
    CLEAR_BROWSER_CACHE = "clear_browser_cache"


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    viewport_width: int = 1280
    viewport_height: int = 720
    default_timeout: int = 30000  # ms
    slow_mo: int = 0  # 减慢操作速度(ms)
    locale: str = "en-US"
    timezone: str = "America/New_York"
    user_agent: str | None = None
    ignore_https_errors: bool = False
    downloads_path: str | None = None


@dataclass
class PageSnapshot:
    """页面快照信息"""
    url: str
    title: str
    html: str
    screenshot: str | None = None  # base64
    elements: list[dict[str, Any]] = field(default_factory=list)
    console_messages: list[dict[str, Any]] = field(default_factory=list)
    network_requests: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class BrowserSession:
    """浏览器会话状态"""
    session_id: str
    config: BrowserConfig
    browser: Any = None  # Browser
    context: Any = None  # BrowserContext
    pages: dict[str, Any] = field(default_factory=dict)  # page_id -> Page
    active_page_id: str = "default"
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


class BrowserTool(BaseTool):
    """
    浏览器自动化工具
    
    支持的 Actions:
    - start: 启动浏览器
    - stop: 关闭浏览器
    - open: 打开URL
    - snapshot: 获取页面快照
    - click: 点击元素
    - type: 输入文本
    - screenshot: 截图
    - evaluate: 执行JS
    等等...
    """

    name = "browser_use"
    description = (
        "Control browser (Playwright). Default is headless. "
        "Supports navigation, interaction, screenshots, JavaScript execution, "
        "multi-tab management, dialog handling, and cookie management."
    )
    requires_sandbox = False  # 浏览器操作不需要沙箱
    timeout = 60

    def __init__(self, config: BrowserConfig | None = None):
        super().__init__()
        self.config = config or BrowserConfig()
        self._sessions: dict[str, BrowserSession] = {}
        self._playwright = None
        self._lock = asyncio.Lock()

    def get_schema(self) -> dict[str, Any]:
        """返回工具参数 Schema"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [a.value for a in BrowserAction],
                    "description": "Browser action to perform"
                },
                "url": {
                    "type": "string",
                    "description": "URL for open/navigate actions"
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element"
                },
                "ref": {
                    "type": "string",
                    "description": "Element reference from snapshot"
                },
                "text": {
                    "type": "string",
                    "description": "Text to type"
                },
                "code": {
                    "type": "string",
                    "description": "JavaScript code to execute"
                },
                "page_id": {
                    "type": "string",
                    "default": "default",
                    "description": "Page/tab identifier"
                },
                "headed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show visible browser window"
                },
                "width": {
                    "type": "integer",
                    "description": "Viewport width"
                },
                "height": {
                    "type": "integer",
                    "description": "Viewport height"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30000,
                    "description": "Timeout in milliseconds"
                },
                "wait": {
                    "type": "integer",
                    "default": 0,
                    "description": "Wait time after action (ms)"
                },
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g., 'Enter', 'Control+a')"
                },
                "submit": {
                    "type": "boolean",
                    "default": False,
                    "description": "Submit form after typing"
                },
                "slowly": {
                    "type": "boolean",
                    "default": False,
                    "description": "Type character by character"
                },
                "double_click": {
                    "type": "boolean",
                    "default": False,
                    "description": "Perform double-click"
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                    "description": "Mouse button for click"
                },
                "path": {
                    "type": "string",
                    "description": "File path for screenshot/PDF save"
                },
                "full_page": {
                    "type": "boolean",
                    "default": False,
                    "description": "Capture full page screenshot"
                },
                "accept": {
                    "type": "boolean",
                    "default": True,
                    "description": "Accept or dismiss dialog"
                },
                "prompt_text": {
                    "type": "string",
                    "description": "Text for prompt dialog"
                },
                "fields_json": {
                    "type": "string",
                    "description": "JSON object for form fields"
                },
                "wait_time": {
                    "type": "number",
                    "description": "Wait time in seconds"
                },
                "wait_for": {
                    "type": "string",
                    "description": "Wait for text/selector"
                },
                "cdp_port": {
                    "type": "integer",
                    "description": "CDP debug port"
                },
                "cdp_url": {
                    "type": "string",
                    "description": "CDP URL for connect"
                },
            },
            "required": ["action"]
        }

    async def execute(self, ctx: ExecutionContext, **kwargs: Any) -> Any:
        """执行浏览器操作"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. "
                "Install with: pip install playwright && playwright install"
            )

        action_str = kwargs.get("action", "")
        try:
            action = BrowserAction(action_str)
        except ValueError:
            return {"error": f"Unknown action: {action_str}"}

        # 路由到对应的处理方法
        handler = getattr(self, f"_handle_{action.value}", None)
        if handler:
            return await handler(ctx, **kwargs)
        else:
            raise ValueError(f"Handler not implemented for action: {action}")

    # ─── 浏览器生命周期 ──────────────────────────────────────────────────────

    async def _handle_start(
        self,
        ctx: ExecutionContext,
        headed: bool = False,
        cdp_port: int = 0,
        **kwargs
    ) -> dict[str, Any]:
        """启动浏览器"""
        async with self._lock:
            session_id = ctx.session_id

            if session_id in self._sessions:
                return {"status": "already_running", "session_id": session_id}

            # 初始化 Playwright
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            # 选择浏览器类型
            browser_launcher = getattr(self._playwright, self.config.browser_type)

            # 启动参数
            launch_args = {
                "headless": not headed,
                "args": []
            }

            if cdp_port > 0:
                launch_args["args"].append(f"--remote-debugging-port={cdp_port}")

            browser = await browser_launcher.launch(**launch_args)

            # 创建上下文
            context = await browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height
                },
                locale=self.config.locale,
                timezone_id=self.config.timezone,
                user_agent=self.config.user_agent,
                ignore_https_errors=self.config.ignore_https_errors,
            )

            # 创建默认页面
            page = await context.new_page()
            page.set_default_timeout(self.config.default_timeout)

            session = BrowserSession(
                session_id=session_id,
                config=self.config,
                browser=browser,
                context=context,
                pages={"default": page}
            )
            self._sessions[session_id] = session

            return {
                "status": "started",
                "session_id": session_id,
                "browser_type": self.config.browser_type,
                "headless": not headed
            }

    async def _handle_stop(self, ctx: ExecutionContext, **kwargs) -> dict[str, Any]:
        """关闭浏览器"""
        session_id = ctx.session_id
        session = self._sessions.get(session_id)

        if not session:
            return {"status": "not_running"}

        await session.browser.close()
        del self._sessions[session_id]

        return {"status": "stopped", "session_id": session_id}

    async def _get_session(self, ctx: ExecutionContext) -> BrowserSession:
        """获取或创建会话"""
        session_id = ctx.session_id
        if session_id not in self._sessions:
            # 自动启动
            await self._handle_start(ctx)
        return self._sessions[session_id]

    async def _get_page(self, ctx: ExecutionContext, page_id: str = "default") -> tuple[BrowserSession, Page]:
        """获取页面"""
        session = await self._get_session(ctx)
        if page_id not in session.pages:
            # 创建新标签页
            page = await session.context.new_page()
            page.set_default_timeout(self.config.default_timeout)
            session.pages[page_id] = page
        return session, session.pages[page_id]

    # ─── 页面操作 ────────────────────────────────────────────────────────────

    async def _handle_open(
        self,
        ctx: ExecutionContext,
        url: str = "",
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """打开URL"""
        if not url:
            return {"error": "URL is required"}

        session, page = await self._get_page(ctx, page_id)
        await page.goto(url)

        return {
            "status": "opened",
            "url": page.url,
            "title": await page.title()
        }

    async def _handle_navigate(
        self,
        ctx: ExecutionContext,
        url: str = "",
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """导航到URL"""
        return await self._handle_open(ctx, url, page_id, **kwargs)

    async def _handle_navigate_back(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """返回上一页"""
        session, page = await self._get_page(ctx, page_id)
        await page.go_back()
        return {"status": "navigated_back", "url": page.url}

    async def _handle_snapshot(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """获取页面快照，包含元素引用"""
        session, page = await self._get_page(ctx, page_id)

        # 获取页面信息
        url = page.url
        title = await page.title()

        # 获取交互元素
        elements = await self._extract_interactive_elements(page)

        # 获取 HTML 片段
        html = await page.evaluate("""
            () => {
                const body = document.body;
                return body ? body.innerHTML.substring(0, 50000) : '';
            }
        """)

        return {
            "url": url,
            "title": title,
            "elements": elements,
            "html_preview": html[:5000],  # 截断预览
            "page_id": page_id
        }

    async def _extract_interactive_elements(self, page: Page) -> list[dict[str, Any]]:
        """提取页面上可交互的元素"""
        selector = "a, button, input, select, textarea, [role='button'], [role='link'], [onclick], [tabindex]"
        elements = await page.query_selector_all(selector)

        result = []
        for i, el in enumerate(elements[:100]):  # 最多100个元素
            try:
                is_visible = await el.is_visible()
                if not is_visible:
                    continue

                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                text = await el.inner_text()
                attrs = await el.evaluate("""
                    el => ({
                        id: el.id,
                        className: el.className,
                        name: el.name,
                        type: el.type,
                        placeholder: el.placeholder,
                        value: el.value,
                        href: el.href,
                        ariaLabel: el.getAttribute('aria-label')
                    })
                """)

                # 生成引用
                ref = f"e{i}"

                result.append({
                    "ref": ref,
                    "tag": tag,
                    "text": text[:100] if text else "",
                    "attrs": attrs,
                    "selector": self._generate_selector(el, i)
                })
            except Exception:
                continue

        return result

    def _generate_selector(self, element, index: int) -> str:
        """生成CSS选择器"""
        # 简化版，实际应更智能
        return f"[data-ref='e{index}']"

    async def _handle_screenshot(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        path: str = "",
        full_page: bool = False,
        screenshot_type: str = "png",
        **kwargs
    ) -> dict[str, Any]:
        """截图"""
        session, page = await self._get_page(ctx, page_id)

        options = {
            "type": screenshot_type,
            "full_page": full_page
        }

        if path:
            await page.screenshot(path=path, **options)
            return {"status": "saved", "path": path}
        else:
            buffer = await page.screenshot(**options)
            b64 = base64.b64encode(buffer).decode()
            return {
                "status": "captured",
                "data": b64,
                "type": screenshot_type
            }

    async def _handle_pdf(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        path: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """导出PDF"""
        session, page = await self._get_page(ctx, page_id)

        if not path:
            path = f"/tmp/page_{int(time.time())}.pdf"

        await page.pdf(path=path)
        return {"status": "exported", "path": path}

    # ─── 元素交互 ────────────────────────────────────────────────────────────

    async def _handle_click(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        selector: str = "",
        ref: str = "",
        button: str = "left",
        double_click: bool = False,
        wait: int = 0,
        **kwargs
    ) -> dict[str, Any]:
        """点击元素"""
        session, page = await self._get_page(ctx, page_id)

        target = selector or f"[data-ref='{ref}']"
        element = await page.wait_for_selector(target, timeout=5000)

        if double_click:
            await element.dblclick(button=button)
        else:
            await element.click(button=button)

        if wait > 0:
            await page.wait_for_timeout(wait)

        return {"status": "clicked", "selector": target}

    async def _handle_type(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        selector: str = "",
        ref: str = "",
        text: str = "",
        slowly: bool = False,
        submit: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """输入文本"""
        session, page = await self._get_page(ctx, page_id)

        target = selector or f"[data-ref='{ref}']"
        element = await page.wait_for_selector(target, timeout=5000)

        if slowly:
            await element.type(text, delay=50)
        else:
            await element.fill(text)

        if submit:
            await element.press("Enter")

        return {"status": "typed", "text": text[:50]}

    async def _handle_press_key(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        key: str = "Enter",
        **kwargs
    ) -> dict[str, Any]:
        """按键"""
        session, page = await self._get_page(ctx, page_id)
        await page.keyboard.press(key)
        return {"status": "pressed", "key": key}

    async def _handle_hover(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        selector: str = "",
        ref: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """悬停"""
        session, page = await self._get_page(ctx, page_id)
        target = selector or f"[data-ref='{ref}']"
        await page.hover(target)
        return {"status": "hovered", "selector": target}

    async def _handle_drag(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        start_selector: str = "",
        end_selector: str = "",
        start_ref: str = "",
        end_ref: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """拖拽"""
        session, page = await self._get_page(ctx, page_id)

        source = start_selector or f"[data-ref='{start_ref}']"
        target = end_selector or f"[data-ref='{end_ref}']"

        await page.drag_and_drop(source, target)
        return {"status": "dragged", "from": source, "to": target}

    async def _handle_select_option(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        selector: str = "",
        values_json: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """选择下拉选项"""
        session, page = await self._get_page(ctx, page_id)
        values = json.loads(values_json) if values_json else []
        await page.select_option(selector, values)
        return {"status": "selected", "values": values}

    # ─── JavaScript 执行 ──────────────────────────────────────────────────────

    async def _handle_eval(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        code: str = "",
        selector: str = "",
        ref: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """执行 JavaScript"""
        session, page = await self._get_page(ctx, page_id)

        if selector or ref:
            target = selector or f"[data-ref='{ref}']"
            element = await page.wait_for_selector(target, timeout=5000)
            result = await element.evaluate(code)
        else:
            result = await page.evaluate(code)

        return {"status": "executed", "result": result}

    async def _handle_evaluate(self, ctx: ExecutionContext, **kwargs) -> dict[str, Any]:
        """evaluate 是 eval 的别名"""
        return await self._handle_eval(ctx, **kwargs)

    async def _handle_run_code(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        code: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """运行代码块"""
        return await self._handle_eval(ctx, page_id=page_id, code=code)

    # ─── 对话框处理 ──────────────────────────────────────────────────────────

    async def _handle_handle_dialog(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        accept: bool = True,
        prompt_text: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """处理对话框"""
        session, page = await self._get_page(ctx, page_id)

        dialog_handled = False

        async def on_dialog(dialog):
            nonlocal dialog_handled
            dialog_handled = True
            if dialog.type == "prompt" and prompt_text:
                await dialog.accept(prompt_text)
            elif accept:
                await dialog.accept()
            else:
                await dialog.dismiss()

        page.on("dialog", on_dialog)

        # 等待对话框
        await page.wait_for_timeout(1000)

        return {"status": "dialog_handled" if dialog_handled else "no_dialog"}

    # ─── 表单操作 ──────────────────────────────────────────────────────────────

    async def _handle_fill_form(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        fields_json: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """填充表单"""
        session, page = await self._get_page(ctx, page_id)

        fields = json.loads(fields_json) if fields_json else {}
        filled = []

        for field_name, value in fields.items():
            try:
                await page.fill(f"[name='{field_name}']", str(value))
                filled.append(field_name)
            except Exception as e:
                logger.warning("fill_form_field_error", field=field_name, error=str(e))

        return {"status": "filled", "fields": filled}

    async def _handle_file_upload(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        selector: str = "",
        paths_json: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """文件上传"""
        session, page = await self._get_page(ctx, page_id)

        paths = json.loads(paths_json) if paths_json else []
        element = await page.wait_for_selector(selector, timeout=5000)

        await element.set_input_files(paths)

        return {"status": "uploaded", "files": paths}

    # ─── 标签页管理 ────────────────────────────────────────────────────────────

    async def _handle_tabs(
        self,
        ctx: ExecutionContext,
        tab_action: str = "list",
        index: int = -1,
        **kwargs
    ) -> dict[str, Any]:
        """标签页管理"""
        session = await self._get_session(ctx)

        if tab_action == "list":
            pages = session.context.pages
            return {
                "tabs": [
                    {"id": f"tab_{i}", "url": p.url}
                    for i, p in enumerate(pages)
                ]
            }
        elif tab_action == "new":
            page = await session.context.new_page()
            page_id = f"tab_{len(session.pages)}"
            session.pages[page_id] = page
            return {"status": "created", "page_id": page_id}
        elif tab_action == "close" and index >= 0:
            pages = session.context.pages
            if index < len(pages):
                await pages[index].close()
                return {"status": "closed", "index": index}
        elif tab_action == "select" and index >= 0:
            pages = session.context.pages
            if index < len(pages):
                pages[index].bring_to_front()
                return {"status": "selected", "index": index}

        return {"status": "unknown_action"}

    # ─── 等待 ──────────────────────────────────────────────────────────────────

    async def _handle_wait_for(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        wait_time: float = 0,
        text: str = "",
        text_gone: str = "",
        selector: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """等待"""
        session, page = await self._get_page(ctx, page_id)

        if wait_time > 0:
            await page.wait_for_timeout(int(wait_time * 1000))
        elif text:
            await page.wait_for_selector(f"text={text}")
        elif text_gone:
            await page.wait_for_selector(f"text={text_gone}", state="hidden")
        elif selector:
            await page.wait_for_selector(selector)

        return {"status": "waited"}

    # ─── Cookie 管理 ──────────────────────────────────────────────────────────

    async def _handle_cookies_get(
        self,
        ctx: ExecutionContext,
        url: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """获取 Cookies"""
        session = await self._get_session(ctx)
        cookies = await session.context.cookies(url if url else None)
        return {"cookies": cookies}

    async def _handle_cookies_set(
        self,
        ctx: ExecutionContext,
        fields_json: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """设置 Cookies"""
        session = await self._get_session(ctx)
        cookies = json.loads(fields_json) if fields_json else []
        await session.context.add_cookies(cookies)
        return {"status": "cookies_set", "count": len(cookies)}

    async def _handle_cookies_clear(
        self,
        ctx: ExecutionContext,
        **kwargs
    ) -> dict[str, Any]:
        """清除 Cookies"""
        session = await self._get_session(ctx)
        await session.context.clear_cookies()
        return {"status": "cookies_cleared"}

    # ─── 控制台和网络 ────────────────────────────────────────────────────────

    async def _handle_console_messages(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        level: str = "info",
        **kwargs
    ) -> dict[str, Any]:
        """获取控制台消息"""
        session, page = await self._get_page(ctx, page_id)
        # 这里需要页面级别监听，简化处理
        return {"messages": [], "note": "Console messages require page-level listener"}

    async def _handle_network_requests(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        include_static: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """获取网络请求"""
        session, page = await self._get_page(ctx, page_id)
        return {"requests": [], "note": "Network requests require page-level listener"}

    # ─── 视口调整 ─────────────────────────────────────────────────────────────

    async def _handle_resize(
        self,
        ctx: ExecutionContext,
        width: int = 1280,
        height: int = 720,
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """调整视口大小"""
        session, page = await self._get_page(ctx, page_id)
        await page.set_viewport_size({"width": width, "height": height})
        return {"status": "resized", "width": width, "height": height}

    # ─── CDP 连接 ─────────────────────────────────────────────────────────────

    async def _handle_connect_cdp(
        self,
        ctx: ExecutionContext,
        cdp_url: str = "",
        **kwargs
    ) -> dict[str, Any]:
        """连接到 CDP 端点"""
        if not cdp_url:
            return {"error": "CDP URL is required"}

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser = await self._playwright.chromium.connect_over_cdp(cdp_url)

        session_id = ctx.session_id
        session = BrowserSession(
            session_id=session_id,
            config=self.config,
            browser=browser,
            context=browser.contexts[0] if browser.contexts else await browser.new_context()
        )
        self._sessions[session_id] = session

        return {"status": "connected", "cdp_url": cdp_url}

    async def _handle_list_cdp_targets(
        self,
        ctx: ExecutionContext,
        port: int = 0,
        port_min: int = 9000,
        port_max: int = 10000,
        **kwargs
    ) -> dict[str, Any]:
        """列出 CDP 目标"""
        import aiohttp

        targets = []

        if port > 0:
            ports = [port]
        else:
            ports = range(port_min, port_max + 1)

        for p in ports:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://localhost:{p}/json/list", timeout=0.5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            targets.extend([
                                {"port": p, **t} for t in data
                            ])
            except Exception:
                pass

        return {"targets": targets}

    # ─── 缓存清理 ────────────────────────────────────────────────────────────

    async def _handle_clear_browser_cache(
        self,
        ctx: ExecutionContext,
        page_id: str = "default",
        **kwargs
    ) -> dict[str, Any]:
        """清除浏览器缓存"""
        session, page = await self._get_page(ctx, page_id)

        client = await session.context.new_cdp_session(page)
        await client.send("Network.clearBrowserCache")

        return {"status": "cache_cleared"}

    # ─── 安装浏览器 ──────────────────────────────────────────────────────────

    async def _handle_install(self, ctx: ExecutionContext, **kwargs) -> dict[str, Any]:
        """安装浏览器（需要系统命令）"""
        return {
            "status": "manual_action_required",
            "message": "Run: playwright install chromium"
        }
