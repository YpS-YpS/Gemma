# -*- coding: utf-8 -*-
"""
Run Manager for tracking and coordinating automation runs across multiple SUTs
"""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import queue
import copy

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Status of an automation run"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class RunProgress:
    """Progress tracking for a run"""
    current_iteration: int = 0
    total_iterations: int = 1
    current_step: int = 0
    total_steps: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class RunResult:
    """Results from a completed run"""
    success_rate: float = 0.0
    successful_runs: int = 0
    total_iterations: int = 0
    run_directory: Optional[str] = None
    error_logs: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutomationRun:
    """Represents a single automation run"""
    run_id: str
    game_name: str
    sut_ip: str
    sut_device_id: str
    status: RunStatus = RunStatus.QUEUED
    iterations: int = 1
    progress: RunProgress = field(default_factory=RunProgress)
    results: Optional[RunResult] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'run_id': self.run_id,
            'game_name': self.game_name,
            'sut_ip': self.sut_ip,
            'sut_device_id': self.sut_device_id,
            'status': self.status.value,
            'iterations': self.iterations,
            'progress': {
                'current_iteration': self.progress.current_iteration,
                'total_iterations': self.progress.total_iterations,
                'current_step': self.progress.current_step,
                'total_steps': self.progress.total_steps
            },
            'start_time': self.progress.start_time.isoformat() if self.progress.start_time else None,
            'end_time': self.progress.end_time.isoformat() if self.progress.end_time else None,
            'results': self.results.__dict__ if self.results else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat()
        }


