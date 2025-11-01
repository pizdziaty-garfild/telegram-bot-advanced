"""
Enhanced Scheduler Service - Global/Per-Group Intervals

Handles:
- Global interval from Config
- Per-group custom intervals
- Ex-Time for excluded groups
- Job regeneration on config changes
- Retry/backoff with tenacity
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
import pytz
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
        
        # Services
        self.config_service = ConfigService(database)
        self.groups_service = GroupsService(database)
        
        # Job tracking and metrics
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._job_metrics = {
            "total_executed": 0,
            "total_failed": 0,
            "total_retries": 0,
            "last_execution_time": None,
            "avg_execution_time_ms": 0.0
        }
        
        # Background tasks
        self._config_watcher_task: Optional[asyncio.Task] = None
        self._last_config_hash = None
        
    async def initialize(self):
        """Initialize enhanced scheduler with job recovery"""
        try:
            # Configure scheduler
            jobstores = {
                'default': MemoryJobStore()
            }
            
            executors = {
                'default': AsyncIOExecutor(max_workers=self.settings.scheduler_max_workers)
            }
            
            job_defaults = {
                'coalesce': True,  # Combine missed jobs
                'max_instances': 1,  # Prevent job overlap
                'misfire_grace_time': 300,  # 5 minutes grace period
                'replace_existing': True  # Allow job updates
            }
            
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=self.timezone
            )
            
            # Add event listeners
            self.scheduler.add_listener(
                self._job_event_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
            
            self.logger.info("Enhanced scheduler initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Enhanced scheduler initialization failed: {e}")
            raise
    
    async def start(self):
        """Start scheduler and background tasks"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        self.scheduler.start()
        
        # Start config watcher
        self._config_watcher_task = asyncio.create_task(self._watch_config_changes())
        
        # Initial job setup
        await self._setup_initial_jobs()
        
        self.logger.info("Enhanced scheduler started with config watching")
    
    async def _setup_initial_jobs(self):
        """Setup jobs based on current config and groups"""
        try:
            # Get global interval from config
            global_interval = await self._get_global_interval()
            excluded_interval = await self._get_excluded_interval()
            
            # Get all active groups
            groups_page = await self.groups_service.list_groups(page=1, per_page=1000)
            
            jobs_scheduled = 0
            
            for group in groups_page.groups:
                if not group.is_active:
                    continue
                
                # Determine interval for this group
                if group.excluded_from_global and excluded_interval:
                    interval_minutes = excluded_interval
                elif group.custom_interval:
                    interval_minutes = group.custom_interval
                elif global_interval:
                    interval_minutes = global_interval
                else:
                    continue  # No valid interval
                
                # Schedule job for this group
                job_id = f"group_{group.telegram_id}"
                success = await self._schedule_group_job(
                    job_id=job_id,
                    group_id=group.telegram_id,
                    interval_minutes=interval_minutes
                )
                
                if success:
                    jobs_scheduled += 1
            
            self.logger.info(f"Scheduled {jobs_scheduled} initial jobs")
            
        except Exception as e:
            self.logger.error(f"Failed to setup initial jobs: {e}")
    
    async def _schedule_group_job(self, job_id: str, group_id: str, interval_minutes: int) -> bool:
        """Schedule a recurring job for a group"""
        try:
            # Remove existing job if present
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # Schedule new job
            self.scheduler.add_job(
                func=self._execute_group_job,
                trigger="interval",
                minutes=interval_minutes,
                id=job_id,
                args=[group_id],
                next_run_time=datetime.now(self.timezone) + timedelta(minutes=1),  # Start in 1 minute
                replace_existing=True
            )
            
            # Track job
            self._active_jobs[job_id] = {
                "group_id": group_id,
                "interval_minutes": interval_minutes,
                "created_at": datetime.utcnow(),
                "execution_count": 0,
                "last_execution": None,
                "retry_count": 0
            }
            
            self.logger.debug(f"Scheduled job {job_id} with {interval_minutes}min interval")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule job {job_id}: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def _execute_group_job(self, group_id: str):
        """Execute job for a group with retry logic"""
        job_id = f"group_{group_id}"
        start_time = datetime.utcnow()
        
        try:
            self.logger.debug(f"Executing job for group {group_id}")
            
            # Track execution attempt
            if job_id in self._active_jobs:
                self._active_jobs[job_id]["execution_count"] += 1
                self._active_jobs[job_id]["last_execution"] = start_time
            
            # Simulate work (replace with actual message sending)
            await asyncio.sleep(0.1)
            
            # Update metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_metrics(success=True, execution_time_ms=execution_time)
            
            self.logger.debug(f"Job {job_id} executed successfully in {execution_time:.2f}ms")
            
        except Exception as e:
            # Update retry count
            if job_id in self._active_jobs:
                self._active_jobs[job_id]["retry_count"] += 1
            
            self._update_metrics(success=False)
            self.logger.error(f"Job {job_id} failed: {e}")
            
            # Save error to database
            await self._save_job_error(group_id, str(e))
            
            raise  # Re-raise for tenacity retry
    
    async def _save_job_error(self, group_id: str, error_message: str):
        """Save job execution error to database"""
        try:
            async with self.database.get_session() as db:
                # Find group
                group_result = await db.execute(
                    "SELECT id FROM groups WHERE telegram_id = :group_id",
                    {"group_id": group_id}
                )
                group_row = group_result.fetchone()
                
                if group_row:
                    # Update or create job record
                    await db.execute(
                        """
                        INSERT INTO jobs (job_id, group_id, status, error_message, retry_count, created_at, updated_at)
                        VALUES (:job_id, :group_id, 'failed', :error_message, 1, :now, :now)
                        ON CONFLICT (job_id) DO UPDATE SET
                            status = 'failed',
                            error_message = EXCLUDED.error_message,
                            retry_count = retry_count + 1,
                            updated_at = EXCLUDED.updated_at
                        """,
                        {
                            "job_id": f"group_{group_id}",
                            "group_id": group_row.id,
                            "error_message": error_message,
                            "now": datetime.utcnow()
                        }
                    )
                    await db.commit()
        except Exception as e:
            self.logger.error(f"Failed to save job error: {e}")
    
    def _update_metrics(self, success: bool, execution_time_ms: float = 0.0):
        """Update job execution metrics"""
        if success:
            self._job_metrics["total_executed"] += 1
            self._job_metrics["last_execution_time"] = datetime.utcnow()
            
            # Update average execution time
            current_avg = self._job_metrics["avg_execution_time_ms"]
            total_executed = self._job_metrics["total_executed"]
            
            if total_executed == 1:
                self._job_metrics["avg_execution_time_ms"] = execution_time_ms
            else:
                # Running average
                self._job_metrics["avg_execution_time_ms"] = (
                    (current_avg * (total_executed - 1) + execution_time_ms) / total_executed
                )
        else:
            self._job_metrics["total_failed"] += 1
    
    def _job_event_listener(self, event):
        """Handle job execution events"""
        if event.exception:
            self.logger.warning(f"Job {event.job_id} failed with exception: {event.exception}")
            self._job_metrics["total_retries"] += 1
        else:
            self.logger.debug(f"Job {event.job_id} executed successfully")
    
    async def _watch_config_changes(self):
        """Background task to watch for config changes and regenerate jobs"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Get current config hash
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
        """Get hash of relevant config values for change detection"""
        try:
            global_interval = await self._get_global_interval()
            excluded_interval = await self._get_excluded_interval()
            
            # Get groups configuration
            groups_page = await self.groups_service.list_groups(page=1, per_page=1000)
            groups_config = [
                f"{g.telegram_id}:{g.is_active}:{g.custom_interval}:{g.excluded_from_global}"
                for g in groups_page.groups
            ]
            
            config_string = f"{global_interval}:{excluded_interval}:{'|'.join(groups_config)}"
            return str(hash(config_string))
            
        except Exception as e:
            self.logger.error(f"Failed to get config hash: {e}")
            return str(datetime.utcnow().timestamp())
    
    async def _regenerate_all_jobs(self):
        """Regenerate all jobs based on current config"""
        try:
            # Clear existing jobs
            for job_id in list(self._active_jobs.keys()):
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                del self._active_jobs[job_id]
            
            # Setup jobs again
            await self._setup_initial_jobs()
            
            self.logger.info("All jobs regenerated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to regenerate jobs: {e}")
    
    async def _get_global_interval(self) -> Optional[int]:
        """Get global interval from config in minutes"""
        try:
            async with self.database.get_session() as db:
                result = await db.execute(
                    "SELECT value FROM config WHERE key = 'global_interval_minutes'",
                )
                row = result.fetchone()
                if row and row.value:
                    import json
                    return int(json.loads(row.value))
        except Exception as e:
            self.logger.error(f"Failed to get global interval: {e}")
        return None
    
    async def _get_excluded_interval(self) -> Optional[int]:
        """Get excluded groups interval from config in minutes"""
        try:
            async with self.database.get_session() as db:
                result = await db.execute(
                    "SELECT value FROM config WHERE key = 'excluded_interval_minutes'",
                )
                row = result.fetchone()
                if row and row.value:
                    import json
                    return int(json.loads(row.value))
        except Exception as e:
            self.logger.error(f"Failed to get excluded interval: {e}")
        return None
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.scheduler.running if self.scheduler else False
    
    def get_jobs(self) -> List:
        """Get all scheduled jobs"""
        return self.scheduler.get_jobs() if self.scheduler else []
    
    def get_job_metrics(self) -> Dict[str, Any]:
        """Get job execution metrics"""
        total_jobs = self._job_metrics["total_executed"] + self._job_metrics["total_failed"]
        success_rate = (
            self._job_metrics["total_executed"] / total_jobs * 100
            if total_jobs > 0 else 0.0
        )
        
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
                    "last_execution": info["last_execution"]
                }
                for job_id, info in self._active_jobs.items()
            }
        }
    
    async def shutdown(self):
        """Shutdown scheduler and background tasks"""
        if self._config_watcher_task:
            self._config_watcher_task.cancel()
            try:
                await self._config_watcher_task
            except asyncio.CancelledError:
                pass
        
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
        
        self.logger.info("Enhanced scheduler shutdown complete")
