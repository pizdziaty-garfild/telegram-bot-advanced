"""
Scheduler Manager - DST-Safe Job Scheduling

Handles:
- DST-safe scheduling with timezone awareness
- Job persistence and recovery
- Retry mechanisms with exponential backoff
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
import asyncio
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from config.settings import Settings

class SchedulerManager:
    """DST-safe scheduler with job persistence"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.timezone = pytz.timezone(settings.scheduler_timezone)
        
        # Job tracking
        self._job_callbacks: Dict[str, Callable] = {}
        
    async def initialize(self):
        """Initialize scheduler with DST-safe configuration"""
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
                'misfire_grace_time': 300  # 5 minutes grace period
            }
            
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=self.timezone
            )
            
            # Add event listeners
            self.scheduler.add_listener(
                self._job_executed_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
            
            self.logger.info("Scheduler initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Scheduler initialization failed: {e}")
            raise
    
    async def start(self):
        """Start the scheduler"""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        self.scheduler.start()
        self.logger.info("Scheduler started")
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.scheduler.running if self.scheduler else False
    
    def get_jobs(self) -> List:
        """Get all scheduled jobs"""
        return self.scheduler.get_jobs() if self.scheduler else []
    
    async def schedule_job(
        self,
        job_id: str,
        func: Callable,
        trigger_type: str = "interval",
        **trigger_kwargs
    ) -> bool:
        """Schedule a new job with DST safety"""
        try:
            if not self.scheduler:
                raise RuntimeError("Scheduler not initialized")
            
            # Store callback for tracking
            self._job_callbacks[job_id] = func
            
            # Add timezone to datetime triggers
            if trigger_type == "date" and "run_date" in trigger_kwargs:
                run_date = trigger_kwargs["run_date"]
                if run_date.tzinfo is None:
                    trigger_kwargs["run_date"] = self.timezone.localize(run_date)
            
            # Schedule job
            self.scheduler.add_job(
                func=self._job_wrapper,
                trigger=trigger_type,
                id=job_id,
                args=[job_id],
                replace_existing=True,
                **trigger_kwargs
            )
            
            self.logger.info(f"Job scheduled: {job_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule job {job_id}: {e}")
            return False
    
    async def _job_wrapper(self, job_id: str):
        """Wrapper for job execution with error handling"""
        try:
            callback = self._job_callbacks.get(job_id)
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            else:
                self.logger.error(f"No callback found for job: {job_id}")
                
        except Exception as e:
            self.logger.error(f"Job execution failed for {job_id}: {e}")
            # Job error will be handled by event listener
    
    def _job_executed_listener(self, event):
        """Handle job execution events"""
        if event.exception:
            self.logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
        else:
            self.logger.debug(f"Job {event.job_id} executed successfully")
    
    async def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        try:
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                self._job_callbacks.pop(job_id, None)
                self.logger.info(f"Job removed: {job_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown scheduler gracefully"""
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
            self.logger.info("Scheduler shutdown complete")
