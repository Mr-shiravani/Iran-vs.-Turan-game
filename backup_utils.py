#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ابزارهای بکاپ و فشرده‌سازی
"""

import zipfile
import os
from datetime import datetime
from pathlib import Path

class BackupUtils:
    """ابزارهای کمکی برای بکاپ"""
    
    @staticmethod
    def create_backup_zip(backup_file_path: str, output_dir: str = "backups") -> str:
        """
        ایجاد فایل ZIP از بکاپ
        
        Args:
            backup_file_path: مسیر فایل بکاپ
            output_dir: پوشه خروجی
        
        Returns:
            مسیر فایل ZIP
        """
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"فایل بکاپ {backup_file_path} یافت نشد")
        
        # ایجاد نام فایل ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = os.path.basename(backup_file_path)
        zip_name = f"backup_{timestamp}.zip"
        zip_path = os.path.join(output_dir, zip_name)
        
        # ایجاد فایل ZIP
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_file_path, arcname=backup_name)
        
        return zip_path
    
    @staticmethod
    def get_backup_zip_size(zip_path: str) -> float:
        """دریافت اندازه فایل ZIP (MB)"""
        if os.path.exists(zip_path):
            return os.path.getsize(zip_path) / (1024 * 1024)
        return 0.0
