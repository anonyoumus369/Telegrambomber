import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import csv
import io

class Database:
    def __init__(self, db_name: str = "bombing_bot.db"):
        # Use Railway's data directory if available
        if os.environ.get('RAILWAY_VOLUME_MOUNT_PATH'):
            db_path = os.path.join(os.environ['RAILWAY_VOLUME_MOUNT_PATH'], db_name)
            self.db_name = db_path
        else:
            self.db_name = db_name
        
        self.lock = threading.Lock()
        self.init_database()
        self.start_auto_downgrade()

    def get_connection(self):
        """Create and return a database connection"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Initialize database tables"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    plan TEXT DEFAULT 'free',
                    bomb_count INTEGER DEFAULT 0,
                    total_bomb_time INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_bomb_time TIMESTAMP,
                    plan_expiry TIMESTAMP,
                    is_banned INTEGER DEFAULT 0,
                    total_spam INTEGER DEFAULT 0,
                    total_requests_sent INTEGER DEFAULT 0,
                    total_successful INTEGER DEFAULT 0
                )
            ''')
            
            # Bombing sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bombing_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    target_number TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration INTEGER,
                    requests_sent INTEGER DEFAULT 0,
                    successful_requests INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    plan_used TEXT,
                    speed_used INTEGER,
                    FOREIGN KEY (chat_id) REFERENCES users (chat_id)
                )
            ''')
            
            # Admin actions log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT,
                    target_user INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Payments/upgrades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    plan TEXT,
                    amount REAL,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiry_date TIMESTAMP,
                    status TEXT DEFAULT 'completed',
                    FOREIGN KEY (chat_id) REFERENCES users (chat_id)
                )
            ''')
            
            # API statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_stats (
                    api_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT,
                    total_attempts INTEGER DEFAULT 0,
                    total_success INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            conn.commit()
            conn.close()

    def add_user(self, chat_id: int, username: str, first_name: str, last_name: str = ""):
        """Add a new user to the database with 30-day expiry"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Set expiry to 30 days from now for all plans
            expiry_date = datetime.now() + timedelta(days=30)
            
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (chat_id, username, first_name, last_name, plan, plan_expiry)
                VALUES (?, ?, ?, ?, 'free', ?)
            ''', (chat_id, username, first_name, last_name, expiry_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            # If user already exists, update username/name
            cursor.execute('''
                UPDATE users 
                SET username = ?, first_name = ?, last_name = ?
                WHERE chat_id = ?
            ''', (username, first_name, last_name, chat_id))
            
            conn.commit()
            conn.close()

    def get_user(self, chat_id: int) -> Optional[Dict]:
        """Get user information"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE chat_id = ?', (chat_id,))
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None

    def update_user_plan(self, chat_id: int, plan: str):
        """Update user's plan with 30-day expiry"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Set expiry to 30 days from now
            expiry = datetime.now() + timedelta(days=30)
            
            cursor.execute('''
                UPDATE users 
                SET plan = ?, plan_expiry = ?
                WHERE chat_id = ?
            ''', (plan, expiry.strftime('%Y-%m-%d %H:%M:%S'), chat_id))
            
            # Log payment/upgrade
            cursor.execute('''
                INSERT INTO payments (chat_id, plan, amount, expiry_date)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, plan, 0.0, expiry.strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()

    def get_bombing_duration(self, plan: str) -> int:
        """Get bombing duration in seconds based on plan"""
        durations = {
            "free": 1 * 60,  # 1 minute for free users
            "premium": 4 * 60 * 60,  # 4 hours
            "ultra": 24 * 60 * 60  # 24 hours
        }
        return durations.get(plan, 1 * 60)

    def can_user_bomb(self, chat_id: int) -> tuple:
        """Check if user can bomb (not banned, plan not expired)"""
        user = self.get_user(chat_id)
        if not user:
            return False, "User not found. Please /start first."
        
        if user.get('is_banned'):
            return False, "You are banned from using this bot."
        
        # Check plan expiry
        expiry_str = user.get('plan_expiry')
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() > expiry_date:
                    # Auto-downgrade to free if expired
                    self.update_user_plan(chat_id, 'free')
                    return True, "Plan expired, downgraded to free"
            except:
                pass
        
        return True, "OK"

    def create_bombing_session(self, chat_id: int, target_number: str, plan: str) -> int:
        """Create a new bombing session and return session ID"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            duration = self.get_bombing_duration(plan)
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=duration)
            
            # Get speed based on plan
            if plan == "free":
                speed = 10
            elif plan == "premium":
                speed = 30
            elif plan == "ultra":
                speed = 50
            else:
                speed = 10
            
            cursor.execute('''
                INSERT INTO bombing_sessions 
                (chat_id, target_number, start_time, end_time, duration, plan_used, speed_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (chat_id, target_number, 
                  start_time.strftime('%Y-%m-%d %H:%M:%S'),
                  end_time.strftime('%Y-%m-%d %H:%M:%S'),
                  duration, plan, speed))
            
            session_id = cursor.lastrowid
            
            # Update user stats
            cursor.execute('''
                UPDATE users 
                SET bomb_count = bomb_count + 1,
                    last_bomb_time = ?
                WHERE chat_id = ?
            ''', (start_time.strftime('%Y-%m-%d %H:%M:%S'), chat_id))
            
            conn.commit()
            conn.close()
            
            return session_id

    def update_bombing_stats(self, session_id: int, requests_sent: int, successful: int):
        """Update bombing session statistics"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get chat_id from session
            cursor.execute('SELECT chat_id FROM bombing_sessions WHERE session_id = ?', (session_id,))
            session = cursor.fetchone()
            
            if session:
                chat_id = session['chat_id']
                
                # Update session stats
                cursor.execute('''
                    UPDATE bombing_sessions 
                    SET requests_sent = requests_sent + ?,
                        successful_requests = successful_requests + ?
                    WHERE session_id = ?
                ''', (requests_sent, successful, session_id))
                
                # Update user total spam stats
                cursor.execute('''
                    UPDATE users 
                    SET total_spam = total_spam + ?,
                        total_requests_sent = total_requests_sent + ?,
                        total_successful = total_successful + ?
                    WHERE chat_id = ?
                ''', (requests_sent, requests_sent, successful, chat_id))
            
            conn.commit()
            conn.close()

    def end_bombing_session(self, session_id: int):
        """Mark bombing session as completed"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE bombing_sessions 
                SET status = 'completed'
                WHERE session_id = ?
            ''', (session_id,))
            
            conn.commit()
            conn.close()

    def get_active_sessions(self) -> List[Dict]:
        """Get all active bombing sessions"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM bombing_sessions 
                WHERE status = 'active' 
                AND datetime(end_time) > datetime('now')
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def get_user_sessions(self, chat_id: int, limit: int = 10) -> List[Dict]:
        """Get user's bombing sessions"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM bombing_sessions 
                WHERE chat_id = ?
                ORDER BY start_time DESC
                LIMIT ?
            ''', (chat_id, limit))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def get_all_users(self, limit: int = 1000) -> List[Dict]:
        """Get all users"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM users 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def add_admin_log(self, admin_id: int, action: str, target_user: int = None, details: str = ""):
        """Log admin action"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO admin_logs (admin_id, action, target_user, details)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, action, target_user, details))
            
            conn.commit()
            conn.close()

    def ban_user(self, chat_id: int):
        """Ban a user"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET is_banned = 1 
                WHERE chat_id = ?
            ''', (chat_id,))
            
            self.add_admin_log(0, "ban_user", chat_id, "User banned")
            
            conn.commit()
            conn.close()

    def unban_user(self, chat_id: int):
        """Unban a user"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET is_banned = 0 
                WHERE chat_id = ?
            ''', (chat_id,))
            
            self.add_admin_log(0, "unban_user", chat_id, "User unbanned")
            
            conn.commit()
            conn.close()

    def auto_downgrade_users(self):
        """Auto-downgrade users whose plan has expired (after 30 days)"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Find users with expired premium/ultra plans
            cursor.execute('''
                SELECT chat_id, plan FROM users 
                WHERE plan IN ('premium', 'ultra') 
                AND datetime(plan_expiry) <= datetime('now')
                AND is_banned = 0
            ''')
            
            expired_users = cursor.fetchall()
            
            for user in expired_users:
                cursor.execute('''
                    UPDATE users 
                    SET plan = 'free',
                        plan_expiry = datetime('now', '+30 days')
                    WHERE chat_id = ?
                ''', (user['chat_id'],))
                
                # Log the auto-downgrade
                self.add_admin_log(0, "auto_downgrade", user['chat_id'], 
                                 f"Auto-downgraded from {user['plan']} to free (plan expired)")
                
                print(f"Auto-downgraded user {user['chat_id']} from {user['plan']} to free")
            
            conn.commit()
            conn.close()

    def start_auto_downgrade(self):
        """Start the auto-downgrade scheduler (runs every hour)"""
        def scheduler():
            while True:
                try:
                    self.auto_downgrade_users()
                except Exception as e:
                    print(f"Error in auto-downgrade: {e}")
                time.sleep(3600)  # Check every hour
        
        thread = threading.Thread(target=scheduler, daemon=True)
        thread.start()

    def get_user_stats(self) -> Dict:
        """Get overall user statistics"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as total FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) as banned FROM users WHERE is_banned = 1')
            banned_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) as active FROM users WHERE is_banned = 0')
            active_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT plan, COUNT(*) as count FROM users GROUP BY plan')
            plan_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get users with expired plans
            cursor.execute('''
                SELECT COUNT(*) as expired FROM users 
                WHERE datetime(plan_expiry) <= datetime('now')
                AND is_banned = 0
            ''')
            expired_users = cursor.fetchone()[0]
            
            # Get total spam stats
            cursor.execute('SELECT SUM(total_spam) as total_spam, SUM(total_requests_sent) as total_requests, SUM(total_successful) as total_success FROM users')
            spam_stats = cursor.fetchone()
            
            conn.close()
            
            return {
                'total_users': total_users,
                'banned_users': banned_users,
                'active_users': active_users,
                'expired_users': expired_users,
                'plan_stats': plan_stats,
                'total_spam': spam_stats[0] or 0,
                'total_requests': spam_stats[1] or 0,
                'total_success': spam_stats[2] or 0
            }

    def export_users_csv(self) -> str:
        """Export all users to CSV format"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    plan,
                    bomb_count,
                    total_spam,
                    total_requests_sent,
                    total_successful,
                    strftime('%Y-%m-%d %H:%M:%S', created_at) as created_at,
                    strftime('%Y-%m-%d %H:%M:%S', plan_expiry) as plan_expiry,
                    CASE WHEN is_banned = 1 THEN 'Yes' ELSE 'No' END as is_banned,
                    CASE WHEN datetime(plan_expiry) <= datetime('now') THEN 'Expired' ELSE 'Active' END as plan_status
                FROM users
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Create CSV content
            csv_content = "Chat ID,Username,First Name,Last Name,Plan,Bomb Count,Total Spam,Total Requests,Total Successful,Created At,Plan Expiry,Is Banned,Plan Status\n"
            for row in rows:
                csv_content += f"{row[0]},{row[1] or ''},{row[2] or ''},{row[3] or ''},{row[4]},{row[5]},{row[6]},{row[7]},{row[8]},{row[9]},{row[10]},{row[11]},{row[12]}\n"
            
            return csv_content

    def extend_user_plan(self, chat_id: int, days: int = 30):
        """Extend user's plan expiry by days"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET plan_expiry = datetime(plan_expiry, ?)
                WHERE chat_id = ?
            ''', (f"+{days} days", chat_id))
            
            self.add_admin_log(0, "extend_plan", chat_id, f"Extended plan by {days} days")
            
            conn.commit()
            conn.close()

    def get_recent_sessions(self, hours: int = 24) -> List[Dict]:
        """Get recent bombing sessions"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    bs.session_id,
                    bs.chat_id,
                    u.username,
                    bs.target_number,
                    bs.requests_sent,
                    bs.successful_requests,
                    bs.start_time,
                    bs.duration,
                    bs.plan_used,
                    bs.speed_used
                FROM bombing_sessions bs
                LEFT JOIN users u ON bs.chat_id = u.chat_id
                WHERE bs.start_time >= datetime('now', ?)
                ORDER BY bs.start_time DESC
                LIMIT 50
            ''', (f"-{hours} hours",))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def update_api_stats(self, api_name: str, success: bool):
        """Update API usage statistics"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if API exists
            cursor.execute('SELECT api_id FROM api_stats WHERE api_name = ?', (api_name,))
            api_exists = cursor.fetchone()
            
            if api_exists:
                # Update existing API stats
                if success:
                    cursor.execute('''
                        UPDATE api_stats 
                        SET total_attempts = total_attempts + 1,
                            total_success = total_success + 1,
                            last_used = datetime('now')
                        WHERE api_name = ?
                    ''', (api_name,))
                else:
                    cursor.execute('''
                        UPDATE api_stats 
                        SET total_attempts = total_attempts + 1,
                            last_used = datetime('now')
                        WHERE api_name = ?
                    ''', (api_name,))
            else:
                # Insert new API
                if success:
                    cursor.execute('''
                        INSERT INTO api_stats (api_name, total_attempts, total_success, last_used)
                        VALUES (?, 1, 1, datetime('now'))
                    ''', (api_name,))
                else:
                    cursor.execute('''
                        INSERT INTO api_stats (api_name, total_attempts, total_success, last_used)
                        VALUES (?, 1, 0, datetime('now'))
                    ''', (api_name,))
            
            conn.commit()
            conn.close()

    def get_api_stats(self) -> List[Dict]:
        """Get API usage statistics"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    api_name,
                    total_attempts,
                    total_success,
                    CASE 
                        WHEN total_attempts > 0 
                        THEN ROUND((total_success * 100.0) / total_attempts, 2)
                        ELSE 0 
                    END as success_rate,
                    last_used
                FROM api_stats
                WHERE is_active = 1
                ORDER BY total_attempts DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Get top users by total spam"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    chat_id,
                    username,
                    first_name,
                    plan,
                    bomb_count,
                    total_spam,
                    total_requests_sent,
                    total_successful,
                    CASE 
                        WHEN total_requests_sent > 0 
                        THEN ROUND((total_successful * 100.0) / total_requests_sent, 2)
                        ELSE 0 
                    END as success_rate
                FROM users
                WHERE is_banned = 0
                ORDER BY total_spam DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def cleanup_old_sessions(self, days: int = 7):
        """Clean up old bombing sessions to save space"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM bombing_sessions 
                WHERE start_time < datetime('now', ?)
                AND status = 'completed'
            ''', (f"-{days} days",))
            
            deleted_count = cursor.rowcount
            
            cursor.execute('VACUUM')  # Clean up database file
            
            conn.commit()
            conn.close()
            
            return deleted_count

    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """Get daily statistics for the last N days"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    DATE(start_time) as date,
                    COUNT(*) as session_count,
                    SUM(requests_sent) as total_requests,
                    SUM(successful_requests) as total_success,
                    COUNT(DISTINCT chat_id) as unique_users
                FROM bombing_sessions
                WHERE start_time >= datetime('now', ?)
                GROUP BY DATE(start_time)
                ORDER BY date DESC
            ''', (f"-{days} days",))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]

    def backup_database(self) -> bytes:
        """Create a backup of the database"""
        import shutil
        import tempfile
        
        with self.lock:
            # Create a temporary file for backup
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
                # Copy the database
                shutil.copy2(self.db_name, tmp_file.name)
                
                # Read the backup
                with open(tmp_file.name, 'rb') as f:
                    backup_data = f.read()
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return backup_data

    def optimize_database(self):
        """Optimize database performance"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Analyze tables for better query planning
            cursor.execute('ANALYZE')
            
            # Update statistics
            cursor.execute('UPDATE sqlite_stat1')
            
            # Reindex tables
            cursor.execute('REINDEX')
            
            conn.commit()
            conn.close()

# Create global database instance
db = Database()