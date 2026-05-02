"""任务状态管理（线程安全 + 落盘持久化）"""

import json
import os
import threading
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger


_logger = get_logger('minifish.task')


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0
    message: str = ""
    result: Optional[Dict] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    progress_detail: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Task":
        return cls(
            task_id=d["task_id"],
            task_type=d.get("task_type", ""),
            status=TaskStatus(d.get("status", "pending")),
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            progress=d.get("progress", 0),
            message=d.get("message", ""),
            result=d.get("result"),
            error=d.get("error"),
            metadata=d.get("metadata") or {},
            progress_detail=d.get("progress_detail") or {},
        )


TASKS_DIR = Path(Config.UPLOAD_FOLDER) / "tasks"


class TaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance

    # ---------- 持久化 ----------

    def _persist(self, task: Task):
        """把单个任务原子写盘。调用方需已持 _task_lock。"""
        try:
            TASKS_DIR.mkdir(parents=True, exist_ok=True)
            path = TASKS_DIR / f"{task.task_id}.json"
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            _logger.warning(f"持久化任务 {task.task_id} 失败: {e}")

    def load_from_disk(self):
        """启动时调用：从 TASKS_DIR 恢复任务,把仍处于运行中的标记为 failed。"""
        if not TASKS_DIR.exists():
            return
        loaded = 0
        interrupted = 0
        for fp in TASKS_DIR.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    task = Task.from_dict(json.load(f))
            except Exception as e:
                _logger.warning(f"读取任务文件失败 {fp.name}: {e}")
                continue
            # 后端进程没了,运行中的任务一定中断了
            if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                task.status = TaskStatus.FAILED
                task.error = "interrupted by backend restart"
                task.message = "任务因后端重启被中断"
                task.updated_at = datetime.now()
                with self._task_lock:
                    self._tasks[task.task_id] = task
                    self._persist(task)
                interrupted += 1
            else:
                with self._task_lock:
                    self._tasks[task.task_id] = task
            loaded += 1
        _logger.info(f"任务恢复完成: 共 {loaded} 条, 其中 {interrupted} 条被标记为中断")

    def all_tasks(self):
        with self._task_lock:
            return list(self._tasks.values())

    # ---------- CRUD ----------

    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now()
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._task_lock:
            self._tasks[task_id] = task
            self._persist(task)
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._task_lock:
            return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None,
    ):
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.updated_at = datetime.now()
            if status is not None:
                task.status = status
            if progress is not None:
                task.progress = progress
            if message is not None:
                task.message = message
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if progress_detail is not None:
                task.progress_detail = progress_detail
            self._persist(task)

    def complete_task(self, task_id: str, result: Dict):
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="任务完成",
            result=result,
        )

    def fail_task(self, task_id: str, error: str):
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="任务失败",
            error=error,
        )
