import os
import shutil
from datetime import datetime

def rotate_logs():
    """
    Rotates the bot.log file.
    1. Reads content of logs/bot.log
    2. Appends it to logs/bot_history.log with a timestamp header
    3. Clears logs/bot.log
    """
    log_dir = os.path.join(os.getcwd(), 'logs')
    bot_log = os.path.join(log_dir, 'bot.log')
    history_log = os.path.join(log_dir, 'bot_history.log')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    if os.path.exists(bot_log):
        try:
            with open(bot_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if content.strip():
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                header = f"\n\n{'='*50}\nARCHIVED SESSION: {timestamp}\n{'='*50}\n"
                
                with open(history_log, 'a', encoding='utf-8') as f:
                    f.write(header + content)
                    
                # Clear the current log
                with open(bot_log, 'w', encoding='utf-8') as f:
                    f.write("")
                
                print(f"Log rotated. Previous session appended to {history_log}")
        except Exception as e:
            print(f"Failed to rotate logs: {e}")
