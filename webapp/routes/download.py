# -*- coding: utf-8 -*-
"""Download route module.
Provides a blueprint to serve generated files for download.
"""

import os
from flask import Blueprint, send_from_directory, abort
from ..helpers import _err
from ..core import state as S

bp = Blueprint('download', __name__)

@bp.route('/descargas/<path:filename>')
def descargar(filename):
    """Serve a file from the output directory.

    Args:
        filename: Relative path of the file requested.
    Returns:
        Flask response sending the file or 404 if not found.
    """
    # Load state to get the configured output directory.
    st = S.cargar()
    outdir = st.get('outdir') or getattr(S, 'SALIDA', '')
    # Resolve the absolute file path safely.
    safe_path = os.path.abspath(os.path.join(outdir, filename))
    # Ensure the path is within the output directory to prevent directory traversal.
    if not safe_path.startswith(os.path.abspath(outdir)):
        abort(404)
    if not os.path.isfile(safe_path):
        abort(404)
    # Use Flask's send_from_directory to serve the file as an attachment.
    return send_from_directory(outdir, filename, as_attachment=True)
