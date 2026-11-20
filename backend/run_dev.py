"""Local development entrypoint (Windows-friendly).

`flask run` serves one request at a time by default, so a single slow RDS
call blocks every other request -- including /api/health -- until it
finishes. Gunicorn (used in production/Docker) fixes this with worker
threads, but Gunicorn does not run on Windows. This script gets the same
threading behaviour locally via Werkzeug's built-in dev server.
"""
from dotenv import load_dotenv

from app import create_app

if __name__ == "__main__":
    # Only in the main process: the "spawn" workers re-import this module as
    # __mp_main__, and loading .env there would put the secrets back into
    # each worker's environment (see app/utils/secrets.py).
    load_dotenv()  # `flask run` does this automatically; a plain script does not.
    app = create_app()
    # threaded=True so a slow RDS call doesn't block every other request.
    # use_reloader=False: the reloader spawns a second process that re-runs
    # the (slow, network-dependent) startup guard and complicates the process
    # tree on Windows for no benefit in this workflow.
    app.run(host="127.0.0.1", port=5001, threaded=True, debug=False, use_reloader=False)
