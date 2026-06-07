#!/usr/bin/env python3
"""
Create JOB_EXECUTION_LOG table in Oracle ATP
Run this once to set up job execution logging
"""
import oracledb
import sys

DB_CONFIG = {
    'user': 'admin',
    'password': 'QuantMudra@2026',
    'dsn': 'quantmudra_high',
    'wallet_location': '/tmp/quantmudra_wallet',
    'wallet_password': 'QuantMudra@2026'
}

def create_job_execution_log_table(conn):
    """Create JOB_EXECUTION_LOG table and views"""
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME = 'JOB_EXECUTION_LOG'")
    if cursor.fetchone():
        print("JOB_EXECUTION_LOG table already exists. Skipping table creation.")
    else:
        # Create main table
        cursor.execute("""
            CREATE TABLE admin.JOB_EXECUTION_LOG (
                LOG_ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                JOB_NAME            VARCHAR2(50) NOT NULL,
                JOB_TYPE            VARCHAR2(30) NOT NULL,
                START_TIME          TIMESTAMP NOT NULL,
                END_TIME            TIMESTAMP,
                STATUS              VARCHAR2(20) NOT NULL,
                RECORDS_ADDED       NUMBER DEFAULT 0,
                RECORDS_UPDATED     NUMBER DEFAULT 0,
                RECORDS_FAILED      NUMBER DEFAULT 0,
                ERROR_MESSAGE       VARCHAR2(2000),
                DURATION_SECONDS    NUMBER,
                RUN_ENVIRONMENT     VARCHAR2(20) DEFAULT 'PRODUCTION',
                CREATED_AT          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT chk_status CHECK (STATUS IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'))
            )
        """)
        print("✅ Created JOB_EXECUTION_LOG table")
        
        # Create indexes
        cursor.execute("CREATE INDEX admin.idx_job_exec_log_job_name ON admin.JOB_EXECUTION_LOG(JOB_NAME)")
        cursor.execute("CREATE INDEX admin.idx_job_exec_log_start_time ON admin.JOB_EXECUTION_LOG(START_TIME DESC)")
        cursor.execute("CREATE INDEX admin.idx_job_exec_log_status ON admin.JOB_EXECUTION_LOG(STATUS)")
        print("✅ Created indexes")
    
    # Drop views if exist and recreate
    try:
        cursor.execute("DROP VIEW admin.V_JOB_LAST_RUN")
    except:
        pass
    
    try:
        cursor.execute("DROP VIEW admin.V_DAILY_JOB_SUMMARY")
    except:
        pass
    
    # Create V_JOB_LAST_RUN view
    cursor.execute("""
        CREATE OR REPLACE VIEW admin.V_JOB_LAST_RUN AS
        SELECT JOB_NAME, JOB_TYPE, START_TIME, END_TIME, STATUS, 
               RECORDS_ADDED, RECORDS_UPDATED, DURATION_SECONDS, ERROR_MESSAGE
        FROM (
            SELECT JOB_EXECUTION_LOG.*, 
                   ROW_NUMBER() OVER (PARTITION BY JOB_NAME ORDER BY START_TIME DESC) as rn
            FROM admin.JOB_EXECUTION_LOG
        )
        WHERE rn = 1
    """)
    print("✅ Created V_JOB_LAST_RUN view")
    
    # Create V_DAILY_JOB_SUMMARY view (simpler version without DECODE)
    cursor.execute("""
        CREATE OR REPLACE VIEW admin.V_DAILY_JOB_SUMMARY AS
        SELECT TRUNC(START_TIME) AS RUN_DATE, 
               COUNT(*) AS TOTAL_RUNS,
               SUM(RECORDS_ADDED) AS TOTAL_ADDED, 
               SUM(RECORDS_UPDATED) AS TOTAL_UPDATED,
               AVG(DURATION_SECONDS) AS AVG_DURATION_SEC
        FROM admin.JOB_EXECUTION_LOG
        GROUP BY TRUNC(START_TIME)
    """)
    print("✅ Created V_DAILY_JOB_SUMMARY view")
    
    # Add comments
    try:
        cursor.execute("COMMENT ON TABLE admin.JOB_EXECUTION_LOG IS 'Tracks all scheduled job executions with statistics'")
    except:
        pass
    
    conn.commit()
    cursor.close()
    print("\n✅ All objects created successfully!")

def verify_table(conn):
    """Verify table and views created correctly"""
    cursor = conn.cursor()
    
    print("\n📋 Verifying tables and views...")
    
    # Check table
    cursor.execute("SELECT COUNT(*) FROM admin.JOB_EXECUTION_LOG")
    print(f"✅ JOB_EXECUTION_LOG: {cursor.fetchone()[0]} rows")
    
    # Check views
    cursor.execute("SELECT VIEW_NAME FROM USER_VIEWS WHERE VIEW_NAME IN ('V_JOB_LAST_RUN', 'V_DAILY_JOB_SUMMARY')")
    views = [row[0] for row in cursor.fetchall()]
    print(f"✅ Views created: {views}")
    
    # Show structure
    print("\n📊 Table Structure:")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH 
        FROM USER_TAB_COLUMNS 
        WHERE TABLE_NAME = 'JOB_EXECUTION_LOG' 
        ORDER BY COLUMN_ID
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]:<20} {row[1]:<15} ({row[2]})")
    
    cursor.close()

def main():
    print("="*60)
    print("QuantMudra - Creating JOB_EXECUTION_LOG Table")
    print("="*60)
    
    try:
        print("\nConnecting to Oracle ATP...")
        conn = oracledb.connect(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dsn=DB_CONFIG['dsn'],
            config_dir=DB_CONFIG['wallet_location'],
            wallet_location=DB_CONFIG['wallet_location'],
            wallet_password=DB_CONFIG['wallet_password']
        )
        print("✅ Connected successfully!")
        
        create_job_execution_log_table(conn)
        verify_table(conn)
        
        conn.close()
        print("\n" + "="*60)
        print("✅ Setup Complete!")
        print("="*60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())