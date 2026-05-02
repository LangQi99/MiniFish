"""MiniFish Backend - Flask 应用工厂"""

import os
import warnings

warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    logger = setup_logger('minifish')

    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiniFish Backend 启动中...")
        logger.info("=" * 50)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.before_request
    def log_request():
        get_logger('minifish.request').debug(f"请求: {request.method} {request.path}")

    @app.after_request
    def log_response(response):
        get_logger('minifish.request').debug(f"响应: {response.status_code}")
        return response

    from .api import graph_bp, personas_bp, tasks_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(personas_bp, url_prefix='/api/personas')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')

    # 启动时把磁盘上的任务恢复到内存,运行中的任务标记为中断
    from .models.task import TaskManager
    if not (debug_mode and not is_reloader_process):
        # debug 模式下父进程不做恢复,避免和 reloader 子进程双写
        TaskManager().load_from_disk()

    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiniFish Backend'}

    if should_log_startup:
        logger.info("MiniFish Backend 启动完成")

    return app
