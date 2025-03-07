from argparse import ArgumentParser
from xai_components.base import SubGraphExecutor, InArg, OutArg, Component, xai_component, parse_bool
from xai_components.xai_playwright.playwright_components import PlaywrightClickElement, PlaywrightOpenBrowser, PlaywrightIdentifyElement, PlaywrightPressKey, PlaywrightFillInput, PlaywrightScrolling, PlaywrightCloseBrowser, PlaywrightWaitForTime, PlaywrightTakeScreenshot

@xai_component(type='xircuits_workflow')
class PlaywrightSample(Component):

    def __init__(self):
        super().__init__()
        self.__start_nodes__ = []
        self.c_0 = PlaywrightIdentifyElement()
        self.c_1 = PlaywrightOpenBrowser()
        self.c_2 = PlaywrightTakeScreenshot()
        self.c_3 = PlaywrightScrolling()
        self.c_4 = PlaywrightClickElement()
        self.c_5 = PlaywrightIdentifyElement()
        self.c_6 = PlaywrightFillInput()
        self.c_7 = PlaywrightPressKey()
        self.c_8 = PlaywrightCloseBrowser()
        self.c_9 = PlaywrightWaitForTime()
        self.c_0.page.connect(self.c_2.out_page)
        self.c_0.role.value = 'button'
        self.c_0.name.value = 'Search BBC'
        self.c_1.url.value = 'https://www.bbc.com/'
        self.c_2.page.connect(self.c_3.out_page)
        self.c_2.file_path.value = 'Image.png'
        self.c_3.page.connect(self.c_1.page)
        self.c_3.y.value = 3000
        self.c_4.page.connect(self.c_0.out_page)
        self.c_4.locator.connect(self.c_0.locator)
        self.c_5.page.connect(self.c_4.out_page)
        self.c_5.role.value = 'textbox'
        self.c_5.name.value = 'Search News'
        self.c_6.page.connect(self.c_5.out_page)
        self.c_6.locator.connect(self.c_5.locator)
        self.c_6.text.value = 'Tokyo'
        self.c_7.page.connect(self.c_6.out_page)
        self.c_7.key.value = 'Enter'
        self.c_8.page.connect(self.c_7.out_page)
        self.c_9.time_in_seconds.value = 3
        self.c_0.next = self.c_4
        self.c_1.next = self.c_3
        self.c_2.next = self.c_0
        self.c_3.next = self.c_2
        self.c_4.next = self.c_5
        self.c_5.next = self.c_6
        self.c_6.next = self.c_7
        self.c_7.next = self.c_9
        self.c_8.next = None
        self.c_9.next = self.c_8

    def execute(self, ctx):
        for node in self.__start_nodes__:
            if hasattr(node, 'init'):
                node.init(ctx)
        next_component = self.c_1
        while next_component is not None:
            next_component = next_component.do(ctx)

def main(args):
    import pprint
    ctx = {}
    ctx['args'] = args
    flow = PlaywrightSample()
    flow.next = None
    flow.do(ctx)
if __name__ == '__main__':
    parser = ArgumentParser()
    args, _ = parser.parse_known_args()
    main(args)
    print('\nFinished Executing')