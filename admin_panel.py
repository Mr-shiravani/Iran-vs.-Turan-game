#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
پنل ادمین امن با رمزنگاری
- مدیریت بکاپ‌ها
- انتقال درفش/XP/سطح
- مسدود کردن کاربران
"""

import hashlib
import os
import secrets
from datetime import datetime
import sqlite3
from typing import Optional, Tuple

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or "0")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


class AdminPanel:
    """مدیریت امن پنل ادمین"""
    
    @staticmethod
    def generate_access_token() -> str:
        """تولید توکن دسترسی یکبار مصرف"""
        token = secrets.token_urlsafe(32)
        return token
    
    @staticmethod
    def hash_password(password: str) -> str:
        """رمزنگاری کلمه عبور"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, admin_id: int) -> bool:
        """تأیید کلمه عبور ادمین"""
        # فقط ادمین مشخص شده می‌تواند وارد شود
        if not ADMIN_ID or admin_id != ADMIN_ID:
            return False
        
        # تأیید کلمه عبور
        expected_hash = AdminPanel.hash_password(ADMIN_PASSWORD)
        provided_hash = AdminPanel.hash_password(password)
        return provided_hash == expected_hash
    
    @staticmethod
    def create_access_session(admin_id: int, db_path: str) -> Optional[str]:
        """ایجاد جلسه دسترسی برای ادمین"""
        if not ADMIN_ID or admin_id != ADMIN_ID:
            return None
        
        token = AdminPanel.generate_access_token()
        
        # ذخیره توکن در دیتابیس
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            
            # ایجاد جدول جلسات اگر وجود ندارد
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    token TEXT UNIQUE,
                    created_at TEXT,
                    expires_at TEXT,
                    used INTEGER DEFAULT 0
                )
            """)
            
            # ذخیره جلسه جدید (۱ ساعت اعتبار)
            from datetime import timedelta
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            
            cur.execute("""
                INSERT INTO admin_sessions (admin_id, token, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (admin_id, token, datetime.utcnow().isoformat(), expires_at))
            
            conn.commit()
            return token
        finally:
            conn.close()
    
    @staticmethod
    def verify_session_token(token: str, db_path: str) -> Tuple[bool, Optional[int]]:
        """تأیید توکن جلسه"""
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT admin_id, expires_at FROM admin_sessions 
                WHERE token = ? AND used = 0
            """, (token,))
            
            row = cur.fetchone()
            if not row:
                return False, None
            
            admin_id, expires_at = row
            
            # بررسی انقضای توکن
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.utcnow() > exp_dt:
                    return False, None
            except:
                return False, None
            
            return True, admin_id
        finally:
            conn.close()
    
    @staticmethod
    def invalidate_session(token: str, db_path: str) -> bool:
        """غیرفعال کردن جلسه"""
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("UPDATE admin_sessions SET used = 1 WHERE token = ?", (token,))
            conn.commit()
            return True
        finally:
            conn.close()


class AdminActions:
    """اقدامات ادمینی"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def transfer_drafsh(self, from_user_id: int, to_user_id: int, amount: int) -> Tuple[bool, str]:
        """انتقال درفش بین کاربران"""
        if amount <= 0:
            return False, "❌ مقدار باید بیشتر از صفر باشد"
        
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # بررسی موجودی
            cur.execute("SELECT drafsh FROM users WHERE user_id = ?", (from_user_id,))
            from_row = cur.fetchone()
            if not from_row or int(from_row[0] or 0) < amount:
                return False, f"❌ درفش کافی نیست (موجود: {int(from_row[0] or 0)})"
            
            # بررسی وجود کاربر مقصد
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (to_user_id,))
            if not cur.fetchone():
                return False, "❌ کاربر مقصد یافت نشد"
            
            # انتقال
            cur.execute("UPDATE users SET drafsh = drafsh - ? WHERE user_id = ?", (amount, from_user_id))
            cur.execute("UPDATE users SET drafsh = drafsh + ? WHERE user_id = ?", (amount, to_user_id))
            conn.commit()
            
            return True, f"✅ {amount} درفش از {from_user_id} به {to_user_id} منتقل شد"
        except Exception as e:
            return False, f"❌ خطا: {e}"
        finally:
            conn.close()
    
    def transfer_xp(self, from_user_id: int, to_user_id: int, amount: int) -> Tuple[bool, str]:
        """انتقال XP بین کاربران"""
        if amount <= 0:
            return False, "❌ مقدار باید بیشتر از صفر باشد"
        
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # بررسی موجودی
            cur.execute("SELECT xp FROM users WHERE user_id = ?", (from_user_id,))
            from_row = cur.fetchone()
            if not from_row or int(from_row[0] or 0) < amount:
                return False, f"❌ XP کافی نیست (موجود: {int(from_row[0] or 0)})"
            
            # بررسی وجود کاربر مقصد
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (to_user_id,))
            if not cur.fetchone():
                return False, "❌ کاربر مقصد یافت نشد"
            
            # انتقال
            cur.execute("UPDATE users SET xp = xp - ? WHERE user_id = ?", (amount, from_user_id))
            cur.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, to_user_id))
            conn.commit()
            
            return True, f"✅ {amount} XP از {from_user_id} به {to_user_id} منتقل شد"
        except Exception as e:
            return False, f"❌ خطا: {e}"
        finally:
            conn.close()
    
    def set_level(self, user_id: int, level: int) -> Tuple[bool, str]:
        """تنظیم سطح کاربر"""
        if level < 1 or level > 9999:
            return False, "❌ سطح باید بین 1 و 9999 باشد"
        
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # بررسی وجود کاربر
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cur.fetchone():
                return False, "❌ کاربر یافت نشد"
            
            # تنظیم سطح
            cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
            conn.commit()
            
            return True, f"✅ سطح {user_id} به {level} تنظیم شد"
        except Exception as e:
            return False, f"❌ خطا: {e}"
        finally:
            conn.close()
    
    def block_user(self, user_id: int, reason: str = "") -> Tuple[bool, str]:
        """مسدود کردن کاربر"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # ایجاد جدول مسدود شدگان اگر وجود ندارد
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    reason TEXT,
                    blocked_at TEXT
                )
            """)
            
            # بررسی وجود کاربر
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cur.fetchone():
                return False, "❌ کاربر یافت نشد"
            
            # مسدود کردن
            cur.execute("""
                INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at)
                VALUES (?, ?, ?)
            """, (user_id, reason, datetime.utcnow().isoformat()))
            
            conn.commit()
            return True, f"✅ کاربر {user_id} مسدود شد"
        except Exception as e:
            return False, f"❌ خطا: {e}"
        finally:
            conn.close()
    
    def unblock_user(self, user_id: int) -> Tuple[bool, str]:
        """رفع مسدودیت کاربر"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # حذف از لیست مسدود شدگان
            cur.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
            conn.commit()
            
            return True, f"✅ مسدودیت کاربر {user_id} رفع شد"
        except Exception as e:
            return False, f"❌ خطا: {e}"
        finally:
            conn.close()
    
    def is_user_blocked(self, user_id: int) -> bool:
        """بررسی مسدود بودن کاربر"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM blocked_users WHERE user_id = ?", (user_id,))
            return cur.fetchone() is not None
        finally:
            conn.close()
    
    def get_user_info(self, user_id: int) -> Optional[dict]:
        """دریافت اطلاعات کاربر"""
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT user_id, username, full_name, hero, level, xp, honor, drafsh
                FROM users WHERE user_id = ?
            """, (user_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                'user_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'hero': row[3],
                'level': row[4],
                'xp': row[5],
                'honor': row[6],
                'drafsh': row[7]
            }
        finally:
            conn.close()


if __name__ == "__main__":
    if not ADMIN_PASSWORD or not ADMIN_ID:
        print("ADMIN_PASSWORD و ADMIN_ID را در .env تنظیم کنید.")
    else:
        hashed = AdminPanel.hash_password(ADMIN_PASSWORD)
        print(f"Hash: {hashed[:20]}...")
        print(f"Valid: {AdminPanel.verify_password(ADMIN_PASSWORD, ADMIN_ID)}")
