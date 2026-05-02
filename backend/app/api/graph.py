"""Step 01：长文本 + 模拟需求 → 本体 → GraphRAG 实时构建

接口：
- POST /api/graph/ontology/generate   生成本体
- POST /api/graph/build               异步构建图谱
- GET  /api/graph/task/<task_id>      查询任务进度
- GET  /api/graph/data/<graph_id>     拉取图谱数据（节点 + 边）
- GET  /api/graph/project/<id>        项目详情
- GET  /api/graph/project/list        项目列表
- DELETE /api/graph/project/<id>      删除项目
"""

import os
import threading
import traceback
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.local_graph_builder import LocalGraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

logger = get_logger('minifish.api.graph')


def allowed_file(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": f"项目不存在: {project_id}"}), 404
    return jsonify({"success": True, "data": project.to_dict()})


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    return jsonify({"success": True, "data": [p.to_dict() for p in projects], "count": len(projects)})


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    success = ProjectManager.delete_project(project_id)
    if not success:
        return jsonify({"success": False, "error": f"项目不存在: {project_id}"}), 404
    return jsonify({"success": True, "message": f"项目已删除: {project_id}"})


# ============== 本体生成 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """multipart/form-data: files + simulation_requirement + project_name"""
    try:
        logger.info("=== 开始生成本体定义 ===")

        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')

        if not simulation_requirement:
            return jsonify({"success": False, "error": "请提供 simulation_requirement"}), 400

        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({"success": False, "error": "请至少上传一个文档文件"}), 400

        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"创建项目: {project.project_id}")

        document_texts = []
        all_text = ""

        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                file_info = ProjectManager.save_file_to_project(project.project_id, file, file.filename)
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"],
                })
                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({"success": False, "error": "没有成功处理任何文档，请检查文件格式"}), 400

        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"文本提取完成，共 {len(all_text)} 字符")

        logger.info("调用 LLM 生成本体定义...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None,
        )

        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", []),
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)

        logger.info(f"=== 本体生成完成 === project_id={project.project_id}")

        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length,
            },
        })

    except Exception as e:
        logger.error(f"本体生成失败: {e}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== 图谱构建 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """JSON: { project_id, graph_name?, chunk_size?, chunk_overlap?, force? }"""
    try:
        logger.info("=== 开始构建图谱 ===")

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

        force = data.get('force', False)
        if project.status == ProjectStatus.CREATED:
            return jsonify({"success": False, "error": "项目尚未生成本体，请先调用 /ontology/generate"}), 400

        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "图谱正在构建中，如需强制重建请添加 force: true",
                "task_id": project.graph_build_task_id,
            }), 400

        if force and project.status in [
            ProjectStatus.GRAPH_BUILDING,
            ProjectStatus.FAILED,
            ProjectStatus.GRAPH_COMPLETED,
        ]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None

        graph_name = data.get('graph_name', project.name or 'MiniFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)

        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap

        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({"success": False, "error": "未找到提取的文本内容"}), 400

        ontology = project.ontology
        if not ontology:
            return jsonify({"success": False, "error": "未找到本体定义"}), 400

        task_manager = TaskManager()
        task_id = task_manager.create_task(f"构建图谱: {graph_name}")
        logger.info(f"创建图谱构建任务: task_id={task_id}, project_id={project_id}")

        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)

        def build_task():
            build_logger = get_logger('minifish.build')
            try:
                build_logger.info(f"[{task_id}] 开始构建图谱...")
                task_manager.update_task(task_id, status=TaskStatus.PROCESSING, message="初始化图谱构建服务...")

                builder = LocalGraphBuilderService()

                def progress_cb(msg: str, ratio: float):
                    progress = min(99, max(1, int(ratio * 95)))
                    task_manager.update_task(task_id, message=msg, progress=progress)

                graph_id, graph_data = builder.build_graph_from_text(
                    project_id=project_id,
                    text=text,
                    ontology=ontology,
                    graph_name=graph_name,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    progress_callback=progress_cb,
                )
                total_chunks = len(TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap))

                project.graph_id = graph_id
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(
                    f"[{task_id}] 图谱构建完成: graph_id={graph_id}, 节点={node_count}, 边={edge_count}"
                )

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="图谱构建完成",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks,
                    },
                )

            except Exception as e:
                build_logger.error(f"[{task_id}] 图谱构建失败: {e}")
                build_logger.debug(traceback.format_exc())

                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"构建失败: {e}",
                    error=traceback.format_exc(),
                )

        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "图谱构建任务已启动",
            },
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


# ============== 任务查询 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"任务不存在: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


# ============== 图谱数据 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    try:
        builder = LocalGraphBuilderService()
        graph_data = builder.get_graph_data(graph_id)
        return jsonify({"success": True, "data": graph_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    try:
        builder = LocalGraphBuilderService()
        builder.delete_graph(graph_id)
        return jsonify({"success": True, "message": f"图谱已删除: {graph_id}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500
