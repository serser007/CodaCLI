# CodaCLI
The command line interface for Coda (https://coda.io)

You will need to provide API KEY from your account settings on first sturtup.


### Currently supported features:

    - help                            help page
    - list-ws                         list all workspaces (id & name)
    - list-doc                        list all docs (id & name)
    - list-doc <ws-id>                list all docs in workspace <ws-id> (id & name)
    - rename_pages <doc-id> <prefix>  adds prefix <prefix> to all pages in document <doc-id>
    - remove-pages <doc-id> <prefix>  removes pages with prefix <prefix> from document <doc-id>
