# -*- coding: utf-8 -*-
"""Static file routes (index page)."""

from flask import Blueprint, send_from_directory

bp = Blueprint('static', __name__)

@bp.route('/')
def index():
    return send_from_directory('static', 'index.html')
