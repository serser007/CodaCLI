from time import sleep
import os
import sys
import logging

from coda import Coda
from coda_classes import CodaPageRef
from coda_exceptions import CodaInvalidApiKeyException
from thread_pool import ThreadPool

logging.basicConfig(level=logging.FATAL)

GLOBAL_THREAD_POOL = ThreadPool()
APIKEY_PATH = "apikey.key"


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
