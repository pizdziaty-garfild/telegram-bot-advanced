import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from sqlalchemy import text

from config.settings import Settings
from bot.infra.database import DatabaseManager
from bot.services.config_service import ConfigService
from bot.services.groups_service import GroupsService

logger = logging.getLogger(__name__)


class EnhancedSchedulerService:
    """DST-safe scheduler with global/per-group intervals and retry logic"""

    def __init__(self, database: DatabaseManager, settings: Settings):
        self.database = database
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.timezone = pytz.timezone(settings.scheduler_timezone)

        self.config_service = ConfigService(database)
        self.groups_service = GroupsService(database)

        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._job_metrics = {
            "total_executed": 0,
            "total_failed": 0,
            "total_retries": 0,
            "last_execution_time": None,
            "avg_execution_time_ms": 0.0,
        }

        self._config_watcher_task: Optional[asyncio.Task] = None
        self._last_config_hash = None

    async def initialize(self):
        try:
            jobstores = {"default": MemoryJobStore()}
            # AsyncIOExecutor in APScheduler 3.x doesn't accept max_workers; use default
            executors = {"default": AsyncIOExecutor()}
            job_defaults = {
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": int(self.settings.scheduler_job_grace_time or 300),
                "replace_existing": True,
            }
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone=self.timezone
            )
            self.scheduler.add_listener(
                self._job_event_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
            self.logger.info("Enhanced scheduler initialized successfully")
        except Exception as e:
            self.logger.error(f"Enhanced scheduler initialization failed: {e}")
            raise

    async def start(self):
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        self.scheduler.start()
        self._config_watcher_task = asyncio.create_task(self._watch_config_changes())
        await self._setup_initial_jobs()
        self.logger.info("Enhanced scheduler started with config watching")

    async def _setup_initial_jobs(self):
        try:
            global_interval = await self._get_global_interval()
            excluded_interval = await self._get_excluded_interval()
            self.logger.debug(f"Intervals: global={global_interval}, excluded={excluded_interval}")

            groups_page = await self.groups_service.list_groups(page=1, per_page=1000)
            jobs_scheduled = 0
            for group in groups_page.groups:
                if not group.is_active:
                    continue
                interval_minutes = None
                if group.excluded_from_global and excluded_interval and excluded_interval > 0:
                    interval_minutes = excluded_interval
                elif group.custom_interval and group.custom_interval > 0:
                    interval_minutes = group.custom_interval
                elif global_interval and global_interval > 0:
                    interval_minutes = global_interval

                if not interval_minutes:
                    self.logger.debug(f"Skipping group {group.telegram_id}: no valid interval")
                    continue
                success = await self._schedule_group_job(
                    job_id=f"group_{group.telegram_id}", group_id=group.telegram_id, interval_minutes=int(interval_minutes)
                )
                if success:
                    jobs_scheduled += 1
            self.logger.info(f"Scheduled {jobs_scheduled} initial jobs")
        except Exception as e:
            self.logger.error(f"Failed to setup initial jobs: {e}")

    async def _schedule_group_job(self, job_id: str, group_id: str, interval_minutes: int) -> bool:
        try:
            if interval_minutes is None or int(interval_minutes) <= 0:
                self.logger.warning(f"Invalid interval for job {job_id}: {interval_minutes}")
                return False
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            self.scheduler.add_job(
                func=self._execute_group_job,
                trigger="interval",
                minutes=int(interval_minutes),
                id=job_id,
                args=[group_id],
                next_run_time=datetime.now(self.timezone) + timedelta(minutes=1),
                replace_existing=True,
            )
            self._active_jobs[job_id] = {
                "group_id": group_id,
                "interval_minutes": int(interval_minutes),
                "created_at": datetime.utcnow(),
                "execution_count": 0,
                "last_execution": None,
                "retry_count": 0,
            }
            self.logger.debug(f"Scheduled job {job_id} with {interval_minutes}min interval")
            return True
        except Exception as e:
            self.logger.error(f"Failed to schedule job {job_id}: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(Exception))
    async def _execute_group_job(self, group_id: str):
        job_id = f"group_{group_id}"
        start_time = datetime.utcnow()
        try:
            self.logger.debug(f"Executing job for group {group_id}")
            if job_id in self._active_jobs:
                self._active_jobs[job_id]["execution_count"] += 1
                self._active_jobs[job_id]["last_execution"] = start_time
            await asyncio.sleep(0.1)
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_metrics(success=True, execution_time_ms=execution_time)
            self.logger.debug(f"Job {job_id} executed successfully in {execution_time:.2f}ms")
        except Exception as e:
            if job_id in self._active_jobs:
                self._active_jobs[job_id]["retry_count"] += 1
            self._update_metrics(success=False)
            self.logger.error(f"Job {job_id} failed: {e}")
            await self._save_job_error(group_id, str(e))
            raise

    def _update_metrics(self, success: bool, execution_time_ms: float = 0.0):
        if success:
            self._job_metrics["total_executed"] += 1
            self._job_metrics["last_execution_time"] = datetime.utcnow()
            current_avg = self._job_metrics["avg_execution_time_ms"]
            total_executed = self._job_metrics["total_executed"]
            if total_executed == 1:
                self._job_metrics["avg_execution_time_ms"] = execution_time_ms
            else:
                self._job_metrics["avg_execution_time_ms"] = (
                    (current_avg * (total_executed - 1) + execution_time_ms) / total_executed
                )
        else:
            self._job_metrics["total_failed"] += 1

    def _job_event_listener(self, event):
        if event.exception:
            self.logger.warning(f"Job {event.job_id} failed with exception: {event.exception}")
            self._job_metrics["total_retries"] += 1
        else:
            self.logger.debug(f"Job {event.job_id} executed successfully")

    async def _watch_config_changes(self):
        while True:
            try:
                await asyncio.sleep(30)
                current_hash = await self._get_config_hash()
                if self._last_config_hash is None:
                    self._last_config_hash = current_hash
                    continue
                if current_hash != self._last_config_hash:
                    self.logger.info("Config changes detected, regenerating jobs...")
                    await self._regenerate_all_jobs()
                    self._last_config_hash = current_hash
            except Exception as e:
                self.logger.error(f"Error in config watcher: {e}")

    async def _get_config_hash(self) -> str:
        try:
            global_interval = await self._get_global_interval()
            excluded_interval = await self._get_excluded_interval()
            groups_page = await self.groups_service.list_groups(page=1, per_page=1000)
            groups_config = [
                f"{g.telegram_id}:{g.is_active}:{g.custom_interval}:{g.excluded_from_global}" for g in groups_page.groups
            ]
            config_string = f"{global_interval}:{excluded_interval}:{'|'.join(groups_config)}"
            return str(hash(config_string))
        except Exception as e:
            self.logger.error(f"Failed to get config hash: {e}")
            return str(datetime.utcnow().timestamp())

    async def _regenerate_all_jobs(self):
        try:
            for job_id in list(self._active_jobs.keys()):
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                del self._active_jobs[job_id]
            await self._setup_initial_jobs()
            self.logger.info("All jobs regenerated successfully")
        except Exception as e:
            self.logger.error(f"Failed to regenerate jobs: {e}")

    async def _get_global_interval(self) -> Optional[int]:
        try:
            async with self.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'global_interval_minutes'"))
                row = result.fetchone()
                if row and row.value:
                    import json
                    try:
                        return int(json.loads(row.value))
                    except Exception:
                        return int(row.value)
        except Exception as e:
            self.logger.error(f"Failed to get global interval: {e}")
        return None

    async def _get_excluded_interval(self) -> Optional[int]:
        try:
            async with self.database.get_session() as db:
                result = await db.execute(text("SELECT value FROM config WHERE key = 'excluded_interval_minutes'"))
                row = result.fetchone()
                if row and row.value:
                    import json
                    try:
                        return int(json.loads(row.value))
                    except Exception:
                        return int(row.value)
        except Exception as e:
            self.logger.error(f"Failed to get excluded interval: {e}")
        return None

    def is_running(self) -> bool:
        return self.scheduler.running if self.scheduler else False

    def get_jobs(self) -> List:
        return self.scheduler.get_jobs() if self.scheduler else []

    def get_job_metrics(self) -> Dict[str, Any]:
        total_jobs = self._job_metrics["total_executed"] + self._job_metrics["total_failed"]
        success_rate = (self._job_metrics["total_executed"] / total_jobs * 100) if total_jobs > 0 else 0.0
        return {
            "total_jobs": total_jobs,
            "successful_jobs": self._job_metrics["total_executed"],
            "failed_jobs": self._job_metrics["total_failed"],
            "retry_attempts": self._job_metrics["total_retries"],
            "success_rate": round(success_rate, 2),
            "avg_execution_time_ms": round(self._job_metrics["avg_execution_time_ms"], 2),
            "last_execution": self._job_metrics["last_execution_time"],
            "active_jobs_count": len(self._active_jobs),
            "active_jobs": {
                job_id: {
                    "group_id": info["group_id"],
                    "interval_minutes": info["interval_minutes"],
                    "execution_count": info["execution_count"],
                    "retry_count": info["retry_count"],
                    "last_execution": info["last_execution"],
                }
                for job_id, info in self._active_jobs.items()
            },
        }

    async def shutdown(self):
        if self._config_watcher_task:
            self._config_watcher_task.cancel()
            try:
                await self._config_watcher_task
            except asyncio.CancelledError:
                pass
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
        self.logger.info("Enhanced scheduler shutdown complete")
