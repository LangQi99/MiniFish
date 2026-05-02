"""Step 02：基于图谱节点 → 并行生成 Agent 人设

接口：
- POST /api/personas/generate     启动人设生成任务（异步）
- GET  /api/personas/task/<id>    查询任务进度
- GET  /api/personas/<project_id> 获取已生成的人设（支持实时增量）
"""

import json
import os
import threading
import traceback
from flask import request, jsonify

from . import personas_bp
from ..config import Config
from ..models.project import ProjectManager, ProjectStatus
from ..models.task import TaskManager, TaskStatus
from ..services.local_entity_reader import LocalEntityReader
from ..services.persona_generator import PersonaGenerator
from ..utils.logger import get_logger

logger = get_logger('minifish.api.personas')


@personas_bp.route('/generate', methods=['POST'])
def generate_personas():
    """JSON: { project_id, entity_types?, use_llm?, parallel?, force? }"""
    try:
        errors = Config.validate()
        if errors:
            return jsonify({"success": False, "error": "配置错误: " + "; ".join(errors)}), 500

        data = request.get_json() or {}
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({"success": False, "error": "请提供 project_id"}), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({"success": False, "error": f"项目不存在: {project_id}"}), 404

        if not project.graph_id:
            return jsonify({"success": False, "error": "项目尚未构建图谱，请先完成 Step01"}), 400

        force = data.get('force', False)
        if project.status == ProjectStatus.PERSONAS_GENERATING and not force:
            return jsonify({
                "success": False,
                "error": "人设生成中，如需强制重新生成请添加 force: true",
                "task_id": project.personas_task_id,
            }), 400

        entity_types_list = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        parallel = data.get('parallel', Config.PERSONA_CONCURRENCY)

        # 同步读取实体数量供前端展示
        reader = LocalEntityReader()
        preview = reader.filter_defined_entities(
            graph_id=project.graph_id,
            defined_entity_types=entity_types_list,
            enrich_with_edges=False,
        )
        expected_count = preview.filtered_count

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="personas_generate",
            metadata={"project_id": project_id, "expected_count": expected_count},
        )

        project.status = ProjectStatus.PERSONAS_GENERATING
        project.personas_task_id = task_id
        ProjectManager.save_project(project)

        personas_path = ProjectManager.get_personas_path(project_id)
        # 重置实时落盘文件，避免与上一次结果混淆
        try:
            with open(personas_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        def run():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=2,
                    message=f"读取图谱实体（预期 {expected_count} 个）...",
                )

                full = reader.filter_defined_entities(
                    graph_id=project.graph_id,
                    defined_entity_types=entity_types_list,
                    enrich_with_edges=True,
                )
                entities = full.entities

                if not entities:
                    task_manager.complete_task(task_id, result={"count": 0, "message": "图谱中没有可用实体"})
                    project.status = ProjectStatus.PERSONAS_COMPLETED
                    project.personas_count = 0
                    ProjectManager.save_project(project)
                    return

                generator = PersonaGenerator()

                def progress_cb(current: int, total: int, msg: str):
                    progress = min(99, 5 + int(current / max(total, 1) * 90))
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=msg,
                        progress_detail={"current": current, "total": total},
                    )

                profiles = generator.generate_profiles(
                    entities=entities,
                    use_llm=use_llm,
                    progress_callback=progress_cb,
                    parallel_count=int(parallel),
                    realtime_output_path=personas_path,
                )

                # 最终落盘一次（保证完整）
                with open(personas_path, 'w', encoding='utf-8') as f:
                    json.dump([p.to_dict() for p in profiles], f, ensure_ascii=False, indent=2)

                project.status = ProjectStatus.PERSONAS_COMPLETED
                project.personas_count = len(profiles)
                ProjectManager.save_project(project)

                task_manager.complete_task(
                    task_id,
                    result={
                        "project_id": project_id,
                        "count": len(profiles),
                        "personas_path": personas_path,
                    },
                )
            except Exception as e:
                logger.error(f"[{task_id}] 人设生成失败: {e}")
                logger.debug(traceback.format_exc())
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                task_manager.fail_task(task_id, str(e))

        threading.Thread(target=run, daemon=True).start()

        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "expected_count": expected_count,
                "entity_types": list(preview.entity_types),
                "message": "人设生成任务已启动",
            },
        })

    except Exception as e:
        logger.error(f"启动人设生成任务失败: {e}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@personas_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"任务不存在: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@personas_bp.route('/<project_id>', methods=['GET'])
def get_personas(project_id: str):
    """获取项目的人设列表（实时读取落盘文件，支持轮询增量更新）"""
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": f"项目不存在: {project_id}"}), 404

    personas_path = ProjectManager.get_personas_path(project_id)
    personas = []
    if os.path.exists(personas_path):
        try:
            with open(personas_path, 'r', encoding='utf-8') as f:
                personas = json.load(f)
        except Exception as e:
            logger.warning(f"读取 personas 文件失败（可能正在写入）: {e}")
            personas = []

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "status": project.status.value,
            "count": len(personas),
            "personas": personas,
        },
    })
