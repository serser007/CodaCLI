import json
import logging
import os
from threading import Thread
from time import sleep

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

from coda_classes import CodaWorkspace, CodaDocument, CodaPage, CodaInteractiveDocument
from coda_exceptions import CodaInvalidApiKeyException
from thread_pool import ThreadPool


class Coda:
    def __init__(self, key: str, max_threads=5):
        self._headers = {"Authorization": f"Bearer {key}"}
        self._cookie_path = "cookie_bar.ck"
        self._threads = 0
        self._pool = ThreadPool(max_threads=max_threads)
        self._sign_in_required = False
        self.__browser = None
        Thread(target=self._sign_in_thread, daemon=True).start()

    @staticmethod
    def _req_method(method, *args, **kwargs):
        res = getattr(requests, method)(*args, **kwargs)
        if res.status_code == 401:
            raise CodaInvalidApiKeyException()
        return res

    @staticmethod
    def _get(*args, **kwargs):
        return Coda._req_method("get", *args, **kwargs)

    @staticmethod
    def _put(*args, **kwargs):
        return Coda._req_method("put", *args, **kwargs)

    def _sign_in_thread(self):
        while True:
            if self._sign_in_required:
                self._sign_in()
                self._sign_in_required = False
            sleep(2)

    def _load_cookies(self, browser):
        browser.get("https://coda.io/")
        browser.delete_all_cookies()
        if os.path.exists(self._cookie_path) and os.path.isfile(self._cookie_path):
            with open(self._cookie_path, "r") as file:
                cookies = json.loads(file.read())
                for cookie in cookies:
                    if "coda.io" in cookie["domain"]:
                        browser.add_cookie(cookie)

    def _save_cookies(self, browser):
        with open(self._cookie_path, "w") as file:
            cookies = browser.get_cookies()
            cookies_json = json.dumps(cookies)
            file.writelines(cookies_json)

    @staticmethod
    def _is_signed(browser):
        uri = "https://coda.io/workspaces"
        browser.get(uri)
        return browser.current_url.startswith(uri)

    def _sign_in(self):
        uri = "https://coda.io/workspaces"
        auth_completed = False
        while not auth_completed:
            try:
                browser = self.prepare_browser()
                if Coda._is_signed(browser):
                    browser.close()
                    break
                browser = self.prepare_browser(False)
                browser.get(uri)
                while not browser.current_url.startswith(uri):
                    sleep(1)
                self._save_cookies(browser)
                browser.close()
                auth_completed = True
            except KeyboardInterrupt as e:
                raise e
            except BaseException as e:
                pass

    def _page_enumerable(self, base_uri, limit=25, **kwargs):
        uri = f"{base_uri}?limit={limit}"
        while uri:
            res = Coda._get(uri, headers=self._headers, params=kwargs).json()
            for item in res["items"]:
                yield item
            token = res.get("nextPageToken", None)
            uri = None
            if token:
                uri = f"{base_uri}?limit={limit}&pageToken={token}"

    def _get_workspace_name(self, workspace_id):
        uri = f"https://coda.io/workspaces/{workspace_id}/docs"
        browser = self.prepare_browser()
        browser.get(uri)
        name = ""
        while name == "":
            name = browser.find_element(By.XPATH, "//h1[@data-coda-ui-id='coda-dashboard-header-title']").text
        browser.close()
        return name

    def prepare_browser(self, headless=True):
        options = Options()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if headless:
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        path = ChromeDriverManager(log_level=logging.FATAL).install()
        service = Service(path, 0, None, None)
        browser = webdriver.Chrome(service=service, options=options)
        self._load_cookies(browser)
        while not Coda._is_signed(browser):
            self._sign_in_required = True
            sleep(5)
            self._load_cookies(browser)
        return browser

    def get_workspaces(self):
        queue = dict()

        def f(doc, index):
            wn = self._get_workspace_name(doc.workspace_id)
            queue[index] = CodaWorkspace(self, id=doc.workspace_id, name=wn)

        used = set()
        idx_nxt = 0
        for document in self.get_documents():
            if document.workspace_id in used:
                continue
            used.add(document.workspace_id)
            self._pool.add_thread(f, (document, idx_nxt))
            idx_nxt += 1

        for i in range(idx_nxt):
            while i not in queue.keys():
                sleep(0.1)
            yield queue[i]

    def get_documents(self, **kwargs):
        uri = f"https://coda.io/apis/v1/docs"
        return map(lambda document: CodaDocument(self, **document), self._page_enumerable(uri, **kwargs))

    def get_document(self, document_id: str):
        uri = f"https://coda.io/apis/v1/docs/{document_id}"
        res = Coda._get(uri, headers=self._headers).json()
        return CodaDocument(self, **res)

    def get_interactive_document(self, document_id: str):
        return CodaInteractiveDocument(self, document_id)

    def get_pages(self, document_id: str):
        uri = f"https://coda.io/apis/v1/docs/{document_id}/pages"
        return map(lambda page: CodaPage(self, document_id=document_id, **page), self._page_enumerable(uri))

    def get_page(self, document_id: str, page_id: str):
        uri = f"https://coda.io/apis/v1/docs/{document_id}/pages/{page_id}"
        res = Coda._get(uri, headers=self._headers).json()
        return CodaPage(self, document_id=document_id, **res)

    def update_page(self, document_id: str, page_id: str, **kwargs):
        uri = f"https://coda.io/apis/v1/docs/{document_id}/pages/{page_id}"
        req = Coda._put(uri, headers=self._headers, json=kwargs)
        return req
