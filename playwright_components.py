from xai_components.base import InArg, OutArg, Component, xai_component
from playwright.sync_api import sync_playwright
from playwright.sync_api import Page
import queue
import threading

class PlaywrightWorker:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self._playwright = None
        self._browser = None
        self._page = None

    def _run(self):
        self._playwright = sync_playwright().start()
        while True:
            func, args, kwargs, result_queue = self.task_queue.get()
            try:
                result = func(*args, **kwargs)
                result_queue.put((True, result))
            except Exception as e:
                result_queue.put((False, e))

    def run(self, func, *args, **kwargs):
        result_queue = queue.Queue()
        self.task_queue.put((func, args, kwargs, result_queue))
        success, result = result_queue.get()
        if success:
            return result
        else:
            raise result

    def get_playwright(self):
        return self._playwright

    def set_browser(self, browser):
        self._browser = browser

    def get_browser(self):
        return self._browser

    def set_page(self, page):
        self._page = page

    def get_page(self):
        return self._page

global_worker = None

@xai_component
class PlaywrightOpenBrowser(Component):
    """Opens a Playwright browser and navigates to a specified URL using a dedicated worker thread.

    ##### inPorts:
    - url: The URL to visit.
    - headless: Whether to run the browser in headless mode (default: False).

    ##### outPorts:
    - page: The Playwright page instance.
    - browser: The Playwright browser instance.
    - worker: The PlaywrightWorker instance (for reuse in subsequent components).
    """
    url: InArg[str]
    headless: InArg[bool]
    page: OutArg[Page]
    browser: OutArg[any]
    worker: OutArg[any]

    def execute(self, ctx) -> None:
        global global_worker
        if global_worker is None:
            global_worker = PlaywrightWorker()  

        headless_mode = self.headless.value if self.headless.value is not None else False

        def open_browser():
            browser = global_worker.get_playwright().chromium.launch(headless=headless_mode)
            page = browser.new_page()
            page.goto(self.url.value)
            global_worker.set_browser(browser)
            global_worker.set_page(page)
            return (browser, page)

        browser, page = global_worker.run(open_browser)
        self.browser.value = browser
        self.page.value = page
        self.worker.value = global_worker
        ctx["browser"] = browser
        ctx["page"] = page
        print(f"Browser opened and navigated to: {self.url.value} | Headless: {headless_mode}")

@xai_component
class PlaywrightIdentifyElement(Component):
    """
    Identifies an element on the page using one of the locator methods 
    (CSS selector, role with optional name, or label) and returns its locator.

    inPorts:
    - page: The Playwright page instance.
    - selector: The CSS selector for the element (optional).
    - role: The role of the element (optional).
    - name: The accessible name for role (optional).
    - label: The label text (optional).

    outPorts:
    - locator: The identified Playwright locator.
    - out_page: The unchanged Playwright page instance.
    """
    page: InArg[Page]
    selector: InArg[str]
    role: InArg[str]
    name: InArg[str]
    label: InArg[str]
    out_page: OutArg[Page]
    locator: OutArg[any]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        selector_value = self.selector.value if self.selector.value is not None else ""
        role_value = self.role.value if self.role.value is not None else ""
        name_value = self.name.value if self.name.value is not None else ""
        label_value = self.label.value if self.label.value is not None else ""

        if not page_obj:
            raise ValueError("No valid Playwright page instance provided.")

        def identify(p):
            if selector_value:
                try:
                    formatted_selector = selector_value.format(**ctx)
                except Exception as e:
                    raise ValueError(f"Error formatting selector: {selector_value}. Error: {e}")
                print(f"Identifying element using CSS selector: {formatted_selector}")
                return p.locator(formatted_selector)
            elif role_value:
                print(f"Identifying element using role: {role_value} {'with name: ' + name_value if name_value else ''}")
                if name_value:
                    return p.get_by_role(role_value, name=name_value)
                else:
                    return p.get_by_role(role_value)
            elif label_value:
                print(f"Identifying element using label: {label_value}")
                return p.get_by_label(label_value)
            else:
                raise ValueError("Must provide at least one locator method (selector, role, or label).")
        
        result_locator = global_worker.run(identify, page_obj)
        self.locator.value = result_locator
        self.out_page.value = page_obj
        print("Element identified successfully.")

