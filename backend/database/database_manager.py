# -*- coding: utf-8 -*-
"""
Database Manager for Gaming Benchmark Automation System
Handles persistent storage for SUT pairing, run history, and performance data
"""

import sqlite3
import logging
import json
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for benchmark automation system"""
    
    def __init__(self, db_path: str = "gemma_benchmark.db"):
        # Ensure database directory exists
        db_dir = Path(db_path).parent
        if str(db_dir) != '.':  # Only create if not current directory
            db_dir.mkdir(parents=True, exist_ok=True)
            
        self.db_path = db_path
        self._lock = threading.Lock()
        
        try:
            self.init_database()
            logger.info(f"DatabaseManager initialized with database: {db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def init_database(self):
        """Initialize database and create tables"""
        with self.get_connection() as conn:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # SUTs table - for paired/discovered SUTs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS suts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT UNIQUE NOT NULL,
                    ip_address TEXT NOT NULL,
                    port INTEGER NOT NULL DEFAULT 8080,
                    hostname TEXT,
                    nickname TEXT,
                    paired BOOLEAN DEFAULT FALSE,
                    paired_at DATETIME,
                    capabilities TEXT, -- JSON array
                    last_seen DATETIME,
                    first_discovered DATETIME,
                    status TEXT DEFAULT 'offline', -- online, offline, busy
                    total_pings INTEGER DEFAULT 0,
                    successful_pings INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Automation runs table - master run records
            conn.execute("""
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    sut_device_id TEXT NOT NULL,
                    game_name TEXT NOT NULL,
                    game_config_path TEXT,
                    status TEXT NOT NULL, -- queued, running, completed, failed, stopped
                    iterations INTEGER NOT NULL DEFAULT 1,
                    current_iteration INTEGER DEFAULT 0,
                    current_step INTEGER DEFAULT 0,
                    start_time DATETIME,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    success_rate REAL,
                    successful_runs INTEGER DEFAULT 0,
                    total_iterations INTEGER,
                    run_directory TEXT,
                    error_message TEXT,
                    error_logs TEXT, -- JSON array
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sut_device_id) REFERENCES suts(device_id)
                )
            """)
            
            # Run iterations table - detailed iteration data
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_iterations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    iteration_number INTEGER NOT NULL,
                    status TEXT NOT NULL, -- running, completed, failed
                    start_time DATETIME,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    steps_completed INTEGER DEFAULT 0,
                    total_steps INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT FALSE,
                    error_message TEXT,
                    screenshots_path TEXT,
                    logs_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES automation_runs(run_id),
                    UNIQUE(run_id, iteration_number)
                )
            """)
            
            # Performance metrics table - Phase 2 ready
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    iteration_number INTEGER,
                    metric_type TEXT NOT NULL, -- fps, frame_time, cpu_usage, gpu_usage, memory_usage, temperature
                    metric_value REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    metadata TEXT, -- JSON for additional data
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES automation_runs(run_id)
                )
            """)
            
            # Scheduled runs table - for future scheduling feature
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sut_device_ids TEXT NOT NULL, -- JSON array of SUT device IDs
                    game_names TEXT NOT NULL, -- JSON array of game names
                    iterations INTEGER DEFAULT 1,
                    schedule_type TEXT NOT NULL, -- once, daily, weekly, on_sut_online
                    schedule_config TEXT, -- JSON configuration
                    enabled BOOLEAN DEFAULT TRUE,
                    last_run_time DATETIME,
                    next_run_time DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_suts_device_id ON suts(device_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_suts_ip_address ON suts(ip_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_suts_status ON suts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_run_id ON automation_runs(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_sut_device_id ON automation_runs(sut_device_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON automation_runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON automation_runs(created_at)")
            
            conn.commit()
            logger.info("Database tables initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic closing"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    # SUT Management Methods
    def upsert_sut(self, device_id: str, ip_address: str, port: int = 8080, 
                   hostname: str = None, capabilities: List[str] = None,
                   status: str = 'online') -> bool:
        """Insert or update SUT information"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    capabilities_json = json.dumps(capabilities or [])
                    now = datetime.now(timezone.utc).isoformat()
                    
                    # Check if SUT exists
                    existing = conn.execute(
                        "SELECT id, paired FROM suts WHERE device_id = ?", 
                        (device_id,)
                    ).fetchone()
                    
                    if existing:
                        # Update existing SUT
                        conn.execute("""
                            UPDATE suts SET 
                                ip_address = ?, port = ?, hostname = ?, 
                                capabilities = ?, last_seen = ?, status = ?,
                                updated_at = ?
                            WHERE device_id = ?
                        """, (ip_address, port, hostname, capabilities_json, now, status, now, device_id))
                    else:
                        # Insert new SUT
                        conn.execute("""
                            INSERT INTO suts (device_id, ip_address, port, hostname, capabilities, 
                                            last_seen, first_discovered, status, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (device_id, ip_address, port, hostname, capabilities_json, 
                              now, now, status, now, now))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error upserting SUT {device_id}: {e}")
            return False
    
    def pair_sut(self, device_id: str, nickname: str = None) -> bool:
        """Pair a SUT (like pairing a Bluetooth device)"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    now = datetime.now(timezone.utc).isoformat()
                    cursor = conn.execute("""
                        UPDATE suts SET paired = TRUE, paired_at = ?, nickname = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (now, nickname, now, device_id))
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.info(f"SUT {device_id} paired successfully with nickname: {nickname}")
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error pairing SUT {device_id}: {e}")
            return False
    
    def unpair_sut(self, device_id: str) -> bool:
        """Unpair a SUT (forget device)"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    now = datetime.now(timezone.utc).isoformat()
                    cursor = conn.execute("""
                        UPDATE suts SET paired = FALSE, paired_at = NULL, nickname = NULL, updated_at = ?
                        WHERE device_id = ?
                    """, (now, device_id))
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.info(f"SUT {device_id} unpaired successfully")
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error unpairing SUT {device_id}: {e}")
            return False
    
    def get_paired_suts(self) -> List[Dict[str, Any]]:
        """Get all paired SUTs"""
        try:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM suts WHERE paired = TRUE ORDER BY nickname, device_id
                """).fetchall()
                
                suts = []
                for row in rows:
                    sut = dict(row)
                    sut['capabilities'] = json.loads(sut['capabilities'] or '[]')
                    suts.append(sut)
                
                return suts
        except Exception as e:
            logger.error(f"Error getting paired SUTs: {e}")
            return []
    
    def get_all_suts(self) -> List[Dict[str, Any]]:
        """Get all SUTs (paired and discovered)"""
        try:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT * FROM suts ORDER BY paired DESC, last_seen DESC
                """).fetchall()
                
                suts = []
                for row in rows:
                    sut = dict(row)
                    sut['capabilities'] = json.loads(sut['capabilities'] or '[]')
                    suts.append(sut)
                
                return suts
        except Exception as e:
            logger.error(f"Error getting all SUTs: {e}")
            return []
    
    def delete_sut(self, device_id: str) -> bool:
        """Completely remove a SUT from database"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.execute("DELETE FROM suts WHERE device_id = ?", (device_id,))
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.info(f"SUT {device_id} deleted from database")
                        return True
                    return False
        except Exception as e:
            logger.error(f"Error deleting SUT {device_id}: {e}")
            return False
    
    # Run Management Methods
    def create_run_record(self, run_data: Dict[str, Any]) -> bool:
        """Create a new run record in database"""
        logger.info(f"DatabaseManager.create_run_record called with: {run_data}")
        try:
            logger.info("Acquiring database lock...")
            with self._lock:
                logger.info("Database lock acquired, getting connection...")
                with self.get_connection() as conn:
                    logger.info("Database connection established, executing INSERT...")
                    conn.execute("""
                        INSERT INTO automation_runs (
                            run_id, sut_device_id, game_name, game_config_path, status,
                            iterations, total_iterations, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        run_data['run_id'],
                        run_data['sut_device_id'], 
                        run_data['game_name'],
                        run_data.get('game_config_path'),
                        run_data['status'],
                        run_data['iterations'],
                        run_data['iterations'],
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    ))
                    logger.info("INSERT executed, committing transaction...")
                    conn.commit()
                    logger.info("Transaction committed successfully")
                    return True
        except Exception as e:
            logger.error(f"Error creating run record: {e}", exc_info=True)
            return False
    
    def update_run_status(self, run_id: str, status: str, progress: Dict[str, Any] = None,
                         results: Dict[str, Any] = None, error_message: str = None) -> bool:
        """Update run status and progress"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    update_fields = ["status = ?", "updated_at = ?"]
                    values = [status, datetime.now(timezone.utc).isoformat()]
                    
                    if progress:
                        update_fields.append("current_iteration = ?")
                        update_fields.append("current_step = ?")
                        values.extend([progress.get('current_iteration', 0), progress.get('current_step', 0)])
                        
                        if status in ['completed', 'failed', 'stopped'] and progress.get('end_time'):
                            update_fields.append("end_time = ?")
                            values.append(progress['end_time'])
                        elif status == 'running' and progress.get('start_time'):
                            update_fields.append("start_time = ?") 
                            values.append(progress['start_time'])
                    
                    if results:
                        update_fields.extend([
                            "success_rate = ?", "successful_runs = ?", 
                            "run_directory = ?", "error_logs = ?"
                        ])
                        values.extend([
                            results.get('success_rate', 0),
                            results.get('successful_runs', 0),
                            results.get('run_directory'),
                            json.dumps(results.get('error_logs', []))
                        ])
                    
                    if error_message:
                        update_fields.append("error_message = ?")
                        values.append(error_message)
                    
                    values.append(run_id)  # For WHERE clause
                    
                    query = f"UPDATE automation_runs SET {', '.join(update_fields)} WHERE run_id = ?"
                    cursor = conn.execute(query, values)
                    conn.commit()
                    
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating run {run_id}: {e}")
            return False
    
    def get_run_history(self, limit: int = 50, sut_device_id: str = None) -> List[Dict[str, Any]]:
        """Get run history with optional filtering"""
        try:
            with self.get_connection() as conn:
                if sut_device_id:
                    query = """
                        SELECT r.*, s.nickname as sut_nickname, s.hostname 
                        FROM automation_runs r 
                        LEFT JOIN suts s ON r.sut_device_id = s.device_id 
                        WHERE r.sut_device_id = ?
                        ORDER BY r.created_at DESC LIMIT ?
                    """
                    rows = conn.execute(query, (sut_device_id, limit)).fetchall()
                else:
                    query = """
                        SELECT r.*, s.nickname as sut_nickname, s.hostname 
                        FROM automation_runs r 
                        LEFT JOIN suts s ON r.sut_device_id = s.device_id 
                        ORDER BY r.created_at DESC LIMIT ?
                    """
                    rows = conn.execute(query, (limit,)).fetchall()
                
                runs = []
                for row in rows:
                    run = dict(row)
                    if run['error_logs']:
                        run['error_logs'] = json.loads(run['error_logs'])
                    runs.append(run)
                
                return runs
        except Exception as e:
            logger.error(f"Error getting run history: {e}")
            return []
    
    def get_active_runs(self) -> List[Dict[str, Any]]:
        """Get currently active runs"""
        try:
            with self.get_connection() as conn:
                rows = conn.execute("""
                    SELECT r.*, s.nickname as sut_nickname, s.hostname 
                    FROM automation_runs r 
                    LEFT JOIN suts s ON r.sut_device_id = s.device_id 
                    WHERE r.status IN ('queued', 'running')
                    ORDER BY r.created_at ASC
                """).fetchall()
                
                runs = []
                for row in rows:
                    run = dict(row)
                    if run['error_logs']:
                        run['error_logs'] = json.loads(run['error_logs'])
                    runs.append(run)
                
                return runs
        except Exception as e:
            logger.error(f"Error getting active runs: {e}")
            return []
    
    def get_run_by_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID"""
        try:
            with self.get_connection() as conn:
                row = conn.execute("""
                    SELECT r.*, s.nickname as sut_nickname, s.hostname 
                    FROM automation_runs r 
                    LEFT JOIN suts s ON r.sut_device_id = s.device_id 
                    WHERE r.run_id = ?
                """, (run_id,)).fetchone()
                
                if row:
                    run = dict(row)
                    if run['error_logs']:
                        run['error_logs'] = json.loads(run['error_logs'])
                    return run
                return None
        except Exception as e:
            logger.error(f"Error getting run {run_id}: {e}")
            return None
    
    def cleanup_old_runs(self, days: int = 30) -> int:
        """Clean up old run records"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cutoff_date = datetime.now(timezone.utc).replace(day=datetime.now().day - days).isoformat()
                    
                    # Delete old run iterations first (foreign key constraint)
                    conn.execute("""
                        DELETE FROM run_iterations WHERE run_id IN (
                            SELECT run_id FROM automation_runs 
                            WHERE created_at < ? AND status IN ('completed', 'failed', 'stopped')
                        )
                    """, (cutoff_date,))
                    
                    # Delete old performance metrics
                    conn.execute("""
                        DELETE FROM performance_metrics WHERE run_id IN (
                            SELECT run_id FROM automation_runs 
                            WHERE created_at < ? AND status IN ('completed', 'failed', 'stopped')
                        )
                    """, (cutoff_date,))
                    
                    # Delete old automation runs
                    cursor = conn.execute("""
                        DELETE FROM automation_runs 
                        WHERE created_at < ? AND status IN ('completed', 'failed', 'stopped')
                    """, (cutoff_date,))
                    
                    deleted_count = cursor.rowcount
                    conn.commit()
                    
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old run records")
                    
                    return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old runs: {e}")
            return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                stats = {}
                
                # SUT stats
                sut_stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_suts,
                        COUNT(CASE WHEN paired = TRUE THEN 1 END) as paired_suts,
                        COUNT(CASE WHEN status = 'online' THEN 1 END) as online_suts
                    FROM suts
                """).fetchone()
                stats['suts'] = dict(sut_stats)
                
                # Run stats
                run_stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_runs,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_runs,
                        COUNT(CASE WHEN status IN ('queued', 'running') THEN 1 END) as active_runs
                    FROM automation_runs
                """).fetchone()
                stats['runs'] = dict(run_stats)
                
                # Database file size
                db_path = Path(self.db_path)
                if db_path.exists():
                    stats['database_size_mb'] = round(db_path.stat().st_size / (1024 * 1024), 2)
                
                return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}