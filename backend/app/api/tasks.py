"""任务列表查询接口"""

from flask import jsonify

from . import tasks_bp
from ..models.task import TaskManager


@tasks_bp.route('/list', methods=['GET'])
def list_tasks():
    """所有任务,按 updated_at 倒序"""
    tasks = sorted(
        TaskManager().all_tasks(),
        key=lambda t: t.updated_at,
        reverse=True,
    )
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks),
    })
