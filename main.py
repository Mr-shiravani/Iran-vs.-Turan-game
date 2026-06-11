#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# این فایل "main.py" یک ربات تلگرام با نام «جنگ پهلوانان» را با استفاده از کتابخانه python-telegram-bot پیاده‌سازی می‌کند.
# هدف: بازی متنی حماسی الهام‌گرفته از شاهنامه با انتخاب قهرمان، نبرد، تمرین روزانه، آمار و جدول افتخارات.

# نکات مهم:
# - از ContextTypes.DEFAULT_TYPE در هندلرها استفاده شده است (نسخه 20+ کتابخانه).
# - دیتابیس SQLite با جداول users و user_training (برای محدودیت تمرین روزانه) استفاده می‌شود.
# - عضویت اجباری در یک کانال/گروه با چک کردن get_chat_member انجام می‌شود.
# - پیام‌ها با Markdown و ایموجی‌ها و لحن حماسی ارسال می‌شوند.
# - ساختار کد ماژولار است تا توسعه آینده (رویدادها، آیتم‌ها، سیستم سطح) آسان باشد.

import os  # برای خواندن متغیرهای محیطی مانند توکن ربات و شناسه کانال

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
# JSON ارسال فایل حذف شد؛ پیاده‌سازی درون‌بات انجام می‌شود
import sqlite3  # برای ارتباط با دیتابیس SQLite
import random  # برای اتفاقات و محاسبات تصادفی در نبرد
import logging  # برای لاگ‌گیری و عیب‌یابی
from datetime import datetime, timedelta  # برای مدیریت محدودیت تمرین روزانه
from backup_manager import BackupManager  # برای مدیریت بکاپ‌های دیتابیس
from admin_panel import AdminPanel, AdminActions  # برای پنل ادمین امن
from backup_utils import BackupUtils  # برای فشرده‌سازی بکاپ

from typing import Optional, Dict, Any, Tuple, List  # تایپ‌دهی خواناتر

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ChatMember,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)


# --------------------------- پیکربندی و ثابت‌ها ---------------------------

# توکن ربات — حتماً در فایل .env تنظیم کنید
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# نام کاربری یا آیدی کانال/گروهی که عضویت در آن اجباری است (مانند @your_channel)
REQUIRED_CHAT = os.environ.get("REQUIRED_CHAT", "@your_channel")

# مسیر دیتابیس SQLite
DB_PATH = os.environ.get("DB_PATH", "war_of_heroes.db")

# شناسه ادمین و رمزهای دسترسی
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or "0")
ADMIN_PANEL_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD", "")
GODMODE_CODE = os.environ.get("GODMODE_CODE", "")

# نام و برند بازی
GAME_NAME = "جنگ پهلوانان"

# نگاشت نژادها و اثرات پایه آن‌ها
# هر نژاد اثراتی روی ویژگی‌ها و منطق نبرد دارد
RACES: Dict[str, Dict[str, Any]] = {
    "🇮🇷 ایران": {"power_bonus": 5, "wisdom_bonus": 0, "health_bonus": 0, "speed_bonus": 0, "honor_win_bonus": 5},
    "🐉 توران": {"power_bonus": 0, "wisdom_bonus": 0, "health_bonus": 0, "speed_bonus": 5, "double_attack_chance": 0.15},
    "🕊 سیستان": {"power_bonus": 0, "wisdom_bonus": 5, "health_bonus": 0, "speed_bonus": 0, "simorgh_revive": True},
    "🌊 سمنگان": {"power_bonus": 0, "wisdom_bonus": 0, "health_bonus": 10, "speed_bonus": 0, "better_training": True},
    "🔥 دیوان": {"power_bonus": 8, "wisdom_bonus": -2, "health_bonus": 0, "speed_bonus": 0, "honor_win_penalty": -5},
}

# نگاشت قهرمان‌ها و ویژگی‌های اولیه‌شان
HEROES: Dict[str, Dict[str, Any]] = {
    "🌸 تهمینه": {
        "power": 45, 
        "wisdom": 65, 
        "health": 80,
        "required_level": 1, 
        "race": "🌊 سمنگان",
        "ability": "شفای مهربان",
        "ability_desc": "15٪ احتمال بازیابی 5 سلامت پس از حمله",
        "description": "آغازگر مسیر پهلوانی؛ خردمند و مقاوم."
    },
    "🌹 رودابه": {
        "power": 50, 
        "wisdom": 70, 
        "health": 85,
        "required_level": 3, 
        "race": "🌊 سمنگان",
        "ability": "برکت سیمرغ",
        "ability_desc": "10٪ احتمال کاهش دمیج دشمن",
        "description": "نماد آرامش و فرزانگی؛ حامی پهلوانان."
    },
    "🦅 زال": {
        "power": 65, 
        "wisdom": 80, 
        "health": 100,
        "required_level": 6, 
        "race": "🕊 سیستان",
        "ability": "دعوت سیمرغ",
        "ability_desc": "1 بار در هر نبرد احیای جزئی سلامت",
        "description": "فرزانه‌ی سپیدموی، استاد رزم و خرد."
    },
    "⚔️ سهراب": {
        "power": 85, 
        "wisdom": 45, 
        "health": 110,
        "required_level": 10, 
        "race": "🐉 توران",
        "ability": "خشم جوانی",
        "ability_desc": "20٪ احتمال ضربه دوبرابر",
        "description": "جوان، نیرومند و بی‌پروا؛ دشمن و فرزند پهلوانان."
    },
    "🛡 اسفندیار": {
        "power": 90, 
        "wisdom": 60, 
        "health": 120,
        "required_level": 15, 
        "race": "🇮🇷 ایران",
        "ability": "بدن رویین",
        "ability_desc": "15٪ احتمال بی‌اثر شدن ضربه دشمن",
        "description": "رویین‌تن و نیرومند، نماد استقامت و فرمان."
    },
    "🦁 رستم": {
        "power": 100, 
        "wisdom": 70, 
        "health": 140,
        "required_level": 20, 
        "race": "🕊 سیستان",
        "ability": "غرش رخش",
        "ability_desc": "20٪ احتمال حمله دوم پشت‌سرهم",
        "description": "بزرگ‌ترین پهلوان ایران‌زمین، شکست‌ناپذیر در نبرد."
    },
}

# مجموعه ابیات حماسی برای هر پهلوان
QUOTES: Dict[str, Dict[str, List[str]]] = {
    "🦁 رستم": {
        "attack_quotes": [
            "⚔️ > ز خشم و ز نیروی یزدانِ پاک\nبرآورد فریاد چون ابرِ خاک",
            "🔥 > چو رستم برانگیخت رخشِ دلیر\nزمین شد چو دریای خون تا به سیر",
            "🩸 > یکی گرزِ گاوسر آمد به کار\nجهان شد پر از بانگِ کین و دمار",
        ],
        "revenge_quotes": [
            "⚡️ > بزد بر سر دشمنان تیز گرز\nکه شد خاک با خون برابر به مرز",
            "🛡 > دلیران ز بیمش شدند اشکبار\nچو رستم برآورد بانگِ شکار",
            "🔥 > به خشم اندر آمد چو شیر ژیان\nبزد تا نماند از بدی نشان",
        ],
    },
    "⚔️ سهراب": {
        "attack_quotes": [
            "⚔️ > ز خشم و جوانی برآورد بانگ\nز آهنگِ شمشیر شد کوه تنگ",
            "🔥 > چو شیر ژیان حمله آورد پیش\nزمین شد به خون چون گل و برگِ خیش",
            "🩸 > ز برقِ سنانش هوا شد سپید\nدلِ دشمن از بیم شد ناپدید",
        ],
        "revenge_quotes": [
            "⚡️ > بزد تیغ چون آذر از آسمان\nبرآمد خروش از دلِ بدگمان",
            "🩸 > چو بختِ جوانش به خون دست شست\nزمین گشت چون دامنِ لاله‌دُست",
            "🔥 > به شمشیر گفتا که: «وقتِ من است»\nجهان زیر تیغش به ماتم نشست",
        ],
    },
    "🦅 زال": {
        "attack_quotes": [
            "⚔️ > چو زال آذرخش از سپهر انداخت\nزمین را ز برقِ سنان برفراخت",
            "🔥 > دلیر از برِ رخش چون کوه شد\nبه تیغ از هوا آتش افروخت خود",
            "🩸 > یکی بانگ بر زد چو شیرِ ژیان\nکه لرزید از آن کوه و دشتِ جهان",
        ],
        "revenge_quotes": [
            "🩸 > به خون شست تیغ از کران تا کران\nکه گفتی برآمد ز دریا طوفان",
            "⚡️ > چو سیمرغ یادش به بال و پرش\nوزید از دلش بادِ خشم و شرش",
            "🔥 > برآورد تیغ و به فریاد گفت:\n«نبینی ز من جز ندامت و زَفت»",
        ],
    },
    "🛡 اسفندیار": {
        "attack_quotes": [
            "⚔️ > چو آهن در آهن بیفکند تیغ\nزمین شد ز خون همچو دریای میغ",
            "🔥 > ز نیروی یزدان و نیرنگ خویش\nبزد تا نماند از بدی هیچ بیش",
            "🩸 > یکی بانگ زد چون خروشِ سپاه\nز بیمش زمین گشت چون دود و آه",
        ],
        "revenge_quotes": [
            "🔥 > چو اسفندیار از برِ زین خمید\nبه خشم از دلش آتشِ کین دمید",
            "⚡️ > جهان گشت تیره ز برقِ نگاه\nچو برخاست آوازِ فریاد و آه",
            "🩸 > ز تیغش نرست آن‌که جان داشت نیز\nچو آذر در افتاد بر دشتِ تیز",
        ],
    },
    "🌸 تهمینه": {
        "attack_quotes": [
            "⚔️ > به مهرِ سهراب و خونِ پدر\nزنی شد چو مردان به تیغ و سپر",
            "🔥 > چو خشمش برآمد چو توفانِ گرد\nز دشمن نماند آن‌که جان در بَرد",
            "🩸 > به یک‌بار زد بر زمین برفراز\nکه گفتی ز کوه آتش آمد به باز",
        ],
        "revenge_quotes": [
            "⚡️ > بزد خنده بر مرگ و تیغ از نیام\nبرآورد آواز چون صبر و کام",
            "🩸 > به خونِ ستمکار شست آستین\nکه گفتی به گیتی نماند از کین",
            "🔥 > به دادِ دلِ سهراب برخاست باز\nچو آذر برآمد ز دشتِ نباز",
        ],
    },
    "🌹 رودابه": {
        "attack_quotes": [
            "🔥 > ز زیبایی و خشم شد آتشین\nبزد بر دلِ دشمنان آفرین",
            "⚔️ > چو شیرِ دلیر از برِ بامِ گرد\nفرود آمد و دشمن از پای مرد",
            "🩸 > ز بانگش جهان پر شد از کارزار\nچو برخاست بانگِ دلیرانِ یار",
        ],
        "revenge_quotes": [
            "⚡️ > به یادِ زال و تبارِ سیستان\nبرافروخت شمشیر بر دشمنان",
            "🔥 > چو تیغ از نیامش برآورد باد\nزمین و زمان را همه خشم داد",
            "🩸 > چو زن در نبرد آمد از خشمِ خویش\nجهان ز آتش و خون شد آمیخته بیش",
        ],
    },
}

