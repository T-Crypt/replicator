# Security

## Report a vulnerability

Report it privately through GitHub: open the **Security** tab of
[T-Crypt/replicator](https://github.com/T-Crypt/replicator) and choose **Report a vulnerability**.
Do not open a public issue for it. Include the file or program that triggers it and the command you ran.

## What Replicator trusts

Replicator runs on your machine with your user's permissions. The table lists each input from outside and what
the code does with it.

| Input | Handling |
|---|---|
| Imported models and archives | Archives unpack into a new, empty folder. An entry that would land outside it, more than 5,000 entries, or more than 2 GB unpacked stops the import (`importers.unpack`). Nothing from an imported file is executed. |
| `.blend`, FBX, USD and Alembic files | Blender converts them with `--factory-startup --disable-autoexec`, so a file's embedded Python does not run, whatever your Blender preferences say. |
| BuildProgram JSON | The schema validates every op. Parameter sizes are bounded so a program cannot hang the kernel. A `mesh` op reads only `.npz` files inside the program's folder, with pickles disabled. |
| Model replies | A reply is parsed as JSON and validated like any other program before anything is built. |
| The MCP server | It reads and writes any path the connected agent names, like any local tool the agent runs. Connect only agents you trust with your files. |
| The Blender link | The vendored add-on listens on `127.0.0.1:9876` only. |

## Network

Replicator calls only the engines you configure (`local` and the `endpoints` in `services.json`). API keys stay in
the environment variables that `key_env` names. Web research is off until you turn it on, and then it sends only
search words.
