#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
مدیریت بکاپ خودکار دیتابیس
- بکاپ روزانه خودکار
- بکاپ قبل از هر تغییر مهم
- بازیابی از بکاپ در صورت خرابی
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BackupManager:
    """مدیریت بکاپ‌های دیتابیس"""
    
    def __init__(self, db_path: str, backup_dir: str = "backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self) -> None:
        """ایجاد پوشه بکاپ اگر وجود ندارد"""
        Path(self.backup_dir).mkdir(exist_ok=True)
    
    def create_backup(self, reason: str = "manual") -> str:
        """
        ایجاد بکاپ فوری
        
        Args:
            reason: دلیل بکاپ (manual, daily, before_update, etc)
        
        Returns:
            مسیر فایل بکاپ
        """
        if not os.path.exists(self.db_path):
            logger.warning(f"دیتابیس {self.db_path} وجود ندارد")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{reason}_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        try:
            # کپی فایل دیتابیس
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"✅ بکاپ ایجاد شد: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد بکاپ: {e}")
            return ""
    
    def create_daily_backup(self) -> str:
        """ایجاد بکاپ روزانه (فقط اگر امروز بکاپ نشده باشد)"""
        today = datetime.now().strftime("%Y%m%d")
        
        # چک کردن اینکه امروز بکاپ شده یا نه
        for file in os.listdir(self.backup_dir):
            if f"backup_daily_{today}" in file:
                logger.info("✅ بکاپ روزانه امروز قبلاً ایجاد شده است")
                return ""
        
        return self.create_backup("daily")
    
    def get_latest_backup(self) -> Optional[str]:
        """دریافت آخرین بکاپ"""
        backups = sorted(
            [f for f in os.listdir(self.backup_dir) if f.endswith('.db')],
            reverse=True
        )
        
        if backups:
            return os.path.join(self.backup_dir, backups[0])
        return None
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """
        بازیابی دیتابیس از بکاپ
        
        Args:
            backup_path: مسیر فایل بکاپ
        
        Returns:
            موفقیت یا عدم موفقیت
        """
        if not os.path.exists(backup_path):
            logger.error(f"❌ فایل بکاپ {backup_path} وجود ندارد")
            return False
        
        try:
            # بکاپ از دیتابیس فعلی قبل از بازیابی
            self.create_backup("before_restore")
            
            # کپی بکاپ به جای دیتابیس فعلی
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"✅ دیتابیس از بکاپ بازیابی شد: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در بازیابی: {e}")
            return False
    
    def restore_latest(self) -> bool:
        """بازیابی از آخرین بکاپ"""
        latest = self.get_latest_backup()
        if not latest:
            logger.error("❌ هیچ بکاپی موجود نیست")
            return False
        
        return self.restore_from_backup(latest)
    
    def cleanup_old_backups(self, keep_days: int = 7) -> int:
        """
        حذف بکاپ‌های قدیمی‌تر از تعداد روز مشخص شده
        
        Args:
            keep_days: تعداد روزهایی که بکاپ نگه‌داری شود
        
        Returns:
            تعداد بکاپ‌های حذف شده
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for file in os.listdir(self.backup_dir):
            if not file.endswith('.db'):
                continue
            
            file_path = os.path.join(self.backup_dir, file)
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            if file_time < cutoff_date:
                try:
                    os.remove(file_path)
                    logger.info(f"🗑️ بکاپ قدیمی حذف شد: {file}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"❌ خطا در حذف {file}: {e}")
        
        return deleted_count
    
    def list_backups(self) -> list:
        """لیست تمام بکاپ‌ها"""
        backups = []
        for file in sorted(os.listdir(self.backup_dir), reverse=True):
            if file.endswith('.db'):
                file_path = os.path.join(self.backup_dir, file)
                size = os.path.getsize(file_path) / 1024  # KB
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                backups.append({
                    'name': file,
                    'path': file_path,
                    'size_kb': round(size, 2),
                    'created': mtime.strftime("%Y-%m-%d %H:%M:%S")
                })
        return backups
    
    def verify_backup(self, backup_path: str) -> bool:
        """
        تأیید سلامت فایل بکاپ
        
        Args:
            backup_path: مسیر فایل بکاپ
        
        Returns:
            آیا بکاپ سالم است
        """
        try:
            conn = sqlite3.connect(backup_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            conn.close()
            logger.info(f"✅ بکاپ سالم است: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ بکاپ خراب است: {e}")
            return False


# تست
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    bm = BackupManager("war_of_heroes.db")
    
    # ایجاد بکاپ
    print("📦 ایجاد بکاپ...")
    backup = bm.create_backup("test")
    
    # لیست بکاپ‌ها
    print("\n📋 لیست بکاپ‌ها:")
    for b in bm.list_backups():
        print(f"  - {b['name']} ({b['size_kb']} KB) - {b['created']}")
    
    # تأیید بکاپ
    if backup:
        print(f"\n✔️ تأیید بکاپ...")
        is_valid = bm.verify_backup(backup)
        print(f"  نتیجه: {'✅ سالم' if is_valid else '❌ خراب'}")
    
    # پاک‌سازی بکاپ‌های قدیمی
    print(f"\n🗑️ پاک‌سازی بکاپ‌های قدیمی...")
    deleted = bm.cleanup_old_backups(keep_days=7)
    print(f"  {deleted} بکاپ حذف شد")
