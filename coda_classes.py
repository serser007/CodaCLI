from time import sleep

from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By


class CodaWorkspace:
    def __init__(self, coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)


class CodaPageRef:
    def __init__(self, coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)

    def fetch(self):
        return self._coda.get_page(self.document_id, self.id)


class CodaPage:
    def __init__(self, coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)
        self.browser_id = kwargs.get("browserLink", "-----")[-5:]
        self.children = list(map(
            lambda page: CodaPageRef(coda, document_id=self.document_id, **page),
            kwargs.get("children", [])
        ))

    def update(self, **kwargs):
        return self._coda.update_page(self.document_id, self.id, **kwargs)


class CodaDocument:
    def __init__(self, coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.workspace_id = kwargs.get("workspaceId", None)

    def pages(self):
        return self._coda.get_pages(self.id)


class CodaInteractiveDocument:
    def __init__(self, coda, document_id: str):
        uri = f"https://coda.io/d/document_d{document_id}"
        self._browser = coda.prepare_browser()
        self._browser.get(uri)
        self._get_element(By.CSS_SELECTOR, "div[data-coda-ui-id=page-list-item]")
        self._open_groups()

    def _get_element(self, by: By, locator: str, on_element=None, loop=True):
        if not on_element:
            on_element = self._browser
        while True:
            elements = on_element.find_elements(by, locator)
            if len(elements) > 0:
                return elements[0]
            if not loop:
                return None
            sleep(0.3)

    def _open_groups(self):
        actions = ActionChains(self._browser)
        opened_boxes = set()
        while True:
            opened = 0
            rows = self._browser.find_elements(By.CSS_SELECTOR, "div[data-coda-ui-id=page-list-item]")
            for row in rows:
                boxes = row.find_elements(By.CSS_SELECTOR, "span[data-kr-interactive=true]")
                if len(boxes) == 0:
                    continue
                box = boxes[0]
                class_count = len(box.get_attribute("class").split(' '))
                if class_count == 5 and box not in opened_boxes:
                    opened_boxes.add(box)
                    opened += 1
                    actions.click(box).perform()
                    sleep(0.1)
            if opened == 0:
                break
            sleep(0.5)

    def remove_page(self, page_id):
        actions = ActionChains(self._browser)
        button = self._get_element(By.CSS_SELECTOR, f"a[href$=_{page_id}]", loop=False)
        if not button:
            return
        button = button.find_element(By.CSS_SELECTOR, "div[data-coda-ui-id=page-list-item]")
        actions.context_click(button).perform()
        delete_button = self._get_element(By.CSS_SELECTOR, "span[data-coda-menu-item-id=Delete]")
        actions.click(delete_button).perform()
        sleep(0.2)
        confirm_buttons = self._browser.find_elements(By.CSS_SELECTOR, "span[data-coda-ui-id=confirmButton]")
        if len(confirm_buttons) > 0:
            actions.click(confirm_buttons[0]).perform()
        header = self._browser.find_element(By.CSS_SELECTOR, "div[data-coda-ui-id=canvasHeader")
        actions.click(header).perform()
        sleep(0.1)