class RunManager:
    """Manages automation runs across multiple SUTs"""
    
    def __init__(self, max_concurrent_runs: int = 10, orchestrator=None):
        self.max_concurrent_runs = max_concurrent_runs
        self.orchestrator = orchestrator
        self.active_runs: Dict[str, AutomationRun] = {}
        self.run_history: List[AutomationRun] = []
        self.run_queue = queue.Queue()
        self.worker_threads: List[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()
        
        
        # Event callbacks
        self.on_run_started = None
        self.on_run_progress = None
        self.on_run_completed = None
        self.on_run_failed = None
        
        logger.info(f"RunManager initialized with max_concurrent_runs={max_concurrent_runs} (in-memory mode)")
    
    def set_orchestrator(self, orchestrator):
        """Set the automation orchestrator"""
        self.orchestrator = orchestrator
    
    
    def start(self):
        """Start the run manager worker threads"""
        if self.running:
            return
            
        self.running = True
        
        # Start single worker thread for sequential execution (CPU performance testing)
        for i in range(1):  # Only 1 worker for sequential execution
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"RunWorker-{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
            
        logger.info(f"RunManager started with {len(self.worker_threads)} worker threads")
    
    def stop(self):
        """Stop the run manager and all running automation"""
        if not self.running:
            return
            
        logger.info("Stopping RunManager...")
        self.running = False
        
        # Stop all active runs
        with self._lock:
            for run in self.active_runs.values():
                if run.status == RunStatus.RUNNING:
                    run.status = RunStatus.STOPPED
                    run.error_message = "Stopped by system shutdown"
                    run.progress.end_time = datetime.now()
        
        # Wait for worker threads to finish with timeout
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)  # 2 second timeout per thread
                if thread.is_alive():
                    logger.warning(f"Worker thread {thread.name} did not shut down gracefully")
        
        # Clear the queue to help threads exit
        try:
            while not self.run_queue.empty():
                self.run_queue.get_nowait()
        except:
            pass
        
        logger.info("RunManager stopped")
    
    def queue_run(self, game_name: str, sut_ip: str, sut_device_id: str, iterations: int = 1) -> str:
        """Queue a new automation run"""
        logger.info(f"Attempting to queue run: {game_name} on {sut_ip} ({iterations} iterations)")
        
        # Check if run manager is running
        if not self.running:
            logger.error("Cannot queue run: Run manager is not running")
            raise RuntimeError("Run manager is not running")
        
        try:
            run_id = str(uuid.uuid4())
            logger.info(f"Generated run_id: {run_id}")
            
            run = AutomationRun(
                run_id=run_id,
                game_name=game_name,
                sut_ip=sut_ip,
                sut_device_id=sut_device_id,
                iterations=iterations
            )
            run.progress.total_iterations = iterations
            logger.info(f"Created AutomationRun object for {run_id}")
            
            with self._lock:
                self.active_runs[run_id] = run
                logger.info(f"Added run {run_id} to active runs. Current active runs: {len(self.active_runs)}")
            
            logger.info(f"Adding run {run_id} to queue")
            self.run_queue.put(run_id)
            
            queue_size = self.run_queue.qsize()
            worker_count = len([t for t in self.worker_threads if t.is_alive()])
            logger.info(f"Queued run {run_id}: {game_name} on {sut_ip} ({iterations} iterations)")
            logger.info(f"Queue size: {queue_size}, Active workers: {worker_count}")
            
            return run_id
            
        except Exception as e:
            logger.error(f"Error queuing run: {e}", exc_info=True)
            raise
    
    def stop_run(self, run_id: str) -> bool:
        """Stop a specific run"""
        with self._lock:
            if run_id in self.active_runs:
                run = self.active_runs[run_id]
                if run.status == RunStatus.RUNNING:
                    run.status = RunStatus.STOPPED
                    run.error_message = "Stopped by user"
                    run.progress.end_time = datetime.now()
                    
                    logger.info(f"Stopped run {run_id}")
                    return True
        return False
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific run"""
        with self._lock:
            if run_id in self.active_runs:
                return self.active_runs[run_id].to_dict()
            
            # Check history
            for run in self.run_history:
                if run.run_id == run_id:
                    return run.to_dict()
        return None
    
    def get_all_runs(self) -> Dict[str, Any]:
        """Get all runs (active and history)"""
        with self._lock:
            # Get active runs from memory
            active_dict = {run_id: run.to_dict() for run_id, run in self.active_runs.items()}
            
            # Get history from memory only (Phase 1 - no database)
            history_list = [run.to_dict() for run in self.run_history[-50:]]
            
            return {
                'active': active_dict,
                'history': history_list
            }
    
    def update_run_progress(self, run_id: str, current_iteration: int = None, current_step: int = None):
        """Update progress for a running automation"""
        with self._lock:
            if run_id not in self.active_runs:
                return
                
            run = self.active_runs[run_id]
            
            if current_iteration is not None:
                run.progress.current_iteration = current_iteration
            if current_step is not None:
                run.progress.current_step = current_step
            
            # Trigger progress callback
            if self.on_run_progress:
                try:
                    self.on_run_progress(run_id, run.to_dict())
                except Exception as e:
                    logger.error(f"Error in run progress callback: {e}")
    
    def complete_run(self, run_id: str, success: bool, results: Optional[RunResult] = None, error_message: str = None):
        """Mark a run as completed"""
        logger.info(f"complete_run called for {run_id}, acquiring lock...")
        with self._lock:
            logger.info(f"complete_run acquired lock for {run_id}")
            if run_id not in self.active_runs:
                logger.warning(f"Run {run_id} not found in active_runs, returning early")
                return
                
            logger.info(f"Updating run status for {run_id}")
            run = self.active_runs[run_id]
            run.status = RunStatus.COMPLETED if success else RunStatus.FAILED
            run.progress.end_time = datetime.now()
            run.results = results
            if error_message:
                run.error_message = error_message
            
            logger.info(f"Moving run {run_id} to history")
            # Move to history
            self.run_history.append(copy.deepcopy(run))
            del self.active_runs[run_id]
            logger.info(f"Removed run {run_id} from active_runs")
            
            # Keep history manageable
            if len(self.run_history) > 100:
                self.run_history = self.run_history[-100:]
            
            logger.info(f"Completed run {run_id}: {run.game_name} ({'success' if success else 'failed'})")
            
            # Log queue state for debugging
            queue_size = self.run_queue.qsize()
            active_runs_count = len(self.active_runs)
            logger.info(f"After completion - Queue size: {queue_size}, Active runs: {active_runs_count}")
            if active_runs_count > 0:
                pending_games = [(run.game_name, run.sut_ip) for run in self.active_runs.values()]
                logger.info(f"Pending games: {pending_games}")
            
            if queue_size > 0:
                logger.info(f"Worker should pick up next run from queue (size: {queue_size})")
        
        # Trigger completion callback OUTSIDE the lock to avoid deadlock
        logger.info(f"About to trigger completion callback for {run_id}")
        callback = self.on_run_completed if success else self.on_run_failed
        if callback:
            try:
                logger.info(f"Calling completion callback for {run_id}")
                callback(run_id, run.to_dict())
                logger.info(f"Completion callback finished for {run_id}")
            except Exception as e:
                logger.error(f"Error in run completion callback: {e}")
        else:
            logger.info(f"No completion callback set for {run_id}")
    
    def _worker_loop(self):
        """Worker thread main loop"""
        logger.info(f"Worker thread {threading.current_thread().name} started")
        
        while self.running:
            logger.debug(f"Worker {threading.current_thread().name} waiting for next run...")
            try:
                # Wait for a run to process with shorter timeout for responsiveness
                try:
                    run_id = self.run_queue.get(timeout=0.5)
                    logger.info(f"Worker dequeued run: {run_id}")
                except queue.Empty:
                    # Only log occasionally to avoid spam
                    continue
                
                # Double-check we're still running
                if not self.running:
                    logger.info(f"Worker thread {threading.current_thread().name} stopping")
                    break
                
                with self._lock:
                    if run_id not in self.active_runs:
                        continue
                    run = self.active_runs[run_id]
                
                # Process the run
                self._execute_run(run)
                logger.info(f"Worker completed processing run {run_id}, returning to queue loop")
                
            except Exception as e:
                logger.error(f"Error in worker thread: {e}", exc_info=True)
                
                # Mark the current run as failed if we can identify it
                try:
                    if 'run' in locals() and run:
                        self.complete_run(run.run_id, False, error_message=f"Worker thread error: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"Error during worker thread cleanup: {cleanup_error}")
                
                # Continue running even if one run fails
        
        logger.info(f"Worker thread {threading.current_thread().name} ended")
    
    def _execute_run(self, run: AutomationRun):
        """Execute a single automation run"""
        logger.info(f"Starting execution of run {run.run_id}: {run.game_name} on {run.sut_ip}")
        
        # Mark as running
        with self._lock:
            run.status = RunStatus.RUNNING
            run.progress.start_time = datetime.now()
        
        # Trigger started callback
        if self.on_run_started:
            try:
                self.on_run_started(run.run_id, run.to_dict())
            except Exception as e:
                logger.error(f"Error in run started callback: {e}")
        
        try:
            # Execute the automation using orchestrator
            logger.info(f"Starting automation execution for run {run.run_id}")
            success = self._simulate_automation_execution(run)
            logger.info(f"Automation execution completed for run {run.run_id} with success={success}")
            
            # Create results (results may be set by orchestrator)
            if not hasattr(run, '_execution_results'):
                results = RunResult(
                    success_rate=1.0 if success else 0.0,
                    successful_runs=run.iterations if success else 0,
                    total_iterations=run.iterations,
                    run_directory=f"logs/{run.game_name}/run_{run.run_id}",
                )
            else:
                results = run._execution_results
            
            # Determine final error message
            error_message = None
            if not success and hasattr(run, '_execution_error'):
                error_message = run._execution_error
            
            logger.info(f"About to complete run {run.run_id} with success={success}")
            self.complete_run(run.run_id, success, results, error_message)
            logger.info(f"Completed run call finished for {run.run_id}")
            
        except Exception as e:
            logger.error(f"Critical error executing run {run.run_id}: {e}", exc_info=True)
            self.complete_run(run.run_id, False, error_message=f"Critical error: {str(e)}")
    
    def _simulate_automation_execution(self, run: AutomationRun) -> bool:
        """Execute automation using the orchestrator or simulate if not available"""
        if self.orchestrator:
            logger.info(f"Executing real automation for run {run.run_id}")
            try:
                logger.info(f"Calling orchestrator.execute_run for {run.run_id}")
                success, results, error_message = self.orchestrator.execute_run(run)
                logger.info(f"Orchestrator.execute_run returned for {run.run_id}: success={success}")
                
                # Store results and error on the run object for later retrieval
                if results:
                    run._execution_results = results
                if error_message:
                    run._execution_error = error_message
                    logger.error(f"Automation execution failed: {error_message}")
                
                return success
            except Exception as e:
                logger.error(f"Error in orchestrator execution: {e}", exc_info=True)
                return False
        else:
            # Fallback to simulation
            logger.info(f"Simulating automation for run {run.run_id} (no orchestrator)")
            
            # Simulate multiple iterations
            for i in range(run.iterations):
                if run.status != RunStatus.RUNNING:
                    return False
                    
                # Update progress
                self.update_run_progress(run.run_id, current_iteration=i + 1)
                
                # Simulate work
                time.sleep(2)  # Simulate 2 seconds per iteration
                
                logger.info(f"Run {run.run_id}: Completed iteration {i + 1}/{run.iterations}")
            
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get run manager statistics"""
        with self._lock:
            active_count = len(self.active_runs)
            queued_count = self.run_queue.qsize()
            
            # Calculate history stats
            completed_count = len([r for r in self.run_history if r.status == RunStatus.COMPLETED])
            failed_count = len([r for r in self.run_history if r.status == RunStatus.FAILED])
            
            # Get detailed queue info for debugging
            active_games = [run.game_name for run in self.active_runs.values()]
            
            return {
                'active_runs': active_count,
                'queued_runs': queued_count,
                'total_history': len(self.run_history),
                'completed_runs': completed_count,
                'failed_runs': failed_count,
                'worker_threads': len(self.worker_threads),
                'running': self.running,
                'active_games': active_games  # For debugging
            }