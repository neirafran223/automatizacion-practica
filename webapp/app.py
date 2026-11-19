# -*- coding: utf-8 -*-
"""Main entry point for the Flask server.

All route implementations are delegated to blueprints located in
`webapp/routes/`.  This file only creates the Flask app, registers the
blueprints and starts the server when executed directly.
"""

from flask import Flask

# Import the helper that registers every blueprint.
from .routes import register_routes

app = Flask(__name__, static_folder='static', static_url_path='/static')
# Limit upload size to 100 MB (same as original implementation).
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Register all routes – the function lives in `webapp/routes/__init__.py`.
register_routes(app)

if __name__ == '__main__':
    import os
    from .core import loader
    port = int(os.environ.get('PML_PORT') or 8778)
    print(f'PlanillasML-Web -> http://127.0.0.1:{port}')
    if not loader.DISPONIBLE:
        print('AVISO:', loader.ERROR)
    try:
        app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
    except OSError as e:
        print(f'No pude abrir el puerto {port} ({e}).')
        try:
            input('Enter para salir...')
        except EOFError:
            pass
