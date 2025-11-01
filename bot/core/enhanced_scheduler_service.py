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

    def _job_event_listener(self, event):
        if event.exception:
            self.logger.warning(f"Job {event.job_id} failed with exception: {event.exception}")
            self._job_metrics["total_retries"] += 1
        else:
            self.logger.debug(f"Job {event.job_id} executed successfully")

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

    # (execute job and metrics methods unchanged from previous commit)