# کاتالوگ پهلوانان با جزئیات (سلامت، سرعت، قابلیت‌ها) برای داخلی‌سازی قابلیت‌ها
HERO_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "🦁 رستم",
        "race": "🕊 سیستان",
        "power": 85,
        "wisdom": 60,
        "health": 120,
        "speed": 55,
        "abilities": [
            {
                "name": "گرز گاوسر",
                "description": "رستم، آن شیرِ دلاور سیستان، که با یک ضربه کوه را می‌شکافد.",
                "effect": "حملهٔ بعدی +35% دمیج.",
                "cooldown": "3 نوبت",
                "risk": "—",
            },
            {
                "name": "خروشِ رخش",
                "description": "بانگ رخش، دل دشمنان را می‌لرزاند.",
                "effect": "کاهش 20% دمیج دشمن برای 1 نوبت.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
        ],
    },
    {
        "name": "⚔️ سهراب",
        "race": "🐉 توران",
        "power": 80,
        "wisdom": 55,
        "health": 110,
        "speed": 65,
        "abilities": [
            {
                "name": "یورش جوانی",
                "description": "خیزش تندرگونِ سهراب، تیغ را به آذر بدل کند.",
                "effect": "70% احتمال دمیج ×2.",
                "cooldown": "3 نوبت",
                "risk": "در صورت ناکامی، دمیج به 50% کاهش می‌یابد.",
            },
            {
                "name": "خونِ گرم",
                "description": "با آتشِ جوانی، زخم‌ها زود التیام یابند.",
                "effect": "بازیابی 20 سلامت.",
                "cooldown": "4 نوبت",
                "risk": "برای یک نوبت، دمیج دریافتی +10%.",
            },
        ],
    },
    {
        "name": "🦅 زال",
        "race": "🕊 سیستان",
        "power": 70,
        "wisdom": 80,
        "health": 105,
        "speed": 60,
        "abilities": [
            {
                "name": "فرّهٔ سیمرغ",
                "description": "نسیمِ بالِ سیمرغ، خرد می‌افزاید و جان را نیرو بخشد.",
                "effect": "+25 خرد تا پایان نبرد (یک‌بار مصرف).",
                "cooldown": "—",
                "risk": "—",
            },
            {
                "name": "تدبیر کهن",
                "description": "با یک اشارت، دشمن را از یورش بازدارد.",
                "effect": "لغو حملهٔ حریف در این نوبت (Stun 1).",
                "cooldown": "5 نوبت",
                "risk": "در نوبت بعد، دمیج -10%.",
            },
        ],
    },
    {
        "name": "🛡 اسفندیار",
        "race": "🇮🇷 ایران",
        "power": 75,
        "wisdom": 70,
        "health": 115,
        "speed": 55,
        "abilities": [
            {
                "name": "رویین‌تن",
                "description": "جوشنِ اسفندیار، آتش و آهن را خُرد کند.",
                "effect": "برای 2 نوبت، 30% کاهش دمیج دریافتی.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
            {
                "name": "تیغ یزدان",
                "description": "ضربتی که از دعا و دلاوری نیرو گیرد.",
                "effect": "+20% دمیج و +10 احترام در پیروزی.",
                "cooldown": "3 نوبت",
                "risk": "در شکست، -5 احترام.",
            },
        ],
    },
    {
        "name": "🌸 تهمینه",
        "race": "🌊 سمنگان",
        "power": 60,
        "wisdom": 85,
        "health": 110,
        "speed": 60,
        "abilities": [
            {
                "name": "دلاوریِ دل‌آگاه",
                "description": "هوشیاری تهمینه، راه پیروزی را هموار کند.",
                "effect": "+25% دقت ضربه (کاهش نوسان تصادفی دمیج).",
                "cooldown": "3 نوبت",
                "risk": "—",
            },
            {
                "name": "مرهم سمنگانی",
                "description": "مرهمی از آب و گیاه، جان را التیام بخشد.",
                "effect": "بازیابی 30 سلامت.",
                "cooldown": "5 نوبت",
                "risk": "برای 1 نوبت، سرعت -10.",
            },
        ],
    },
    {
        "name": "🌹 رودابه",
        "race": "🌊 سمنگان",
        "power": 55,
        "wisdom": 90,
        "health": 105,
        "speed": 60,
        "abilities": [
            {
                "name": "فرّهٔ مادرانگی",
                "description": "مهری که دل را نیرومند کند و دست را استوار.",
                "effect": "+15 قدرت و +15 خرد برای 2 نوبت.",
                "cooldown": "5 نوبت",
                "risk": "پس از پایان اثر، -10 قدرت برای 1 نوبت.",
            },
            {
                "name": "فروغ امید",
                "description": "امیدی که زخم را می‌بندد و پای را به میدان بازگرداند.",
                "effect": "بازیابی 20 سلامت و رفع یک ناتوانی.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
        ],
    },
]

# کاتالوگ دیوان (سیستم جدید - ساده‌شده)
DEMONS_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "❄️ دیو سفید",
        "race": "🔥 دیوان",
        "power": 70,
        "wisdom": 30,
        "health": 80,
        "required_level": 1,
        "honor_penalty": (-15, -10),
        "ability": "زمستان مرگ",
        "ability_desc": "15٪ احتمال یخ‌زدگی دشمن برای یک نوبت",
        "description": "دیوی از سپیدکوه البرز، مظهر سرمای مرگ‌بار و دشمن بزرگ زال.",
        "speed": 50,
        "abilities": [
            {
                "name": "یخ‌بندان اهریمنی",
                "description": "دم سردِ دیو سفید، جانِ پهلوان را کرخت کند.",
                "effect": "50% احتمال یخ‌زدگی حریف (از دست دادن نوبت).",
                "cooldown": "4 نوبت",
                "risk": "10% احتمال کندیِ خود: سرعت -10 برای 1 نوبت.",
            },
            {
                "name": "چنگال برفی",
                "description": "ضربه‌ای که استخوان را می‌ساید.",
                "effect": "+40% دمیج.",
                "cooldown": "3 نوبت",
                "risk": "خودآسیبی 5 سلامت.",
            },
        ],
    },
    {
        "name": "🗻 ارژنگ دیو",
        "race": "🔥 دیوان",
        "power": 75,
        "wisdom": 35,
        "health": 85,
        "required_level": 3,
        "honor_penalty": (-25, -15),
        "ability": "فریاد کوهستان",
        "ability_desc": "10٪ احتمال ترساندن دشمن و کاهش دمیج او در نوبت بعد",
        "description": "از دیوان کوهستانی توران، وحشی اما فاقد درایت؛ ضربات سنگین می‌زند ولی زود گیج می‌شود.",
        "speed": 52,
        "abilities": [
            {
                "name": "غرش کوهستان",
                "description": "غریوی که دل‌ها را بلغزاند و زمین را بلرزاند.",
                "effect": "-20% دقت و -10 سرعت برای حریف تا 2 نوبت.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
            {
                "name": "سنگ‌افکن",
                "description": "پرتاب تخته‌سنگ، چون شهابِ تیز.",
                "effect": "دمیج سنگین (×1.6).",
                "cooldown": "3 نوبت",
                "risk": "اگر خطا رود، نوبت بعد دمیج -20%.",
            },
        ],
    },
    {
        "name": "🌪 اکوان دیو",
        "race": "🔥 دیوان",
        "power": 80,
        "wisdom": 40,
        "health": 100,
        "required_level": 6,
        "honor_penalty": (-30, -20),
        "ability": "پرتاب آسمانی",
        "ability_desc": "20٪ احتمال پرتاب دشمن و از دست دادن نوبت بعدی",
        "description": "دشمن دیرینه‌ی رستم؛ مغرور و حیله‌گر. در نبرد بی‌رحم است اما ناپایدار و بی‌خرد.",
        "speed": 65,
        "abilities": [
            {
                "name": "طَرحِ اکوان",
                "description": "نیرنگی که پهلوان را به هوا برد و بر زمین کوبد.",
                "effect": "70% احتمال دمیج ×2 و Stun 1.",
                "cooldown": "5 نوبت",
                "risk": "30% احتمال واژگونی: خودآسیبی 10 سلامت.",
            },
            {
                "name": "بادِ هرج‌ومرج",
                "description": "آشوبی که نظم رزمگاه را برهم زند.",
                "effect": "نوسان دمیج حریف +50% (بی‌ثباتی).",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
        ],
    },
    {
        "name": "🌑 دیو سیاه",
        "race": "🔥 دیوان",
        "power": 90,
        "wisdom": 50,
        "health": 120,
        "required_level": 10,
        "honor_penalty": (-40, -30),
        "ability": "تاریکی جاودان",
        "ability_desc": "15٪ احتمال کاهش 10٪ از قدرت دشمن تا پایان نبرد",
        "description": "فرمانروای سیاهی؛ از اهریمن نیرو می‌گیرد. قدرتمند ولی اسیر خشم و غرور خویش.",
        "speed": 58,
        "abilities": [
            {
                "name": "سایهٔ هراس",
                "description": "تاریکی که چشمان را بپوشاند و دل را بلرزاند.",
                "effect": "-25% دقت حریف برای 2 نوبت.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
            {
                "name": "خنجر ظلمت",
                "description": "ضربه‌ای از پشت سایه‌ها.",
                "effect": "دمیج ×1.5.",
                "cooldown": "3 نوبت",
                "risk": "10% احتمال از دست دادن نوبت بعدی.",
            },
        ],
    },
    {
        "name": "🏔 دیو سپیدکوهی",
        "race": "🔥 دیوان",
        "power": 95,
        "wisdom": 55,
        "health": 130,
        "required_level": 15,
        "honor_penalty": (-45, -30),
        "ability": "غرش کوهستان",
        "ability_desc": "10٪ احتمال بازتاب نیمی از دمیج دشمن",
        "description": "غول سپیدِ البرز، دشمن زال و رستم. جسمی سنگین، قدرتی سهمگین، ولی اندیشه‌ای تاریک.",
        "speed": 48,
        "abilities": [
            {
                "name": "برف‌پیچ سهمگین",
                "description": "کولاکی که رمق از تن حریف برباید.",
                "effect": "-20 سرعت و -10% دمیج حریف برای 2 نوبت.",
                "cooldown": "4 نوبت",
                "risk": "—",
            },
            {
                "name": "کوه‌کوب",
                "description": "مشت کوه‌افکن، همچون پتک آهنین.",
                "effect": "دمیج بسیار سنگین (×1.7).",
                "cooldown": "4 نوبت",
                "risk": "خودآسیبی 8 سلامت.",
            },
        ],
    },
    {
        "name": "🛡 دیو زره‌پوش",
        "race": "🔥 دیوان",
        "power": 100,
        "wisdom": 60,
        "health": 100,
        "required_level": 18,
        "honor_penalty": (-50, -35),
        "ability": "زره اهریمنی",
        "ability_desc": "20٪ احتمال کاهش 50٪ از دمیج برای دو نوبت",
        "description": "ساخته‌شده از فولاد و نفرت، بی‌احساس و بی‌خرد. هر ضربه‌اش لرزاننده‌ی زمین است.",
        "speed": 45,
        "abilities": [
            {
                "name": "زره آهنین",
                "description": "سپر و جوشن چندلایه در برابر آتش و آهن.",
                "effect": "برای 2 نوبت، 35% کاهش دمیج دریافتی.",
                "cooldown": "4 نوبت",
                "risk": "سرعت -10 برای همان مدت.",
            },
            {
                "name": "ضربهٔ سنگین",
                "description": "ضربتی کند اما کوبنده.",
                "effect": "دمیج ×1.4.",
                "cooldown": "3 نوبت",
                "risk": "اگر حریف سریع‌تر باشد، 20% احتمال خالی‌زدن.",
            },
        ],
    },
    {
        "name": "👁 خیره‌چشم دیو",
        "race": "🔥 دیوان",
        "power": 110,
        "wisdom": 65,
        "health": 120,
        "required_level": 20,
        "honor_penalty": (-55, -40),
        "ability": "نگاه مرگ",
        "ability_desc": "10٪ احتمال نابودی دشمنی با سلامت کمتر از ۳۰٪",
        "description": "از نگاهش مرگ می‌بارد، زاده‌ی نفرین و تاریکی. کمتر کسی از دیدارش زنده مانده.",
        "speed": 60,
        "abilities": [
            {
                "name": "نگاه نفرین",
                "description": "نگاهی که امید را از دل بزداید.",
                "effect": "-10 خرد و -10 قدرت حریف برای 2 نوبت.",
                "cooldown": "5 نوبت",
                "risk": "—",
            },
            {
                "name": "جهش مهلک",
                "description": "یورش ناگهانی از کمین.",
                "effect": "دمیج ×1.5 و 20% احتمال Stun 1.",
                "cooldown": "3 نوبت",
                "risk": "اگر Stun فعال نشود، دمیج دریافتی بعدی +10%.",
            },
        ],
    },
    {
        "name": "🩸 دیو خون‌آشام",
        "race": "🔥 دیوان",
        "power": 115,
        "wisdom": 70,
        "health": 145,
        "required_level": 25,
        "honor_penalty": (-70, -40),
        "ability": "نوش خون",
        "ability_desc": "20٪ احتمال بازگرداندن ۵ سلامت از آسیب واردشده",
        "description": "آخرین و مخوف‌ترین دیو توران؛ زاده‌ی شب و خون. هر که شکستش دهد، احترام بسیار می‌یابد.",
        "speed": 62,
        "abilities": [
            {
                "name": "مکیدن خون",
                "description": "از خونِ دشمن نیرو گیرد.",
                "effect": "50% دمیجِ واردشده را به سلامت تبدیل می‌کند.",
                "cooldown": "4 نوبت",
                "risk": "اگر حمله خطا رود، 10 سلامت از دست می‌دهد.",
            },
            {
                "name": "تبِ خون",
                "description": "خونی که چون آتش در رگ‌ها بدود.",
                "effect": "+25% دمیج برای 2 نوبت.",
                "cooldown": "5 نوبت",
                "risk": "پس از پایان اثر، 10 سلامت کاسته می‌شود.",
            },
        ],
    },
]

# جدول مبارزات پهلوانان (matchup table)
HERO_MATCHUPS: Dict[Tuple[str, str], Dict[str, Any]] = {
    # تهمینه مهاجم
    ("🌸 تهمینه", "🌸 تهمینه"): {"damage": (20, 40), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (10, 20)},
    ("🌸 تهمینه", "🌹 رودابه"): {"damage": (15, 30), "drafsh": (30, 70), "honor": (15, 20), "win_chance": 0.45, "loss_damage": (15, 25)},
    ("🌸 تهمینه", "🦅 زال"): {"damage": (10, 25), "drafsh": (20, 60), "honor": (10, 15), "win_chance": 0.40, "loss_damage": (20, 30)},
    ("🌸 تهمینه", "⚔️ سهراب"): {"damage": (5, 15), "drafsh": (15, 50), "honor": (5, 10), "win_chance": 0.35, "loss_damage": (25, 35)},
    ("🌸 تهمینه", "🛡 اسفندیار"): {"damage": (0, 10), "drafsh": (10, 40), "honor": (0, 10), "win_chance": 0.30, "loss_damage": (30, 40)},
    ("🌸 تهمینه", "🦁 رستم"): {"damage": (0, 5), "drafsh": (5, 30), "honor": (0, 10), "win_chance": 0.20, "loss_damage": (35, 45)},
    
    # رودابه مهاجم
    ("🌹 رودابه", "🌸 تهمینه"): {"damage": (30, 50), "drafsh": (60, 100), "honor": (20, 40), "win_chance": 0.65, "loss_damage": (30, 50)},
    ("🌹 رودابه", "🌹 رودابه"): {"damage": (20, 40), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (20, 40)},
    ("🌹 رودابه", "🦅 زال"): {"damage": (15, 30), "drafsh": (30, 60), "honor": (15, 25), "win_chance": 0.45, "loss_damage": (15, 30)},
    ("🌹 رودابه", "⚔️ سهراب"): {"damage": (10, 25), "drafsh": (20, 40), "honor": (10, 20), "win_chance": 0.35, "loss_damage": (10, 25)},
    ("🌹 رودابه", "🛡 اسفندیار"): {"damage": (5, 20), "drafsh": (10, 20), "honor": (5, 15), "win_chance": 0.25, "loss_damage": (5, 20)},
    ("🌹 رودابه", "🦁 رستم"): {"damage": (0, 10), "drafsh": (5, 15), "honor": (0, 10), "win_chance": 0.20, "loss_damage": (0, 10)},
    
    # زال مهاجم
    ("🦅 زال", "🌸 تهمینه"): {"damage": (35, 60), "drafsh": (70, 120), "honor": (25, 45), "win_chance": 0.75, "loss_damage": (35, 60)},
    ("🦅 زال", "🌹 رودابه"): {"damage": (30, 55), "drafsh": (60, 110), "honor": (22, 38), "win_chance": 0.70, "loss_damage": (30, 55)},
    ("🦅 زال", "🦅 زال"): {"damage": (20, 40), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (20, 40)},
    ("🦅 زال", "⚔️ سهراب"): {"damage": (12, 30), "drafsh": (25, 55), "honor": (8, 18), "win_chance": 0.40, "loss_damage": (12, 30)},
    ("🦅 زال", "🛡 اسفندیار"): {"damage": (6, 22), "drafsh": (12, 40), "honor": (4, 14), "win_chance": 0.30, "loss_damage": (6, 22)},
    ("🦅 زال", "🦁 رستم"): {"damage": (0, 15), "drafsh": (5, 30), "honor": (0, 10), "win_chance": 0.25, "loss_damage": (0, 15)},
    
    # سهراب مهاجم
    ("⚔️ سهراب", "🌸 تهمینه"): {"damage": (40, 65), "drafsh": (80, 130), "honor": (25, 50), "win_chance": 0.80, "loss_damage": (40, 65)},
    ("⚔️ سهراب", "🌹 رودابه"): {"damage": (35, 60), "drafsh": (70, 120), "honor": (22, 40), "win_chance": 0.75, "loss_damage": (35, 60)},
    ("⚔️ سهراب", "🦅 زال"): {"damage": (25, 50), "drafsh": (50, 100), "honor": (18, 30), "win_chance": 0.60, "loss_damage": (25, 50)},
    ("⚔️ سهراب", "⚔️ سهراب"): {"damage": (20, 40), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (20, 40)},
    ("⚔️ سهراب", "🛡 اسفندیار"): {"damage": (10, 25), "drafsh": (20, 50), "honor": (10, 20), "win_chance": 0.35, "loss_damage": (10, 25)},
    ("⚔️ سهراب", "🦁 رستم"): {"damage": (10, 20), "drafsh": (15, 40), "honor": (5, 15), "win_chance": 0.30, "loss_damage": (10, 20)},
    
    # اسفندیار مهاجم
    ("🛡 اسفندیار", "🌸 تهمینه"): {"damage": (45, 70), "drafsh": (90, 150), "honor": (30, 50), "win_chance": 0.85, "loss_damage": (45, 70)},
    ("🛡 اسفندیار", "🌹 رودابه"): {"damage": (40, 65), "drafsh": (80, 130), "honor": (25, 45), "win_chance": 0.80, "loss_damage": (40, 65)},
    ("🛡 اسفندیار", "🦅 زال"): {"damage": (30, 55), "drafsh": (70, 120), "honor": (20, 35), "win_chance": 0.65, "loss_damage": (30, 55)},
    ("🛡 اسفندیار", "⚔️ سهراب"): {"damage": (25, 50), "drafsh": (50, 100), "honor": (15, 30), "win_chance": 0.55, "loss_damage": (25, 50)},
    ("🛡 اسفندیار", "🛡 اسفندیار"): {"damage": (20, 40), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (20, 40)},
    ("🛡 اسفندیار", "🦁 رستم"): {"damage": (15, 30), "drafsh": (30, 70), "honor": (10, 20), "win_chance": 0.40, "loss_damage": (15, 30)},
    
    # رستم مهاجم - بزرگ‌ترین پهلوان ایران‌زمین
    ("🦁 رستم", "🌸 تهمینه"): {"damage": (60, 90), "drafsh": (100, 160), "honor": (30, 60), "win_chance": 0.95, "loss_damage": (60, 90)},
    ("🦁 رستم", "🌹 رودابه"): {"damage": (55, 85), "drafsh": (90, 150), "honor": (25, 50), "win_chance": 0.90, "loss_damage": (55, 85)},
    ("🦁 رستم", "🦅 زال"): {"damage": (50, 80), "drafsh": (80, 140), "honor": (25, 45), "win_chance": 0.85, "loss_damage": (50, 80)},
    ("🦁 رستم", "⚔️ سهراب"): {"damage": (45, 75), "drafsh": (70, 130), "honor": (20, 40), "win_chance": 0.80, "loss_damage": (45, 75)},
    ("🦁 رستم", "🛡 اسفندیار"): {"damage": (35, 65), "drafsh": (60, 110), "honor": (15, 30), "win_chance": 0.65, "loss_damage": (35, 65)},
    ("🦁 رستم", "🦁 رستم"): {"damage": (25, 50), "drafsh": (40, 80), "honor": (15, 25), "win_chance": 0.50, "loss_damage": (25, 50)},
}

def get_matchup_stats(attacker_hero: str, defender_hero: str) -> Dict[str, Any]:
    """دریافت آمار مبارزه بین دو پهلوان"""
    key = (attacker_hero, defender_hero)
    if key in HERO_MATCHUPS:
        return HERO_MATCHUPS[key]
    # مقادیر پیش‌فرض (برای حالتی که جدول کامل نیست)
    return {"damage": (10, 30), "drafsh": (20, 60), "honor": (10, 20), "win_chance": 0.50, "loss_damage": (15, 25)}

def get_hero_quote(hero_name: str, kind: str = "attack_quotes") -> Optional[str]:
    data = QUOTES.get(hero_name or "")
    if not data:
        return None
    arr = data.get(kind) or []
    if not arr:
        return None
    return random.choice(arr)

def row_get(row: sqlite3.Row, key: str, default=None):
    """Helper function to safely get value from sqlite3.Row with default"""
    try:
        return row[key] if row[key] is not None else default
    except (KeyError, IndexError):
        return default

def xp_required_for_level(level: int) -> int:
    """محاسبه XP موردنیاز برای رسیدن به سطح بعدی
    سطح 1→2: 100 XP
    سطح 2→3: 250 XP  
    سطح 3→4: 400 XP
    سطح 4→5: 550 XP
    و به همین ترتیب: هر سطح 150 XP بیشتر از قبلی
    """
    if level <= 1:
        return 100
    return 100 + (level - 1) * 150

# دکمه‌های منوی اصلی - بهینه شده
MAIN_MENU_BUTTONS = [
    [KeyboardButton("🏹 پهلوانان"), KeyboardButton("⚔️ نبرد")],
    [KeyboardButton("🏺 بازار قهوه خانه"), KeyboardButton("⛏ معدن"), KeyboardButton("🎁 جایزه روزانه")],
    [KeyboardButton("💰 تبادل درفش"), KeyboardButton("🏕 مأموریت روزانه"), KeyboardButton("🕊 دعوت سیمرغ")],
    [KeyboardButton("🏆 رنکینگ"), KeyboardButton("💼 دارایی"), KeyboardButton("👹 دیوان")],
    [KeyboardButton("❓ راهنما"), KeyboardButton("🆘 پشتیبانی")],
]

# دکمه‌های منوی ادمین (فقط برای ادمین)
ADMIN_MENU_BUTTONS = [
    [KeyboardButton("🏹 پهلوانان"), KeyboardButton("⚔️ نبرد")],
    [KeyboardButton("🏺 بازار قهوه خانه"), KeyboardButton("⛏ معدن"), KeyboardButton("🎁 جایزه روزانه")],
    [KeyboardButton("💰 تبادل درفش"), KeyboardButton("🏕 مأموریت روزانه"), KeyboardButton("🕊 دعوت سیمرغ")],
    [KeyboardButton("🏆 رنکینگ"), KeyboardButton("💼 دارایی"), KeyboardButton("👹 دیوان")],
    [KeyboardButton("❓ راهنما"), KeyboardButton("🆘 پشتیبانی")],
    [KeyboardButton("🔐 پنل ادمین")],
]


# --------------------------- لاگ‌گیری ---------------------------

# پیکربندی لاگر برای کمک به عیب‌یابی در زمان اجرا
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# --------------------------- لایه دیتابیس ---------------------------

class Database:
    """لایه دسترسی به دیتابیس SQLite برای مدیریت کاربران و تمرین روزانه."""

    def __init__(self, db_path: str) -> None:
        # مسیر دیتابیس را ذخیره می‌کنیم
        self.db_path = db_path
        # ایجاد مدیریت بکاپ
        self.backup_manager = BackupManager(db_path)
        # ایجاد بکاپ روزانه خودکار
        self.backup_manager.create_daily_backup()
        # پاک‌سازی بکاپ‌های قدیمی‌تر از 7 روز
        self.backup_manager.cleanup_old_backups(keep_days=7)
        # ایجاد جداول در صورت عدم وجود
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # ایجاد اتصال جدید به دیتابیس برای هر عملیات
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        # ایجاد جداول users و user_training اگر وجود ندارند
        conn = self._connect()
        try:
            cur = conn.cursor()
            # جدول کاربران مطابق مشخصات
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    hero TEXT,
                    race TEXT,
                    power INTEGER,
                    wisdom INTEGER,
                    health INTEGER,
                    honor INTEGER,
                    drafsh INTEGER,
                    items TEXT,
                    joined_channel INTEGER DEFAULT 0
                );
                """
            )
            # افزودن ستون سطح کاربر اگر نباشد
            try:
                cur.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
            except Exception:
                pass
            # افزودن ستون‌های جدید اگر موجود نباشند
            for alt in [
                "ALTER TABLE users ADD COLUMN full_name TEXT",
                "ALTER TABLE users ADD COLUMN race TEXT",
                "ALTER TABLE users ADD COLUMN drafsh INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN items TEXT",
                "ALTER TABLE users ADD COLUMN last_simorgh TEXT",
                "ALTER TABLE users ADD COLUMN last_mission TEXT",
                "ALTER TABLE users ADD COLUMN skill_unlocked INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN default_demon TEXT",
            ]:
                try:
                    cur.execute(alt)
                except Exception:
                    pass
            # جدول تمرین روزانه برای نگهداری آخرین زمان تمرین هر کاربر
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_training (
                    user_id INTEGER PRIMARY KEY,
                    last_trained_at TEXT
                );
                """
            )
            # جدول مالکیت پهلوانان توسط کاربران
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_heroes (
                    user_id INTEGER,
                    hero TEXT,
                    owned INTEGER DEFAULT 0,
                    health INTEGER,
                    last_revive TEXT,
                    PRIMARY KEY(user_id, hero)
                );
                """
            )
            # اگر جدول user_heroes قدیمی باشد و ستون health نداشته باشد، اضافه‌اش کن
            try:
                cur.execute("ALTER TABLE user_heroes ADD COLUMN health INTEGER")
            except Exception:
                pass
            # افزودن ستون زمان احیای پهلوان
            try:
                cur.execute("ALTER TABLE user_heroes ADD COLUMN last_revive TEXT")
            except Exception:
                pass
            # ارتقای ستون‌های معدن و دفاع
            for alt in [
                "ALTER TABLE users ADD COLUMN mine_level INTEGER DEFAULT 1",
                "ALTER TABLE users ADD COLUMN mine_last_collect TEXT",
                "ALTER TABLE users ADD COLUMN defend_ready INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0",  # سیستم XP جدید
                "ALTER TABLE users ADD COLUMN tea_active_until TEXT",  # چای پهلوانی
                "ALTER TABLE users ADD COLUMN gorz_active_until TEXT",  # گرز رستم
                "ALTER TABLE users ADD COLUMN last_tea_use TEXT",  # آخرین استفاده از چای
                "ALTER TABLE users ADD COLUMN last_feather_use TEXT",  # آخرین استفاده از پر سیمرغ
                "ALTER TABLE users ADD COLUMN last_gorz_use TEXT",  # آخرین استفاده از گرز
                "ALTER TABLE users ADD COLUMN last_daily_reward TEXT",  # آخرین دریافت جایزه روزانه
                "ALTER TABLE users ADD COLUMN daily_transfer_amount INTEGER DEFAULT 0",  # مقدار انتقال روزانه
                "ALTER TABLE users ADD COLUMN last_transfer_date TEXT",  # آخرین تاریخ انتقال
            ]:
                try:
                    cur.execute(alt)
                except Exception:
                    pass
            # جدول محدودیت حمله‌های روزانه
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_battles (
                    user_id INTEGER,
                    battle_date TEXT,
                    battle_count INTEGER DEFAULT 0,
                    PRIMARY KEY(user_id, battle_date)
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_user(self, user_id: int, username: Optional[str], full_name: Optional[str]) -> None:
        # ایجاد یا به‌روزرسانی کاربر در جدول users
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO users (user_id, username, full_name, health, honor, joined_channel) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, full_name, 100, 0, 0),
                )
            else:
                cur.execute(
                    "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                    (username, full_name, user_id),
                )
            conn.commit()
        finally:
            conn.close()

    def set_joined_channel(self, user_id: int, joined: bool) -> None:
        # ثبت وضعیت عضویت کاربر در کانال/گروه اجباری
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET joined_channel = ? WHERE user_id = ?",
                (1 if joined else 0, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_hero(self, user_id: int, hero: str, power: int, wisdom: int, race: Optional[str] = None) -> None:
        # ذخیره قهرمان انتخابی و ویژگی‌های اولیه
        conn = self._connect()
        try:
            cur = conn.cursor()
            # اعمال بونوس‌های نژاد روی سلامت اولیه
            base_health = 100
            if race and race in RACES:
                base_health += int(RACES[race].get("health_bonus", 0))
            cur.execute(
                "UPDATE users SET hero = ?, race = COALESCE(?, race), power = ?, wisdom = ?, health = COALESCE(health, ?), honor = COALESCE(honor, 0), drafsh = COALESCE(drafsh, 0) WHERE user_id = ?",
                (hero, race, power, wisdom, base_health, user_id),
            )
            # مالکیت پهلوان تنظیم شود
            # تنظیم سلامت اولیه قهرمان در جدول user_heroes اگر نبود
            cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, hero))
            uh = cur.fetchone()
            if uh is None or uh[0] is None:
                cur.execute(
                    "REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)",
                    (user_id, hero, base_health),
                )
            else:
                cur.execute(
                    "REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)",
                    (user_id, hero, uh[0]),
                )
            conn.commit()
        finally:
            conn.close()

    def add_rewards(self, user_id: int, honor: int = 0, drafsh: int = 0, xp: int = 0) -> None:
        # افزودن پاداش احترام، درفش و XP و به‌روزرسانی سطح
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET honor = COALESCE(honor,0) + ?, drafsh = COALESCE(drafsh,0) + ?, xp = COALESCE(xp,0) + ? WHERE user_id = ?", 
                (int(honor), int(drafsh), int(xp), user_id)
            )
            # به‌روزرسانی سطح بر اساس XP (سیستم جدید)
            cur.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            current_xp = int(row[0]) if row and row[0] is not None else 0
            current_level = int(row[1]) if row and row[1] is not None else 1
            
            # چک کردن آیا XP کافی برای ارتقا هست
            while current_xp >= xp_required_for_level(current_level):
                xp_needed = xp_required_for_level(current_level)
                current_xp -= xp_needed  # کسر XP مصرف شده
                current_level += 1  # ارتقای سطح
            
            # ذخیره سطح و XP باقیمانده
            cur.execute("UPDATE users SET level = ?, xp = ? WHERE user_id = ?", (current_level, current_xp, user_id))
            conn.commit()
        finally:
            conn.close()

    def get_cooldowns(self, user_id: int) -> Dict[str, Optional[str]]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT last_simorgh, last_mission FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return {"last_simorgh": row[0] if row else None, "last_mission": row[1] if row else None}
        finally:
            conn.close()

    def set_last_simorgh(self, user_id: int) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET last_simorgh = ? WHERE user_id = ?", (datetime.utcnow().isoformat(), user_id))
            conn.commit()
        finally:
            conn.close()

    def set_last_mission(self, user_id: int) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET last_mission = ? WHERE user_id = ?", (datetime.utcnow().isoformat(), user_id))
            conn.commit()
        finally:
            conn.close()

    def get_level(self, user_id: int) -> int:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT level FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 1
        finally:
            conn.close()

    def set_level_from_honor(self, user_id: int) -> int:
        # سطح بر اساس آستانه‌های افتخار: 0=>1, 100=>2, 200=>3, 400=>4 ...
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT honor, level FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            honor = int(row[0]) if row and row[0] is not None else 0
            current_level = int(row[1]) if row and row[1] is not None else 1
            # سطح محاسباتی و سپس جلوگیری از کاهش سطح
            computed_level = 1 + honor // 100
            new_level = max(current_level, computed_level)
            cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
            conn.commit()
            return int(new_level)
        finally:
            conn.close()

    def list_owned_heroes(self, user_id: int) -> List[str]:
        conn = self._connect()
        try:
            cur = conn.cursor()
            # احیای خودکار پهلوانانی که 24 ساعت از صفر بودن سلامتشان گذشته است
            cur.execute("SELECT hero, health, last_revive FROM user_heroes WHERE user_id = ? AND owned = 1", (user_id,))
            rows = cur.fetchall()
            now = datetime.utcnow()
            for hero, hp, lr in rows:
                if (hp or 0) == 0 and lr:
                    try:
                        t = datetime.fromisoformat(lr)
                        if now - t >= timedelta(hours=24):
                            # احیای به سلامت پایه بر اساس نژاد
                            race = HEROES.get(hero, {}).get('race', '')
                            base = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                            cur.execute("UPDATE user_heroes SET health = ?, last_revive = NULL WHERE user_id = ? AND hero = ?", (base, user_id, hero))
                    except Exception:
                        pass
            conn.commit()
            cur.execute("SELECT hero FROM user_heroes WHERE user_id = ? AND owned = 1", (user_id,))
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        # دریافت اطلاعات کاربر از دیتابیس
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cur.fetchone()
        finally:
            conn.close()

    def get_active_opponents(self, exclude_user_id: int, limit: int = 10) -> List[sqlite3.Row]:
        # فهرست تصادفی کاربران فعال برای نبرد (دارای hero)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, username, hero, power, wisdom, health, honor
                FROM users
                WHERE hero IS NOT NULL AND user_id != ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (exclude_user_id, limit),
            )
            return cur.fetchall()
        finally:
            conn.close()

    def can_battle_today(self, user_id: int, max_battles: int = 40) -> Tuple[bool, int]:
        """بررسی اینکه آیا کاربر می‌تواند امروز حمله کند (محدودیت 40 حمله در روز)"""
        today = datetime.utcnow().date().isoformat()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT battle_count FROM user_battles WHERE user_id = ? AND battle_date = ?", (user_id, today))
            row = cur.fetchone()
            battle_count = int(row[0]) if row and row[0] is not None else 0
            
            if battle_count >= max_battles:
                return False, battle_count
            return True, battle_count
        finally:
            conn.close()

    def record_battle(self, user_id: int) -> None:
        """ثبت حمله کاربر برای امروز"""
        today = datetime.utcnow().date().isoformat()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT battle_count FROM user_battles WHERE user_id = ? AND battle_date = ?", (user_id, today))
            row = cur.fetchone()
            
            if row:
                cur.execute("UPDATE user_battles SET battle_count = battle_count + 1 WHERE user_id = ? AND battle_date = ?", (user_id, today))
            else:
                cur.execute("INSERT INTO user_battles (user_id, battle_date, battle_count) VALUES (?, ?, 1)", (user_id, today))
            
            conn.commit()
        finally:
            conn.close()

    def apply_battle_result(
        self,
        winner_user_id: int,
        loser_user_id: int,
    ) -> None:
        # به‌روزرسانی افتخار برنده و کاهش سلامتی بازنده
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET honor = COALESCE(honor,0) + 10 WHERE user_id = ?", (winner_user_id,))
            cur.execute("UPDATE users SET health = MAX(0, COALESCE(health,100) - 5) WHERE user_id = ?", (loser_user_id,))
            # تنظیم سطح بر اساس افتخار جدید
            for uid in (winner_user_id, loser_user_id):
                cur.execute("SELECT honor, level FROM users WHERE user_id = ?", (uid,))
                row = cur.fetchone()
                honor = int(row[0]) if row and row[0] is not None else 0
                current_level = int(row[1]) if row and row[1] is not None else 1
                computed_level = 1 + honor // 100
                new_level = max(current_level, computed_level)
                cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, uid))
            conn.commit()
        finally:
            conn.close()

    def top_honor(self, limit: int = 10) -> List[sqlite3.Row]:
        # ۱۰ کاربر برتر بر اساس افتخار (بدون نمایش ادمین)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, full_name, username, hero, honor FROM users WHERE hero IS NOT NULL AND user_id != ? ORDER BY honor DESC LIMIT ?",
                (ADMIN_ID, limit),
            )
            return cur.fetchall()
        finally:
            conn.close()

    def can_train(self, user_id: int) -> Tuple[bool, Optional[timedelta]]:
        # بررسی امکان تمرین روزانه (هر 24 ساعت یکبار)
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT last_trained_at FROM user_training WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row is None or not row[0]:
                return True, None
            last = datetime.fromisoformat(row[0])
            now = datetime.utcnow()
            delta = now - last
            if delta >= timedelta(hours=24):
                return True, None
            return False, timedelta(hours=24) - delta
        finally:
            conn.close()

    def apply_training(self, user_id: int, attribute: str, amount: int = 5) -> None:
        # اعمال تمرین روزانه و ثبت زمان آخرین تمرین
        if attribute not in ("power", "wisdom"):
            return
        conn = self._connect()
        try:
            cur = conn.cursor()
            # اگر نژاد سمنگان باشد، تمرین مؤثرتر است (+2 اضافی)
            cur.execute("SELECT race FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            bonus = 2 if row and row[0] == "🌊 سمنگان" else 0
            cur.execute(f"UPDATE users SET {attribute} = COALESCE({attribute},0) + ? WHERE user_id = ?", (amount + bonus, user_id))
            cur.execute(
                "REPLACE INTO user_training (user_id, last_trained_at) VALUES (?, ?)",
                (user_id, datetime.utcnow().isoformat()),
            )
            # پاداش تمرین: احترام +5 و درفش +5
            cur.execute("UPDATE users SET honor = COALESCE(honor,0) + 5, drafsh = COALESCE(drafsh,0) + 5 WHERE user_id = ?", (user_id,))
            # سطح به‌روزرسانی بدون کاهش سطح
            cur.execute("SELECT honor, level FROM users WHERE user_id = ?", (user_id,))
            r2 = cur.fetchone()
            total_honor = int(r2[0]) if r2 and r2[0] is not None else 0
            current_level = int(r2[1]) if r2 and r2[1] is not None else 1
            computed_level = 1 + total_honor // 100
            new_level = max(current_level, computed_level)
            cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, user_id))
            conn.commit()
        finally:
            conn.close()

    def decrease_health(self, user_id: int, amount: int) -> None:
        # کاهش سلامت کاربر به میزان دلخواه با کف صفر
        if amount <= 0:
            return
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET health = MAX(0, COALESCE(health,100) - ?) WHERE user_id = ?",
                (int(amount), user_id),
            )
            # هم‌زمان سلامت قهرمان جاری را نیز کاهش بده
            cur.execute("SELECT hero FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            current_hero = row[0] if row else None
            if current_hero:
                # اگر به صفر رسید، زمان آخرین مرگ/احیا را ثبت کن
                cur.execute(
                    "UPDATE user_heroes SET health = MAX(0, COALESCE(health,100) - ?) WHERE user_id = ? AND hero = ?",
                    (int(amount), user_id, current_hero),
                )
                cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, current_hero))
                hrow = cur.fetchone()
                if hrow and int(hrow[0] or 0) == 0:
                    cur.execute("UPDATE user_heroes SET last_revive = ? WHERE user_id = ? AND hero = ?", (datetime.utcnow().isoformat(), user_id, current_hero))
            conn.commit()
        finally:
            conn.close()

    def set_default_demon(self, user_id: int, demon_name: str) -> None:
        # تنظیم دیو پیش‌فرض کاربر
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET default_demon = ? WHERE user_id = ?", (demon_name, user_id))
            conn.commit()
        finally:
            conn.close()

    def grant_unlimited(self, user_id: int, level_target: int = 9999, drafsh_target: int = 9999999, honor_target: int = 999999) -> None:
        # اعطای حالت نامحدود: افزایش سطح، درفش و احترام به مقادیر بسیار بالا
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET honor = ?, level = ?, drafsh = ? WHERE user_id = ?",
                (int(honor_target), int(level_target), int(drafsh_target), user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_current_hero_health(self, user_id: int) -> Optional[int]:
        # دریافت سلامت پهلوان پیش‌فرض کاربر از جدول user_heroes
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT hero FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            current_hero = row[0] if row else None
            if not current_hero:
                return None
            cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, current_hero))
            hrow = cur.fetchone()
            return int(hrow[0]) if hrow and hrow[0] is not None else None
        finally:
            conn.close()

    def set_defend_ready(self, user_id: int, ready: bool) -> None:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET defend_ready = ? WHERE user_id = ?", (1 if ready else 0, user_id))
            conn.commit()
        finally:
            conn.close()

    def heal_hero(self, user_id: int, hero_name: str, heal_amount: int) -> Tuple[bool, str]:
        """
        درمان پهلوان و کسر درفش
        قیمت: 2 درفش برای هر 1 سلامت (بر اساس بازار)
        - کمک‌های اولیه: 100 درفش برای 50 سلامت = 2 درفش/سلامت
        - پر سیمرغ: 700 درفش برای 40 سلامت = 17.5 درفش/سلامت
        
        Returns:
            (موفقیت، پیام)
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            
            # دریافت اطلاعات کاربر
            cur.execute("SELECT drafsh, hero FROM users WHERE user_id = ?", (user_id,))
            user_row = cur.fetchone()
            if not user_row:
                return False, "❌ کاربر یافت نشد"
            
            current_drafsh = int(user_row[0] or 0)
            current_hero = user_row[1]
            
            # محاسبه هزینه درمان: 2 درفش برای هر 1 سلامت (بر اساس کمک‌های اولیه)
            heal_cost = heal_amount * 2
            
            # بررسی درفش کافی
            if current_drafsh < heal_cost:
                return False, f"❌ درفش کافی نداری! نیاز: {heal_cost} درفش، موجود: {current_drafsh} درفش"
            
            # دریافت سلامت فعلی پهلوان
            cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, hero_name))
            hero_row = cur.fetchone()
            if not hero_row:
                return False, f"❌ {hero_name} را نداری"
            
            current_health = int(hero_row[0] or 0)
            
            # محاسبه سلامت پایه
            hero_stats = HEROES.get(hero_name, {})
            race = hero_stats.get('race', '')
            base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
            
            # محاسبه سلامت جدید (حداکثر سلامت پایه)
            new_health = min(current_health + heal_amount, base_health)
            actual_heal = new_health - current_health
            
            # اگر سلامت تا حد نهایی رسیده باشد
            if actual_heal <= 0:
                return False, f"❌ {hero_name} قبلاً سلامت کامل دارد ({current_health}/{base_health})"
            
            # محاسبه هزینه واقعی بر اساس درمان واقعی
            actual_cost = actual_heal * 2
            
            # کسر درفش و افزایش سلامت
            cur.execute("UPDATE users SET drafsh = drafsh - ? WHERE user_id = ?", (actual_cost, user_id))
            cur.execute("UPDATE user_heroes SET health = ? WHERE user_id = ? AND hero = ?", 
                       (new_health, user_id, hero_name))
            conn.commit()
            
            return True, f"✅ {hero_name} درمان شد!\n❤️ سلامت: {current_health} → {new_health}/{base_health}\n🏴 درفش: -{actual_cost}"
        
        except Exception as e:
            logger.error(f"خطا در درمان: {e}")
            return False, f"❌ خطا در درمان: {e}"
        finally:
            conn.close()


# --------------------------- موتور بازی ---------------------------

