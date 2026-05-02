"""API 路由"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
personas_bp = Blueprint('personas', __name__)

from . import graph  # noqa: E402, F401
from . import personas  # noqa: E402, F401