@xai_component
class PlaywrightClickElement(Component):
    """
    Clicks on an element or a specific position on the page.
    Supports double-click and optionally clicking at a specified position without a locator.

    inPorts:
    - page: The Playwright page instance.
    - locator: (Optional) The locator for the element (obtained from IdentifyElement) or a CSS selector string with placeholders.
    - double_click: Boolean indicating if a double-click should be performed (default: False).
    - position: A dictionary specifying the position offset (e.g., {"x": 0, "y": 0}).
                If provided without a locator, it clicks at the specified coordinates on the page.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    double_click: InArg[bool]
    position: InArg[dict]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")

        raw_locator = self.locator.value if self.locator.value is not None else None
        locator_obj = None
        if raw_locator and isinstance(raw_locator, str):
            try:
                formatted_selector = raw_locator.format(**ctx)
            except Exception as e:
                raise ValueError(f"Error in formatting selector: {raw_locator}. Error: {e}")
            locator_obj = page_obj.locator(formatted_selector)
            print(f"Using formatted selector: {formatted_selector}")
        else:
            locator_obj = raw_locator

        double_click_value = self.double_click.value if self.double_click.value is not None else False
        position_value = self.position.value if self.position.value is not None else {}

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")

        def click_action(p):
            if position_value and not locator_obj:
                if double_click_value:
                    p.mouse.dblclick(position_value["x"], position_value["y"])
                    print(f"Double clicked at position {position_value} on the page.")
                else:
                    p.mouse.click(position_value["x"], position_value["y"])
                    print(f"Clicked at position {position_value} on the page.")
            elif locator_obj:
                if position_value:
                    if double_click_value:
                        locator_obj.dblclick(position=position_value)
                        print(f"Double clicked on element at position {position_value}.")
                    else:
                        locator_obj.click(position=position_value)
                        print(f"Clicked on element at position {position_value}.")
                else:
                    if double_click_value:
                        locator_obj.dblclick()
                        print("Double clicked on element.")
                    else:
                        locator_obj.click()
                        print("Clicked on element.")
            else:
                raise ValueError("You must provide either a locator or a valid position dictionary.")

        global_worker.run(click_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightFillInput(Component):
    """
    Fills the identified element with the specified text.
    Supports sequential typing using press_sequentially with an optional delay.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator of the element (from IdentifyElement).
    - text: The text to fill in.
    - sequential: Boolean input; if True, uses press_sequentially (optional, default: False).
    - delay: The delay in milliseconds between key presses when using sequential typing (optional, default: 0).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    text: InArg[str]
    sequential: InArg[bool]
    delay: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        text_value = self.text.value
        sequential_value = self.sequential.value if self.sequential.value is not None else False
        delay_value = self.delay.value if self.delay.value is not None else 0

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def fill_action(p):
            if sequential_value:
                locator_obj.press_sequentially(text_value, delay=delay_value)
                print(f"Typed text sequentially with delay {delay_value}ms on the identified element. Text: {text_value}")
            else:
                locator_obj.fill(text_value)
                print(f"Filled element with text: {text_value}")

        global_worker.run(fill_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightPressKey(Component):
    """
    Presses a specified key on the identified element or on the page globally if no element is specified.

    inPorts:
    - page: The Playwright page instance.
    - locator: (Optional) The locator of the element (from IdentifyElement). If not provided, key press happens globally.
    - key: The key to press (e.g., "Enter", "Tab").

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]  # optional
    key: InArg[str]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value if self.locator.value is not None else None
        key_value = self.key.value

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")
        if not key_value:
            raise ValueError("'key' must be provided.")

        def press_action(p):
            if locator_obj:
                locator_obj.press(key_value)
                print(f"Pressed key: {key_value} on the identified element.")
            else:
                p.keyboard.press(key_value)
                print(f"Pressed key: {key_value} globally on the page.")

        global_worker.run(press_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightHoverElement(Component):
    """
    Hovers over the identified element.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator object obtained from IdentifyElement.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def hover_action(p):
            locator_obj.hover()
            print("Hovered over the identified element.")

        global_worker.run(hover_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightCheckElement(Component):
    """
    Checks a checkbox or radio button if 'to_be_checked' is False (or not provided).
    If 'to_be_checked' is True, it skips performing the check action and only asserts
    that the element is already checked.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator for the element (obtained from IdentifyElement).
    - to_be_checked: Boolean; if True, then do not perform check action, only assert that the element is checked.
      (Default: False)

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[any]
    locator: InArg[any]
    to_be_checked: InArg[bool]
    out_page: OutArg[any]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        to_be_checked_value = self.to_be_checked.value if self.to_be_checked.value is not None else False

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def check_and_assert(p):
            if not to_be_checked_value:
                locator_obj.check()
                print("Performed check action on the element.")
            else:
                print("ℹ️ Skipped check action because 'to_be_checked' is True.")
            p.wait_for_timeout(500)
            if not locator_obj.is_checked():
                raise ValueError("Assertion failed: Element is not checked!")
            print("Assertion passed: Element is checked.")

        global_worker.run(check_and_assert, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightSelectOptions(Component):
    """
    Selects option(s) from a <select> element.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator for the <select> element (obtained from IdentifyElement).
    - options: A list of options to select. (Pass a list even if selecting one option.)
    - by: (Optional) A string indicating the key to use when converting each option.
          For example, "label", "value", or "index". If provided, each option in the list
          will be converted to a dictionary: {by: option}.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    options: InArg[list] 
    by: InArg[str]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        options_value = self.options.value 
        by_value = self.by.value if self.by.value is not None else ""

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def select_action(p):
            if by_value:
                option_list = [{by_value: opt} for opt in options_value]
            else:
                option_list = options_value

            locator_obj.select_option(option_list)
            print(f"Selected options: {option_list} on the identified element.")

        global_worker.run(select_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightUploadFiles(Component):
    """
    Uploads file(s) to a file input element.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator for the file input element (obtained from IdentifyElement).
    - files: A list of file paths to upload.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    files: InArg[list]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        files_list = self.files.value

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def upload_action(p):
            locator_obj.set_input_files(files_list)
            print(f"Uploaded files: {files_list}")

        global_worker.run(upload_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightFocusElement(Component):
    """
    Focuses on an element using its locator.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator for the element (obtained from IdentifyElement).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def focus_action(p):
            locator_obj.focus()
            print("Focused on the identified element.")

        global_worker.run(focus_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightScrolling(Component):
    """
    Scrolls either a specific element or the entire page using different methods.

    inPorts:
    - page: The Playwright page instance.
    - locator: (Optional) The locator for a specific element (obtained from IdentifyElement).
    - method: (Optional) The scrolling method to use. Options:
              "scroll_into_view" - scroll the element into view using scroll_into_view_if_needed().
              "mouse_wheel"     - scroll using the mouse wheel with given offsets.
              "evaluate"        - scroll the element using evaluate() (if locator provided) or the page if not.
              "page_evaluate"   - scroll the entire page using page.evaluate("window.scrollBy(x, y)").
              Defaults to "evaluate" if not provided.
    - x: (Optional) The horizontal scroll offset (default: 0).
    - y: (Optional) The vertical scroll offset (default: 0).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    method: InArg[str]
    x: InArg[int]
    y: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        method_value = self.method.value.lower() if self.method.value is not None else "evaluate"
        x_value = self.x.value if self.x.value is not None else 0
        y_value = self.y.value if self.y.value is not None else 0

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")

        def scroll_action(p):
            if method_value == "scroll_into_view":
                if locator_obj:
                    locator_obj.scroll_into_view_if_needed()
                    print("Scrolled element into view using scroll_into_view_if_needed().")
                else:
                    raise ValueError("'scroll_into_view' method requires a locator.")
            elif method_value == "mouse_wheel":
                if locator_obj:
                    locator_obj.hover()
                p.mouse.wheel(x_value, y_value)
                print(f"Scrolled using mouse wheel by offsets x: {x_value}, y: {y_value}.")
            elif method_value == "evaluate":
                if locator_obj:
                    script = f"e => {{ e.scrollTop += {y_value}; e.scrollLeft += {x_value}; }}"
                    locator_obj.evaluate(script)
                    print(f"Scrolled element using evaluate() with offsets x: {x_value}, y: {y_value}.")
                else:
                    p.evaluate(f"window.scrollBy({x_value}, {y_value})")
                    print(f"Scrolled page using evaluate() with offsets x: {x_value}, y: {y_value}.")
            elif method_value == "page_evaluate":
                p.evaluate(f"window.scrollBy({x_value}, {y_value})")
                print(f"Scrolled page using page_evaluate with offsets x: {x_value}, y: {y_value}.")
            else:
                raise ValueError(f"Unknown scrolling method: {method_value}")

        global_worker.run(scroll_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightDragAndDrop(Component):
    """
    Performs a drag and drop action using the simplified drag_to() method.

    inPorts:
    - page: The Playwright page instance.
    - source: The locator for the element to be dragged (obtained from IdentifyElement).
    - target: The locator for the target element where the item will be dropped (obtained from IdentifyElement).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    source: InArg[any]
    target: InArg[any]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        source_locator = self.source.value
        target_locator = self.target.value

        if not page_obj or not source_locator or not target_locator:
            raise ValueError("Missing page instance or source/target locator.")

        def drag_action(p):
            source_locator.drag_to(target_locator)
            print("Drag and drop action performed using drag_to().")

        global_worker.run(drag_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightTakeScreenshot(Component):
    """
    Captures a screenshot of a specified element or the entire page if no element is specified.

    inPorts:
    - page: The Playwright page instance.
    - file_path: The file path where the screenshot will be saved.
    - full_page: (Optional) Boolean to capture a full-page screenshot when no locator is provided (default: False).
    - locator: (Optional) The locator for the element to capture. If provided, the screenshot will be taken of this element.

    outPorts:
    - page: The updated Playwright page instance.
    - out_path: The file path where the screenshot was saved.
    """
    page: InArg[Page]
    locator: InArg[any]
    file_path: InArg[str]
    full_page: InArg[bool]
    out_page: OutArg[Page]
    out_path: OutArg[str]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        file_path_value = self.file_path.value
        full_page_value = self.full_page.value if self.full_page.value is not None else False
        locator_obj = self.locator.value

        if not page_obj:
            raise ValueError("No valid Playwright page instance provided.")
        if not file_path_value:
            raise ValueError("'file_path' must be provided to save the screenshot.")

        def screenshot_action(p):
            if locator_obj:
                locator_obj.screenshot(path=file_path_value)
                print(f"Screenshot of the element captured and saved to: {file_path_value}")
            else:
                p.screenshot(path=file_path_value, full_page=full_page_value)
                print(f"Screenshot of the page captured and saved to: {file_path_value} | full_page: {full_page_value}")

        global_worker.run(screenshot_action, page_obj)
        self.out_page.value = page_obj
        self.out_path.value = file_path_value


@xai_component
class PlaywrightWaitForElement(Component):
    """
    Waits for the identified element to become visible on the page.

    inPorts:
    - page: The Playwright page instance.
    - locator: The locator for the element (obtained from IdentifyElement).
    - timeout: (Optional) The maximum time in milliseconds to wait for the element to be visible (default: 30000).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    locator: InArg[any]
    timeout: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        locator_obj = self.locator.value
        timeout_value = self.timeout.value if self.timeout.value is not None else 30000

        if not page_obj or not locator_obj:
            raise ValueError("Missing page instance or locator.")

        def wait_action(p):
            locator_obj.wait_for(state="visible", timeout=timeout_value)
            print(f"Element is now visible (waited up to {timeout_value} ms).")

        global_worker.run(wait_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightCloseBrowser(Component):
    """
    Closes the Playwright browser.

    ##### inPorts:
    - page: The Playwright page instance.
    - browser: (Optional) The Playwright browser instance.
      If not provided, it will be retrieved from the context.

    outPorts:
    - (None): This component closes the browser.
    """
    page: InArg[Page]
    browser: InArg[any]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        browser_obj = self.browser.value if self.browser.value is not None else ctx.get("browser")

        if not page_obj or not browser_obj:
            raise ValueError("Missing page instance or browser.")

        def close_action(p):
            browser_obj.close()
            print("Browser closed.")

        global_worker.run(close_action, page_obj)

@xai_component
class PlaywrightWaitForTime(Component):
    """
    Waits for a specified amount of time before proceeding.

    inPorts:
    - time_in_seconds: The number of seconds to wait.

    outPorts:
    - (None): This component simply introduces a delay.
    """
    time_in_seconds: InArg[int]

    def execute(self, ctx) -> None:
        import time

        wait_time = self.time_in_seconds.value if self.time_in_seconds.value is not None else 5
        print(f"Waiting for {wait_time} seconds...")
        time.sleep(wait_time)
        print("Done waiting.")

@xai_component
class PlaywrightWaitForSelector(Component):
    """
    Waits for a selector to appear on the page.

    inPorts:
    - page: The Playwright page instance.
    - selector: The CSS selector to wait for.
    - timeout: (Optional) Maximum wait time in milliseconds (default is 30000 ms = 30 seconds).

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    selector: InArg[str]
    timeout: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker

        page_obj = self.page.value
        selector_value = self.selector.value
        timeout_value = self.timeout.value if self.timeout.value is not None else 30000

        if not page_obj or not selector_value:
            raise ValueError("Page instance and selector must be provided.")

        def wait_selector(p):
            p.wait_for_selector(selector_value, timeout=timeout_value)
            print(f"Selector '{selector_value}' appeared within {timeout_value} ms.")

        global_worker.run(wait_selector, page_obj)

        self.out_page.value = page_obj

@xai_component
class PlaywrightNavigateToURL(Component):
    """
    Navigates to a specified URL using an existing Playwright page instance.

    inPorts:
    - page: The existing Playwright page instance.
    - url: The new URL to navigate to.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    url: InArg[str]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value if self.page.value is not None else ctx.get("page")
        url_value = self.url.value

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")
        if not url_value:
            raise ValueError("URL must be provided.")

        def navigate_action(p):
            p.goto(url_value)
            print(f"Navigated to URL: {url_value}")

        global_worker.run(navigate_action, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightCompileAndRunXircuits(Component):
    """
    Saves, compiles, and runs the current Xircuits workflow.

    inPorts:
    - page: The Playwright page instance.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")

        def compile_and_run(p):
            # Save
            p.locator('jp-button[title="Save (Ctrl+S)"] >>> button').click()
            p.wait_for_timeout(500)

            # Compile
            p.locator('jp-button[title="Compile Xircuits"] >>> button').click()
            p.wait_for_timeout(2000)

            # Compile and Run
            p.locator('jp-button[title="Compile and Run Xircuits"] >>> button').click()
            p.wait_for_timeout(1000)
            p.click("div.jp-Dialog-buttonLabel:has-text('Start')")
            p.wait_for_timeout(1000)
            p.click("div.jp-Dialog-buttonLabel:has-text('Select')")
            p.wait_for_timeout(1000)
            print("Workflow saved, compiled, and running successfully.")

        global_worker.run(compile_and_run, page_obj)
        self.out_page.value = page_obj


@xai_component
class PlaywrightWaitForSplashAndClickXircuitsFile(Component):
    """
    Waits for the JupyterLab splash screen to disappear, then clicks on the 'Xircuits File' button.

    inPorts:
    - page: The Playwright page instance.

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")

        def wait_and_click(p):
            # Wait for splash screen to disappear
            p.wait_for_selector('#jupyterlab-splash', state='detached')
            print("Splash screen disappeared.")

            # Click "Xircuits File"
            p.get_by_text('Xircuits File', exact=True).click()
            print("Clicked 'Xircuits File'.")

        global_worker.run(wait_and_click, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightDragComponentToPosition(Component):
    """
    Drags a component from a library and drops it at a specific position on the Xircuits canvas.

    ##### inPorts:
    - page: The Playwright page object.
    - library_name: The name of the library containing the component.
    - component_name: The name of the component to drag.
    - drop_x: X coordinate on the canvas.
    - drop_y: Y coordinate on the canvas.

    ##### outPorts:
    - page: The updated Playwright page instance.
    """

    page: InArg[Page]
    library_name: InArg[str]
    component_name: InArg[str]
    drop_x: InArg[int]
    drop_y: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker

        page_obj = self.page.value
        library = self.library_name.value
        component = self.component_name.value
        x = self.drop_x.value
        y = self.drop_y.value

        if not page_obj or not library or not component:
            raise ValueError("Page, library name, and component name must be provided.")

        def drag_component(p):
            print(f"Opening library: {library}")
            p.wait_for_selector("[data-id='table-of-contents']")
            p.click("[data-id='table-of-contents']")
            p.wait_for_selector("[data-id='xircuits-component-sidebar']")
            p.click("[data-id='xircuits-component-sidebar']")
            p.get_by_text(library, exact=True).click()
            p.wait_for_timeout(1000)

            print(f"Dragging component: {component} to ({x}, {y})")
            p.evaluate(f"""
            () => {{
              const source = [...document.querySelectorAll("[draggable='true']")]
                .find(el => el.innerText.includes("{component}"));
              const target = document.querySelector(".xircuits-canvas");

              if (!source || !target) {{
                  console.warn("Component or canvas not found.");
                  return;
              }}

              HTMLElement.prototype.dragTo = function(targetElement, x, y) {{
                  const dataTransfer = new DataTransfer();
                  const rect = targetElement.getBoundingClientRect();

                  const clientX = rect.left + x;
                  const clientY = rect.top + y;

                  this.dispatchEvent(new DragEvent('dragstart', {{ dataTransfer, bubbles: true }}));
                  targetElement.dispatchEvent(new DragEvent('dragenter', {{ dataTransfer, bubbles: true, clientX, clientY }}));
                  targetElement.dispatchEvent(new DragEvent('dragover', {{ dataTransfer, bubbles: true, clientX, clientY }}));
                  targetElement.dispatchEvent(new DragEvent('drop', {{ dataTransfer, bubbles: true, clientX, clientY }}));
                  this.dispatchEvent(new DragEvent('dragend', {{ dataTransfer, bubbles: true }}));
              }};

              source.dragTo(target, {x}, {y});
              target.click();
            }}
            """)

        global_worker.run(drag_component, page_obj)
        self.out_page.value = page_obj
        print("Component dragged and dropped successfully.")

@xai_component
class PlaywrightAlignNode(Component):
    """
    Aligns a node (like Start or Finish) relative to a target node on the Xircuits canvas.

    ##### inPorts:
    - page: The Playwright page instance.
    - start_node_name: The name of the node to move (e.g., 'Start').
    - target_node_name: The reference node name.
    - direction: 'left' or 'right' depending on where to place the start node.
    - offset_x: Horizontal offset distance (default 200).

    ##### outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    start_node_name: InArg[str]
    target_node_name: InArg[str]
    direction: InArg[str]
    offset_x: InArg[int]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value
        start_name = self.start_node_name.value
        target_name = self.target_node_name.value
        direction_value = (self.direction.value or 'left').lower()
        offset_x_value = self.offset_x.value if self.offset_x.value is not None else 200

        if not page_obj or not start_name or not target_name:
            raise ValueError("Missing page instance, start_node_name or target_node_name.")

        def align_nodes(p):
            start_node = p.locator(f"div[data-default-node-name='{start_name}']").nth(0)
            target_node = p.locator(f"div[data-default-node-name='{target_name}']").nth(0)

            start_box = start_node.bounding_box()
            target_box = target_node.bounding_box()

            if not start_box or not target_box:
                raise ValueError("Could not find bounding boxes for nodes.")

            target_center_y = target_box['y'] + target_box['height'] / 2

            if direction_value == 'left':
                move_to_x = target_box['x'] - offset_x_value
            elif direction_value == 'right':
                move_to_x = target_box['x'] + target_box['width'] + offset_x_value
            else:
                raise ValueError("direction must be either 'left' or 'right'")

            move_to_y = target_center_y

            start_node.hover()
            p.mouse.down()
            p.mouse.move(move_to_x, move_to_y, steps=10)
            p.mouse.up()

            print(f"Moved {start_name} to the {direction_value} of {target_name} with offset {offset_x_value}.")

        global_worker.run(align_nodes, page_obj)
        self.out_page.value = page_obj

@xai_component
class PlaywrightConnectNodes(Component):
    """
    Connects a port from a source node to a port on a target node in Xircuits canvas.
    
    inPorts:
    - page: The Playwright page instance.
    - source_node: The name of the source node (e.g., "Literal String").
    - source_port: The name of the source port (e.g., "out-0").
    - target_node: The name of the target node (e.g., "Finish").
    - target_port: The name of the target port (e.g., "in-0").

    outPorts:
    - page: The updated Playwright page instance.
    """
    page: InArg[Page]
    source_node: InArg[str]
    source_port: InArg[str]
    target_node: InArg[str]
    target_port: InArg[str]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value

        source_node_value = self.source_node.value
        source_port_value = self.source_port.value
        target_node_value = self.target_node.value
        target_port_value = self.target_port.value

        if not page_obj:
            raise ValueError("Missing Playwright page instance.")

        def connect(p):
            return p.evaluate(f"""
            () => {{
                function getCenter(el) {{
                    const rect = el.getBoundingClientRect();
                    return {{ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }};
                }}

                const sourcePort = document.querySelector("div.node[data-default-node-name='{source_node_value}'] div.port[data-name='{source_port_value}']");
                let targetPort = document.querySelector("div.node[data-default-node-name='{target_node_value}'] div.port[data-name='{target_port_value}']");

                if (!sourcePort || !targetPort) {{
                    console.warn("Source or target port not found.");
                    return false;
                }}

                const from = getCenter(sourcePort);
                const to = getCenter(targetPort);
                const dataTransfer = new DataTransfer();

                function fireEvent(el, type, clientX, clientY) {{
                    const event = new DragEvent(type, {{
                        bubbles: true,
                        cancelable: true,
                        composed: true,
                        clientX: clientX,
                        clientY: clientY,
                        dataTransfer: dataTransfer
                    }});
                    el.dispatchEvent(event);
                }}

                fireEvent(sourcePort, "mousedown", from.x, from.y);
                fireEvent(document, "mousemove", (from.x + to.x) / 2, (from.y + to.y) / 2);
                fireEvent(document, "mousemove", to.x, to.y);
                fireEvent(targetPort, "mouseup", to.x, to.y);

                return true;
            }}
            """)

        result = global_worker.run(connect, page_obj)

        if result:
            print(f"Successfully connected {source_node_value} to {target_node_value}.")
        else:
            print(f"Failed to connect {source_node_value} to {target_node_value}.")

        self.out_page.value = page_obj

