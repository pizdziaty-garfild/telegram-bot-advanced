"""
Enhanced Status Handler - Job Metrics Integration

Displays:
- Scheduler status and job metrics
- Session statistics 
- Groups statistics
- System health indicators
"""

import logging
from typing import Dict, Any
from datetime import datetime

from bot.core.command_bus import CommandBus
from bot.services.groups_service import GroupsService

logger = logging.getLogger(__name__)

class EnhancedStatusHandler:
    """Enhanced status display with comprehensive metrics"""
    
    def __init__(self, command_bus: CommandBus):
        self.command_bus = command_bus
        self.groups_service = GroupsService(command_bus.database)
        self.logger = logging.getLogger(__name__)
    
    async def get_comprehensive_status(self) -> str:
        """Get comprehensive system status with all metrics"""
        try:
            # Get all statistics
            groups_stats = await self.groups_service.get_groups_stats()
            session_stats = await self.command_bus.user_manager.get_session_stats()
            job_metrics = self.command_bus.scheduler.get_job_metrics() if self.command_bus.scheduler else {}
            
            # Build status message
            status_lines = [
                "📊 **Enhanced System Status**",
                "",
                "**🤖 Bot Core:**",
                "🟢 Status: Active",
                "🟢 Database: Connected",
                f"🟢 Scheduler: {'Running' if self.command_bus.scheduler and self.command_bus.scheduler.is_running() else 'Stopped'}",
                ""
            ]
            
            # Groups statistics
            status_lines.extend([
                f"**📱 Groups ({groups_stats['total_groups']}):**",
                f"• Active: {groups_stats['active_groups']}",
                f"• Inactive: {groups_stats['inactive_groups']}",
                f"• Custom intervals: {groups_stats['custom_interval_groups']}",
                f"• Excluded from global: {groups_stats['excluded_groups']}",
                ""
            ])
            
            # Session statistics  
            status_lines.extend([
                f"**👥 Sessions ({session_stats['total_active_sessions']}):**",
                f"• Authenticated: {session_stats['authenticated_sessions']}",
                f"• Cached: {session_stats['cached_sessions']}",
                f"• Total users: {session_stats['total_users']}",
                ""
            ])
            
            # Job metrics (if scheduler is available)
            if job_metrics:
                status_lines.extend([
                    f"**⚡ Job Metrics ({job_metrics.get('total_jobs', 0)} total):**",
                    f"• Success rate: {job_metrics.get('success_rate', 0)}%",
                    f"• Active jobs: {job_metrics.get('active_jobs_count', 0)}",
                    f"• Failed jobs: {job_metrics.get('failed_jobs', 0)}",
                    f"• Retry attempts: {job_metrics.get('retry_attempts', 0)}",
                    f"• Avg execution: {job_metrics.get('avg_execution_time_ms', 0)}ms",
                    ""
                ])
                
                # Last execution time
                last_exec = job_metrics.get('last_execution')
                if last_exec:
                    time_ago = self._time_ago(last_exec)
                    status_lines.append(f"• Last execution: {time_ago}")
                else:
                    status_lines.append("• Last execution: Never")
            else:
                status_lines.extend([
                    "**⚡ Job Metrics:**",
                    "• Scheduler not available",
                    ""
                ])
            
            # FSM state distribution
            if session_stats.get('state_distribution'):
                status_lines.extend([
                    "",
                    "**📋 FSM States:**"
                ])
                for state, count in session_stats['state_distribution'].items():
                    if count > 0:
                        status_lines.append(f"• {state}: {count}")
            
            # Cleanup info
            if session_stats.get('last_cleanup'):
                cleanup_ago = self._time_ago(session_stats['last_cleanup'])
                status_lines.extend([
                    "",
                    f"**🧹 Maintenance:**",
                    f"• Last cleanup: {cleanup_ago}",
                    f"• Cleanup runs: {session_stats.get('cleanup_runs', 0)}"
                ])
            
            return "\n".join(status_lines)
            
        except Exception as e:
            self.logger.error(f"Failed to get comprehensive status: {e}")
            return (
                "📊 **Enhanced System Status**\n\n"
                "❌ Error loading system statistics\n"
                f"Details: {str(e)[:100]}"
            )
    
    def _time_ago(self, dt: datetime) -> str:
        """Format time ago string"""
        if not dt:
            return "Never"
        
        try:
            now = datetime.utcnow()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours}h ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes}m ago"
            else:
                return f"{diff.seconds}s ago"
                
        except Exception:
            return "Unknown"
