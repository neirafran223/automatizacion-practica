# -*- coding: utf-8 -*-
"""Placeholder for preview API.

The original implementation lives in ``helpers.py``; for the purpose of
starting the server we expose a minimal endpoint that returns a clear
"not implemented" message.
"""

from flask import Blueprint, jsonify

bp = Blueprint('preview', __name__)

@bp.route('/api/preview')
def api_preview():
    return jsonify({'ok': False, 'error': 'Preview endpoint not implemented in this stub.'}), 501
