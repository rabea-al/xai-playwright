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
        page_obj = self.page.value
        selector_value = self.selector.value if self.selector.value is not None else ""
        role_value = self.role.value if self.role.value is not None else ""
        name_value = self.name.value if self.name.value is not None else ""
        label_value = self.label.value if self.label.value is not None else ""

        if not page_obj:
            raise ValueError("No valid Playwright page instance provided.")

        def identify(p):
            if selector_value:
                print(f"Identifying element using CSS selector: {selector_value}")
                return p.locator(selector_value)
            elif role_value:
                print(f"Identifying element using role: {role_value} {f'with name: {name_value}' if name_value else ''}")
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
    - locator: (Optional) The locator for the element (obtained from IdentifyElement).
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
        page_obj = self.page.value
        locator_obj = self.locator.value if self.locator.value is not None else None
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
        page_obj = self.page.value
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
    locator: InArg[any]  # Now optional
    key: InArg[str]
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
    """
    page: InArg[Page]
    file_path: InArg[str]
    full_page: InArg[bool]
    locator: InArg[any]  
    out_page: OutArg[Page]

    def execute(self, ctx) -> None:
        global global_worker
        page_obj = self.page.value
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
        page_obj = self.page.value
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
        page_obj = self.page.value
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
