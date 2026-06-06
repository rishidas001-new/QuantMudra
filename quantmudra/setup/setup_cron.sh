#!/bin/bash
# QuantMudra Data Pipeline Scheduler
# Sets up cron jobs for all data pipeline scripts

echo "=============================================="
echo "QuantMudra Data Pipeline - Cron Setup"
echo "=============================================="

# Create log directories
mkdir -p /workspace/quantmudra/logs
mkdir -p /workspace/quantmudra/reports

# Define scripts and their schedules
SCHEDULE_FILE="/workspace/quantmudra/cron_schedule.txt"

cat > $SCHEDULE_FILE << 'EOF'
# QuantMudra Data Pipeline - Cron Schedule
# ========================================

# Daily Data Update - 6:30 PM IST (1:00 PM UTC) on weekdays
30 13 * * 1-5 cd /workspace/quantmudra && python3 update_daily.py >> logs/update_daily.log 2>&1

# Daily Quality Check - 8:00 PM IST (2:30 PM UTC) on weekdays
0 14 * * 1-5 cd /workspace/quantmudra && python3 check_quality.py >> logs/check_quality.log 2>&1

# Daily Corporate Actions - 7:00 AM IST (1:30 AM UTC) EVERY DAY
0 1 * * * cd /workspace/quantmudra && python3 process_corp_actions.py >> logs/corp_actions.log 2>&1

# Weekly Quality Report - Sunday 6:00 PM IST (12:30 PM UTC)
0 12 * * 0 cd /workspace/quantmudra && python3 generate_quality_report.py >> logs/quality_report.log 2>&1

# Weekly Index Composition Update - Monday 3:00 AM IST
0 21 * * 1 cd /workspace/quantmudra && python3 update_index_composition.py >> logs/index_composition.log 2>&1
EOF

echo ""
echo "Schedule file created: $SCHEDULE_FILE"
echo ""
echo "Contents:"
echo "---------"
cat $SCHEDULE_FILE
echo ""
echo "=============================================="
echo "To install these cron jobs, run:"
echo ""
echo "  crontab $SCHEDULE_FILE"
echo ""
echo "To view current crontab:"
echo "  crontab -l"
echo ""
echo "To remove all QuantMudra cron jobs:"
echo "  crontab -r"
echo ""
echo "=============================================="
echo ""
echo "Schedule Summary:"
echo "-----------------"
echo "  Daily Update:     Weekdays at 6:30 PM IST"
echo "  Quality Check:    Weekdays at 8:00 PM IST"  
echo "  Corp Actions:     Daily at 7:00 AM IST"
echo "  Quality Report:   Sunday at 6:00 PM IST"
echo "  Index Update:     Monday at 3:00 AM IST"
echo ""
echo "=============================================="