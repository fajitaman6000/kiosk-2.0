import os
import sys
import time
import datetime
import zipfile
import shutil
from pathlib import Path
import argparse

def archive_old_logs(log_dir="logs", archive_dir="logs/archive", days_to_keep=7, delete_after_archive=False):
    """
    Archive log files older than the specified number of days.
    
    Args:
        log_dir: Directory containing log files
        archive_dir: Directory to store archived log files
        days_to_keep: Number of days to keep logs before archiving
        delete_after_archive: Whether to delete the original log files after archiving
    """
    log_dir = Path(log_dir)
    archive_dir = Path(archive_dir)
    
    # Create archive directory if it doesn't exist
    os.makedirs(archive_dir, exist_ok=True)
    
    # Get current time
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=days_to_keep)
    
    # Find log files older than the cutoff date
    log_files = list(log_dir.glob("kiosk_log_*.txt"))
    old_logs = []
    
    for log_file in log_files:
        try:
            # Extract date from filename (format: kiosk_log_YYYY-MM-DD_HH-MM-SS.txt)
            file_date_str = log_file.name.replace("kiosk_log_", "").replace(".txt", "")
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d_%H-%M-%S")
            
            if file_date < cutoff_date:
                old_logs.append(log_file)
        except Exception as e:
            print(f"Error parsing date from {log_file.name}: {e}")
    
    print(f"Found {len(old_logs)} log files older than {days_to_keep} days")
    
    if not old_logs:
        print("No log files to archive")
        return
    
    # Create archive file with current timestamp
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = archive_dir / f"logs_archive_{timestamp}.zip"
    
    # Create zip archive
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for log_file in old_logs:
            try:
                # Add file to zip with just the filename (not the full path)
                zipf.write(log_file, arcname=log_file.name)
                print(f"Added {log_file.name} to archive")
                
                # Delete original if requested
                if delete_after_archive:
                    os.remove(log_file)
                    print(f"Deleted {log_file.name}")
            except Exception as e:
                print(f"Error archiving {log_file.name}: {e}")
    
    print(f"Archive created: {archive_path}")
    print(f"Archived {len(old_logs)} log files")

def main():
    """Command line interface for the log archiver."""
    parser = argparse.ArgumentParser(description="Archive old kiosk log files")
    parser.add_argument("--log-dir", default="logs", help="Directory containing log files")
    parser.add_argument("--archive-dir", default="logs/archive", help="Directory to store archived log files")
    parser.add_argument("--days", type=int, default=7, help="Number of days to keep logs before archiving")
    parser.add_argument("--delete", action="store_true", help="Delete original log files after archiving")
    
    args = parser.parse_args()
    
    try:
        archive_old_logs(
            log_dir=args.log_dir,
            archive_dir=args.archive_dir,
            days_to_keep=args.days,
            delete_after_archive=args.delete
        )
    except Exception as e:
        print(f"Error archiving logs: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 