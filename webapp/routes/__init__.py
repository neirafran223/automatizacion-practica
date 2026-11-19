# -*- coding: utf-8 -*-
"""Register all route blueprints for the Flask app.

Each submodule in `webapp/routes/` defines a Blueprint named `bp` and
exposes the routes that belong to a specific feature (static files,
initialisation, upload, analysis, etc.).  This function simply imports
those blueprints and registers them on the given Flask app instance.
"""

# -*- coding: utf-8 -*-
"""Register all route blueprints for the Flask app.

Each submodule in `webapp/routes/` defines a Blueprint named `bp` and
exposes the routes that belong to a specific feature (static files,
initialisation, upload, analysis, etc.).  This function simply imports
those blueprints and registers them on the given Flask app instance.
"""

def register_routes(app):
    from webapp.routes.static import bp as static_bp
    from webapp.routes.init import bp as init_bp
    from webapp.routes.upload import bp as upload_bp
    from webapp.routes.analyze import bp as analyze_bp
    from webapp.routes.preview import bp as preview_bp
    from webapp.routes.fotos import bp as fotos_bp
    from webapp.routes.edit import bp as edit_bp
    from webapp.routes.conversion import bp as conversion_bp
    from webapp.routes.download import bp as download_bp

    for bp in (static_bp, init_bp, upload_bp, analyze_bp,
               preview_bp, fotos_bp, edit_bp,
               conversion_bp, download_bp):
        app.register_blueprint(bp)


