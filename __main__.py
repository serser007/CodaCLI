import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from time import sleep
import os
import json
import sys
import logging
from threading import Thread
from collections import deque

logging.basicConfig(level=logging.FATAL)


class ThreadPool(Thread):
    def __init__(self, max_threads=10, max_awaiting=10):
        super(ThreadPool, self).__init__(daemon=True)
        self._max_threads = max_threads
        self._threads = 0
        self._actions = deque()
        self._tags = dict()
        self._max_awaiting = max_awaiting
        super().start()

    def _f(self, f):
        try:
            f[0](*f[1])
        except:
            pass

        self._tags[f[2]] -= 1
        self._threads -= 1

    def count(self, tag=""):
        if tag not in self._tags.keys():
            return 0
        return self._tags[tag]

    def run(self):
        while True:
            while self._threads < self._max_threads and len(self._actions) > 0:
                self._threads += 1
                action = self._actions.pop()
                thread = Thread(target=self._f, args=[action], daemon=True)
                thread.start()

    def add_thread(self, f, args=(), tag=""):
        if tag not in self._tags.keys():
            self._tags[tag] = 1
        else:
            self._tags[tag] += 1
        self._actions.append((f, args, tag))

        while len(self._actions) == self._max_awaiting:
            sleep(0.1)


class CodaInvalidApiKeyException(Exception):
    pass


class Coda:
    def __init__(self, key: str, max_threads=10):
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

    def _prepare_browser(self, headless=True):
        options = Options()
        # options.binary_location = "./chrome/chrome.exe"
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if headless:
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
        path = ChromeDriverManager(log_level=logging.FATAL).install()
        service = Service(path, 0, None, None)
        browser = webdriver.Chrome(service=service, options=options)
        self._load_cookies(browser)
        return browser

    def _sign_in(self):
        uri = "https://coda.io/workspaces"
        auth_completed = False
        while not auth_completed:
            try:
                browser = self._prepare_browser()
                browser.get(uri)
                if browser.current_url.startswith(uri):
                    browser.close()
                    break
                browser = self._prepare_browser(False)
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
        browser = self._prepare_browser()
        browser.get(uri)
        while browser.current_url != uri:
            self._sign_in_required = True
            sleep(5)
            self._load_cookies(browser)
            browser.get(uri)

        name = ""
        while name == "":
            name = browser.find_element(By.XPATH, "//h1[@data-coda-ui-id='coda-dashboard-header-title']").text
        browser.close()
        return name

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


class CodaWorkspace:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)


class CodaPageRef:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)

    def fetch(self):
        return self._coda.get_page(self.document_id, self.id)


class CodaPage:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)
        self.children = list(map(
            lambda page: CodaPageRef(coda, document_id=self.document_id, **page),
            kwargs.get("children", [])
        ))

    def update(self, **kwargs):
        self._coda.update_page(self.document_id, self.id, **kwargs)


class CodaDocument:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.workspace_id = kwargs.get("workspaceId", None)

    def pages(self):
        return self._coda.get_pages(self.id)


def rename_page(page, prefix):
    if isinstance(page, CodaPageRef):
        page = page.fetch()

    def f():
        page.update(name=f"{prefix}{page.name}")
        print(".", end='')
        sys.stdout.flush()

    GLOBAL_THREAD_POOL.add_thread(f, tag="RP")
    for child in page.children:
        GLOBAL_THREAD_POOL.add_thread(rename_page, (child, prefix), "RP")


def rename_pages(pages, prefix):
    print("Renaming")
    for page in pages:
        GLOBAL_THREAD_POOL.add_thread(rename_page, (page, prefix), "RP")
    while GLOBAL_THREAD_POOL.count("RP") > 0:
        sleep(1)
    print("\n--- Done!")


def list_documents(documents, workspace_id=None):
    print("Documents:")
    for document in documents:
        if not workspace_id or workspace_id == document.workspace_id:
            print(f"({document.id}) {document.name}")
    print("--- Done!")


def list_workspaces(workspaces):
    print("Workspaces:")
    for workspace in workspaces:
        print(f"({workspace.id}) {workspace.name}")
    print("--- Done!")


def print_help():
    print("""
    Help
    - help:                           this page
    - list-ws:                        list all workspaces
    - list-doc:                       list all docs
    - list-doc <ws-id>:               list all docs in workspace <ws-id>
    - rename_pages <doc-id> <prefix>: adds prefix <prefix> to all pages in document <doc-id>
    """)


def print_error():
    print("Unknown command. Please use 'help'")


GLOBAL_THREAD_POOL = ThreadPool()
APIKEY_PATH = "apikey.key"

if __name__ == "__main__":
    api_key = None
    if os.path.exists(APIKEY_PATH) and os.path.isfile(APIKEY_PATH):
        with open(APIKEY_PATH, "r") as file:
            api_key = file.read()

    if not api_key:
        api_key = input("API KEY: ")
        with open(APIKEY_PATH, "w") as file:
            file.write(api_key)

    coda = Coda(api_key)

    try:
        len_args = len(sys.argv)
        if len_args > 1:
            cmd = sys.argv[1]
            if cmd == "list-ws" and len_args == 2:
                list_workspaces(coda.get_workspaces())
            elif cmd == "list-doc" and len_args == 2:
                list_documents(coda.get_documents())
            elif cmd == "list-doc" and len_args == 3:
                list_documents(coda.get_documents(workspaceId=sys.argv[2]))
            elif cmd == "rename_pages" and len_args == 4:
                rename_pages(coda.get_pages(sys.argv[2]), sys.argv[3])
            elif cmd == "help" and len_args == 2:
                print_help()
            else:
                print_error()
        else:
            print_help()
    except CodaInvalidApiKeyException as e:
        print("Api key is invalid. Provide the new one")
        if os.path.isfile(APIKEY_PATH):
            os.remove(APIKEY_PATH)
    except:
        pass
