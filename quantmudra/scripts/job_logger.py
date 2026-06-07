"""
Job Execution Logger for QuantMudra
Tracks job runs with statistics in Oracle ATP
"""
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
import oracledb

# Job types
JOB_TYPES = {
    'update_daily': 'DAILY_UPDATE',
    'check_quality': 'QUALITY_CHECK',
    'process_corp_actions': 'CORP_ACTIONS',
    'update_index_composition': 'INDEX_UPDATE',
    'generate_quality_report': 'QUALITY_REPORT',
    'populate_reference_tables': 'REF_TABLES'
}


class JobLogger:
    """Logs job execution to JOB_EXECUTION_LOG table"""
    
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.connection = None
        self.job_name = None
        self.job_type = None
        self.start_time = None
        self.log_id = None
        
    def connect(self):
        """Establish database connection"""
        self.connection = oracledb.connect(
            user=self.db_config['user'],
            password=self.db_config['password'],
            dsn=self.db_config['dsn'],
            wallet_location=self.db_config.get('wallet_location'),
            wallet_password=self.db_config.get('wallet_password')
        )
        
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            
    def start_job(self, job_name: str) -> int:
        """Start logging a job, returns log_id"""
        self.job_name = job_name
        self.job_type = JOB_TYPES.get(job_name, 'UNKNOWN')
        self.start_time = datetime.now()
        
        if not self.connection:
            self.connect()
            
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO JOB_EXECUTION_LOG (JOB_NAME, JOB_TYPE, START_TIME, STATUS)
            VALUES (:1, :2, :3, 'RUNNING')
        """, [self.job_name, self.job_type, self.start_time])
        self.connection.commit()
        
        # Get the log_id
        cursor.execute("SELECT LOG_ID FROM JOB_EXECUTION_LOG WHERE JOB_NAME = :1 AND START_TIME = :2",
                      [self.job_name, self.start_time])
        result = cursor.fetchone()
        self.log_id = result[0] if result else None
        cursor.close()
        
        return self.log_id or 0
    
    def end_job(self, status: str, records_added: int = 0, 
                records_updated: int = 0, records_failed: int = 0,
                error_message: str = None):
        """Complete the job log entry"""
        if not self.start_time:
            return
            
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        cursor = self.connection.cursor()
        cursor.execute("""
            UPDATE JOB_EXECUTION_LOG
            SET END_TIME = :1,
                STATUS = :2,
                RECORDS_ADDED = :3,
                RECORDS_UPDATED = :4,
                RECORDS_FAILED = :5,
                ERROR_MESSAGE = :6,
                DURATION_SECONDS = :7
            WHERE LOG_ID = :8
        """, [end_time, status, records_added, records_updated, 
              records_failed, error_message, duration, self.log_id])
        self.connection.commit()
        cursor.close()
        
        print(f"📊 Job completed: {status} | Added: {records_added} | Updated: {records_updated} | Duration: {duration:.1f}s")
    
    def log_success(self, records_added: int = 0, records_updated: int = 0):
        """Log successful completion"""
        self.end_job('SUCCESS', records_added, records_updated)
        
    def log_failure(self, error: Exception):
        """Log failed job"""
        error_msg = str(error)[:2000] if error else "Unknown error"
        self.end_job('FAILED', error_message=error_msg)
        
    def log_partial(self, records_added: int = 0, records_updated: int = 0, 
                    records_failed: int = 0, error: Exception = None):
        """Log partial success with some failures"""
        error_msg = str(error)[:2000] if error else None
        self.end_job('PARTIAL', records_added, records_updated, records_failed, error_msg)


def get_last_run_status(db_config: dict, job_name: str = None) -> list:
    """Get last run status for jobs"""
    conn = oracledb.connect(
        user=db_config['user'],
        password=db_config['password'],
        dsn=db_config['dsn'],
        wallet_location=db_config.get('wallet_location'),
        wallet_password=db_config.get('wallet_password')
    )
    cursor = conn.cursor()
    
    if job_name:
        cursor.execute("""
            SELECT JOB_NAME, START_TIME, END_TIME, STATUS, 
                   RECORDS_ADDED, RECORDS_UPDATED, DURATION_SECONDS
            FROM V_JOB_LAST_RUN WHERE JOB_NAME = :1
        """, [job_name])
    else:
        cursor.execute("SELECT * FROM V_JOB_LAST_RUN ORDER BY START_TIME DESC")
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def print_job_status(db_config: dict):
    """Print current status of all jobs"""
    print("\n" + "="*70)
    print("📋 QUANTMUDRA JOB STATUS")
    print("="*70)
    
    results = get_last_run_status(db_config)
    
    if not results:
        print("No job runs recorded yet.")
        return
        
    print(f"{'Job Name':<30} {'Last Run':<20} {'Status':<10} {'Added':<8} {'Updated':<8}")
    print("-"*70)
    
    for row in results:
        job, start, end, status, added, updated, duration = row
        last_run = start.strftime('%Y-%m-%d %H:%M') if start else 'Never'
        status_emoji = {'SUCCESS': '✅', 'FAILED': '❌', 'PARTIAL': '⚠️', 'RUNNING': '🔄'}.get(status, '❓')
        print(f"{job:<30} {last_run:<20} {status_emoji} {status:<7} {added or 0:<8} {updated or 0:<8}")
    
    print("="*70)


if __name__ == '__main__':
    # Test - print job status
    from config import DB_CONFIG
    print_job_status(DB_CONFIG)