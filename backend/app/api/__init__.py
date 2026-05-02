"""API 路由"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
personas_bp = Blueprint('personas', __name__)
tasks_bp = Blueprint('tasks', __name__)

from . import graph  # noqa: E402, F401
from . import personas  # noqa: E402, F401
from . import tasks  # noqa: E402, F401