class GameEngine:
    """منطق بازی: نبردها، روایت‌ها، محاسبات برنده و بازنده."""

    def __init__(self, db: Database) -> None:
        # نگهداری مرجع به دیتابیس برای خواندن/نوشتن داده‌ها
        self.db = db

    def combat_score(self, power: int, wisdom: int) -> float:
        # محاسبه امتیاز نبرد با ترکیب تصادف + قدرت + خرد
        # وزن‌دهی ساده: 60% قدرت، 40% خرد + نویز تصادفی
        base = 0.6 * power + 0.4 * wisdom
        noise = random.uniform(-10, 10)
        return base + noise

    def random_narrative(self, hero_a: str, hero_b: str) -> str:
        # تولید چند جمله حماسی تصادفی برای روایت نبرد (بدون بیت‌های قدیمی)
        lines = [
            f"⚔️ در میدان نبرد، {hero_a} و {hero_b} روبروی هم ایستادند...",
            "🌪 باد به خونابه‌ی خاک می‌پیچید و آسمان فریاد می‌کشید...",
            f"🛡 {hero_a} سپر برافراشت و {hero_b} با چشمانی چون آذرخش به پیش تاخت...",
            "🔥 خاکِ رزمگاه به آتشِ غیرت روشن شد...",
            "⚡️ پژواک گرزها و شمشیرها، دشت را پر کرد...",
        ]
        # انتخاب 2 تا 3 خط تصادفی
        picks = random.sample(lines, k=min(3, len(lines)))
        return "\n".join(picks)

    def decide_winner(
        self,
        attacker: sqlite3.Row,
        defender: sqlite3.Row,
    ) -> Tuple[int, int, str]:
        # تعیین برنده و بازنده بر اساس امتیاز نبرد
        score_a = self.combat_score(attacker["power"] or 0, attacker["wisdom"] or 0)
        score_b = self.combat_score(defender["power"] or 0, defender["wisdom"] or 0)
        if score_a >= score_b:
            winner, loser = attacker["user_id"], defender["user_id"]
            winner_name = attacker["hero"] or "پهلوان"
        else:
            winner, loser = defender["user_id"], attacker["user_id"]
            winner_name = defender["hero"] or "پهلوان"
        # تولید روایت کوتاه
        narrative = self.random_narrative(attacker["hero"] or "پهلوان", defender["hero"] or "پهلوان")
        # افزودن نتیجه به روایت
        narrative += f"\n\n🏅 پیروزی نصیب {winner_name} شد! (+10 افتخار)"
        return winner, loser, narrative


# --------------------------- هندلرهای ربات ---------------------------

