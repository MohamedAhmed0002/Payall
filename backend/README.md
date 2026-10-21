# Payall backend

## Requirements

You need Python 3.10 or newer (Python 3.12 is recommended) and Git.

Check your Python version with:

- Windows: `python --version`
- Mac: `python3 --version`

If Python is not installed, download it from [python.org](https://www.python.org/downloads/). On Windows, tick **Add python.exe to PATH** during installation.

## Option A: GitHub Codespaces (recommended, nothing to install)

On the Payall GitHub page, select **Code → Codespaces → Create codespace on main**.

Wait until the setup finishes. The packages install automatically.

Then, in the terminal:

```bash
cd backend
python run.py --host 0.0.0.0
```

Open forwarded port 8000 from the **Ports** tab and add `/docs` to the URL.

Free Codespaces hours are limited, so stop the codespace when you are done.

## Option B: Local setup on Mac

Run all commands from the `backend` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
python run.py
```

Open <http://127.0.0.1:8000/docs>.

## Option C: Local setup on Windows

Run these PowerShell commands from the `backend` folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-test.txt
python run.py
```

If PowerShell says that running scripts is disabled, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

In VS Code, choose the `.venv` interpreter via **Python: Select Interpreter**.

## Every time you work on the project

Activate the virtual environment again:

- Mac: `source .venv/bin/activate`
- Windows PowerShell: `.venv\Scripts\Activate.ps1`

Pull the latest changes:

```bash
git pull
```

If `requirements.txt` changed, reinstall the requirements:

```bash
pip install -r requirements-test.txt
```

## Running the tests

With the virtual environment active, run this from `backend/`:

```bash
pytest
```

## Resetting the database

The database file is `backend/data/payall.sqlite` and is not committed to Git.

If the table models change, or you get a 500 error after pulling new code, stop the server, delete that file, and start the server again. It is recreated from `seed.json`.

## Troubleshooting

- **"No module named fastapi" or "sqlmodel"**: The virtual environment is not active, or packages were installed into a different Python. Activate the virtual environment and reinstall the requirements.
- **"Address already in use"**: Another server is still running on port 8000. Stop it with `Ctrl+C` or use `--port 8001`.