class Handlers:
    """تعریف و پیاده‌سازی هندلرها: شروع، تایید عضویت، انتخاب قهرمان، منوها، نبرد، تمرین، آمار و غیره."""

    def __init__(self, db: Database, engine: GameEngine) -> None:
        # نگهداری مراجع به دیتابیس و موتور بازی
        self.db = db
        self.engine = engine
        # نگهداری آخرین نبرد برای امکان انتقام در گروه‌ها: chat_id -> (attacker_id, defender_id)
        self.last_battle: Dict[int, Tuple[int, int]] = {}
        # نگاشت نام‌های قابل قبول پهلوان‌ها (با/بی ایموجی و فاصله‌ها)
        self.hero_alias_map: Dict[str, str] = {}
        for key in HEROES.keys():
            base = key
            name_only = key.split(" ", 1)[-1]
            emoji = key.split(" ", 1)[0] if " " in key else ""
            aliases = {
                base,
                name_only,
                f"{emoji}{name_only}",
                f"{emoji} {name_only}",
                f"{name_only} {emoji}",
            }
            for a in aliases:
                self.hero_alias_map[self._normalize(a)] = key
        
        # نگاشت نام‌های قابل قبول دیوان (با/بی ایموجی و فاصله‌ها)
        self.demon_alias_map: Dict[str, str] = {}
        for demon in DEMONS_CATALOG:
            key = demon["name"]
            base = key
            name_only = key.split(" ", 1)[-1]
            emoji = key.split(" ", 1)[0] if " " in key else ""
            aliases = {
                base,
                name_only,
                f"{emoji}{name_only}",
                f"{emoji} {name_only}",
                f"{name_only} {emoji}",
            }
            for a in aliases:
                self.demon_alias_map[self._normalize(a)] = key
        # وضعیت نبردهای دکمه‌ای: user_id -> state
        # state: { 'opponent_id': int, 'combo_used': bool, 'defend_next': bool, 'started_at': iso, 'chat_id': int }
        self.active_battles: Dict[int, Dict[str, Any]] = {}
    
    def _get_power_with_items(self, user_id: int, base_power: int, hero_name: str) -> int:
        """محاسبه قدرت با آیتم‌های فعال"""
        power = base_power
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT tea_active_until, gorz_active_until FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                tea_until = row[0]
                gorz_until = row[1]
                
                # چک چای پهلوانی
                if tea_until:
                    try:
                        tea_dt = datetime.fromisoformat(tea_until)
                        if datetime.utcnow() < tea_dt:
                            power += 10
                    except:
                        pass
                
                # چک گرز رستم (فقط برای رستم)
                if gorz_until and hero_name == "🦁 رستم":
                    try:
                        gorz_dt = datetime.fromisoformat(gorz_until)
                        if datetime.utcnow() < gorz_dt:
                            power += 30
                    except:
                        pass
        finally:
            conn.close()
        return power

    async def godmode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # فرمان بسیار محرمانه برای اعطای نامحدود به خودِ ارسال‌کننده
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return
        # اگر ADMIN_ID در محیط تنظیم شده، فقط همان کاربر مجاز است
        if ADMIN_ID and int(ADMIN_ID) != int(user.id):
            await update.effective_message.reply_text("❌ این کد فقط برای مالک ربات مجاز است.")
            return
        args = context.args or []
        code = args[0] if args else ""
        if not code:
            await update.effective_message.reply_text("کد محرمانه را پس از فرمان بنویس: /godmode <code>")
            return
        # فقط اگر کد دقیقاً مطابق باشد، اجرا شود؛ اعمال فقط برای همان کاربر
        if code != GODMODE_CODE:
            await update.effective_message.reply_text("❌ کد نادرست است.")
            return
        try:
            # اعطای نامحدود: سطح و درفش بالا
            self.db.grant_unlimited(user.id)
            me = self.db.get_user(user.id)
            await update.effective_message.reply_text(
                f"✅ حالت نامحدود فعال شد!\nسطح: {me['level'] or 0} | درفش: {me['drafsh'] or 0}"
            )
        except Exception as e:
            logger.error("godmode error for %s: %s", user.id, e)
            await update.effective_message.reply_text("❌ خطا در فعال‌سازی حالت نامحدود.")

    async def restore_backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دستور بازیابی دیتابیس از آخرین بکاپ (فقط برای ادمین)"""
        user = update.effective_user
        if not user:
            return
        
        # فقط ادمین می‌تواند بکاپ بازیابی کند
        if ADMIN_ID and int(ADMIN_ID) != int(user.id):
            await update.effective_message.reply_text("❌ این دستور فقط برای مالک ربات مجاز است.")
            return
        
        try:
            # دریافت لیست بکاپ‌ها
            backups = self.db.backup_manager.list_backups()
            
            if not backups:
                await update.effective_message.reply_text("❌ هیچ بکاپی موجود نیست")
                return
            
            # نمایش لیست بکاپ‌ها
            msg = "📦 بکاپ‌های موجود:\n\n"
            for i, backup in enumerate(backups[:10], 1):  # نمایش 10 بکاپ آخر
                msg += f"{i}. {backup['name']}\n"
                msg += f"   📅 {backup['created']} | 📊 {backup['size_kb']} KB\n\n"
            
            msg += "\nبرای بازیابی، شماره بکاپ را بنویس: /restore_backup <number>"
            await update.effective_message.reply_text(msg)
        
        except Exception as e:
            logger.error(f"خطا در نمایش بکاپ‌ها: {e}")
            await update.effective_message.reply_text(f"❌ خطا: {e}")

    async def restore_backup_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """بازیابی بکاپ شماره مشخص شده"""
        user = update.effective_user
        if not user:
            return
        
        # فقط ادمین می‌تواند بکاپ بازیابی کند
        if ADMIN_ID and int(ADMIN_ID) != int(user.id):
            await update.effective_message.reply_text("❌ این دستور فقط برای مالک ربات مجاز است.")
            return
        
        args = context.args or []
        if not args:
            await update.effective_message.reply_text("استفاده: /restore_backup_number <number>")
            return
        
        try:
            backup_num = int(args[0])
            backups = self.db.backup_manager.list_backups()
            
            if backup_num < 1 or backup_num > len(backups):
                await update.effective_message.reply_text(f"❌ شماره بکاپ نامعتبر است (1-{len(backups)})")
                return
            
            selected_backup = backups[backup_num - 1]
            
            # تأیید قبل از بازیابی
            buttons = [
                [InlineKeyboardButton("✅ بازیابی", callback_data=f"confirm_restore:{selected_backup['path']}")],
                [InlineKeyboardButton("❌ لغو", callback_data="cancel_restore")]
            ]
            
            await update.effective_message.reply_text(
                f"⚠️ آیا مطمئن هستی؟\n\n"
                f"بکاپ: {selected_backup['name']}\n"
                f"تاریخ: {selected_backup['created']}\n\n"
                f"این عملیات دیتابیس فعلی را جایگزین می‌کند!",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        except ValueError:
            await update.effective_message.reply_text("❌ شماره بکاپ باید عدد باشد")
        except Exception as e:
            logger.error(f"خطا در بازیابی بکاپ: {e}")
            await update.effective_message.reply_text(f"❌ خطا: {e}")

    async def confirm_restore_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """تأیید و اجرای بازیابی بکاپ"""
        query = update.callback_query
        if not query or not query.data:
            return
        
        await query.answer()
        
        if not query.data.startswith("confirm_restore:"):
            return
        
        backup_path = query.data.split(":", 1)[1]
        
        try:
            # بازیابی بکاپ
            success = self.db.backup_manager.restore_from_backup(backup_path)
            
            if success:
                await query.edit_message_text(
                    f"✅ دیتابیس با موفقیت بازیابی شد!\n\n"
                    f"بکاپ: {backup_path}\n\n"
                    f"⚠️ لطفاً ربات را ریستارت کنید"
                )
            else:
                await query.edit_message_text("❌ خطا در بازیابی دیتابیس")
        
        except Exception as e:
            logger.error(f"خطا در بازیابی: {e}")
            await query.edit_message_text(f"❌ خطا: {e}")

    async def cancel_restore_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """لغو بازیابی بکاپ"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("❌ بازیابی لغو شد")

    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دستور ورود به پنل ادمین"""
        user = update.effective_user
        if not user:
            return
        
        # فقط ادمین می‌تواند وارد شود
        if user.id != ADMIN_ID:
            await update.effective_message.reply_text("❌ شما ادمین نیستید")
            return
        
        # درخواست کلمه عبور
        await update.effective_message.reply_text(
            "🔐 پنل ادمین\n\n"
            "لطفاً کلمه عبور را وارد کنید:\n"
            "/admin_login <password>"
        )
    
    async def admin_login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ورود به پنل ادمین با کلمه عبور"""
        user = update.effective_user
        if not user or user.id != ADMIN_ID:
            await update.effective_message.reply_text("❌ شما ادمین نیستید")
            return
        
        args = context.args or []
        if not args:
            await update.effective_message.reply_text("استفاده: /admin_login <password>")
            return
        
        password = " ".join(args)
        
        # تأیید کلمه عبور
        if not AdminPanel.verify_password(password, user.id):
            await update.effective_message.reply_text("❌ کلمه عبور نادرست است")
            return
        
        # ذخیره جلسه ادمین در context
        context.user_data['admin_session'] = True
        context.user_data['admin_login_time'] = datetime.utcnow().isoformat()
        
        # نمایش پنل ادمین
        buttons = [
            [InlineKeyboardButton("📦 مدیریت بکاپ", callback_data="admin_backup")],
            [InlineKeyboardButton("💰 انتقال درفش", callback_data="admin_transfer_drafsh")],
            [InlineKeyboardButton("⭐ انتقال XP", callback_data="admin_transfer_xp")],
            [InlineKeyboardButton("� اتنظیم سطح", callback_data="admin_set_level")],
            [InlineKeyboardButton("🚫 مسدود کردن", callback_data="admin_block")],
            [InlineKeyboardButton("✅ رفع مسدودیت", callback_data="admin_unblock")],
            [InlineKeyboardButton("�  اطلاعات کاربر", callback_data="admin_user_info")],
            [InlineKeyboardButton("❌ خروج", callback_data="admin_logout")],
        ]
        
        await update.effective_message.reply_text(
            "✅ خوش آمدید به پنل ادمین!\n\n"
            "یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def admin_panel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """مدیریت کال‌بک‌های پنل ادمین"""
        query = update.callback_query
        if not query or not query.data:
            return
        
        await query.answer()
        
        user = query.from_user
        if not user or user.id != ADMIN_ID:
            await query.edit_message_text("❌ شما ادمین نیستید")
            return
        
        # بررسی جلسه ادمین
        if not context.user_data.get('admin_session'):
            await query.edit_message_text("❌ جلسه منقضی شده است. دوباره وارد شوید: /admin_login")
            return
        
        action = query.data
        admin_actions = AdminActions(DB_PATH)
        
        if action == "admin_backup":
            # نمایش بکاپ‌ها
            backups = self.db.backup_manager.list_backups()
            if not backups:
                await query.edit_message_text("❌ هیچ بکاپی موجود نیست")
                return
            
            msg = "📦 بکاپ‌های موجود:\n\n"
            for i, backup in enumerate(backups[:10], 1):
                msg += f"{i}. {backup['name']}\n"
                msg += f"   📅 {backup['created']} | 📊 {backup['size_kb']} KB\n\n"
            
            buttons = [
                [InlineKeyboardButton("🔄 بکاپ جدید", callback_data="admin_backup_create")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")],
            ]
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
        
        elif action == "admin_backup_create":
            # ایجاد بکاپ جدید
            backup_path = self.db.backup_manager.create_backup("admin_manual")
            if backup_path:
                await query.edit_message_text(f"✅ بکاپ ایجاد شد:\n{backup_path}")
            else:
                await query.edit_message_text("❌ خطا در ایجاد بکاپ")
        
        elif action == "admin_logout":
            # خروج
            context.user_data['admin_session'] = False
            await query.edit_message_text("✅ خروج موفق")
        
        elif action == "admin_back":
            # بازگشت به منوی اصلی
            buttons = [
                [InlineKeyboardButton("📦 مدیریت بکاپ", callback_data="admin_backup")],
                [InlineKeyboardButton("💰 انتقال درفش", callback_data="admin_transfer_drafsh")],
                [InlineKeyboardButton("⭐ انتقال XP", callback_data="admin_transfer_xp")],
                [InlineKeyboardButton("📈 تنظیم سطح", callback_data="admin_set_level")],
                [InlineKeyboardButton("🚫 مسدود کردن", callback_data="admin_block")],
                [InlineKeyboardButton("✅ رفع مسدودیت", callback_data="admin_unblock")],
                [InlineKeyboardButton("👤 اطلاعات کاربر", callback_data="admin_user_info")],
                [InlineKeyboardButton("❌ خروج", callback_data="admin_logout")],
            ]
            await query.edit_message_text(
                "✅ پنل ادمین\n\n"
                "یکی از گزینه‌ها را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        else:
            await query.edit_message_text(f"⏳ این قابلیت در حال توسعه است")

    def _demons_keyboard(self, user_level: int) -> InlineKeyboardMarkup:
        rows: List[List[InlineKeyboardButton]] = []
        # نمایش دیوان با قفل بر اساس سطح کاربر
        for d in DEMONS_CATALOG:
            base_req = int(d.get("unlock_level", 1))
            power_based = 4 + int(int(d.get("power", 0)) // 10)
            req = max(base_req, power_based)
            
            power = d.get('power', 0)
            wisdom = d.get('wisdom', 0)
            base_label = f"{d['name']} — قدرت {power} | خرد {wisdom}"
            
            if user_level >= req:
                label = base_label
                callback_data = f"demon_select:{d['name']}"
            else:
                label = f"{base_label} 🔒 (سطح {req})"
                callback_data = f"demon_locked:{d['name']}"
            
            rows.append([InlineKeyboardButton(label, callback_data=callback_data)])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])
        return InlineKeyboardMarkup(rows)


        # قالب نمایش هویت کاربر در پیام‌ها: «نام» در خط اول و «ID: عددی» در خط بعد
    def _format_user_display(self, row: sqlite3.Row, fallback_name: Optional[str] = None) -> str:
        # نمایش نام نمایشی کاربر (full_name) که در سلامِ شروع استفاده می‌شود
        name = (row["full_name"] or fallback_name or "کاربر") if row else (fallback_name or "کاربر")
        try:
            uid = row["user_id"] if row else None
        except Exception:
            uid = None
        uid_text = str(uid) if uid is not None else "—"
        return f"{name}\nID: {uid_text}"

    def _normalize(self, s: str) -> str:
        # نرمال‌سازی ساده: حذف فاصله‌های اضافه و علائم بی‌ربط در ابتدا/انتها
        s = (s or "").strip()
        s = " ".join(s.split())
        # استانداردسازی کاف/ی فارسی-عربی
        s = s.replace("ي", "ی").replace("ك", "ک")
        return s

    async def _check_membership(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        # بررسی عضویت کاربر در کانال/گروه اجباری با get_chat_member
        try:
            user_id = update.effective_user.id if update.effective_user else None
            if not user_id:
                return False
            member: ChatMember = await context.bot.get_chat_member(chat_id=REQUIRED_CHAT, user_id=user_id)
            status = member.status
            # وضعیت‌های مجاز: creator, administrator, member
            if status in ("creator", "administrator", "member"):
                self.db.set_joined_channel(user_id, True)
                return True
            self.db.set_joined_channel(user_id, False)
            return False
        except Exception as e:
            # در صورت خطا (مثلا دسترسی به کانال خصوصی یا تنظیم نبودن chat id)، عضویت را نامعتبر در نظر می‌گیریم
            logger.warning("Membership check failed: %s", e)
            return False

    def _membership_keyboard(self) -> InlineKeyboardMarkup:
        # کیبورد برای پیوستن و تایید عضویت
        buttons = [
            [InlineKeyboardButton(text="📢 عضویت در کانال", url=f"https://t.me/{REQUIRED_CHAT.lstrip('@')}")],
            [InlineKeyboardButton(text="✅ تایید عضویت", callback_data="verify_membership")],
        ]
        return InlineKeyboardMarkup(buttons)

    async def _show_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup: InlineKeyboardMarkup) -> None:
        # نمایش/ویرایش یک پیام پنلی ثابت برای منوها
        chat = update.effective_chat
        if not chat:
            return
        user_data = context.user_data
        msg_id = user_data.get("panel_msg_id")
        try:
            if msg_id:
                await context.bot.edit_message_text(chat_id=chat.id, message_id=msg_id, text=text, reply_markup=markup)
            else:
                sent = await chat.send_message(text, reply_markup=markup)
                user_data["panel_msg_id"] = sent.message_id
        except Exception:
            sent = await chat.send_message(text, reply_markup=markup)
            user_data["panel_msg_id"] = sent.message_id

    def _heroes_keyboard(self, user_level: int = 1) -> ReplyKeyboardMarkup:
        # کیبورد انتخاب قهرمان (ReplyKeyboard) با فیلتر سطح
        rows = []
        for name, stats in HEROES.items():
            req = int(stats.get("required_level", 1))
            if user_level >= req:
                rows.append([name])
            else:
                rows.append([f"🔒 {name} (سطح {req})"])
        rows.append(["🔙 بازگشت"])
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

    def _main_menu_keyboard(self, user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
        # کیبورد منوی اصلی (با دکمه ادمین برای ادمین)
        if user_id == ADMIN_ID:
            return ReplyKeyboardMarkup(ADMIN_MENU_BUTTONS, resize_keyboard=True)
        return ReplyKeyboardMarkup(MAIN_MENU_BUTTONS, resize_keyboard=True)

    def _heroes_inline_keyboard(self, user_level: int) -> InlineKeyboardMarkup:
        # ساخت کیبورد اینلاین برای فهرست پهلوانان با قفل برای سطح‌های بالاتر
        def _strip_emoji(txt: str) -> str:
            return txt.split(" ", 1)[-1] if " " in txt else txt
        rows: List[List[InlineKeyboardButton]] = []
        for name, stats in HEROES.items():
            base_req = stats.get("required_level", 1)
            power_based = 3 + int(int(stats.get("power", 0)) // 10)
            req = max(int(base_req), int(power_based))
            # تلاش برای یافتن نژاد/توضیح از CHAR_DATA
            race = stats.get("race") or "—"
            power = stats.get("power", 0)
            wisdom = stats.get("wisdom", 0)
            # نمایش جمع‌وجور در برچسب دکمه
            base_label = f"{name} — {race} | 💪 {power} | 🧠 {wisdom}"
            label = base_label if user_level >= req else f"{base_label} 🔒 (lvl {req})"
            rows.append([InlineKeyboardButton(label, callback_data=f"hero_select:{name}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])
        return InlineKeyboardMarkup(rows)

    def _demons_reply_keyboard(self) -> ReplyKeyboardMarkup:
        # کیبورد Reply برای فهرست دیوان
        rows: List[List[str]] = []
        for d in DEMONS_CATALOG:
            rows.append([d["name"]])
        rows.append(["🔙 بازگشت"])
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

    def _shop_reply_keyboard(self) -> ReplyKeyboardMarkup:
        # کیبورد Reply برای بازار قهوه‌خانه با نمایش قیمت‌ها
        rows = [
            ["🍵 چای پهلوانی (+10 قدرت، 20 دقیقه) - 500 درفش"],
            ["🪶 پر سیمرغ (+40 سلامت به همه) - 700 درفش"],
            ["⚔️ گرز رستم (+30 قدرت، 1 ساعت، lvl20) - 5000 درفش"],
            ["🩹 کمک های اولیه (+50 سلامت) - 100 درفش"],
            ["🔙 بازگشت"],
        ]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

    def _mine_reply_keyboard(self) -> ReplyKeyboardMarkup:
        rows = [
            ["⛏ جمع آوری درفش"],
            ["🛠 ارتقا معدن"],
            ["🔙 بازگشت"],
        ]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

    def _mine_rate(self, level: int) -> int:
        # نرخ تولید: 100 درفش در ساعت در هر سطح (سطح×100)
        lvl = max(1, min(int(level or 1), 30))
        return 100 * lvl

    def _mine_upgrade_cost(self, level: int) -> int:
        # هزینه ارتقا به سطح بعد: 500 × سطح فعلی (افزایش یافته)
        lvl = max(1, int(level or 1))
        return 500 * lvl

    async def _battle_demon_by_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE, demon_name: str) -> None:
        demon = next((d for d in DEMONS_CATALOG if d["name"] == demon_name), None)
        if not demon:
            await update.effective_chat.send_message("دیو یافت نشد.")
            return
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        attacker_power = me["power"] or 0
        attacker_wisdom = me["wisdom"] or 0
        base_attacker = int((attacker_power) + random.randint(0, 10) - (0))  # مبنا؛ اثر خرد در فرمول خاص PvE پایین‌تر
        demon_power = int(demon["power"]) or 0
        demon_wisdom = int(demon["wisdom"]) or 0
        base_demon = int(0.75 * demon_power + 0.25 * demon_wisdom + random.randint(0, 10))
        notes: List[str] = []
        abilities = demon.get("abilities", [])
        if any("×2" in (a.get("effect") or "") for a in abilities) and random.random() < 0.5:
            base_demon = int(base_demon * 1.5)
            notes.append("⚡️ یورشِ دیو شدّت گرفت (دمیج افزایشی)")
        if any("کاهش" in (a.get("effect") or "") for a in abilities) and random.random() < 0.4:
            base_attacker = max(1, int(base_attacker * 0.75))
            notes.append("🛡 زرهِ دیو، ضربهٔ تو را کاست")
        if any("خودآسیبی" in (a.get("risk") or "") for a in abilities) and random.random() < 0.3:
            self_harm = random.randint(3, 8)
            base_demon = max(1, base_demon - self_harm)
            notes.append(f"🩸 دیو از نیرنگ خود آسیب دید ({self_harm}-)")
        attacker_score = base_attacker + random.randint(-5, 5)
        demon_score = base_demon + random.randint(-5, 5)
        verse = random.choice([
            "غریو سپاهان و جوشن درید\nدلیران به میدان همی کوفتند",
            "چو صف‌ها بیاراستند انجمن\nجهان شد پر از خنجر و جامهٔ آهن",
        ])
        if attacker_score >= demon_score:
            honor_gain = random.randint(15, 25)
            drafsh_gain = random.randint(15, 25)
            xp_gain = random.randint(5, 10)  # کاهش XP نبرد با دیو
            self.db.add_rewards(user.id, honor_gain, drafsh_gain, xp_gain)
            self.db.decrease_health(user.id, 3)
            me2 = self.db.get_user(user.id)
            text = (
                f"{verse}\n\n"
                f"👹 دیو: {demon_name}\n"
                f"{''.join(n + '\n' for n in notes)}"
                f"🗡 دمیج تو: {base_attacker} | 🛡 دمیج دیو: {base_demon}\n\n"
                f"🏅 پیروز شدی! (+{honor_gain} احترام، +{drafsh_gain} درفش)\n"
                f"❤️ سلامت تو: {me2['health'] or 0}"
            )
        else:
            self.db.decrease_health(user.id, 8)
            self.db.add_rewards(user.id, honor=-5, drafsh=0)
            me2 = self.db.get_user(user.id)
            text = (
                f"{verse}\n\n"
                f"👹 دیو: {demon_name}\n"
                f"{''.join(n + '\n' for n in notes)}"
                f"🗡 دمیج تو: {base_attacker} | 🛡 دمیج دیو: {base_demon}\n\n"
                f"❌ دیو چیره شد... (-5 احترام)\n"
                f"❤️ سلامت تو: {me2['health'] or 0}"
            )
        await update.effective_chat.send_message(text)

    async def _show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "منوی اصلی:") -> None:
        # نمایش یا به‌روزرسانی منوی اصلی و ذخیره message_id برای ویرایش‌های بعدی
        chat = update.effective_chat
        if not chat:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            sent = await chat.send_message(text, reply_markup=self._main_menu_keyboard(user_id))
            if context and hasattr(context, "user_data"):
                context.user_data["menu_msg_id"] = sent.message_id
        except Exception:
            user_id = update.effective_user.id if update.effective_user else None
            await chat.send_message(text, reply_markup=self._main_menu_keyboard(user_id))

    async def back_main_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # بازگشت به منوی اصلی
        query = update.callback_query
        if not query:
            return
        await query.answer()
        try:
            await query.edit_message_text("منوی اصلی:")
        except Exception:
            pass
        # پنل اصلی با دکمه بازگشت‌ها
        await self._show_panel(update, context, "منوی اصلی:", InlineKeyboardMarkup([]))
        user_id = query.from_user.id if query.from_user else None
        await query.message.reply_text("منوی اصلی:", reply_markup=self._main_menu_keyboard(user_id))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # هندلر دستور /start
        user = update.effective_user
        if not user:
            return
        
        # بررسی مسدود بودن کاربر
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM blocked_users WHERE user_id = ?", (user.id,))
            if cur.fetchone():
                await update.effective_chat.send_message(
                    "🚫 متأسفانه شما مسدود شده‌اید و نمی‌توانید از بازی استفاده کنید."
                )
                return
        finally:
            conn.close()
        
        # ثبت/به‌روزرسانی کاربر در دیتابیس
        self.db.upsert_user(user.id, user.username, user.full_name)
        
        # بررسی عضویت قبلی
        me = self.db.get_user(user.id)
        already_joined = me and (me["joined_channel"] if "joined_channel" in me.keys() else 0) == 1
        
        # پیام خوش‌آمد حماسی
        welcome = (
            f"سلام {user.first_name or ''}!\n\n"
            f"به *{GAME_NAME}* خوش آمدی! 🏹\n"
            "در این سرزمین، پهلوانانِ نامدار به نبردهای حماسی می‌روند، افتخار می‌جویند و نام خود را در دفتر روزگار ثبت می‌کنند."
        )
        await update.effective_chat.send_message(welcome, parse_mode=ParseMode.MARKDOWN)

        # اگر قبلاً عضو شده، مستقیم به منو برو
        if already_joined:
            await self._show_main_menu(update, context, "منوی اصلی:")
            return
        
        # الزام عضویت در کانال/گروه
        membership_text = (
            "برای ورود به بازی، ابتدا در کانال/گروهِ موردنظر عضو شو سپس دکمه‌ی زیر را بفشار.\n"
            "بدون عضویت، راه به رزمگاه نیست!"
        )
        await self._show_panel(update, context, membership_text, self._membership_keyboard())

    async def verify_membership(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # کال‌بک تایید عضویت (پس از فشردن دکمه «تایید عضویت»)
        query = update.callback_query
        if not query:
            return
        await query.answer()
        ok = await self._check_membership(update, context)
        if not ok:
            # عدم تایید عضویت
            await query.edit_message_text(
                "هنوز نشانه‌ای از عضویت تو ندیدم. دوباره کوشش کن یا اندکی درنگ کن و سپس تایید بزن.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        # تایید شد: هدایت به انتخاب قهرمان
        await query.edit_message_text(
            "🎖 اکنون به سرای پهلوانان گام نه! از فهرست زیر انتخاب کن:",
            parse_mode=ParseMode.MARKDOWN,
        )
        # ایجاد پیام منوی اصلی و ذخیره شناسه برای ویرایش‌های بعدی
        await self._show_main_menu(update, context)

    async def hero_select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # انتخاب قهرمان از طریق اینلاین کیبورد با قفل سطح
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("hero_select:"):
            return
        hero = query.data.split(":", 1)[1]
        user_id = query.from_user.id
        lvl = self.db.get_level(user_id)
        
        # دریافت آمار پهلوان
        stats = HEROES.get(hero)
        if not stats:
            await query.edit_message_text("پهلوان یافت نشد.")
            return
        
        # چک سطح موردنیاز
        req = stats.get("required_level", 1)
        if lvl < req:
            await query.edit_message_text(f"🔒 سطح تو برای این پهلوان کافی نیست! (نیاز به سطح {req})")
            return
        race = stats.get("race")
        # اعمال بونوس‌های نژادی روی ویژگی‌های ذخیره‌شونده
        rfx = RACES.get(race or "", {})
        power = stats["power"] + int(rfx.get("power_bonus", 0))
        wisdom = stats["wisdom"] + int(rfx.get("wisdom_bonus", 0))
        # اگر همان پهلوانِ فعلی است، اطلاع بده
        me = self.db.get_user(user_id)
        current_hero = me["hero"] if me else None
        if current_hero == hero:
            try:
                await query.edit_message_text("این پهلوان پیش‌تر به عنوان پیش‌فرض برگزیده شده است.")
            except Exception:
                await query.message.reply_text("این پهلوان پیش‌تر به عنوان پیش‌فرض برگزیده شده است.")
            return
        # جایگزینی پهلوان: قبلی از دارایی حذف شود و این یکی پیش‌فرض گردد
        # تعیین سلامت پایه برای ثبت در user_heroes
        base_health = 100 + int(RACES.get(race or "", {}).get("health_bonus", 0))
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            if current_hero:
                cur.execute("DELETE FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, current_hero))
            # ثبت پیش‌فرض جدید در users و user_heroes
            cur.execute(
                "UPDATE users SET hero = ?, race = COALESCE(?, race), power = ?, wisdom = ?, health = COALESCE(health, ?), honor = COALESCE(honor, 0), drafsh = COALESCE(drafsh, 0) WHERE user_id = ?",
                (hero, race, power, wisdom, base_health, user_id),
            )
            cur.execute(
                "REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)",
                (user_id, hero, base_health),
            )
            conn.commit()
        finally:
            conn.close()
        msg = (
            f"🏅 پهلوانِ پیش‌فرض تو اکنون: *{hero}*\n"
            f"👣 نژاد: {race or '—'}\n"
            f"💪 قدرت: {power} | 🧠 خرد: {wisdom} | ❤️ سلامت پایه: {base_health}\n\n"
            "می‌توانی راهی میدان نبرد شوی!"
        )
        user_id = query.from_user.id if query.from_user else None
        await query.message.reply_text(msg, reply_markup=self._main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN)

    async def main_menu_router(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # روتر منوی اصلی بر اساس متن دکمه‌ها
        text = (update.message.text or "").strip()
        user = update.effective_user
        if not user:
            return
        
        # بررسی مسدود بودن کاربر
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM blocked_users WHERE user_id = ?", (user.id,))
            if cur.fetchone():
                await update.effective_chat.send_message(
                    "🚫 متأسفانه شما مسدود شده‌اید و نمی‌توانید از بازی استفاده کنید."
                )
                return
        finally:
            conn.close()
        
        # بررسی اینکه کاربر در حال وارد کردن رمز ادمین است
        if context.user_data.get('waiting_for_admin_password'):
            context.user_data['waiting_for_admin_password'] = False
            if ADMIN_PANEL_PASSWORD and text == ADMIN_PANEL_PASSWORD:
                # رمز صحیح است
                await self._show_admin_panel(update, context)
            else:
                await update.effective_chat.send_message("❌ رمز نادرست است")
            return
        
        # بررسی اقدامات ادمین - broadcast_message (قبل از دیگر شرط‌ها)
        admin_action = context.user_data.get('admin_action')
        if admin_action == 'broadcast_message':
            # کاربر پیام را وارد کرد
            message_text = text
            
            await update.effective_chat.send_message("📢 ارسال پیام به تمام کاربران...\n\nلطفاً صبر کنید...")
            
            # دریافت تمام کاربران
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users")
                users = cur.fetchall()
            finally:
                conn.close()
            
            sent_count = 0
            failed_count = 0
            
            # ارسال پیام به تمام کاربران
            for user_row in users:
                user_id = user_row[0]
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📢 پیام از ادمین:\n\n{message_text}"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام به {user_id}: {e}")
                    failed_count += 1
            
            result_msg = (
                f"✅ ارسال پیام تکمیل شد!\n\n"
                f"✅ موفق: {sent_count}\n"
                f"❌ ناموفق: {failed_count}"
            )
            
            await update.effective_chat.send_message(result_msg)
            context.user_data.pop('admin_action', None)
            await self._show_admin_panel(update, context)
            return
        
        # اگر admin_action دیگری است، ادامه بده
        if admin_action:
            # این بخش برای سایر admin_action ها است
            pass
        
        # اطمینان از ثبت کاربر
        self.db.upsert_user(user.id, user.username, user.full_name)
        # لاگ برای دیباگ
        logger.info(f"main_menu_router: user={user.id}, text={text}")
        
        # بررسی مراحل تبادل درفش
        transfer_step = context.user_data.get('transfer_step')
        if transfer_step == 'waiting_for_id':
            # کاربر در حال وارد کردن آیدی است
            try:
                target_id = int(text)
                await self._transfer_step_2(update, context, target_id)
                return
            except ValueError:
                if text == "/cancel":
                    context.user_data.pop('transfer_step', None)
                    await update.effective_chat.send_message("❌ تبادل لغو شد.")
                    return
                await update.effective_chat.send_message(
                    "❌ لطفاً یک عدد صحیح وارد کنید یا /cancel برای لغو"
                )
                return
        elif transfer_step == 'waiting_for_amount':
            # کاربر در حال وارد کردن مقدار است
            try:
                amount = int(text)
                await self._process_transfer_final(update, context, amount)
                return
            except ValueError:
                if text == "/cancel":
                    context.user_data.pop('transfer_step', None)
                    context.user_data.pop('transfer_target_id', None)
                    await update.effective_chat.send_message("❌ تبادل لغو شد.")
                    return
                await update.effective_chat.send_message(
                    "❌ لطفاً یک عدد صحیح وارد کنید یا /cancel برای لغو"
                )
                return
        
        # بررسی اقدامات ادمین
        admin_action = context.user_data.get('admin_action')
        if admin_action == 'transfer_drafsh_from':
            try:
                to_user_id = int(text)
                context.user_data['admin_transfer_to'] = to_user_id
                context.user_data['admin_action'] = 'transfer_drafsh_amount'
                await update.effective_chat.send_message("مقدار درفش را وارد کنید:")
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'transfer_drafsh_amount':
            try:
                amount = int(text)
                from_id = ADMIN_ID  # ادمین
                to_id = context.user_data.get('admin_transfer_to')
                
                admin_actions = AdminActions(DB_PATH)
                success, msg = admin_actions.transfer_drafsh(from_id, to_id, amount)
                
                await update.effective_chat.send_message(msg)
                
                # ارسال پیام به کاربر گیرنده
                if success:
                    try:
                        await context.bot.send_message(
                            chat_id=to_id,
                            text=f"🎁 هدیه از ادمین!\n\n💰 {amount} درفش دریافت کردی"
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام به {to_id}: {e}")
                
                context.user_data.pop('admin_action', None)
                context.user_data.pop('admin_transfer_to', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'transfer_xp_from':
            try:
                to_user_id = int(text)
                context.user_data['admin_transfer_to'] = to_user_id
                context.user_data['admin_action'] = 'transfer_xp_amount'
                await update.effective_chat.send_message("مقدار XP را وارد کنید:")
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'transfer_xp_amount':
            try:
                amount = int(text)
                from_id = ADMIN_ID  # ادمین
                to_id = context.user_data.get('admin_transfer_to')
                
                admin_actions = AdminActions(DB_PATH)
                success, msg = admin_actions.transfer_xp(from_id, to_id, amount)
                
                await update.effective_chat.send_message(msg)
                
                # ارسال پیام به کاربر گیرنده
                if success:
                    try:
                        await context.bot.send_message(
                            chat_id=to_id,
                            text=f"🎁 هدیه از ادمین!\n\n⭐ {amount} XP دریافت کردی"
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام به {to_id}: {e}")
                
                context.user_data.pop('admin_action', None)
                context.user_data.pop('admin_transfer_to', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'set_level_user':
            try:
                user_id = int(text)
                context.user_data['admin_level_user'] = user_id
                context.user_data['admin_action'] = 'set_level_amount'
                await update.effective_chat.send_message("سطح جدید را وارد کنید:")
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'set_level_amount':
            try:
                level = int(text)
                user_id = context.user_data.get('admin_level_user')
                
                admin_actions = AdminActions(DB_PATH)
                success, msg = admin_actions.set_level(user_id, level)
                
                await update.effective_chat.send_message(msg)
                
                # ارسال پیام به کاربر
                if success:
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🎁 هدیه از ادمین!\n\n📈 سطح تو به {level} تنظیم شد"
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام به {user_id}: {e}")
                
                context.user_data.pop('admin_action', None)
                context.user_data.pop('admin_level_user', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'block_user':
            try:
                user_id = int(text)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS blocked_users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER UNIQUE,
                            reason TEXT,
                            blocked_at TEXT
                        )
                    """)
                    cur.execute("""
                        INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at)
                        VALUES (?, ?, ?)
                    """, (user_id, "مسدود شده توسط ادمین", datetime.utcnow().isoformat()))
                    conn.commit()
                    await update.effective_chat.send_message(f"✅ کاربر {user_id} مسدود شد")
                    
                    # ارسال پیام مسدودیت به کاربر
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="🚫 متأسفانه شما مسدود شده‌اید و نمی‌توانید از بازی استفاده کنید."
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام مسدودیت به {user_id}: {e}")
                finally:
                    conn.close()
                
                context.user_data.pop('admin_action', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'unblock_user':
            try:
                user_id = int(text)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM blocked_users WHERE user_id = ?", (user_id,))
                    conn.commit()
                    await update.effective_chat.send_message(f"✅ مسدودیت کاربر {user_id} رفع شد")
                    
                    # ارسال پیام رفع مسدودیت به کاربر
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="✅ مسدودیت شما رفع شد! اکنون می‌توانید دوباره از بازی استفاده کنید.\n\n/start برای شروع"
                        )
                    except Exception as e:
                        logger.error(f"خطا در ارسال پیام رفع مسدودیت به {user_id}: {e}")
                finally:
                    conn.close()
                
                context.user_data.pop('admin_action', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        elif admin_action == 'user_info':
            try:
                user_id = int(text)
                admin_actions = AdminActions(DB_PATH)
                user_info = admin_actions.get_user_info(user_id)
                
                if user_info:
                    msg = (
                        f"👤 اطلاعات کاربر:\n\n"
                        f"🆔 آیدی: {user_info['user_id']}\n"
                        f"👤 نام کاربری: {user_info['username'] or '—'}\n"
                        f"📝 نام کامل: {user_info['full_name'] or '—'}\n"
                        f"🏹 پهلوان: {user_info['hero'] or '—'}\n"
                        f"📈 سطح: {user_info['level']}\n"
                        f"⭐ XP: {user_info['xp']}\n"
                        f"🌟 افتخار: {user_info['honor']}\n"
                        f"🏴 درفش: {user_info['drafsh']}"
                    )
                else:
                    msg = "❌ کاربر یافت نشد"
                
                await update.effective_chat.send_message(msg)
                context.user_data.pop('admin_action', None)
                await self._show_admin_panel(update, context)
                return
            except ValueError:
                await update.effective_chat.send_message("❌ لطفاً یک عدد صحیح وارد کنید")
                return
        
        # بررسی انتخاب
        if text == "🏹 پهلوانان":
            # نمایش فهرست پهلوانان در ReplyKeyboard (منو جایگزین)
            user_level = self.db.get_level(user.id)
            await update.effective_chat.send_message("فهرست پهلوانان:", reply_markup=self._heroes_keyboard(user_level))
        elif text == "⚔️ نبرد":
            await self._random_battle_opponent(update, context)
        elif text == "🏆 رنکینگ":
            await self._show_leaderboard(update, context)
        elif text == "👹 دیوان":
            # قفل موقت بخش دیوان
            await update.effective_chat.send_message(
                "🔒 این بخش در حال حاضر در دسترس نیست.\n"
                "به زودی فعال خواهد شد!"
            )
        elif text == "💼 دارایی":
            await self._assets(update, context)
        elif text == "❓ راهنما":
            # راهنمای تقسیم شده با دکمه‌ها
            buttons = [
                [InlineKeyboardButton("🎯 شروع بازی", callback_data="help:start")],
                [InlineKeyboardButton("🏹 پهلوانان", callback_data="help:heroes")],
                [InlineKeyboardButton("⚔️ نبردها", callback_data="help:battle")],
                [InlineKeyboardButton("🏺 بازار", callback_data="help:shop")],
                [InlineKeyboardButton("⛏ معدن و مأموریت", callback_data="help:mine")],
                [InlineKeyboardButton("💼 دارایی و سطح", callback_data="help:assets")],
            ]
            await update.effective_chat.send_message(
                "📖 *راهنمای جنگ پهلوانان*\n\n"
                "یک بخش را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )
        elif text == "❓ راهنما OLD":
            help_text = (
                "📖 *راهنمای کامل جنگ پهلوانان*\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎯 *شروع بازی*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ با دستور /start بازی را آغاز کن\n"
                "2️⃣ در کانال اجباری عضو شو\n"
                "3️⃣ یک پهلوان برگزین\n"
                "4️⃣ آماده نبرد شو!\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏹 *پهلوانان*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• هر پهلوان دارای قدرت، خرد و نژاد است\n"
                "• نژادها اثرات خاص دارند:\n"
                "  🇮🇷 ایران: +5 قدرت، +5 احترام در پیروزی\n"
                "  🐉 توران: +5 سرعت، احتمال حمله دوبل\n"
                "  🕊 سیستان: +5 خرد، قابلیت احیای سیمرغ\n"
                "  🌊 سمنگان: +10 سلامتی، تمرین مؤثرتر\n"
                "  🔥 دیوان: +8 قدرت، -5 احترام در پیروزی\n"
                "• با افزایش سطح، پهلوانان بیشتر باز می‌شوند\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚔️ *نبردها*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 *در ربات (خصوصی):*\n"
                "• دکمه «⚔️ نبرد» → انتخاب حریف → حمله\n"
                "• گزینه‌ها: حمله معمولی، حمله ترکیبی (سطح 5+)\n"
                "• برنده: +15 درفش، +10~20 احترام\n"
                "• بازنده: -5 سلامتی\n\n"
                
                "📍 *در گروه‌ها:*\n"
                "• روی پیام حریف ریپلای کن\n"
                "• بنویس: «حمله رستم» یا «حمله <نام پهلوان>»\n"
                "• یا دستور: /attack <نام پهلوان>\n"
                "• به حریف پیام خصوصی ارسال می‌شود\n"
                "• حریف می‌تواند دفاع یا انتقام بگیرد\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💥 *حمله ترکیبی*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• نیازمند سطح ۵ یا بالاتر\n"
                "• هر نبرد فقط یک‌بار قابل استفاده\n"
                "• ۷۰٪ احتمال موفقیت\n"
                "• موفقیت: آسیب ×۲\n"
                "• شکست: آسیب کاهش می‌یابد\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🛡 *دفاع و انتقام*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• وقتی به تو حمله شد، پیام خصوصی می‌آید\n"
                "• دکمه «🛡 دفاع»: ضربه بعدی نصف می‌شود\n"
                "• دکمه «⚡️ انتقام»: فوراً حمله متقابل\n"
                "• انتقام در گروه فقط به صورت خصوصی است\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏺 *بازار قهوه‌خانه*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🍵 چای پهلوانی: +5 قدرت (۳۰ درفش)\n"
                "🪶 پر سیمرغ: +30 سلامتی (۵۰ درفش)\n"
                "⚔️ گرز رستم: +10 قدرت (۸۰ درفش، سطح 5+)\n"
                "🩹 کمک‌های اولیه: +50 سلامت یک پهلوان (۴۰ درفش)\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏕 *مأموریت روزانه*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• هر ۲۴ ساعت یک مأموریت تصادفی\n"
                "• موفقیت: +15 احترام، +30 درفش\n"
                "• احتمال موفقیت: ۶۰٪\n"
                "• در صورت عدم موفقیت، پاداشی نیست\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⛏ *معدن*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• سطح ۱: ۱۰۰ درفش/ساعت\n"
                "• سطح ۲: ۲۰۰ درفش/ساعت (ارتقا: ۲۰۰ درفش)\n"
                "• هر ساعت یک‌بار برداشت کن\n"
                "• ارتقا معدن تولید را دو برابر می‌کند\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🕊 *دعوت سیمرغ*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• فقط وقتی سلامتی زیر ۳۰ باشد\n"
                "• هر ۲۴ ساعت یک‌بار\n"
                "• پاداش: +50 سلامتی، +5 احترام\n"
                "• مخصوص نژاد سیستان\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🌠 *مهارت ویژه*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• نیازمند سطح ۱۰\n"
                "• هر نژاد مهارت ویژه دارد:\n"
                "  🇮🇷 ایران: ضربه کوهستان (+15 قدرت)\n"
                "  🐉 توران: حمله دوبل سریع\n"
                "  🕊 سیستان: احیای کامل (۵۰ درفش)\n"
                "  🌊 سمنگان: محافظ الهی\n"
                "  🔥 دیوان: نفرین تاریکی (-20 سلامت)\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💼 *دارایی*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• نمایش آیدی، سطح، احترام، درفش\n"
                "• فهرست پهلوانان و سلامت هرکدام\n"
                "• پهلوانان با سلامتی صفر بعد از ۲۴ ساعت احیا می‌شوند\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📊 *سطح و احترام*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• هر ۱۰۰ احترام = +1 سطح\n"
                "• احترام از نبردها، تمرین و مأموریت به دست می‌آید\n"
                "• سطح بیشتر = دسترسی به پهلوانان و قابلیت‌های بیشتر\n\n"
                
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 *نکات مهم*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• هر پهلوان سلامتی جداگانه دارد\n"
                "• در نبردها، سلامت کاهش می‌یابد\n"
                "• با کمک‌های اولیه یا احیای سیمرغ درمان کن\n"
                "• در گروه‌ها، انتقام فقط به صورت خصوصی است\n"
                "• بیت‌های حماسی برای هر پهلوان منحصر به فرد است\n\n"
                
                "🎮 *موفق باشی در میدان نبرد!*"
            )
            await update.effective_chat.send_message(help_text, parse_mode=ParseMode.MARKDOWN)
        elif text == "🆘 پشتیبانی":
            await update.effective_chat.send_message(
                "🆘 *پشتیبانی*\n\n"
                "برای پشتیبانی و گزارش مشکلات با ادمین تماس بگیرید:\n"
                "👤 @l420lB",
                parse_mode=ParseMode.MARKDOWN
            )
        elif text == "🔐 پنل ادمین":
            # بررسی اینکه کاربر ادمین است
            if user.id != ADMIN_ID:
                await update.effective_chat.send_message("❌ شما ادمین نیستید")
                return
            
            # درخواست رمز
            await update.effective_chat.send_message(
                "🔐 پنل ادمین\n\n"
                "لطفاً رمز را وارد کنید:"
            )
            context.user_data['waiting_for_admin_password'] = True
        
        # دکمه‌های پنل ادمین
        elif context.user_data.get('in_admin_panel'):
            if text == "📦 مدیریت بکاپ":
                await self._admin_backup_menu(update, context)
            elif text == "💰 انتقال درفش":
                await self._admin_transfer_drafsh_menu(update, context)
            elif text == "⭐ انتقال XP":
                await self._admin_transfer_xp_menu(update, context)
            elif text == "📈 تنظیم سطح":
                await self._admin_set_level_menu(update, context)
            elif text == "🚫 مسدود کردن":
                await self._admin_block_menu(update, context)
            elif text == "✅ رفع مسدودیت":
                await self._admin_unblock_menu(update, context)
            elif text == "👤 اطلاعات کاربر":
                await self._admin_user_info_menu(update, context)
            elif text == "📢 ارسال پیام به همه":
                await update.effective_chat.send_message(
                    "📢 ارسال پیام به تمام کاربران\n\n"
                    "پیام خود را وارد کنید:"
                )
                context.user_data['admin_action'] = 'broadcast_message'
            elif text == "🔙 بازگشت به منو":
                context.user_data['in_admin_panel'] = False
                await update.effective_chat.send_message(
                    "🏠 منوی اصلی",
                    reply_markup=self._main_menu_keyboard(user.id)
                )
            elif text == "🔄 بکاپ جدید":
                await self._admin_create_backup(update, context)
            elif text == "📥 دانلود بکاپ":
                await self._admin_download_backup(update, context)
            elif text == "🔙 بازگشت":
                await self._show_admin_panel(update, context)
        
        elif text == "🎁 جایزه روزانه":
            await self._daily_reward(update, context)
        elif text == "💰 تبادل درفش":
            await self._transfer_menu(update, context)
        elif text == "🕊 دعوت سیمرغ":
            await self._simorgh(update, context)
        elif text == "🏺 بازار قهوه خانه":
            await update.effective_chat.send_message("🏺 بازار قهوه خانه:", reply_markup=self._shop_reply_keyboard())
        elif text == "🏕 مأموریت روزانه":
            await self._daily_mission(update, context)
        elif text == "🌠 مهارت ویژه":
            await self._special_skill(update, context)
        elif text == "⛏ معدن":
            me = self.db.get_user(user.id)
            if not me:
                return
            level = int(me["mine_level"] or 1)
            rate = self._mine_rate(level)
            # محاسبه مقدار آماده جمع‌آوری (سقف 3 ساعت)
            last = me["mine_last_collect"]
            now = datetime.utcnow()
            last_dt = None
            try:
                last_dt = datetime.fromisoformat(last) if last else None
            except Exception:
                last_dt = None
            ready = 0
            if last_dt:
                elapsed_hours = max(0.0, min(3.0, (now - last_dt).total_seconds() / 3600.0))  # سقف 3 ساعت
                ready = int(rate * elapsed_hours)
            else:
                # اگر هرگز برداشت نشده، از اکنون شروع به شمارش می‌کنیم
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET mine_last_collect = ? WHERE user_id = ?", (now.isoformat(), user.id))
                    conn.commit()
                finally:
                    conn.close()
                ready = 0
            next_cost = self._mine_upgrade_cost(level) if level < 30 else None
            info = (
                f"⛏ معدن\n"
                f"سطح کنونی: {level} / 30\n"
                f"نرخ تولید: {rate} درفش/ساعت (سقف 3 ساعت)\n"
                f"آمادهٔ برداشت: {ready} درفش\n" +
                (f"هزینه ارتقا به سطح {level+1}: {next_cost} درفش" if next_cost else "در بیشینهٔ سطح هستی")
            )
            await update.effective_chat.send_message(info, reply_markup=self._mine_reply_keyboard())
        elif text == "⛏ جمع آوری درفش":
            # منطق جمع‌آوری با سقف 3 ساعت
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            level = int(me["mine_level"] or 1)
            rate = self._mine_rate(level)
            last = me["mine_last_collect"]
            now = datetime.utcnow()
            last_dt = None
            try:
                last_dt = datetime.fromisoformat(last) if last else None
            except Exception:
                last_dt = None
            amount = 0
            if last_dt:
                elapsed_hours = max(0.0, min(3.0, (now - last_dt).total_seconds() / 3600.0))  # سقف 3 ساعت
                amount = int(rate * elapsed_hours)
            else:
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET mine_last_collect = ? WHERE user_id = ?", (now.isoformat(), user_id))
                    conn.commit()
                finally:
                    conn.close()
            if amount <= 0:
                await update.effective_chat.send_message("چیزی برای جمع‌آوری نیست؛ اندکی صبر کن.")
            else:
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET drafsh = COALESCE(drafsh,0) + ?, mine_last_collect = ? WHERE user_id = ?", (amount, now.isoformat(), user_id))
                    conn.commit()
                finally:
                    conn.close()
                await update.effective_chat.send_message(f"✅ برداشت شد: +{amount} درفش")
        elif text.startswith("🛠 ارتقا معدن"):
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            level = int(me["mine_level"] or 1)
            if level >= 30:
                await update.effective_chat.send_message("معدن در بیشینهٔ سطح است (۳۰).")
            else:
                cost = self._mine_upgrade_cost(level)
                if int(me["drafsh"] or 0) < cost:
                    await update.effective_chat.send_message(f"برای ارتقا به سطح {level+1} به {cost} درفش نیاز داری.")
                    return
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET drafsh = drafsh - ?, mine_level = mine_level + 1 WHERE user_id = ?", (cost, user_id))
                    conn.commit()
                finally:
                    conn.close()
                new_level = level + 1
                new_rate = self._mine_rate(new_level)
                await update.effective_chat.send_message(f"🛠 معدن به سطح {new_level} ارتقا یافت! نرخ تولید اکنون {new_rate}/ساعت است.")
        elif text in [d["name"] for d in DEMONS_CATALOG] or (text.startswith("🔒") and any(d["name"] in text for d in DEMONS_CATALOG)):
            # انتخاب دیو به عنوان پیش‌فرض
            # اگر متن با قفل شروع شده، یعنی دیو قفله
            if text.startswith("🔒"):
                await update.effective_chat.send_message("🔒 این دیو هنوز برای تو باز نشده! سطح بالاتر برو.")
                return
            
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me or not me["hero"]:
                await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
                return
            demon = next((d for d in DEMONS_CATALOG if d["name"] == text), None)
            if not demon:
                await update.effective_chat.send_message("دیو یافت نشد.")
                return
            # بررسی قفل سطح
            lvl = int(me["level"] or 1)
            req = int(demon.get("required_level", 1))
            if lvl < req:
                await update.effective_chat.send_message(f"🔒 سطح تو برای این دیو کافی نیست (نیاز به سطح {req})")
                return
            # ثبت دیو پیش‌فرض
            self.db.set_default_demon(user_id, text)
            await update.effective_chat.send_message(
                f"✅ دیو پیش‌فرض شما به **{text}** تغییر کرد.\n\n"
                f"💪 قدرت: {demon.get('power', 0)} | 🧠 خرد: {demon.get('wisdom', 0)} | ❤️ سلامت: {demon.get('health', 0)}\n\n"
                "اکنون می‌توانی در نبردها از این دیو استفاده کنی!",
                reply_markup=self._main_menu_keyboard(user.id),
                parse_mode=ParseMode.MARKDOWN
            )
        elif text == "🍵 چای پهلوانی (+10 قدرت، 20 دقیقه) - 500 درفش":
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            if int(me["drafsh"] or 0) < 500:
                await update.effective_chat.send_message("درفش بسنده نداری.")
            else:
                # چک کولدان (2 ساعت)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT last_tea_use FROM users WHERE user_id = ?", (user_id,))
                    row = cur.fetchone()
                    last_use = row[0] if row and row[0] else None
                    
                    if last_use:
                        last_dt = datetime.fromisoformat(last_use)
                        if datetime.utcnow() - last_dt < timedelta(hours=2):
                            remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            await update.effective_chat.send_message(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                            return
                    
                    # اعمال اثر چای (20 دقیقه)
                    tea_until = (datetime.utcnow() + timedelta(minutes=20)).isoformat()
                    cur.execute("UPDATE users SET drafsh = drafsh - ?, tea_active_until = ?, last_tea_use = ? WHERE user_id = ?", 
                               (500, tea_until, datetime.utcnow().isoformat(), user_id))
                    conn.commit()
                finally:
                    conn.close()
                await update.effective_chat.send_message("🍵 چای پهلوانی نوشیدی! +10 قدرت برای 20 دقیقه")
        elif text == "🪶 پر سیمرغ (+40 سلامت به همه) - 700 درفش":
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            if int(me["drafsh"] or 0) < 700:
                await update.effective_chat.send_message("درفش بسنده نداری.")
            else:
                # چک کولدان (2 ساعت)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT last_feather_use FROM users WHERE user_id = ?", (user_id,))
                    row = cur.fetchone()
                    last_use = row[0] if row and row[0] else None
                    
                    if last_use:
                        last_dt = datetime.fromisoformat(last_use)
                        if datetime.utcnow() - last_dt < timedelta(hours=2):
                            remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            await update.effective_chat.send_message(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                            return
                    
                    # +40 سلامت به همه پهلوانان
                    cur.execute("SELECT hero FROM user_heroes WHERE user_id = ? AND owned = 1", (user_id,))
                    heroes = [r[0] for r in cur.fetchall()]
                    
                    for hero in heroes:
                        # محاسبه سلامت پایه
                        race = HEROES.get(hero, {}).get('race', '')
                        base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                        cur.execute("UPDATE user_heroes SET health = MIN(?, COALESCE(health,0) + 40) WHERE user_id = ? AND hero = ?", 
                                   (base_health, user_id, hero))
                    
                    cur.execute("UPDATE users SET drafsh = drafsh - ?, last_feather_use = ? WHERE user_id = ?", 
                               (700, datetime.utcnow().isoformat(), user_id))
                    conn.commit()
                finally:
                    conn.close()
                await update.effective_chat.send_message(f"🪶 پر سیمرغ زخم‌های همه پهلوانانت را مرهم کرد! +40 سلامت به {len(heroes)} پهلوان")
        elif text == "⚔️ گرز رستم (+30 قدرت، 1 ساعت، lvl20) - 5000 درفش":
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            if (int(me["level"] or 1) < 20):
                await update.effective_chat.send_message("برای گرز رستم باید سطح ۲۰ داشته باشی.")
            elif me["hero"] != "🦁 رستم":
                await update.effective_chat.send_message("برای استفاده از گرز رستم باید رستم پهلوان پیش‌فرض تو باشد.")
            elif int(me["drafsh"] or 0) < 5000:
                await update.effective_chat.send_message("درفش بسنده نداری.")
            else:
                # چک کولدان (2 ساعت)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT last_gorz_use FROM users WHERE user_id = ?", (user_id,))
                    row = cur.fetchone()
                    last_use = row[0] if row and row[0] else None
                    
                    if last_use:
                        last_dt = datetime.fromisoformat(last_use)
                        if datetime.utcnow() - last_dt < timedelta(hours=2):
                            remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            await update.effective_chat.send_message(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                            return
                    
                    # اعمال اثر گرز (1 ساعت)
                    gorz_until = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                    cur.execute("UPDATE users SET drafsh = drafsh - ?, gorz_active_until = ?, last_gorz_use = ? WHERE user_id = ?", 
                               (5000, gorz_until, datetime.utcnow().isoformat(), user_id))
                    conn.commit()
                finally:
                    conn.close()
                await update.effective_chat.send_message("⚔️ گرز رستم را به دست گرفتی! +30 قدرت برای 1 ساعت")
        elif text == "🩹 کمک های اولیه (+50 سلامت) - 100 درفش":
            user_id = user.id
            me = self.db.get_user(user_id)
            if not me:
                return
            # فقط پهلوانان باز شده (بر اساس سطح)
            lvl = int(me["level"] or 1)
            available_heroes = []
            for name, stats in HEROES.items():
                req = int(stats.get("required_level", 1))
                if lvl >= req:
                    available_heroes.append(name)
            
            if not available_heroes:
                await update.effective_chat.send_message("پهلوانی برای درمان نداری.")
            else:
                # فهرست درمان به‌صورت ReplyKeyboard
                rows = [[f"درمان {h}"] for h in available_heroes]
                rows.append(["🔙 بازگشت"])
                await update.effective_chat.send_message("کدام پهلوان را درمان کنیم؟ (+50 سلامت، 100 درفش)", reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True))

        elif text.startswith("درمان "):
            user_id = user.id
            hero = text[len("درمان "):].strip()
            me = self.db.get_user(user_id)
            if not me:
                return
            if int(me["drafsh"] or 0) < 100:
                await update.effective_chat.send_message("درفش بسنده نداری.")
            else:
                # سقف سلامت پایه بر اساس نژاد پهلوان انتخابی
                race = HEROES.get(hero, {}).get('race', '')
                base = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET drafsh = drafsh - 100 WHERE user_id = ?", (user_id,))
                    cur.execute("UPDATE user_heroes SET health = MIN(?, COALESCE(health,0) + 50) WHERE user_id = ? AND hero = ?", (base, user_id, hero))
                    conn.commit()
                finally:
                    conn.close()
                await update.effective_chat.send_message(f"🩹 {hero} درمان شد! (+50 سلامت)")
        elif text == "🔙 بازگشت":
            await update.effective_chat.send_message("بازگشت به منوی اصلی", reply_markup=self._main_menu_keyboard(user.id))
        elif text in HEROES.keys() or text.startswith("🔒"):
            # انتخاب پهلوان از ReplyKeyboard
            # اگر متن با قفل شروع شده، یعنی پهلوان قفله
            if text.startswith("🔒"):
                await update.effective_chat.send_message("🔒 این پهلوان هنوز برای تو باز نشده! سطح بالاتر برو.")
                return
            
            user_id = user.id
            lvl = self.db.get_level(user_id)
            req = HEROES.get(text, {}).get("required_level", 1)
            if lvl < req:
                await update.effective_chat.send_message(f"🔒 سطح تو برای این پهلوان کافی نیست (نیاز به سطح {req})")
                return
            stats = HEROES[text]
            race = stats.get("race")
            rfx = RACES.get(race or "", {})
            power = stats.get("power", 0) + int(rfx.get("power_bonus", 0))
            wisdom = stats.get("wisdom", 0) + int(rfx.get("wisdom_bonus", 0))
            self.db.set_hero(user_id, text, power, wisdom, race)
            msg = (
                f"🏅 پهلوانِ تو: *{text}*\n"
                f"👣 نژاد: {race or '—'}\n"
                f"💪 قدرت: {power} | 🧠 خرد: {wisdom} | ❤️ سلامت: 100\n"
                f"اکنون آمادهٔ رزم و فخرآفرینی هستی!"
            )
            await update.effective_chat.send_message(msg, reply_markup=self._main_menu_keyboard(user.id), parse_mode=ParseMode.MARKDOWN)

    async def _start_battle_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش فهرست حریفان فعال برای انتخاب
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        opponents = self.db.get_active_opponents(user.id)
        if not opponents:
            await update.effective_chat.send_message("هنوز پهلوانی برای نبرد آماده نیست. اندکی بعد دوباره بکوش.")
            return
        # ساخت دکمه‌های انتخاب حریف
        rows: List[List[InlineKeyboardButton]] = []
        for op in opponents:
            hero = op["hero"] or "پهلوان"
            op_row = self.db.get_user(op["user_id"])  # برای دریافت نام نمایشی
            disp_name = (op_row["full_name"] if op_row and op_row["full_name"] else (op["username"] or "کاربر"))
            label = f"{hero} — {disp_name} — ID: {op['user_id']}"
            rows.append([InlineKeyboardButton(label, callback_data=f"fight:{op['user_id']}")])
        markup = InlineKeyboardMarkup(rows)
        await update.effective_chat.send_message(
            "حریف خود را برگزین تا ناقوس نبرد به صدا درآید:", reply_markup=markup
        )

    async def fight_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # آغاز نبرد پس از انتخاب حریف از کال‌بک
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        # استخراج user_id حریف از داده کال‌بک
        if not query.data.startswith("fight:"):
            return
        try:
            opponent_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        user_id = query.from_user.id
        
        # بررسی محدودیت حمله‌های روزانه (40 حمله در روز)
        can_battle, battle_count = self.db.can_battle_today(user_id, max_battles=40)
        if not can_battle:
            await query.edit_message_text(f"❌ محدودیت حمله‌های روزانه به پایان رسید!\n\n"
                                         f"📊 حمله‌های امروز: {battle_count}/40\n\n"
                                         f"فردا دوباره می‌توانی حمله کنی.")
            return
        
        attacker = self.db.get_user(user_id)
        defender = self.db.get_user(opponent_id)
        if not attacker or not attacker["hero"]:
            await query.edit_message_text("نخست باید پهلوان خود را برگزینی.")
            return
        if not defender or not defender["hero"]:
            await query.edit_message_text("این حریف آماده‌ی نبرد نیست. حریف دیگری برگزین.")
            return
        
        # ثبت حمله
        self.db.record_battle(user_id)
        
        # ذخیره وضعیت قبل از نبرد
        old_attacker_honor = attacker['honor'] or 0
        old_attacker_drafsh = attacker['drafsh'] or 0
        old_attacker_health = attacker['health'] or 0
        old_defender_honor = defender['honor'] or 0
        old_defender_drafsh = defender['drafsh'] or 0
        old_defender_health = defender['health'] or 0
        
        # استفاده از سیستم matchup
        attacker_hero = attacker["hero"]
        defender_hero = defender["hero"]
        matchup = get_matchup_stats(attacker_hero, defender_hero)
        
        # تصمیم‌گیری برنده
        win_chance = matchup["win_chance"]
        attacker_wins = random.random() < win_chance
        
        # محاسبه دمیج و پاداش‌ها
        if attacker_wins:
            damage = random.randint(*matchup["damage"])
            drafsh_gain = random.randint(*matchup["drafsh"])
            honor_gain = random.randint(*matchup["honor"])
            xp_gain = random.randint(8, 12)
            
            # اعمال تغییرات
            self.db.decrease_health(opponent_id, damage)
            self.db.add_rewards(user_id, honor=honor_gain, drafsh=drafsh_gain, xp=xp_gain)
            
            # کم کردن افتخار و درفش بازنده
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET honor = MAX(0, COALESCE(honor,0) - ?), drafsh = MAX(0, COALESCE(drafsh,0) - ?) WHERE user_id = ?", 
                           (honor_gain, drafsh_gain, opponent_id))
                conn.commit()
            finally:
                conn.close()
        else:
            damage = random.randint(*matchup["loss_damage"])
            self.db.decrease_health(user_id, damage)
        
        # واکشی وضعیت جدید
        new_attacker = self.db.get_user(user_id)
        new_defender = self.db.get_user(opponent_id)
        
        # محاسبه تغییرات
        attacker_honor_change = (new_attacker['honor'] or 0) - old_attacker_honor
        attacker_drafsh_change = (new_attacker['drafsh'] or 0) - old_attacker_drafsh
        attacker_health_change = (new_attacker['health'] or 0) - old_attacker_health
        defender_honor_change = (new_defender['honor'] or 0) - old_defender_honor
        defender_drafsh_change = (new_defender['drafsh'] or 0) - old_defender_drafsh
        defender_health_change = (new_defender['health'] or 0) - old_defender_health
        
        # بیت حماسی
        atk_quote = get_hero_quote(attacker_hero, "attack_quotes")
        
        # ساخت پیام کامل برای مهاجم
        attacker_name = attacker["full_name"] or (attacker["username"] or "کاربر")
        defender_name = defender["full_name"] or (defender["username"] or "کاربر")
        
        result = "⚔️ نبرد\n\n"
        if atk_quote:
            result += f"{atk_quote}\n\n"
        
        result += f"🗡 مهاجم: {attacker_hero} ({attacker_name})\n"
        result += f"🛡 مدافع: {defender_hero} ({defender_name})\n\n"
        
        if attacker_wins:
            result += f"✅ پیروزی!\n"
        else:
            result += f"❌ شکست!\n"
        
        result += f"💥 دمیج: {damage}\n\n"
        
        result += f"📊 تغییرات شما:\n"
        result += f"   ❤️ سلامت: {new_attacker['health'] or 0} ({attacker_health_change:+d})\n"
        if attacker_honor_change != 0:
            result += f"   🌟 افتخار: {new_attacker['honor'] or 0} ({attacker_honor_change:+d})\n"
        if attacker_drafsh_change != 0:
            result += f"   🏴 درفش: {new_attacker['drafsh'] or 0} ({attacker_drafsh_change:+d})\n"
        
        result += f"\n📊 تغییرات حریف:\n"
        result += f"   ❤️ سلامت: {new_defender['health'] or 0} ({defender_health_change:+d})\n"
        if defender_honor_change != 0:
            result += f"   🌟 افتخار: {new_defender['honor'] or 0} ({defender_honor_change:+d})\n"
        if defender_drafsh_change != 0:
            result += f"   🏴 درفش: {new_defender['drafsh'] or 0} ({defender_drafsh_change:+d})\n"
        
        await query.edit_message_text(result)

        # پیام به مدافع با گزینه انتقام
        try:
            def_quote = get_hero_quote(attacker_hero, "attack_quotes")
            result_text = "✅ حریف پیروز شد!" if attacker_wins else "❌ حریف شکست خورد!"
            
            pm_text = "⚠️ به تو حمله شد!\n\n"
            if def_quote:
                pm_text += f"{def_quote}\n\n"
            
            pm_text += f"🗡 مهاجم: {attacker_hero} ({attacker_name})\n"
            pm_text += f"🛡 مدافع: {defender_hero} ({defender_name})\n\n"
            pm_text += f"{result_text}\n"
            pm_text += f"💥 دمیج: {damage}\n\n"
            pm_text += f"📊 تغییرات تو:\n"
            pm_text += f"   ❤️ سلامت: {new_defender['health'] or 0} ({defender_health_change:+d})\n"
            if defender_honor_change != 0:
                pm_text += f"   🌟 افتخار: {new_defender['honor'] or 0} ({defender_honor_change:+d})\n"
            if defender_drafsh_change != 0:
                pm_text += f"   🏴 درفش: {new_defender['drafsh'] or 0} ({defender_drafsh_change:+d})\n"
            pm_text += f"\nبرای انتقام آماده‌ای؟"
            
            await context.bot.send_message(
                chat_id=defender["user_id"],
                text=pm_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{attacker['user_id']}")]])
            )
        except Exception:
            pass

    async def _daily_training(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # تمرین روزانه: افزایش 5 واحد قدرت یا خرد، روزی یک‌بار
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        can, remain = self.db.can_train(user.id)
        if not can and remain:
            # نمایش زمان باقی‌مانده به صورت تقریبی
            hours = int(remain.total_seconds() // 3600)
            minutes = int((remain.total_seconds() % 3600) // 60)
            await update.effective_chat.send_message(
                f"اکنون زمان آسایش است! پس از حدود {hours}ساعت و {minutes}دقیقه بازآ که دگرباره تمرین کنیم."
            )
            return
        # کیبورد انتخاب نوع تمرین
        buttons = [
            [InlineKeyboardButton("💪 افزایش قدرت (+5)", callback_data="train:power")],
            [InlineKeyboardButton("🧠 افزایش خرد (+5)", callback_data="train:wisdom")],
        ]
        await update.effective_chat.send_message(
            "چه می‌خواهی پرورش دهی؟",
            reply_markup=InlineKeyboardMarkup(buttons + [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]]),
        )

    async def train_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # کال‌بک انتخاب نوع تمرین
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("train:"):
            return
        user_id = query.from_user.id
        attr = query.data.split(":", 1)[1]
        can, remain = self.db.can_train(user_id)
        if not can:
            await query.edit_message_text("امروز به اندازه کافی ورزیده‌ای! فردا بازآ.")
            return
        self.db.apply_training(user_id, attr)
        await query.edit_message_text(
            "🏋️ تمرین به سرانجام رسید! +5 افزوده شد."
        )

    async def _show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش آمار کامل کاربر با قالب‌بندی Markdown
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        text = (
            f"🧝 نام پهلوان: {me['hero']}\n"
            f"💪 قدرت: {me['power'] or 0}\n"
            f"🧠 خرد: {me['wisdom'] or 0}\n"
            f"❤️ سلامتی: {me['health'] or 0}\n"
            f"🌟 افتخار: {me['honor'] or 0}\n"
            f"🧭 سطح: {me['level'] or 1}"
        )
        await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)

    async def _assets(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش دارایی‌ها: آیدی، سطح، افتخار، پهلوان‌های مالک
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me:
            return
        owned = self.db.list_owned_heroes(user.id)
        # واکشی سلامت هر پهلوان
        heroes_health: Dict[str, int] = {}
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT hero, health FROM user_heroes WHERE user_id = ? AND owned = 1", (user.id,))
            for h, hp in cur.fetchall():
                heroes_health[h] = int(hp) if hp is not None else 100
        finally:
            conn.close()
        # پهلوان پیش‌فرض + اطلاعات پایه
        default_hero = me["hero"]
        # محاسبه XP موردنیاز برای سطح بعدی
        current_level = int(me['level'] or 1)
        current_xp = int(me['xp'] or 0)
        xp_needed = xp_required_for_level(current_level)
        
        lines = [
            f"👤 نام: {me['full_name'] or (me['username'] or 'کاربر')}",
            f"🆔 ایدی عددی: {user.id}",
            f"🎚 سطح: {current_level}",
            f"⭐️ تجربه: {current_xp}/{xp_needed}",
            f"🏆 افتخار: {me['honor'] or 0}",
            f"💰 درفش: {me['drafsh'] or 0}",
            "\n🛡 پهلوان پیش‌فرض:",
        ]
        if default_hero:
            race = HEROES.get(default_hero, {}).get('race', '')
            base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
            hp = heroes_health.get(default_hero, base_health)
            lines.append(f"• {default_hero} — ❤️ سلامت: {hp}")
        else:
            lines.append("— هنوز پهلوانی برنگزیده‌ای")
        # پهلوان‌های قابل انتخاب - فقط مواردی که باز شده‌اند
        lines.append("\n🎒 پهلوان‌های قابل انتخاب:")
        lvl = int(me["level"] or 1)
        for name, stats in HEROES.items():
            req = int(stats.get("required_level", 1))
            if lvl >= req:  # فقط پهلوان‌های باز شده را نمایش بده
                race = stats.get("race") or "—"
                # دریافت سلامت واقعی از دیتابیس
                actual_hp = heroes_health.get(name)
                if actual_hp is None:
                    actual_hp = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                sel = " (پیش‌فرض)" if default_hero == name else ""
                lines.append(f"• {name}{sel} — ❤️ سلامت: {actual_hp}")
        # دیوان: پیش‌فرض و فهرست قابل انتخاب - فقط مواردی که باز شده‌اند
        lines.append("\n👹 دیو پیش‌فرض:")
        # sqlite3.Row does not support dict.get; use key indexing
        default_demon = me["default_demon"]
        if default_demon:
            demon_stats = next((d for d in DEMONS_CATALOG if d["name"] == default_demon), None)
            if demon_stats:
                lines.append(f"• {default_demon} — ❤️ سلامت: {demon_stats.get('health',0)}")
            else:
                lines.append(f"• {default_demon}")
        else:
            lines.append("— هنوز دیوی برنگزیده‌ای")
        lines.append("\n🗂 دیوان قابل نبرد:")
        for d in DEMONS_CATALOG:
            req = int(d.get("required_level", 1))
            if lvl >= req:  # فقط دیوان باز شده را نمایش بده
                lines.append(f"• {d['name']} — ❤️ سلامت: {d.get('health',0)}")
        
        # نمایش آیتم‌های فعال
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT tea_active_until, gorz_active_until FROM users WHERE user_id = ?", (user.id,))
            row = cur.fetchone()
            if row:
                tea_until = row[0]
                gorz_until = row[1]
                
                active_items = []
                if tea_until:
                    try:
                        tea_dt = datetime.fromisoformat(tea_until)
                        if datetime.utcnow() < tea_dt:
                            remaining = tea_dt - datetime.utcnow()
                            minutes = int(remaining.total_seconds() // 60)
                            active_items.append(f"🍵 چای پهلوانی (+10 قدرت) - {minutes} دقیقه باقی‌مانده")
                    except:
                        pass
                
                if gorz_until:
                    try:
                        gorz_dt = datetime.fromisoformat(gorz_until)
                        if datetime.utcnow() < gorz_dt:
                            remaining = gorz_dt - datetime.utcnow()
                            minutes = int(remaining.total_seconds() // 60)
                            active_items.append(f"⚔️ گرز رستم (+30 قدرت) - {minutes} دقیقه باقی‌مانده")
                    except:
                        pass
                
                if active_items:
                    lines.append("\n🎁 آیتم‌های فعال:")
                    for item in active_items:
                        lines.append(f"• {item}")
        finally:
            conn.close()
        
        await update.effective_chat.send_message("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def _start_bot_battle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش فهرست کاربران برای نبرد درون ربات (خصوصی)
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        opponents = self.db.get_active_opponents(user.id, limit=15)
        if not opponents:
            await update.effective_chat.send_message("پهلوانی برای نبرد در دسترس نیست.")
            return
        rows: List[List[InlineKeyboardButton]] = []
        for op in opponents:
            # نمایش نام/ID، نژاد، سطح
            op_user = self.db.get_user(op["user_id"])  # برای دریافت نژاد، سطح و نام نمایشی
            race = op_user["race"] if op_user else "—"
            lvl = op_user["level"] if op_user else 1
            disp_name = (op_user["full_name"] if op_user and op_user["full_name"] else (op["username"] or "کاربر"))
            label = f"{op['hero']} | {race} | lvl {lvl} — {disp_name} — ID: {op['user_id']}"
            rows.append([InlineKeyboardButton(label, callback_data=f"ib_select:{op['user_id']}")])
        await update.effective_chat.send_message("حریف خود را درون ربات برگزین:", reply_markup=InlineKeyboardMarkup(rows))

    async def _battle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # فهرست تعاملی حریفان برای نبرد مرحله‌ای
        await self._start_bot_battle(update, context)

    def _battle_actions_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        # دکمه‌های نبرد ساده شده - فقط حمله
        buttons = [
            [InlineKeyboardButton("🗡 حمله", callback_data="ib_act:attack")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        return InlineKeyboardMarkup(buttons)

    async def ib_select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # آغاز نبرد مرحله‌ای پس از انتخاب حریف
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("ib_select:"):
            return
        try:
            opponent_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        user_id = query.from_user.id
        me = self.db.get_user(user_id)
        you = self.db.get_user(opponent_id)
        if not me or not me["hero"] or not you or not you["hero"]:
            await query.edit_message_text("هر دو باید پهلوان برگزیده باشند.")
            return
        # چک سلامت پهلوان فقط اگر دیو پیش‌فرض نداشته باشد
        # اگر دیو پیش‌فرض دارد، می‌تواند با دیو حمله کند حتی اگر پهلوانش صفر باشد
        has_demon = me["default_demon"] is not None
        if not has_demon:
            cur_hp = self.db.get_current_hero_health(user_id)
            if cur_hp is not None and int(cur_hp) <= 0:
                await query.edit_message_text("❌ سلامت پهلوان تو صفر است؛ نخست احیا کن سپس نبرد.")
                return
        # ثبت وضعیت نبرد
        self.active_battles[user_id] = {
            "opponent_id": opponent_id,
            "combo_used": False,
            "defend_next": False,
            "started_at": datetime.utcnow().isoformat(),
            "chat_id": query.message.chat_id if query.message else None,
        }
        verse = random.choice([
            "غریو سپاهان و جوشن درید\nدلیران به میدان همی کوفتند",
            "چو صف‌ها بیاراستند انجمن\nجهان شد پر از خنجر و جامهٔ آهن",
        ])
        await query.edit_message_text(
            f"{verse}\n\nنبرد آغاز شد! گزینهٔ عمل را برگزین.",
            reply_markup=self._battle_actions_keyboard(user_id),
        )

    def _race_effects_on_damage(self, attacker: sqlite3.Row, base_damage: int) -> Tuple[int, bool]:
        # اعمال اثرات نژادی روی دمیج و امکان حمله دوبل (برای توران)
        race = attacker["race"] or ""
        doubled = False
        dmg = base_damage
        if race in RACES:
            if RACES[race].get("power_bonus"):
                dmg += int(RACES[race]["power_bonus"] * 0.3)
            # احتمال حمله دوگانه برای توران
            ch = RACES[race].get("double_attack_chance", 0.0)
            if ch and random.random() < ch:
                doubled = True
        return max(1, int(dmg)), doubled

    async def ib_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # پردازش اعمال نبرد مرحله‌ای
        query = update.callback_query
        if not query or not query.data:
            logger.warning("ib_action_callback: query or data is None")
            return
        await query.answer()
        if not query.data.startswith("ib_act:"):
            logger.warning(f"ib_action_callback: data doesn't start with ib_act: {query.data}")
            return
        act = query.data.split(":", 1)[1]
        user_id = query.from_user.id
        logger.info(f"ib_action_callback: user={user_id}, act={act}")
        state = self.active_battles.get(user_id)
        if not state:
            logger.warning(f"ib_action_callback: no active battle for user {user_id}")
            await query.edit_message_text("نبردی در جریان نیست.")
            return
        attacker = self.db.get_user(user_id)
        defender = self.db.get_user(state["opponent_id"])
        if not attacker or not defender:
            await query.edit_message_text("حریف یافت نشد.")
            self.active_battles.pop(user_id, None)
            return

        text_lines: List[str] = []
        end_battle = False
        honor_gain = 0
        drafsh_gain = 0

        if act == "attack":
            # محاسبه پایه دمیج - فقط حمله ساده
            is_demon = False
            # چک سلامت پهلوان
            cur_hp = self.db.get_current_hero_health(user_id)
            if cur_hp is not None and int(cur_hp) <= 0:
                text_lines.append("❌ پهلوان انتخاب پیش‌فرض تو نیست یا سلامت آن صفر است.")
                await query.edit_message_text("\n".join(text_lines), reply_markup=self._battle_actions_keyboard(user_id))
                return
            
            # محاسبه قدرت با آیتم‌های فعال
            power_with_items = self._get_power_with_items(user_id, attacker["power"] or 0, attacker["hero"])
            base = int(0.6 * power_with_items + 0.4 * (attacker["wisdom"] or 0) + random.randint(0, 12))
            
            # تزریق بیت حمله از پهلوان مهاجم
            atk_quote = get_hero_quote(attacker["hero"], "attack_quotes")
            if atk_quote:
                text_lines.append(atk_quote)
            
            dmg, doubled = self._race_effects_on_damage(attacker, base)
            if doubled:
                dmg = int(dmg * 1.5)
                text_lines.append("🐉 یورش دوبل تورانی!")
            # دفاع آماده نزد حریف؟
            if int((defender["defend_ready"] or 0)) == 1:
                dmg = max(1, dmg // 2)
                self.db.set_defend_ready(defender["user_id"], False)
            # اعمال خسارت و نمایش پیام دقیق
            old_health = defender["health"] or 100
            self.db.decrease_health(defender["user_id"], dmg)
            na = self.db.get_user(attacker["user_id"])
            nd = self.db.get_user(defender["user_id"])
            new_health = nd["health"] or 0
            health_lost = old_health - new_health
            
            text_lines.append(
                f"\n💥 دمیج: {dmg}\n"
                f"❤️ سلامت شما: {na['health'] or 0}\n"
                f"❤️ سلامت حریف: {new_health} ({health_lost:+d})"
            )
            # بررسی پایان نبرد با شکست حریف
            if (nd["health"] or 0) <= 0:
                end_battle = True
                # محاسبه پاداش دینامیک بر اساس قدرت
                attacker_power = row_get(attacker, "power", 50)
                defender_power = row_get(defender, "power", 50)
                power_diff = max(0, defender_power - attacker_power)
                
                # پاداش پایه + بونوس برای شکست حریف قوی‌تر
                base_honor = random.randint(8, 15)
                base_drafsh = random.randint(10, 20)
                bonus = int(power_diff * 0.1)
                
                race = attacker["race"] or ""
                if race in RACES:
                    base_honor += int(RACES[race].get("honor_win_bonus", 0))
                    base_honor += int(RACES[race].get("honor_win_penalty", 0))
                
                honor_gain = max(5, base_honor + bonus)
                drafsh_gain = base_drafsh + bonus
                xp_gain = random.randint(10, 15)  # XP نبرد ربات
                
                self.db.add_rewards(attacker["user_id"], honor_gain, drafsh_gain, xp_gain)
                
                # بازنده افتخار از دست میده (رندوم)
                honor_loss = random.randint(8, 15)
                conn = self.db._connect()
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET honor = MAX(0, COALESCE(honor,0) - ?) WHERE user_id = ?", (honor_loss, defender["user_id"]))
                    conn.commit()
                finally:
                    conn.close()
                
                self.db.set_level_from_honor(attacker["user_id"])
                self.db.set_level_from_honor(defender["user_id"])
                text_lines.append(
                    f"\n\n🏅 پیروزی!\n\n"
                    f"📊 پاداش شما:\n"
                    f"   🌟 +{honor_gain} افتخار\n"
                    f"   🏴 +{drafsh_gain} درفش\n"
                    f"   ⭐ +{xp_gain} تجربه\n\n"
                    f"📊 حریف:\n"
                    f"   🌟 -{honor_loss} افتخار"
                )

        # اگر ضربه‌ای وارد شد، پیام خصوصی برای حریف با گزینه دفاع/انتقام بفرست
        try:
            if act in ("attack", "combo", "attack_demon", "combo_demon"):
                # بیت اطلاع برای مدافع (حمله صورت‌گرفته)
                def_quote = None if act in ("attack_demon", "combo_demon") else get_hero_quote(attacker["hero"], "attack_quotes")
                await context.bot.send_message(
                    chat_id=defender["user_id"],
                    text=(
                        "⚠️ به تو حمله شد!\n" +
                        (def_quote + "\n\n" if def_quote else "") +
                        "\n".join(text_lines)
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛡 دفاع", callback_data="defend_ready"), InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{attacker['user_id']}")],
                    ]),
                )
        except Exception:
            pass

        # بروزرسانی پیام
        if end_battle:
            self.active_battles.pop(user_id, None)
            await query.edit_message_text("\n".join(text_lines))
        else:
            await query.edit_message_text("\n".join(text_lines), reply_markup=self._battle_actions_keyboard(user_id))

    async def defend_ready_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # فعال‌سازی دفاع برای ضربهٔ بعدی
        query = update.callback_query
        if not query:
            return
        await query.answer()
        self.db.set_defend_ready(query.from_user.id, True)
        await query.edit_message_text("🛡 سپر برافراشته شد! ضربهٔ بعدی کاستی خواهد یافت.")

    async def _simorgh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # دعوت سیمرغ: فقط وقتی health < 30 و هر 24 ساعت یکبار
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        if (me["health"] or 0) >= 30:
            await update.effective_chat.send_message("سیمرغ زمانی فرود آید که زخم‌ها کاری باشد (سلامت زیر ۳۰).")
            return
        cds = self.db.get_cooldowns(user.id)
        last = cds.get("last_simorgh")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.utcnow() - last_dt < timedelta(hours=24):
                    await update.effective_chat.send_message("سیمرغ در اوج آسمان است؛ هنوز زمان نزول او نرسیده است.")
                    return
            except Exception:
                pass
        # اجرای احیا
        lines = [
            "🕊 بانگ سیمرغ از البرز برخاست...",
            "🌬 پرّ سپیدش مرهمِ زخم‌هایت شد...",
            "✨ آفتاب عدالت بر تو تابید...",
            "🌄 سپیده‌دمِ پیروزی نوید می‌دهد...",
            "🌿 جانِ تو از نو به فریاد برخاست...",
        ]
        picks = "\n".join(random.sample(lines, k=random.randint(3, 5)))
        # health +50 و honor +5
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET health = MIN(100, COALESCE(health,0) + 50), honor = COALESCE(honor,0) + 5 WHERE user_id = ?", (user.id,))
            conn.commit()
        finally:
            conn.close()
        self.db.set_last_simorgh(user.id)
        await update.effective_chat.send_message(picks + "\n\n🕊 سیمرغ تو را برکشید! (+50 سلامت، +5 احترام)")

    async def _shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش بازار قهوه‌خانه و دکمه‌های خرید
        buttons = [
            [InlineKeyboardButton("🍵 چای پهلوانی (+10 قدرت، 20 دقیقه) — 500 درفش", callback_data="shop:tea")],
            [InlineKeyboardButton("🪶 پر سیمرغ (+40 سلامت به همه) — 700 درفش", callback_data="shop:feather")],
            [InlineKeyboardButton("⚔️ گرز رستم (+30 قدرت، 1 ساعت، lvl20) — 5000 درفش", callback_data="shop:club")],
            [InlineKeyboardButton("🩹 کمک‌های اولیه (+50 سلامت) — 100 درفش", callback_data="shop:firstaid")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.effective_chat.send_message("🏺 بازار قهوه‌خانه:", reply_markup=InlineKeyboardMarkup(buttons))

    async def shop_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # خرید اقلام بازار
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("shop:"):
            return
        item = query.data.split(":", 1)[1]
        user_id = query.from_user.id
        me = self.db.get_user(user_id)
        if not me:
            return
        drafsh = int(me["drafsh"] or 0)
        level = int(me["level"] or 1)
        msg = ""
        cost = 0
        if item == "tea":
            cost = 500
            if drafsh < cost:
                await query.edit_message_text("درفش بسنده نداری.")
                return
            
            # چک کولدان (2 ساعت)
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT last_tea_use FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                last_use = row[0] if row and row[0] else None
                
                if last_use:
                    last_dt = datetime.fromisoformat(last_use)
                    if datetime.utcnow() - last_dt < timedelta(hours=2):
                        remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        await query.edit_message_text(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                        return
                
                # اعمال اثر چای (20 دقیقه)
                tea_until = (datetime.utcnow() + timedelta(minutes=20)).isoformat()
                cur.execute("UPDATE users SET drafsh = drafsh - ?, tea_active_until = ?, last_tea_use = ? WHERE user_id = ?", 
                           (cost, tea_until, datetime.utcnow().isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
            msg = "🍵 چای پهلوانی نوشیدی! +10 قدرت برای 20 دقیقه"
        elif item == "feather":
            cost = 700
            if drafsh < cost:
                await query.edit_message_text("درفش بسنده نداری.")
                return
            
            # چک کولدان (2 ساعت)
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT last_feather_use FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                last_use = row[0] if row and row[0] else None
                
                if last_use:
                    last_dt = datetime.fromisoformat(last_use)
                    if datetime.utcnow() - last_dt < timedelta(hours=2):
                        remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        await query.edit_message_text(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                        return
                
                # +40 سلامت به همه پهلوانان
                cur.execute("SELECT hero FROM user_heroes WHERE user_id = ? AND owned = 1", (user_id,))
                heroes = [r[0] for r in cur.fetchall()]
                
                for hero in heroes:
                    # محاسبه سلامت پایه
                    race = HEROES.get(hero, {}).get('race', '')
                    base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                    cur.execute("UPDATE user_heroes SET health = MIN(?, COALESCE(health,0) + 40) WHERE user_id = ? AND hero = ?", 
                               (base_health, user_id, hero))
                
                cur.execute("UPDATE users SET drafsh = drafsh - ?, last_feather_use = ? WHERE user_id = ?", 
                           (cost, datetime.utcnow().isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
            msg = f"🪶 پر سیمرغ زخم‌های همه پهلوانانت را مرهم کرد! +40 سلامت به {len(heroes)} پهلوان"
        elif item == "club":
            cost = 5000
            if level < 20:
                await query.edit_message_text("برای گرز رستم باید سطح ۲۰ داشته باشی.")
                return
            if drafsh < cost:
                await query.edit_message_text("درفش بسنده نداری.")
                return
            
            # چک اینکه پهلوان پیش‌فرض رستم باشه
            if me["hero"] != "🦁 رستم":
                await query.edit_message_text("برای استفاده از گرز رستم باید رستم پهلوان پیش‌فرض تو باشد.")
                return
            
            # چک کولدان (2 ساعت)
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT last_gorz_use FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                last_use = row[0] if row and row[0] else None
                
                if last_use:
                    last_dt = datetime.fromisoformat(last_use)
                    if datetime.utcnow() - last_dt < timedelta(hours=2):
                        remaining = timedelta(hours=2) - (datetime.utcnow() - last_dt)
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        await query.edit_message_text(f"⏳ باید {hours} ساعت و {minutes} دقیقه صبر کنی.")
                        return
                
                # اعمال اثر گرز (1 ساعت)
                gorz_until = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                cur.execute("UPDATE users SET drafsh = drafsh - ?, gorz_active_until = ?, last_gorz_use = ? WHERE user_id = ?", 
                           (cost, gorz_until, datetime.utcnow().isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
            msg = "⚔️ گرز رستم را به دست گرفتی! +30 قدرت برای 1 ساعت"
        elif item == "firstaid":
            cost = 100
            if drafsh < cost:
                await query.edit_message_text("برای کمک‌های اولیه به ۱۰۰ درفش نیاز داری.")
                return
            # انتخاب پهلوان برای درمان - فقط پهلوانان باز شده
            lvl = int(me["level"] or 1)
            available_heroes = []
            for name, stats in HEROES.items():
                req = int(stats.get("required_level", 1))
                if lvl >= req:
                    available_heroes.append(name)
            
            if not available_heroes:
                await query.edit_message_text("پهلوانی برای درمان نداری.")
                return
            buttons = [[InlineKeyboardButton(f"درمان {h} (100 درفش)", callback_data=f"heal:{h}")] for h in available_heroes]
            buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])
            await query.edit_message_text("کدام پهلوان را درمان کنیم؟ (+50 سلامت)", reply_markup=InlineKeyboardMarkup(buttons))
            return
        if msg:
            await query.edit_message_text(msg)

    async def heal_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # درمان پهلوان انتخابی با کسر ۱۰۰ درفش و +50 سلامت
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("heal:"):
            return
        hero = query.data.split(":", 1)[1]
        user_id = query.from_user.id
        me = self.db.get_user(user_id)
        if not me:
            return
        if int(me["drafsh"] or 0) < 100:
            await query.edit_message_text("درفش بسنده نداری.")
            return
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            # افزایش سلامت پهلوان، سقف سلامت پایه
            race = HEROES.get(hero, {}).get('race', '')
            base = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
            cur.execute("UPDATE users SET drafsh = drafsh - 100 WHERE user_id = ?", (user_id,))
            cur.execute("UPDATE user_heroes SET health = MIN(?, COALESCE(health,0) + 50) WHERE user_id = ? AND hero = ?", (base, user_id, hero))
            conn.commit()
        finally:
            conn.close()
        await query.edit_message_text(f"🩹 {hero} درمان شد! (+50 سلامت)")

    async def _mine(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # منوی معدن: نمایش سطح، نرخ، جمع‌آوری و ارتقا
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me:
            return
        level = int(me["mine_level"] or 1)
        rate = 100 if level <= 1 else 200
        buttons = [
            [InlineKeyboardButton("⛏ جمع‌آوری درفش", callback_data="mine:collect")],
            [InlineKeyboardButton("🛠 ارتقا معدن (۲۰۰ درفش)", callback_data="mine:upgrade")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")],
        ]
        await update.effective_chat.send_message(
            f"⛏ معدن\nسطح: {level}\nنرخ تولید: {rate} درفش/ساعت",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def mine_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("mine:"):
            return
        action = query.data.split(":", 1)[1]
        user_id = query.from_user.id
        me = self.db.get_user(user_id)
        if not me:
            return
        level = int(me["mine_level"] or 1)
        rate = self._mine_rate(level)
        # محاسبه مقدار قابل جمع‌آوری (سقف 3 ساعت)
        last = me["mine_last_collect"]
        now = datetime.utcnow()
        last_dt = None
        try:
            last_dt = datetime.fromisoformat(last) if last else None
        except Exception:
            last_dt = None
        hours = 0
        if last_dt:
            delta = now - last_dt
            hours = min(3.0, delta.total_seconds() / 3600.0)  # سقف 3 ساعت
        else:
            # اگر هرگز برداشت نشده، از اکنون شروع به شمارش می‌کنیم
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET mine_last_collect = ? WHERE user_id = ?", (now.isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
        amount = int(hours * rate)
        if action == "collect":
            if hours <= 0:
                await query.edit_message_text("چیزی برای جمع‌آوری نیست؛ اندکی صبر کن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]]))
                return
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET drafsh = COALESCE(drafsh,0) + ?, mine_last_collect = ? WHERE user_id = ?", (amount, now.isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
            await query.edit_message_text(f"✅ برداشت شد: +{amount} درفش (برای {hours} ساعت)")
        elif action == "upgrade":
            cost = self._mine_upgrade_cost(level)
            if int(me["drafsh"] or 0) < cost:
                await query.edit_message_text(f"برای ارتقا به سطح {level+1} به {cost} درفش نیاز داری.")
                return
            if level >= 30:
                await query.edit_message_text("معدن در بالاترین سطح است.")
                return
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET drafsh = drafsh - ?, mine_level = ? WHERE user_id = ?", (cost, level+1, user_id))
                conn.commit()
            finally:
                conn.close()
            new_rate = self._mine_rate(level+1)
            await query.edit_message_text(f"🛠 معدن به سطح {level+1} ارتقا یافت! نرخ تولید اکنون {new_rate}/ساعت است.")

    async def _daily_mission(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # مأموریت روزانه با پاداش و کول‌دان 24ساعته
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        cds = self.db.get_cooldowns(user.id)
        last = cds.get("last_mission")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                remaining = timedelta(hours=24) - (datetime.utcnow() - last_dt)
                if remaining > timedelta(0):
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    await update.effective_chat.send_message(f"⏳ زمان مانده تا مأموریت بعدی: {hours} ساعت و {minutes} دقیقه")
                    return
            except Exception:
                pass
        missions = [
            "شکست دادن دیوی در دماوند",
            "حفاظت از کاروان بازرگانان در ری",
            "پاک‌سازی گردنهٔ الموت از راهزنان",
            "یاری به دهقانان توس در برداشت گندم",
        ]
        task = random.choice(missions)
        success = random.random() < 0.6
        if success:
            self.db.add_rewards(user.id, honor=15, drafsh=30, xp=10)  # کاهش XP مأموریت
            self.db.set_last_mission(user.id)
            await update.effective_chat.send_message(f"🏕 مأموریت: {task}\n\n✅ به پیروزی انجامید! (+15 احترام، +30 درفش)")
        else:
            self.db.set_last_mission(user.id)
            await update.effective_chat.send_message(f"🏕 مأموریت: {task}\n\n❌ ناکام ماند؛ دستاوردی نبود.")

    async def _special_skill(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # مهارت ویژه نژادها (سطح ≥ ۱۰، هر ۱۲ ساعت یک‌بار)
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        if (me["level"] or 1) < 10:
            await update.effective_chat.send_message("برای مهارت ویژه باید به سطح ۱۰ برسی.")
            return
        # از ستون skill_unlocked برای ثبت کول‌دان استفاده می‌کنیم به‌صورت زمان ISO نگهداری در items یا همین ستون؟
        # برای سادگی: skill_unlocked را به عنوان timestamp آخرین استفاده ذخیره نمی‌کنیم؛ در این نسخه از items یک کلید نیمه‌ساختگی استفاده نمی‌کنیم.
        # پیاده‌سازی ساده: از honored cooldown با last_simorgh سوءاستفاده نمی‌کنیم؛ فقط یک کول‌دان درون‌حافظه‌ای کوتاه.
        # برای پایداری: پیام راهنما نمایش داده می‌شود؛ اجرای اثرات نیازمند هدف/سکانس نبرد است که در این نسخه به‌صورت خودی اعمال می‌شود.
        race = me["race"] or ""
        msg = ""
        if race == "🇮🇷 ایران":
            # ضربه کوهستان: افزایش موقت قدرت
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET power = COALESCE(power,0) + 15 WHERE user_id = ?", (user.id,))
                conn.commit()
            finally:
                conn.close()
            msg = "⛰ ضربه کوهستان: نیروی کوه در مشت تو جمع شد! (+15 قدرت موقت)"
        elif race == "🐉 توران":
            msg = "⚡️ حملهٔ دوبل سریع: در نبردهای آتی بختِ یورش دوگانه افزون است!"
        elif race == "🕊 سیستان":
            # احیای کامل با مصرف ۵۰ درفش
            if (me["drafsh"] or 0) < 50:
                await update.effective_chat.send_message("برای احیای سیستانی به ۵۰ درفش نیاز داری.")
                return
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET drafsh = drafsh - 50, health = 100 WHERE user_id = ?", (user.id,))
                conn.commit()
            finally:
                conn.close()
            msg = "🕊 سیمرغِ سیستان جانت را بازآفرید! (سلامت کامل، -50 درفش)"
        elif race == "🌊 سمنگان":
            msg = "🛡 محافظ الهی: تا نوبت بعدی در امان خواهی بود!"
        elif race == "🔥 دیوان":
            # نفرین تاریکی: هم خود و هم دشمن -20 سلامت (اگر در نبرد فعالی باشد)
            self.db.decrease_health(user.id, 20)
            msg = "🕯 نفرین تاریکی: آتش درونت شعله کشید؛ همگان گزند دیدند! (-20 سلامت)"
        else:
            msg = "مهارت ویژه‌ای برای این نژاد ثبت نشده است."
        await update.effective_chat.send_message(msg)

    async def _daily_reward(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # جایزه روزانه: 200 درفش هر 24 ساعت
        user = update.effective_user
        if not user:
            return
        
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        
        # بررسی آخرین دریافت جایزه
        last_reward = me["last_daily_reward"] if me and "last_daily_reward" in me.keys() else None
        if last_reward:
            try:
                last_dt = datetime.fromisoformat(last_reward)
                if datetime.utcnow() - last_dt < timedelta(hours=24):
                    remaining = timedelta(hours=24) - (datetime.utcnow() - last_dt)
                    hours = int(remaining.total_seconds() // 3600)
                    minutes = int((remaining.total_seconds() % 3600) // 60)
                    await update.effective_chat.send_message(
                        f"🎁 جایزه روزانه قبلاً دریافت شده!\n"
                        f"⏳ زمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه"
                    )
                    return
            except Exception:
                pass
        
        # اعطای جایزه
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET drafsh = COALESCE(drafsh,0) + 200, last_daily_reward = ? WHERE user_id = ?",
                (datetime.utcnow().isoformat(), user.id)
            )
            conn.commit()
        finally:
            conn.close()
        
        await update.effective_chat.send_message(
            "🎁 جایزه روزانه دریافت شد!\n"
            "💰 +200 درفش به حساب شما اضافه شد\n\n"
            "فردا دوباره بازگردید! 🌅"
        )

    async def _transfer_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # منوی تبادل درفش - مرحله 1: درخواست آیدی
        user = update.effective_user
        if not user:
            return
        
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        
        # بررسی محدودیت روزانه
        today = datetime.utcnow().date().isoformat()
        last_transfer_date = me["last_transfer_date"] if me and "last_transfer_date" in me.keys() else None
        daily_amount = me["daily_transfer_amount"] if me and "daily_transfer_amount" in me.keys() and me["daily_transfer_amount"] is not None else 0
        
        # اگر روز جدید است، ریست کن
        if last_transfer_date != today:
            daily_amount = 0
        
        # محدودیت برای کاربر خاص
        is_admin = user.id == ADMIN_ID
        remaining_limit = "نامحدود" if is_admin else max(0, 1000 - daily_amount)
        
        text = (
            f"💰 تبادل درفش\n\n"
            f"💳 موجودی شما: {me['drafsh'] or 0} درفش\n"
            f"📊 انتقال امروز: {daily_amount}/{'∞' if is_admin else '1000'}\n"
            f"🔄 باقی‌مانده: {remaining_limit}\n\n"
            f"📝 مرحله 1: آیدی عددی گیرنده را وارد کنید\n"
            f"مثال: 123456789\n\n"
            f"برای لغو: /cancel"
        )
        
        # ذخیره وضعیت در context
        context.user_data['transfer_step'] = 'waiting_for_id'
        
        # دکمه لغو
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_transfer")]])
        
        await update.effective_chat.send_message(text, reply_markup=keyboard)
    
    async def _transfer_step_2(self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int) -> None:
        # مرحله 2: درخواست مقدار
        user = update.effective_user
        if not user:
            return
        
        me = self.db.get_user(user.id)
        if not me:
            return
        
        # بررسی وجود کاربر مقصد
        target_user = self.db.get_user(target_id)
        if not target_user:
            await update.effective_chat.send_message(
                f"❌ کاربر با آیدی {target_id} در بازی ثبت نام نکرده است.\n\n"
                f"لطفاً آیدی صحیح وارد کنید یا /cancel برای لغو"
            )
            return
        
        target_name = target_user["full_name"] or (target_user["username"] or "کاربر")
        
        text = (
            f"💰 تبادل درفش\n\n"
            f"👤 گیرنده: {target_name}\n"
            f"🆔 آیدی: {target_id}\n\n"
            f"💳 موجودی شما: {me['drafsh'] or 0} درفش\n\n"
            f"📝 مرحله 2: مقدار درفش را وارد کنید\n"
            f"مثال: 500\n\n"
            f"برای لغو: /cancel"
        )
        
        # ذخیره آیدی گیرنده
        context.user_data['transfer_step'] = 'waiting_for_amount'
        context.user_data['transfer_target_id'] = target_id
        
        # دکمه لغو
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_transfer")]])
        
        await update.effective_chat.send_message(text, reply_markup=keyboard)
    
    async def _process_transfer_final(self, update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> None:
        # مرحله نهایی: انجام انتقال
        user = update.effective_user
        if not user:
            return
        
        target_id = context.user_data.get('transfer_target_id')
        if not target_id:
            await update.effective_chat.send_message("❌ خطا: آیدی گیرنده یافت نشد. لطفاً دوباره تلاش کنید.")
            context.user_data.pop('transfer_step', None)
            return
        
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            context.user_data.pop('transfer_step', None)
            return
        
        # بررسی مقدار
        if amount <= 0:
            await update.effective_chat.send_message("❌ مقدار باید بیشتر از صفر باشد.")
            return
        
        # بررسی موجودی
        current_drafsh = me["drafsh"] or 0
        if current_drafsh < amount:
            await update.effective_chat.send_message(
                f"❌ موجودی ناکافی!\n"
                f"💳 موجودی شما: {current_drafsh} درفش\n"
                f"💰 مقدار درخواستی: {amount} درفش"
            )
            context.user_data.pop('transfer_step', None)
            return
        
        # بررسی محدودیت روزانه
        is_admin = user.id == ADMIN_ID
        if not is_admin:
            today = datetime.utcnow().date().isoformat()
            last_transfer_date = me["last_transfer_date"] if me and "last_transfer_date" in me.keys() else None
            daily_amount = me["daily_transfer_amount"] if me and "daily_transfer_amount" in me.keys() and me["daily_transfer_amount"] is not None else 0
            
            # اگر روز جدید است، ریست کن
            if last_transfer_date != today:
                daily_amount = 0
            
            if daily_amount + amount > 1000:
                remaining = 1000 - daily_amount
                await update.effective_chat.send_message(
                    f"❌ محدودیت روزانه!\n"
                    f"📊 انتقال امروز: {daily_amount}/1000\n"
                    f"🔄 باقی‌مانده: {remaining} درفش\n"
                    f"💰 درخواست شما: {amount} درفش"
                )
                context.user_data.pop('transfer_step', None)
                return
        
        # بررسی وجود کاربر مقصد
        target_user = self.db.get_user(target_id)
        if not target_user:
            await update.effective_chat.send_message(
                f"❌ کاربر با آیدی {target_id} در بازی ثبت نام نکرده است."
            )
            context.user_data.pop('transfer_step', None)
            return
        
        # انجام انتقال
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            
            # کسر از فرستنده
            cur.execute("UPDATE users SET drafsh = drafsh - ? WHERE user_id = ?", (amount, user.id))
            
            # اضافه به گیرنده
            cur.execute("UPDATE users SET drafsh = COALESCE(drafsh,0) + ? WHERE user_id = ?", (amount, target_id))
            
            # به‌روزرسانی محدودیت روزانه (فقط برای غیر ادمین)
            if not is_admin:
                today = datetime.utcnow().date().isoformat()
                last_transfer_date = me["last_transfer_date"] if me and "last_transfer_date" in me.keys() else None
                daily_amount = me["daily_transfer_amount"] if me and "daily_transfer_amount" in me.keys() and me["daily_transfer_amount"] is not None else 0
                
                if last_transfer_date != today:
                    daily_amount = 0
                
                new_daily_amount = daily_amount + amount
                cur.execute(
                    "UPDATE users SET daily_transfer_amount = ?, last_transfer_date = ? WHERE user_id = ?",
                    (new_daily_amount, today, user.id)
                )
            
            conn.commit()
        finally:
            conn.close()
        
        # پیام موفقیت به فرستنده
        sender_name = me["full_name"] or (me["username"] or "کاربر")
        target_name = target_user["full_name"] or (target_user["username"] or "کاربر")
        
        await update.effective_chat.send_message(
            f"✅ انتقال موفق!\n\n"
            f"💰 مقدار: {amount} درفش\n"
            f"👤 به: {target_name} (ID: {target_id})\n"
            f"💳 موجودی جدید شما: {current_drafsh - amount} درفش"
        )
        
        # پیام اطلاع به گیرنده
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"💰 درفش دریافت شد!\n\n"
                    f"💵 مقدار: {amount} درفش\n"
                    f"👤 از: {sender_name} (ID: {user.id})\n"
                    f"💳 موجودی جدید شما: {(target_user['drafsh'] or 0) + amount} درفش"
                )
            )
        except Exception:
            # اگر نتوانست پیام بفرستد (کاربر ربات را بلاک کرده)
            pass
        
        # پاک کردن وضعیت
        context.user_data.pop('transfer_step', None)
        context.user_data.pop('transfer_target_id', None)

    async def _random_battle_opponent(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش یک حریف تصادفی برای نبرد
        user = update.effective_user
        if not user:
            return
        
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        
        # دریافت یک حریف تصادفی
        opponents = self.db.get_active_opponents(user.id, limit=1)
        if not opponents:
            await update.effective_chat.send_message("هیچ پهلوانی برای نبرد یافت نشد. بعداً تلاش کنید.")
            return
        
        opponent = opponents[0]
        op_row = self.db.get_user(opponent["user_id"])
        disp_name = (op_row["full_name"] if op_row and op_row["full_name"] else (opponent["username"] or "کاربر"))
        
        buttons = [
            [InlineKeyboardButton("⚔️ حمله", callback_data=f"fight:{opponent['user_id']}")],
            [InlineKeyboardButton("🔄 حریف بعدی", callback_data="next_opponent")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ]
        
        text = (
            f"⚔️ حریف پیشنهادی:\n\n"
            f"🏹 پهلوان: {opponent['hero']}\n"
            f"👤 نام: {disp_name}\n"
            f"🆔 آیدی: {opponent['user_id']}\n"
            f"💪 قدرت: {opponent['power'] or 0}\n"
            f"🧠 خرد: {opponent['wisdom'] or 0}\n"
            f"🌟 افتخار: {opponent['honor'] or 0}\n\n"
            f"آماده نبرد هستید؟"
        )
        
        await update.effective_chat.send_message(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def cancel_transfer_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # لغو تبادل درفش (از دکمه)
        query = update.callback_query
        if not query:
            return
        await query.answer()
        
        # پاک کردن وضعیت
        context.user_data.pop('transfer_step', None)
        context.user_data.pop('transfer_target_id', None)
        
        await query.edit_message_text("❌ تبادل درفش لغو شد.")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # لغو تبادل درفش (از دستور /cancel)
        user = update.effective_user
        if not user:
            return
        
        # بررسی اینکه آیا در حال تبادل است
        transfer_step = context.user_data.get('transfer_step')
        if transfer_step:
            # پاک کردن وضعیت
            context.user_data.pop('transfer_step', None)
            context.user_data.pop('transfer_target_id', None)
            await update.effective_chat.send_message("❌ تبادل درفش لغو شد.")
        else:
            await update.effective_chat.send_message("هیچ عملیاتی برای لغو وجود ندارد.")
    
    async def next_opponent_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش حریف بعدی
        query = update.callback_query
        if not query:
            return
        await query.answer()
        
        user_id = query.from_user.id
        opponents = self.db.get_active_opponents(user_id, limit=1)
        
        if not opponents:
            await query.edit_message_text("هیچ پهلوانی برای نبرد یافت نشد.")
            return
        
        opponent = opponents[0]
        op_row = self.db.get_user(opponent["user_id"])
        disp_name = (op_row["full_name"] if op_row and op_row["full_name"] else (opponent["username"] or "کاربر"))
        
        buttons = [
            [InlineKeyboardButton("⚔️ حمله", callback_data=f"fight:{opponent['user_id']}")],
            [InlineKeyboardButton("🔄 حریف بعدی", callback_data="next_opponent")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ]
        
        text = (
            f"⚔️ حریف پیشنهادی:\n\n"
            f"🏹 پهلوان: {opponent['hero']}\n"
            f"👤 نام: {disp_name}\n"
            f"🆔 آیدی: {opponent['user_id']}\n"
            f"💪 قدرت: {opponent['power'] or 0}\n"
            f"🧠 خرد: {opponent['wisdom'] or 0}\n"
            f"🌟 افتخار: {opponent['honor'] or 0}\n\n"
            f"آماده نبرد هستید؟"
        )
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def bot_fight_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نبرد درون ربات با انتخاب اینلاین
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("bot_fight:"):
            return
        try:
            opponent_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        attacker_user_id = query.from_user.id
        attacker = self.db.get_user(attacker_user_id)
        defender = self.db.get_user(opponent_id)
        if not attacker or not attacker["hero"]:
            await query.edit_message_text("نخست باید پهلوان خود را برگزینی.")
            return
        if not defender or not defender["hero"]:
            await query.edit_message_text("این حریف هنوز پهلوانی برنگزیده است.")
            return
        # استفاده از قهرمان فعلی مهاجم
        winner_id, loser_id, narrative = self.engine.decide_winner(attacker, defender)
        self.db.apply_battle_result(winner_id, loser_id)
        # دمیج پویا بر اساس قدرت مهاجم
        atk_power = attacker["power"] or 0
        damage = max(1, int(atk_power * 0.12 + random.randint(0, 7)))
        if winner_id == attacker_user_id:
            self.db.decrease_health(opponent_id, damage)
        else:
            self.db.decrease_health(attacker_user_id, max(1, damage // 2))
        na = self.db.get_user(attacker_user_id)
        nd = self.db.get_user(opponent_id)
        # پیام نتیجه برای مهاجم
        atk_quote = get_hero_quote(attacker["hero"], "attack_quotes")
        res_attacker = (
            f"⚔️ نبرد\n\n"
            f"پهلوان مهاجم: {attacker['hero']} | پهلوان مدافع: {defender['hero']}\n\n"
            f"{(atk_quote + '\n\n') if atk_quote else ''}{narrative}\n\n"
            f"🗡 دمیج: {damage}\n"
            f"❤️ سلامت من: {na['health'] or 0} | ❤️ سلامت حریف: {nd['health'] or 0}"
        )
        await query.edit_message_text(res_attacker)
        # پیام اطلاع به مدافع + دکمه انتقام خصوصی
        try:
            def_quote = get_hero_quote(attacker["hero"], "attack_quotes")
            await context.bot.send_message(
                chat_id=opponent_id,
                text=(
                    f"⚠️ به تو حمله شد!\n\nپهلوان مهاجم: {attacker['hero']} | پهلوان مدافع: {defender['hero']}\n\n{(def_quote + '\n\n') if def_quote else ''}{narrative}\n\n"
                    f"کاربر {(attacker['full_name'] or (attacker['username'] or 'کاربر'))}\n"
                    f"ایدی عددی : {attacker_user_id}\n\n"
                    f"به کاربر {(defender['full_name'] or (defender['username'] or 'کاربر'))}\n"
                    f"ایدی عددی : {opponent_id} یورش برد!\n\n"
                    f"🗡 دمیج: {damage}\n"
                    f"🌟 {'+10' if winner_id==attacker_user_id else '+0'} افتخار برای حریف"
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{attacker_user_id}")]]),
            )
        except Exception:
            pass

    async def _show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
        # نمایش 5 تایی رنکینگ با صفحه‌بندی
        per_page = 5
        offset = page * per_page
        
        # دریافت کل تعداد
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE hero IS NOT NULL")
            total = cur.fetchone()[0]
        finally:
            conn.close()
        
        rows = self.db.top_honor(per_page + offset)[offset:offset + per_page]
        
        if not rows:
            await update.effective_chat.send_message("هنوز نام‌آوری بر سکوی افتخار ننشسته است!")
            return
        
        lines = [f"🏆 جدول افتخارات (صفحه {page + 1}):\n"]
        medals = ["🥇", "🥈", "🥉", "⭐️", "⭐️"]
        
        for idx, r in enumerate(rows):
            rank = offset + idx + 1
            m = medals[idx] if idx < len(medals) else "⭐️"
            name = r["full_name"] or (r["username"] or "کاربر")
            honor = r["honor"] or 0
            lines.append(f"{m} {rank}. {name} — 🌟 {honor}")
        
        # دکمه‌های صفحه‌بندی
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"rank:{page-1}"))
        if offset + per_page < total:
            buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"rank:{page+1}"))
        
        keyboard = InlineKeyboardMarkup([buttons]) if buttons else None
        await update.effective_chat.send_message("\n".join(lines), reply_markup=keyboard)

    async def rank_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # کال‌بک صفحه‌بندی رنکینگ
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("rank:"):
            return
        try:
            page = int(query.data.split(":", 1)[1])
        except Exception:
            return
        
        # دریافت کل تعداد
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users WHERE hero IS NOT NULL")
            total = cur.fetchone()[0]
        finally:
            conn.close()
        
        per_page = 5
        offset = page * per_page
        rows = self.db.top_honor(per_page + offset)[offset:offset + per_page]
        
        if not rows:
            await query.edit_message_text("هنوز نام‌آوری بر سکوی افتخار ننشسته است!")
            return
        
        lines = [f"🏆 جدول افتخارات (صفحه {page + 1}):\n"]
        medals = ["🥇", "🥈", "🥉", "⭐️", "⭐️"]
        
        for idx, r in enumerate(rows):
            rank = offset + idx + 1
            m = medals[idx] if idx < len(medals) else "⭐️"
            name = r["full_name"] or (r["username"] or "کاربر")
            honor = r["honor"] or 0
            lines.append(f"{m} {rank}. {name} — 🌟 {honor}")
        
        # دکمه‌های صفحه‌بندی
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"rank:{page-1}"))
        if offset + per_page < total:
            buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"rank:{page+1}"))
        
        keyboard = InlineKeyboardMarkup([buttons]) if buttons else None
        await query.edit_message_text("\n".join(lines), reply_markup=keyboard)

    async def help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # کال‌بک راهنمای تقسیم شده
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("help:"):
            return
        
        section = query.data.split(":", 1)[1]
        
        if section == "start":
            text = (
                "🎯 *شروع بازی*\n\n"
                "1️⃣ با دستور /start بازی را آغاز کن\n"
                "2️⃣ در کانال اجباری عضو شو\n"
                "3️⃣ یک پهلوان برگزین\n"
                "4️⃣ آماده نبرد شو!\n\n"
                "پس از انتخاب پهلوان، منوی اصلی نمایش داده می‌شود."
            )
        elif section == "heroes":
            text = (
                "🏹 *پهلوانان*\n\n"
                "• هر پهلوان دارای قدرت، خرد و نژاد است\n"
                "• نژادها اثرات خاص دارند:\n"
                "  🇮🇷 ایران: +5 قدرت، +5 احترام در پیروزی\n"
                "  🐉 توران: +5 سرعت، احتمال حمله دوبل\n"
                "  🕊 سیستان: +5 خرد، قابلیت احیای سیمرغ\n"
                "  🌊 سمنگان: +10 سلامتی، تمرین مؤثرتر\n"
                "  🔥 دیوان: +8 قدرت، -5 احترام در پیروزی\n"
                "• با افزایش سطح، پهلوانان بیشتر باز می‌شوند"
            )
        elif section == "battle":
            text = (
                "⚔️ *نبردها*\n\n"
                "📍 *در ربات (خصوصی):*\n"
                "• دکمه «⚔️ نبرد» → انتخاب حریف → حمله\n"
                "• برنده: +15 درفش، +10~20 احترام\n"
                "• بازنده: -5 سلامتی\n\n"
                "📍 *در گروه‌ها:*\n"
                "• روی پیام حریف ریپلای کن\n"
                "• بنویس: «حمله رستم» یا «حمله <نام پهلوان>»\n"
                "• یا دستور: /attack <نام پهلوان>\n"
                "• به حریف پیام خصوصی ارسال می‌شود\n"
                "• حریف می‌تواند دفاع یا انتقام بگیرد"
            )
        elif section == "shop":
            text = (
                "🏺 *بازار قهوه‌خانه*\n\n"
                "🍵 چای پهلوانی: +10 قدرت (500 درفش)\n"
                "🪶 پر سیمرغ: +40 سلامتی (700 درفش)\n"
                "⚔️ گرز رستم: +30 قدرت (5000 درفش، سطح 20+)\n"
                "🩹 کمک‌های اولیه: +50 سلامت یک پهلوان (100 درفش)\n\n"
                "• همه آیتم‌ها 2 ساعت کولدان دارند\n"
                "• گرز رستم فقط برای رستم و سطح 20+"
            )
        elif section == "mine":
            text = (
                "⛏ *معدن و مأموریت*\n\n"
                "🏕 *مأموریت روزانه:*\n"
                "• هر ۲۴ ساعت یک مأموریت تصادفی\n"
                "• موفقیت: +15 احترام، +30 درفش\n"
                "• احتمال موفقیت: ۶۰٪\n\n"
                "⛏ *معدن:*\n"
                "• سطح ۱: ۱۰۰ درفش/ساعت\n"
                "• سطح ۲: ۲۰۰ درفش/ساعت\n"
                "• هر ساعت یک‌بار برداشت کن\n"
                "• ارتقا معدن تولید را دو برابر می‌کند"
            )
        elif section == "assets":
            text = (
                "💼 *دارایی و سطح*\n\n"
                "• نمایش آیدی، سطح، احترام، درفش\n"
                "• فهرست پهلوانان و سلامت هرکدام\n"
                "• پهلوانان با سلامتی صفر بعد از ۲۴ ساعت احیا می‌شوند\n\n"
                "📊 *سطح و احترام:*\n"
                "• هر ۱۰۰ احترام = +1 سطح\n"
                "• احترام از نبردها، تمرین و مأموریت به دست می‌آید\n"
                "• سطح بیشتر = دسترسی به پهلوانان و قابلیت‌های بیشتر"
            )
        else:
            text = "بخش راهنما یافت نشد."
        
        # دکمه بازگشت به منوی راهنما
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به راهنما", callback_data="help:main")]])
        
        if section == "main":
            # نمایش منوی اصلی راهنما
            buttons = [
                [InlineKeyboardButton("🎯 شروع بازی", callback_data="help:start")],
                [InlineKeyboardButton("🏹 پهلوانان", callback_data="help:heroes")],
                [InlineKeyboardButton("⚔️ نبردها", callback_data="help:battle")],
                [InlineKeyboardButton("🏺 بازار", callback_data="help:shop")],
                [InlineKeyboardButton("⛏ معدن و مأموریت", callback_data="help:mine")],
                [InlineKeyboardButton("💼 دارایی و سطح", callback_data="help:assets")],
            ]
            await query.edit_message_text(
                "📖 *راهنمای جنگ پهلوانان*\n\n"
                "یک بخش را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(text, reply_markup=back_button, parse_mode=ParseMode.MARKDOWN)

    async def _demons_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # فهرست دیوان برای انتخاب پیش‌فرض با ReplyKeyboard
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        # نمایش دیوان با ReplyKeyboard
        lvl = int(me["level"] or 1)
        rows: List[List[str]] = []
        for d in DEMONS_CATALOG:
            req = int(d.get("required_level", 1))
            if lvl >= req:
                rows.append([d["name"]])
            else:
                # فقط نام دیو + قفل + سطح (بدون ایموجی اضافی)
                demon_name = d["name"]
                rows.append([f"🔒 {demon_name} (سطح {req})"])
        rows.append(["🔙 بازگشت"])
        await update.effective_chat.send_message(
            "👹 دیو پیش‌فرض خود را برگزین:\n\n"
            "با انتخاب یک دیو، می‌توانی در نبردها از آن استفاده کنی حتی اگر سلامت پهلوانت صفر باشد.",
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)
        )




    async def _about_hero(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # توضیح کوتاه درباره شاهنامه و قهرمان انتخابی
        user = update.effective_user
        if not user:
            return
        me = self.db.get_user(user.id)
        if not me or not me["hero"]:
            await update.effective_chat.send_message("نخست باید پهلوان خود را برگزینی.")
            return
        hero = me["hero"]
        text = (
            "📜 شاهنامه، کتاب سترگ حکیم ابوالقاسم فردوسی، داستان دلاوری و خرد است.\n"
            f"تو پهلوان *{hero}* را برگزیده‌ای؛ راه تو راه شکوه و نام جاودان است."
        )
        await update.effective_chat.send_message(text, parse_mode=ParseMode.MARKDOWN)

    async def group_fight(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # دستور /fight @username در گروه‌ها
        if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
            await update.effective_chat.send_message("این فرمان ویژه‌ی گروه‌هاست.")
            return
        args = context.args or []
        if not args or not args[0].startswith("@"):
            await update.effective_chat.send_message("کاربرد: /fight @username")
            return
        target_username = args[0][1:]
        # یافتن هر دو کاربر در دیتابیس
        attacker_user = update.effective_user
        if not attacker_user:
            return
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = ?", (attacker_user.id,))
            attacker = cur.fetchone()
            cur.execute("SELECT * FROM users WHERE username = ?", (target_username,))
            defender = cur.fetchone()
        finally:
            conn.close()
        # اعتبارسنجی‌ها
        if not attacker or not attacker["hero"]:
            await update.effective_chat.send_message("نخست باید در ربات عضو شوی و پهلوان برگزینی.")
            return
        if not defender or not defender["hero"]:
            await update.effective_chat.send_message("حریفِ یادشده هنوز در ربات عضو نشده یا پهلوانی برگرفته نیست.")
            return
        # نبرد و نتیجه
        winner_id, loser_id, narrative = self.engine.decide_winner(attacker, defender)
        self.db.apply_battle_result(winner_id, loser_id)
        result = (
            f"پهلوان مهاجم: {(attacker['hero'] or '—')} | پهلوان مدافع: {(defender['hero'] or '—')}\n\n"
            f"{narrative}\n\n"
            f"🏅 برنده: {self._format_user_display(attacker if winner_id==attacker['user_id'] else defender)}\n"
            f"📉 بازنده: 5❤️ سلامتی کاسته شد"
        )
        # ثبت آخرین نبرد برای امکان انتقام
        self.last_battle[update.effective_chat.id] = (winner_id, loser_id)
        await update.effective_chat.send_message(result, parse_mode=ParseMode.MARKDOWN)

    async def ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # تست اتصال در هر چت (گروه/خصوصی)
        chat = update.effective_chat
        title = chat.title if getattr(chat, 'title', None) else (update.effective_user.full_name if update.effective_user else "")
        await update.effective_message.reply_text(
            f"✅ بات آنلاین است\n🏷 چت: {title}\n🆔 chat_id: {chat.id}\n👥 نوع: {chat.type}"
        )

    async def chatid(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # نمایش chat_id برای پیکربندی‌ها
        chat = update.effective_chat
        await update.effective_message.reply_text(f"chat_id: {chat.id} | type: {chat.type}")

    async def group_reply_attack(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # حمله در گروه با ریپلای: متن به شکل "حمله <نام پهلوان>"
        chat = update.effective_chat
        if not chat or chat.type not in ("group", "supergroup"):
            return
        msg = update.effective_message
        if not msg or not msg.reply_to_message:
            return
        text = (msg.text or "").strip()
        if not text.startswith("حمله"):
            return
        logger.info(f"group_reply_attack: text={text}")
        # استخراج بخش پس از کلمه «حمله» و نرمال‌سازی فاصله‌ها/ایموجی‌ها
        after = self._normalize(text[len("حمله"):])
        selected_hero = self.hero_alias_map.get(self._normalize(after)) if after else None
        selected_demon = self.demon_alias_map.get(self._normalize(after)) if after else None
        
        if not selected_hero and not selected_demon:
            hero_samples = "، ".join([h for h in HEROES.keys()])
            demon_samples = "، ".join([d["name"] for d in DEMONS_CATALOG])
            await msg.reply_text(f"نام پهلوان یا دیو درست نیست. نمونه: حمله رستم یا حمله ❄️ دیو سفید\nپهلوانان: {hero_samples}\nدیوان: {demon_samples}")
            return
        
        # تعیین نوع حمله (پهلوان یا دیو)
        is_demon_attack = selected_demon is not None
        selected_name = selected_demon if is_demon_attack else selected_hero
        attacker_user = update.effective_user
        defender_user = msg.reply_to_message.from_user
        if not attacker_user or not defender_user:
            return
        # اعتبار عضویت هر دو در بازی
        attacker = self.db.get_user(attacker_user.id)
        defender = self.db.get_user(defender_user.id)
        if not attacker or not attacker["hero"]:
            await msg.reply_text("نخست باید در ربات عضو شوی و پهلوان برگزینی.")
            return
        if not defender or not defender["hero"]:
            await msg.reply_text("طرف مقابل هنوز پهلوانی برنگزیده است.")
            return
        # جلوگیری از حمله با پهلوان اگر سلامت پهلوانِ مهاجم صفر باشد
        # اما اگر با دیو حمله می‌کند، مشکلی نیست
        if not is_demon_attack:
            cur_hp = self.db.get_current_hero_health(attacker_user.id)
            if cur_hp is not None and int(cur_hp) <= 0:
                await msg.reply_text("❌ پهلوان انتخاب پیش‌فرض تو نیست یا سلامت آن صفر است.")
                return
        # فقط با پهلوان/دیو پیش‌فرض مهاجم اجازه حمله است
        if is_demon_attack:
            # بررسی دیو پیش‌فرض
            if attacker["default_demon"] != selected_name:
                await msg.reply_text("این دیو انتخاب پیش‌فرض شما نیست.")
                return
            # استفاده از دیو به عنوان مهاجم
            demon_stats = next((d for d in DEMONS_CATALOG if d["name"] == selected_name), None)
            if not demon_stats:
                await msg.reply_text("دیو یافت نشد.")
                return
            temp_attacker = dict(attacker)
            temp_attacker["hero"] = selected_name  # استفاده از نام دیو به عنوان hero برای سازگاری با سیستم موجود
            temp_attacker["power"] = demon_stats.get("power", 0)
            temp_attacker["wisdom"] = demon_stats.get("wisdom", 0)
            temp_attacker["race"] = "🔥 دیوان"
        else:
            # بررسی اینکه پهلوان انتخابی باز شده باشد (سطح کافی)
            lvl = int(row_get(attacker, "level", 1))
            stats = HEROES.get(selected_name)
            if not stats:
                await msg.reply_text("پهلوان یافت نشد.")
                return
            
            req = int(stats.get("required_level", 1))
            if lvl < req:
                await msg.reply_text(f"🔒 سطح شما برای استفاده از {selected_name} کافی نیست (نیاز به سطح {req}).")
                return
            # بررسی سلامت پهلوان انتخابی
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (attacker_user.id, selected_name))
                hrow = cur.fetchone()
                hero_hp = int(hrow[0]) if hrow and hrow[0] is not None else None
            finally:
                conn.close()
            if hero_hp is not None and hero_hp <= 0:
                await msg.reply_text(f"❌ سلامت {selected_name} صفر است؛ ابتدا احیا کن.")
                return
            # بررسی اینکه پهلوان انتخابی پیش‌فرض باشد
            if attacker["hero"] != selected_name:
                await msg.reply_text(f"❌ {selected_name} پهلوان انتخاب پیش‌فرض تو نیست.")
                return
            # ساخت مهاجم موقت با آمار پهلوان انتخابی
            temp_attacker = dict(attacker)
            temp_stats = HEROES.get(selected_name, {"power": 0, "wisdom": 0})
            race = temp_stats.get("race")
            rfx = RACES.get(race or "", {})
            temp_attacker["hero"] = selected_name
            base_power = int(temp_stats.get("power", 0)) + int(rfx.get("power_bonus", 0))
            # اضافه کردن قدرت آیتم‌های فعال
            temp_attacker["power"] = self._get_power_with_items(attacker_user.id, base_power, selected_name)
            temp_attacker["wisdom"] = int(temp_stats.get("wisdom", 0)) + int(rfx.get("wisdom_bonus", 0))
            temp_attacker["race"] = race
        # ذخیره وضعیت قبل از نبرد
        old_attacker_honor = attacker['honor'] or 0
        old_attacker_drafsh = attacker['drafsh'] or 0
        old_defender_honor = defender['honor'] or 0
        old_defender_drafsh = defender['drafsh'] or 0
        
        # دریافت سلامت واقعی پهلوانان قبل از نبرد
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            # سلامت پهلوان مهاجم قبل از نبرد
            cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (attacker_user.id, selected_name))
            ah_row = cur.fetchone()
            if ah_row and ah_row[0] is not None:
                old_attacker_health = int(ah_row[0])
            else:
                # اگر رکورد نداشت، ایجاد کن با سلامت پایه
                race = HEROES.get(selected_name, {}).get('race', '')
                base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                cur.execute("INSERT OR REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)", 
                           (attacker_user.id, selected_name, base_health))
                conn.commit()
                old_attacker_health = base_health
            
            # سلامت پهلوان/دیو مدافع قبل از نبرد
            # اگر حمله با دیو بود، سلامت دیو مدافع رو بگیر
            defender_char = defender["default_demon"] if is_demon_attack else defender['hero']
            
            # برای دیوان، سلامت ثابت از کاتالوگ
            if is_demon_attack and defender_char:
                demon_stats = next((d for d in DEMONS_CATALOG if d["name"] == defender_char), None)
                old_defender_health = demon_stats.get("health", 100) if demon_stats else 100
            else:
                cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (defender_user.id, defender_char))
                dh_row = cur.fetchone()
                if dh_row and dh_row[0] is not None:
                    old_defender_health = int(dh_row[0])
                else:
                    # اگر رکورد نداشت، ایجاد کن با سلامت پایه
                    race = HEROES.get(defender_char, {}).get('race', '')
                    base_health = 100 + int(RACES.get(race, {}).get('health_bonus', 0))
                    cur.execute("INSERT OR REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)", 
                               (defender_user.id, defender_char, base_health))
                    conn.commit()
                    old_defender_health = base_health
        finally:
            conn.close()
        
        # استفاده از جدول matchup برای محاسبه دقیق
        attacker_hero_name = selected_name
        # اگر مهاجم با دیو حمله کرد، مدافع هم باید دیو پیش‌فرضش باشه
        if is_demon_attack:
            defender_hero_name = defender["default_demon"] or defender["hero"]
        else:
            defender_hero_name = defender["hero"]
        
        # دریافت آمار matchup
        matchup = get_matchup_stats(attacker_hero_name, defender_hero_name)
        
        # تصمیم‌گیری برنده بر اساس احتمال matchup
        win_chance = matchup["win_chance"]
        attacker_wins = random.random() < win_chance
        
        # محاسبه دمیج و پاداش‌ها
        damage_to_defender = 0
        damage_to_attacker = 0
        honor_gain = 0
        drafsh_gain = 0
        honor_loss = 0
        
        if attacker_wins:
            # مهاجم برنده شد
            damage_to_defender = random.randint(*matchup["damage"])
            drafsh_gain = random.randint(*matchup["drafsh"])
            honor_gain = random.randint(*matchup["honor"])
            honor_loss = honor_gain  # بازنده همون مقدار از دست میده
            drafsh_loss = drafsh_gain  # بازنده همون مقدار درفش از دست میده
            xp_gain = random.randint(10, 15)  # XP نبرد گروهی
            
            # اعمال تغییرات
            self.db.decrease_health(defender_user.id, damage_to_defender)
            self.db.add_rewards(attacker_user.id, honor=honor_gain, drafsh=drafsh_gain, xp=xp_gain)
            
            # کم کردن افتخار و درفش بازنده
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET honor = MAX(0, COALESCE(honor,0) - ?), drafsh = MAX(0, COALESCE(drafsh,0) - ?) WHERE user_id = ?", (honor_loss, drafsh_loss, defender_user.id))
                conn.commit()
            finally:
                conn.close()
        else:
            # مهاجم باخت - فقط سلامتش کم میشه
            damage_to_attacker = random.randint(*matchup["loss_damage"])
            self.db.decrease_health(attacker_user.id, damage_to_attacker)
        
        # واکشی وضعیت جدید
        new_attacker = self.db.get_user(attacker_user.id)
        new_defender = self.db.get_user(defender_user.id)
        
        # دریافت سلامت واقعی پهلوانان/دیوان بعد از نبرد
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            # سلامت مهاجم (پهلوان یا دیو)
            if is_demon_attack:
                # برای دیو، سلامت ثابت از کاتالوگ
                demon_stats = next((d for d in DEMONS_CATALOG if d["name"] == selected_name), None)
                attacker_hero_health = demon_stats.get("health", 100) if demon_stats else 100
            else:
                cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (attacker_user.id, selected_name))
                ah_row = cur.fetchone()
                attacker_hero_health = int(ah_row[0]) if ah_row and ah_row[0] is not None else 100
            
            # سلامت مدافع (پهلوان یا دیو)
            defender_char = defender["default_demon"] if is_demon_attack else defender['hero']
            if is_demon_attack and defender_char:
                # برای دیو، سلامت ثابت از کاتالوگ
                demon_stats = next((d for d in DEMONS_CATALOG if d["name"] == defender_char), None)
                defender_hero_health = demon_stats.get("health", 100) if demon_stats else 100
            else:
                cur.execute("SELECT health FROM user_heroes WHERE user_id = ? AND hero = ?", (defender_user.id, defender_char))
                dh_row = cur.fetchone()
                defender_hero_health = int(dh_row[0]) if dh_row and dh_row[0] is not None else 100
        finally:
            conn.close()
        
        # محاسبه تغییرات واقعی
        attacker_honor_change = (new_attacker['honor'] or 0) - old_attacker_honor
        attacker_drafsh_change = (new_attacker['drafsh'] or 0) - old_attacker_drafsh
        defender_honor_change = (new_defender['honor'] or 0) - old_defender_honor
        defender_drafsh_change = (new_defender['drafsh'] or 0) - old_defender_drafsh
        
        target_name = defender['full_name'] or (defender['username'] or 'کاربر')
        attacker_name = attacker['full_name'] or (attacker['username'] or 'کاربر')
        atk_quote = get_hero_quote(selected_name, "attack_quotes") if not is_demon_attack else None
        attacker_type = "دیو" if is_demon_attack else "پهلوان"
        defender_type = "دیو" if is_demon_attack else "پهلوان"
        
        # پیام شیک و مرتب
        res = f"{(atk_quote + '\n\n') if atk_quote else ''}"
        res += f"⚔️ {attacker_type} مهاجم: {selected_name}\n"
        res += f"🛡 {defender_type} مدافع: {defender_hero_name}\n\n"
        res += f"👤 {attacker_name} (ID: {attacker_user.id})\n"
        res += f"⚡️ به {target_name} (ID: {defender_user.id}) یورش برد!\n\n"
        
        # نمایش نتیجه
        if attacker_wins:
            res += f"✅ پیروزی!\n"
            res += f"💥 دمیج وارد شده: {damage_to_defender}\n"
            res += f"❤️ سلامت مهاجم: {attacker_hero_health}\n"
            res += f"❤️ سلامت مدافع: {defender_hero_health}\n\n"
        else:
            res += f"❌ شکست!\n"
            res += f"⚡️ ضدحمله: {damage_to_attacker}\n"
            res += f"❤️ سلامت مهاجم: {attacker_hero_health}\n"
            res += f"❤️ سلامت مدافع: {defender_hero_health}\n\n"
        
        # تغییرات تفصیلی
        res += "📊 تغییرات مهاجم:\n"
        if attacker_honor_change != 0:
            res += f"   🌟 افتخار: {new_attacker['honor'] or 0} ({attacker_honor_change:+d})\n"
        if attacker_drafsh_change != 0:
            res += f"   🏴 درفش: {new_attacker['drafsh'] or 0} ({attacker_drafsh_change:+d})\n"
        
        if defender_honor_change != 0 or defender_drafsh_change != 0:
            res += "\n📊 تغییرات مدافع:\n"
            if defender_honor_change != 0:
                res += f"   🌟 افتخار: {new_defender['honor'] or 0} ({defender_honor_change:+d})\n"
            if defender_drafsh_change != 0:
                res += f"   🏴 درفش: {new_defender['drafsh'] or 0} ({defender_drafsh_change:+d})\n"

        # ثبت نبرد برای انتقام (فقط برای PM به مدافع)
        self.last_battle[chat.id] = (attacker_user.id, defender_user.id)
        await msg.reply_text(res)
        # اطلاع خصوصی به مدافع با دکمه دفاع/انتقام
        try:
            # متن اختصاصی اطلاع به مدافع با یک بیت (بدون تکرار)
            one_quote = get_hero_quote(selected_name, "attack_quotes")
            # نمایش دمیج بر اساس نتیجه
            damage_text = f"💥 دمیج: {damage_to_defender}" if attacker_wins else f"⚡️ ضدحمله: {damage_to_attacker}"
            result_text = "✅ حریف پیروز شد!" if attacker_wins else "❌ حریف شکست خورد!"
            
            pm_text = (
                (one_quote + "\n\n" if one_quote else "") +
                f"⚠️ به تو حمله شد!\n\n" +
                f"⚔️ {attacker_type} مهاجم: {selected_name}\n" +
                f"�  {defender_type} مدافع: {defender_hero_name}\n\n" +
                f"👤 {attacker_name} (ID: {attacker_user.id})\n" +
                f"⚡️ به تو یورش برد!\n\n" +
                f"{result_text}\n" +
                f"{damage_text}\n" +
                f"❤️ سلامت تو: {defender_hero_health}\n\n" +
                "برای انتقام آماده‌ای؟"
            )
            await context.bot.send_message(
                chat_id=defender_user.id,
                text=pm_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛡 دفاع", callback_data="defend_ready"), InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{attacker_user.id}")]
                ]),
            )
        except Exception:
            pass

    async def group_attack_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # دستور جایگزین برای گروه‌ها: /attack <نام پهلوان> (روی ریپلای به پیام هدف)
        chat = update.effective_chat
        if not chat or chat.type not in ("group", "supergroup"):
            return
        msg = update.effective_message
        if not msg:
            return
        if not msg.reply_to_message:
            await msg.reply_text("برای حمله، ابتدا روی پیام حریف ریپلای کن و سپس بنویس: /attack رستم")
            return
        args_text = " ".join(context.args or []).strip()
        if not args_text:
            await msg.reply_text("نام پهلوان را مشخص کن. نمونه: /attack رستم")
            return
        # تلاش تطبیق نام پهلوان یا دیو
        selected_hero = self.hero_alias_map.get(self._normalize(args_text))
        selected_demon = self.demon_alias_map.get(self._normalize(args_text))
        
        if not selected_hero and not selected_demon:
            hero_samples = "، ".join([h for h in HEROES.keys()])
            demon_samples = "، ".join([d["name"] for d in DEMONS_CATALOG])
            await msg.reply_text(f"نام پهلوان یا دیو درست نیست. نمونه: /attack رستم یا /attack ❄️ دیو سفید\nپهلوانان: {hero_samples}\nدیوان: {demon_samples}")
            return
        
        selected_name = selected_demon if selected_demon else selected_hero
        # تفویض به منطق اصلی ریپلای-حمله با ساخت متن مصنوعی
        msg.text = f"حمله {selected_name}"
        await self.group_reply_attack(update, context)

    async def revenge_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()
        chat = query.message.chat if query.message else None
        if not chat:
            return
        last = self.last_battle.get(chat.id)
        if not last:
            await query.edit_message_text("نبردی برای انتقام در یاد نیست.")
            return
        attacker_id, defender_id = last[1], last[0]  # جابجایی برای انتقام
        attacker = self.db.get_user(attacker_id)
        defender = self.db.get_user(defender_id)
        if not attacker or not defender or not attacker["hero"] or not defender["hero"]:
            await query.edit_message_text("شرایط انتقام مهیا نیست.")
            return
        winner_id, loser_id, narrative = self.engine.decide_winner(attacker, defender)
        self.db.apply_battle_result(winner_id, loser_id)
        verse = random.choice([
            "یکی داستانست پر آبِ چشم\nدل نازک از رستم آید به خشم",
            "به یزدان که گر ما خرد داشتیم\nکجا این سرانجام بد داشتیم",
        ])
        result = f"{verse}\n\n{narrative}"
        # پاک‌کردن انتقام پس از اجرا
        try:
            del self.last_battle[chat.id]
        except Exception:
            pass
        await query.edit_message_text(result)

    async def revenge_pm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # انتقام در پیام خصوصی: ابتدا گزینهٔ انتخاب پهلوان
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("revenge_pm:"):
            return
        try:
            target_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        buttons = [
            [InlineKeyboardButton("⚡️ انتقام با پهلوان پیش‌فرض", callback_data=f"revenge_go:{target_id}")],
            [InlineKeyboardButton("📝 تغییر پهلوان و سپس انتقام", callback_data=f"revenge_choose:{target_id}")],
        ]
        await query.edit_message_text("یکی از گزینه‌ها را برگزین:", reply_markup=InlineKeyboardMarkup(buttons))

    async def revenge_go_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("revenge_go:"):
            return
        try:
            target_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        attacker_id = query.from_user.id
        attacker = self.db.get_user(attacker_id)
        defender = self.db.get_user(target_id)
        if not attacker or not defender or not attacker["hero"] or not defender["hero"]:
            await query.edit_message_text("شرایط انتقام مهیا نیست.")
            return
        
        # چک سلامت پهلوان مهاجم
        cur_hp = self.db.get_current_hero_health(attacker_id)
        if cur_hp is not None and int(cur_hp) <= 0:
            await query.edit_message_text("❌ سلامت پهلوان تو صفر است؛ نخست احیا کن سپس انتقام بگیر.")
            return
        
        # ذخیره وضعیت قبل از نبرد
        old_attacker_honor = attacker['honor'] or 0
        old_attacker_drafsh = attacker['drafsh'] or 0
        old_defender_honor = defender['honor'] or 0
        old_defender_drafsh = defender['drafsh'] or 0
        
        # استفاده از سیستم matchup
        attacker_hero_name = attacker["hero"]
        defender_hero_name = defender["hero"]
        matchup = get_matchup_stats(attacker_hero_name, defender_hero_name)
        
        # تصمیم‌گیری برنده
        win_chance = matchup["win_chance"]
        attacker_wins = random.random() < win_chance
        
        # محاسبه دمیج و پاداش‌ها
        if attacker_wins:
            damage = random.randint(*matchup["damage"])
            drafsh_gain = random.randint(*matchup["drafsh"])
            honor_gain = random.randint(*matchup["honor"])
            xp_gain = random.randint(10, 15)  # XP انتقام
            
            # اعمال تغییرات
            self.db.decrease_health(target_id, damage)
            self.db.add_rewards(attacker_id, honor=honor_gain, drafsh=drafsh_gain, xp=xp_gain)
            
            # کم کردن افتخار و درفش بازنده
            conn = self.db._connect()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE users SET honor = MAX(0, COALESCE(honor,0) - ?), drafsh = MAX(0, COALESCE(drafsh,0) - ?) WHERE user_id = ?", (honor_gain, drafsh_gain, target_id))
                conn.commit()
            finally:
                conn.close()
        else:
            damage = random.randint(*matchup["loss_damage"])
            self.db.decrease_health(attacker_id, damage)
        
        # واکشی وضعیت جدید
        new_attacker = self.db.get_user(attacker_id)
        new_defender = self.db.get_user(target_id)
        
        # محاسبه تغییرات
        attacker_honor_change = (new_attacker['honor'] or 0) - old_attacker_honor
        attacker_drafsh_change = (new_attacker['drafsh'] or 0) - old_attacker_drafsh
        defender_honor_change = (new_defender['honor'] or 0) - old_defender_honor
        defender_drafsh_change = (new_defender['drafsh'] or 0) - old_defender_drafsh
        
        revenge_quote = get_hero_quote(attacker["hero"], "revenge_quotes")
        
        msg = "⚡️ انتقام!\n\n"
        if revenge_quote:
            msg += f"{revenge_quote}\n\n"
        msg += f"⚔️ پهلوان مهاجم: {attacker['hero']}\n"
        msg += f"🛡 پهلوان مدافع: {defender['hero']}\n\n"
        
        if attacker_wins:
            msg += f"✅ پیروزی!\n"
        else:
            msg += f"❌ شکست!\n"
        
        msg += f"💥 دمیج: {damage}\n\n"
        
        msg += f"📊 تغییرات شما:\n"
        msg += f"   ❤️ سلامت: {new_attacker['health'] or 0}\n"
        if attacker_honor_change != 0:
            msg += f"   🌟 افتخار: {new_attacker['honor'] or 0} ({attacker_honor_change:+d})\n"
        if attacker_drafsh_change != 0:
            msg += f"   🏴 درفش: {new_attacker['drafsh'] or 0} ({attacker_drafsh_change:+d})\n"
        
        msg += f"\n📊 تغییرات حریف:\n"
        msg += f"   ❤️ سلامت: {new_defender['health'] or 0}\n"
        if defender_honor_change != 0:
            msg += f"   🌟 افتخار: {new_defender['honor'] or 0} ({defender_honor_change:+d})\n"
        if defender_drafsh_change != 0:
            msg += f"   🏴 درفش: {new_defender['drafsh'] or 0} ({defender_drafsh_change:+d})\n"
        
        await query.edit_message_text(msg)
        
        # ارسال پیام انتقام متقابل به مدافع
        try:
            rev_for_target = get_hero_quote(attacker["hero"], "revenge_quotes")
            result_text = "✅ حریف پیروز شد!" if attacker_wins else "❌ حریف شکست خورد!"
            attacker_name = attacker["full_name"] or (attacker["username"] or "کاربر")
            defender_name = defender["full_name"] or (defender["username"] or "کاربر")
            
            pm_text = "⚠️ بر تو انتقام گرفته شد!\n\n"
            if rev_for_target:
                pm_text += f"{rev_for_target}\n\n"
            
            pm_text += f"🗡 مهاجم: {attacker['hero']} ({attacker_name})\n"
            pm_text += f"🛡 مدافع: {defender['hero']} ({defender_name})\n\n"
            pm_text += f"{result_text}\n"
            pm_text += f"💥 دمیج: {damage}\n\n"
            pm_text += f"📊 تغییرات تو:\n"
            pm_text += f"   ❤️ سلامت: {new_defender['health'] or 0}\n"
            if defender_honor_change != 0:
                pm_text += f"   🌟 افتخار: {new_defender['honor'] or 0} ({defender_honor_change:+d})\n"
            if defender_drafsh_change != 0:
                pm_text += f"   🏴 درفش: {new_defender['drafsh'] or 0} ({defender_drafsh_change:+d})\n"
            pm_text += f"\nبرای انتقام آماده‌ای؟"
            
            await context.bot.send_message(
                chat_id=target_id,
                text=pm_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{attacker_id}")]]),
            )
        except Exception:
            pass

    async def revenge_choose_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("revenge_choose:"):
            return
        try:
            target_id = int(query.data.split(":", 1)[1])
        except Exception:
            return
        user_id = query.from_user.id
        lvl = self.db.get_level(user_id)
        rows: List[List[InlineKeyboardButton]] = []
        for name, stats in HEROES.items():
            req = int(stats.get("required_level", 1))
            race = stats.get("race") or "—"
            power = stats.get("power", 0)
            wisdom = stats.get("wisdom", 0)
            base = f"{name} — {race} | 💪{power} | 🧠{wisdom}"
            label = base if lvl >= req else f"{base} 🔒 (lvl {req})"
            rows.append([InlineKeyboardButton(label, callback_data=f"revenge_select:{target_id}:{name}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"revenge_pm:{target_id}")])
        await query.edit_message_text("کدام پهلوان را برای انتقام برمی‌گزینی؟", reply_markup=InlineKeyboardMarkup(rows))

    async def revenge_select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        if not query.data.startswith("revenge_select:"):
            return
        try:
            _, target_id_str, hero = query.data.split(":", 2)
            target_id = int(target_id_str)
        except Exception:
            return
        user_id = query.from_user.id
        lvl = self.db.get_level(user_id)
        req = int(HEROES.get(hero, {}).get("required_level", 1))
        if lvl < req:
            await query.edit_message_text("سطح شما برای این پهلوان کافی نیست.")
            return
        # جایگزینی پهلوان پیش‌فرض با انتخاب کاربر و سپس اجرای انتقام
        stats = HEROES.get(hero, {})
        race = stats.get("race")
        rfx = RACES.get(race or "", {})
        power = int(stats.get("power", 0)) + int(rfx.get("power_bonus", 0))
        wisdom = int(stats.get("wisdom", 0)) + int(rfx.get("wisdom_bonus", 0))
        base_health = 100 + int(RACES.get(race or "", {}).get("health_bonus", 0))
        conn = self.db._connect()
        try:
            cur = conn.cursor()
            # حذف پیش‌فرض قبلی از دارایی و ثبت جدید
            cur.execute("SELECT hero FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            old = row[0] if row else None
            if old:
                cur.execute("DELETE FROM user_heroes WHERE user_id = ? AND hero = ?", (user_id, old))
            cur.execute(
                "UPDATE users SET hero = ?, race = COALESCE(?, race), power = ?, wisdom = ?, health = COALESCE(health, ?), honor = COALESCE(honor, 0), drafsh = COALESCE(drafsh, 0) WHERE user_id = ?",
                (hero, race, power, wisdom, base_health, user_id),
            )
            cur.execute(
                "REPLACE INTO user_heroes (user_id, hero, owned, health) VALUES (?, ?, 1, ?)",
                (user_id, hero, base_health),
            )
            conn.commit()
        finally:
            conn.close()
        # اجرای انتقام با پهلوان تازه‌انتخاب‌شده
        attacker = self.db.get_user(user_id)
        defender = self.db.get_user(target_id)
        if not attacker or not defender or not attacker["hero"] or not defender["hero"]:
            await query.edit_message_text("شرایط انتقام مهیا نیست.")
            return
        winner_id, loser_id, narrative = self.engine.decide_winner(attacker, defender)
        self.db.apply_battle_result(winner_id, loser_id)
        atk_power = attacker["power"] or 0
        damage = max(1, int(int(atk_power) * 0.12 + random.randint(0, 7)))
        if winner_id == user_id:
            self.db.decrease_health(target_id, damage)
        else:
            self.db.decrease_health(user_id, max(1, damage // 2))
        # واکشی وضعیت جدید برای نمایش تغییرات
        new_attacker = self.db.get_user(user_id)
        new_defender = self.db.get_user(target_id)
        
        revenge_quote = get_hero_quote(attacker["hero"], "revenge_quotes")
        
        msg = "⚡️ انتقام!\n\n"
        if revenge_quote:
            msg += f"{revenge_quote}\n\n"
        msg += f"⚔️ پهلوان مهاجم: {attacker['hero']}\n"
        msg += f"🛡 پهلوان مدافع: {defender['hero']}\n\n"
        msg += f"💥 دمیج: {damage}\n\n"
        msg += f"📊 شما:\n"
        msg += f"   ❤️ سلامت: {new_attacker['health'] or 0}\n"
        msg += f"   🌟 افتخار: {new_attacker['honor'] or 0}\n\n"
        msg += f"📊 حریف:\n"
        msg += f"   ❤️ سلامت: {new_defender['health'] or 0}\n"
        msg += f"   🌟 افتخار: {new_defender['honor'] or 0}"
        
        await query.edit_message_text(msg)
        try:
            rev_for_target = get_hero_quote(attacker["hero"], "revenge_quotes")
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "⚠️ بر تو انتقام گرفته شد!\n\n" +
                    f"پهلوان مهاجم: {attacker['hero']} | پهلوان مدافع: {defender['hero']}\n\n" +
                    (rev_for_target + "\n\n" if rev_for_target else "") + narrative + f"\n\n💥 دمیج: {damage}"
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡️ انتقام", callback_data=f"revenge_pm:{user_id}")]]),
            )
        except Exception:
            pass

    async def group_heal_hero(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        درمان پهلوان در گروه
        فرمت: سلامت <نام پهلوان> <مقدار>
        مثال: سلامت تهمینه 50
        """
        chat = update.effective_chat
        if not chat or chat.type not in ("group", "supergroup"):
            return
        
        msg = update.effective_message
        if not msg or not msg.text:
            return
        
        user = update.effective_user
        if not user:
            return
        
        text = msg.text.strip()
        if not text.startswith("سلامت"):
            return
        
        # استخراج بخش پس از "سلامت"
        after = text[len("سلامت"):].strip()
        if not after:
            await msg.reply_text("فرمت: سلامت <نام پهلوان> <مقدار>\nمثال: سلامت تهمینه 50")
            return
        
        # تقسیم نام پهلوان و مقدار
        parts = after.split()
        if len(parts) < 2:
            await msg.reply_text("فرمت: سلامت <نام پهلوان> <مقدار>\nمثال: سلامت تهمینه 50")
            return
        
        # آخرین بخش مقدار است
        try:
            heal_amount = int(parts[-1])
        except ValueError:
            await msg.reply_text("❌ مقدار سلامت باید عدد باشد")
            return
        
        # بقیه نام پهلوان است
        hero_name_input = " ".join(parts[:-1])
        selected_hero = self.hero_alias_map.get(self._normalize(hero_name_input))
        
        if not selected_hero:
            hero_samples = "، ".join([h for h in HEROES.keys()])
            await msg.reply_text(f"❌ نام پهلوان درست نیست\nپهلوانان: {hero_samples}")
            return
        
        # بررسی مقدار سلامت
        if heal_amount <= 0:
            await msg.reply_text("❌ مقدار سلامت باید بیشتر از صفر باشد")
            return
        
        if heal_amount > 500:
            await msg.reply_text("❌ حداکثر درمان در یک بار 500 سلامت است")
            return
        
        # درمان پهلوان
        success, message = self.db.heal_hero(user.id, selected_hero, heal_amount)
        
        if success:
            await msg.reply_text(message)
        else:
            await msg.reply_text(message)

    async def _show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """نمایش پنل ادمین با Reply Keyboard"""
        buttons = [
            [KeyboardButton("📦 مدیریت بکاپ")],
            [KeyboardButton("💰 انتقال درفش"), KeyboardButton("⭐ انتقال XP")],
            [KeyboardButton("📈 تنظیم سطح"), KeyboardButton("🚫 مسدود کردن")],
            [KeyboardButton("✅ رفع مسدودیت"), KeyboardButton("👤 اطلاعات کاربر")],
            [KeyboardButton("📢 ارسال پیام به همه")],
            [KeyboardButton("🔙 بازگشت به منو")],
        ]
        
        await update.effective_chat.send_message(
            "🔐 پنل ادمین\n\n"
            "یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        context.user_data['in_admin_panel'] = True

    async def _admin_backup_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی مدیریت بکاپ"""
        backups = self.db.backup_manager.list_backups()
        
        msg = "📦 بکاپ‌های موجود:\n\n"
        for i, backup in enumerate(backups[:10], 1):
            msg += f"{i}. {backup['name']}\n"
            msg += f"   📅 {backup['created']} | 📊 {backup['size_kb']} KB\n\n"
        
        buttons = [
            [KeyboardButton("🔄 بکاپ جدید"), KeyboardButton("📥 دانلود بکاپ")],
            [KeyboardButton("🔙 بازگشت")],
        ]
        
        await update.effective_chat.send_message(
            msg,
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        context.user_data['admin_action'] = 'backup_menu'

    async def _admin_transfer_drafsh_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی انتقال درفش"""
        await update.effective_chat.send_message(
            "💰 انتقال درفش\n\n"
            "آیدی کاربر مقصد را وارد کنید:"
        )
        context.user_data['admin_action'] = 'transfer_drafsh_from'

    async def _admin_transfer_xp_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی انتقال XP"""
        await update.effective_chat.send_message(
            "⭐ انتقال XP\n\n"
            "آیدی کاربر مقصد را وارد کنید:"
        )
        context.user_data['admin_action'] = 'transfer_xp_from'

    async def _admin_set_level_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی تنظیم سطح"""
        await update.effective_chat.send_message(
            "📈 تنظیم سطح\n\n"
            "آیدی کاربر را وارد کنید:"
        )
        context.user_data['admin_action'] = 'set_level_user'

    async def _admin_block_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی مسدود کردن"""
        await update.effective_chat.send_message(
            "🚫 مسدود کردن کاربر\n\n"
            "آیدی کاربر را وارد کنید:"
        )
        context.user_data['admin_action'] = 'block_user'

    async def _admin_unblock_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی رفع مسدودیت"""
        await update.effective_chat.send_message(
            "✅ رفع مسدودیت\n\n"
            "آیدی کاربر را وارد کنید:"
        )
        context.user_data['admin_action'] = 'unblock_user'

    async def _admin_user_info_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """منوی اطلاعات کاربر"""
        await update.effective_chat.send_message(
            "👤 اطلاعات کاربر\n\n"
            "آیدی کاربر را وارد کنید:"
        )
        context.user_data['admin_action'] = 'user_info'

    async def _admin_create_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """ایجاد بکاپ جدید"""
        backup_path = self.db.backup_manager.create_backup("admin_manual")
        if backup_path:
            await update.effective_chat.send_message(f"✅ بکاپ ایجاد شد:\n{backup_path}")
        else:
            await update.effective_chat.send_message("❌ خطا در ایجاد بکاپ")

    async def _admin_download_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دانلود بکاپ به صورت ZIP"""
        backups = self.db.backup_manager.list_backups()
        if not backups:
            await update.effective_chat.send_message("❌ هیچ بکاپی موجود نیست")
            return
        
        try:
            # آخرین بکاپ را انتخاب کن
            latest_backup = backups[0]
            backup_path = latest_backup['path']
            
            # ایجاد ZIP
            zip_path = BackupUtils.create_backup_zip(backup_path)
            
            # ارسال فایل
            with open(zip_path, 'rb') as f:
                await update.effective_chat.send_document(
                    document=f,
                    filename=os.path.basename(zip_path),
                    caption=f"📦 بکاپ: {latest_backup['name']}\n📅 {latest_backup['created']}"
                )
            
            await update.effective_chat.send_message("✅ بکاپ ارسال شد")
        except Exception as e:
            logger.error(f"خطا در دانلود بکاپ: {e}")
            await update.effective_chat.send_message(f"❌ خطا: {e}")


# --------------------------- نقطه شروع برنامه ---------------------------

def build_application() -> "ApplicationBuilder":
    # ساخت Application با توکن
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN در محیط تنظیم نشده است.")
    
    builder = ApplicationBuilder().token(BOT_TOKEN)
    
    # تنظیمات timeout برای اتصال بهتر
    builder = builder.connect_timeout(30.0).read_timeout(30.0).write_timeout(30.0)
    
    # اگر نیاز به پروکسی داری، این خطوط رو uncomment کن:
    # PROXY_URL = "http://127.0.0.1:10809"  # آدرس پروکسی خودت رو بذار
    # builder = builder.proxy_url(PROXY_URL)
    
    app = builder.build()
    return app


def main() -> None:
    # مقداردهی لایه دیتابیس و موتور بازی
    db = Database(DB_PATH)
    engine = GameEngine(db)
    handlers = Handlers(db, engine)

    # ساخت اپلیکیشن
    app = build_application()

    # دستور /start
    app.add_handler(CommandHandler("start", handlers.start))
    # دستور /cancel
    app.add_handler(CommandHandler("cancel", handlers.cancel_command))
    # تست اتصال
    app.add_handler(CommandHandler("ping", handlers.ping))
    app.add_handler(CommandHandler("chatid", handlers.chatid))
    # حالت نامحدود: فقط با کد محرمانه
    app.add_handler(CommandHandler("godmode", handlers.godmode))
    
    # دستورات ادمین (فقط برای ادمین)
    app.add_handler(CommandHandler("admin", handlers.admin_panel_command))
    app.add_handler(CommandHandler("admin_login", handlers.admin_login_command))
    app.add_handler(CallbackQueryHandler(handlers.admin_panel_callback, pattern=r"^admin_"))

    # کال‌بک تایید عضویت
    app.add_handler(CallbackQueryHandler(handlers.verify_membership, pattern=r"^verify_membership$"))

    # روتر منوی اصلی
    # منوی اصلی فقط در چت خصوصی تا مزاحم دستورات گروهی نشود
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handlers.main_menu_router))

    # کال‌بک‌ها
    app.add_handler(CallbackQueryHandler(handlers.fight_callback, pattern=r"^fight:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.train_callback, pattern=r"^train:(power|wisdom)$"))
    app.add_handler(CallbackQueryHandler(handlers.hero_select_callback, pattern=r"^hero_select:"))
    app.add_handler(CallbackQueryHandler(handlers.revenge_callback, pattern=r"^revenge$"))
    app.add_handler(CallbackQueryHandler(handlers.bot_fight_callback, pattern=r"^bot_fight:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.revenge_pm_callback, pattern=r"^revenge_pm:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.revenge_go_callback, pattern=r"^revenge_go:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.revenge_choose_callback, pattern=r"^revenge_choose:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.revenge_select_callback, pattern=r"^revenge_select:\d+:.+$"))
    # نبرد تعاملی (دکمه‌ای)
    app.add_handler(CallbackQueryHandler(handlers.ib_select_callback, pattern=r"^ib_select:\d+$"))
    app.add_handler(CallbackQueryHandler(handlers.ib_action_callback, pattern=r"^ib_act:attack$"))
    # بازار
    app.add_handler(CallbackQueryHandler(handlers.shop_callback, pattern=r"^shop:(tea|feather|club|firstaid)$"))
    app.add_handler(CallbackQueryHandler(handlers.heal_callback, pattern=r"^heal:.*$"))
    # دفاع آماده
    app.add_handler(CallbackQueryHandler(handlers.defend_ready_callback, pattern=r"^defend_ready$"))
    # معدن
    app.add_handler(CallbackQueryHandler(handlers.mine_callback, pattern=r"^mine:(collect|upgrade)$"))
    # راهنما
    app.add_handler(CallbackQueryHandler(handlers.help_callback, pattern=r"^help:"))
    # رنکینگ
    app.add_handler(CallbackQueryHandler(handlers.rank_callback, pattern=r"^rank:\d+$"))
    # حریف بعدی
    app.add_handler(CallbackQueryHandler(handlers.next_opponent_callback, pattern=r"^next_opponent$"))
    # لغو تبادل
    app.add_handler(CallbackQueryHandler(handlers.cancel_transfer_callback, pattern=r"^cancel_transfer$"))
    # بازگشت به منو
    app.add_handler(CallbackQueryHandler(handlers.back_main_callback, pattern=r"^back_main$"))

    # دستور گروهی /fight @username
    app.add_handler(CommandHandler("fight", handlers.group_fight))
    # دستور جایگزین حمله در گروه: /attack <hero> (روی ریپلای)
    app.add_handler(CommandHandler("attack", handlers.group_attack_command))

    # حمله در گروه‌ها: متن باید با "حمله" شروع شود (خودِ هندلر الزام ریپلای را چک می‌کند)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & filters.Regex(r"^حمله"), handlers.group_reply_attack))

    # درمان پهلوان در گروه: متن باید با "سلامت" شروع شود
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & filters.Regex(r"^سلامت"), handlers.group_heal_hero))

    # اجرای ربات
    logger.info("%s bot is running...", GAME_NAME)
    app.run_polling()


if __name__ == "__main__":
    # اجرای نقطه شروع
    main()


