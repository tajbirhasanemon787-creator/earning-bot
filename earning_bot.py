#!/usr/bin/env python3
import logging,sqlite3,random,string
from datetime import datetime
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,CallbackQueryHandler,MessageHandler,filters,ContextTypes

BOT_TOKEN="8916888298:AAG8L6-NRmaxxkLOX-2aglX7rawzMh1Yx9A"
ADMIN_ID=8078398755
CHANNEL_USERNAME="@Tajbir345"
CHANNEL_LINK="https://t.me/Tajbir345"
DB_FILE="earning_bot.db"

logging.basicConfig(format='%(asctime)s-%(levelname)s-%(message)s',level=logging.INFO)
logger=logging.getLogger(__name__)

def init_db():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,balance REAL DEFAULT 0.0,total_earned REAL DEFAULT 0.0,referred_by INTEGER DEFAULT NULL,referral_count INTEGER DEFAULT 0,join_date TEXT,is_banned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS tasks(task_id INTEGER PRIMARY KEY AUTOINCREMENT,link TEXT NOT NULL,description TEXT,reward REAL NOT NULL,verify_code TEXT DEFAULT NULL,task_type TEXT DEFAULT "normal",is_active INTEGER DEFAULT 1,created_at TEXT);
        CREATE TABLE IF NOT EXISTS completed_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,task_id INTEGER,completed_at TEXT,UNIQUE(user_id,task_id));
        CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount REAL,method TEXT,number TEXT,status TEXT DEFAULT "pending",requested_at TEXT,processed_at TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS screenshot_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,task_id INTEGER,file_id TEXT,status TEXT DEFAULT "pending",submitted_at TEXT,processed_at TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
    ''')
    for k,v in [('referral_bonus','1.0'),('min_withdraw','50.0'),('welcome_msg','টাস্ক করুন আর টাকা আয় করুন!')]:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)",(k,v))
    conn.commit()
    conn.close()

def get_setting(key):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?",(key,))
    row=c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key,value):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",(key,str(value)))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?",(user_id,))
    row=c.fetchone()
    conn.close()
    return row

def create_user(user_id,username,full_name,referred_by=None):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id,username,full_name,referred_by,join_date) VALUES (?,?,?,?,?)",(user_id,username or '',full_name,referred_by,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    is_new=c.rowcount>0
    if is_new and referred_by:
        bonus=float(get_setting('referral_bonus') or 1.0)
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+?,referral_count=referral_count+1 WHERE user_id=?",(bonus,bonus,referred_by))
    conn.commit()
    conn.close()
    return is_new

def get_all_users():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT user_id,username,full_name,balance,total_earned,referral_count,join_date,is_banned FROM users ORDER BY total_earned DESC")
    rows=c.fetchall()
    conn.close()
    return rows

def ban_user(user_id,ban=True):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("UPDATE users SET is_banned=? WHERE user_id=?",(1 if ban else 0,user_id))
    conn.commit()
    conn.close()

def admin_give_balance(user_id,amount):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(amount,amount,user_id))
    conn.commit()
    conn.close()

def get_tasks(user_id=None):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    if user_id:
        c.execute("SELECT * FROM tasks WHERE is_active=1 AND task_id NOT IN (SELECT task_id FROM completed_tasks WHERE user_id=?) ORDER BY task_id DESC",(user_id,))
    else:
        c.execute("SELECT * FROM tasks ORDER BY task_id DESC")
    rows=c.fetchall()
    conn.close()
    return rows

def get_task(task_id):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,))
    row=c.fetchone()
    conn.close()
    return row

def add_task_db(link,description,reward,task_type,verify_code=None):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("INSERT INTO tasks (link,description,reward,verify_code,task_type,created_at) VALUES (?,?,?,?,?,?)",(link,description,reward,verify_code,task_type,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def toggle_task(task_id,active):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("UPDATE tasks SET is_active=? WHERE task_id=?",(active,task_id))
    conn.commit()
    conn.close()

def delete_task_db(task_id):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("DELETE FROM tasks WHERE task_id=?",(task_id,))
    conn.commit()
    conn.close()

def complete_task(user_id,task_id,reward):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    try:
        c.execute("INSERT INTO completed_tasks (user_id,task_id,completed_at) VALUES (?,?,?)",(user_id,task_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(reward,reward,user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def already_completed(user_id,task_id):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT id FROM completed_tasks WHERE user_id=? AND task_id=?",(user_id,task_id))
    row=c.fetchone()
    conn.close()
    return row is not None

def add_screenshot(user_id,task_id,file_id):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("INSERT INTO screenshot_tasks (user_id,task_id,file_id,submitted_at) VALUES (?,?,?,?)",(user_id,task_id,file_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    sid=c.lastrowid
    conn.commit()
    conn.close()
    return sid

def get_pending_screenshots():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT s.id,s.user_id,s.task_id,s.file_id,s.submitted_at,u.full_name,t.description,t.reward FROM screenshot_tasks s JOIN users u ON s.user_id=u.user_id JOIN tasks t ON s.task_id=t.task_id WHERE s.status='pending' ORDER BY s.submitted_at")
    rows=c.fetchall()
    conn.close()
    return rows

def process_screenshot(sid,status,user_id,task_id,reward):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("UPDATE screenshot_tasks SET status=?,processed_at=? WHERE id=?",(status,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),sid))
    if status=='approved':
        try:
            c.execute("INSERT INTO completed_tasks (user_id,task_id,completed_at) VALUES (?,?,?)",(user_id,task_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        except sqlite3.IntegrityError:
            pass
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(reward,reward,user_id))
    conn.commit()
    conn.close()

def add_withdrawal(user_id,amount,method,number):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?",(amount,user_id))
    c.execute("INSERT INTO withdrawals (user_id,amount,method,number,requested_at) VALUES (?,?,?,?,?)",(user_id,amount,method,number,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    wid=c.lastrowid
    conn.commit()
    conn.close()
    return wid

def get_pending_withdrawals():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT w.id,w.user_id,w.amount,w.method,w.number,w.requested_at,u.full_name FROM withdrawals w JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.requested_at")
    rows=c.fetchall()
    conn.close()
    return rows

def process_withdrawal(wid,status):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    if status=='rejected':
        c.execute("SELECT user_id,amount FROM withdrawals WHERE id=?",(wid,))
        row=c.fetchone()
        if row:
            c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(row[1],row[0]))
    c.execute("UPDATE withdrawals SET status=?,processed_at=? WHERE id=?",(status,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),wid))
    conn.commit()
    conn.close()

def get_stats():
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=0"); active=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'"); pend=c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='approved'"); paid=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE is_active=1"); tasks=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM completed_tasks"); done=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM screenshot_tasks WHERE status='pending'"); ss=c.fetchone()[0]
    conn.close()
    return total,active,pend,paid,tasks,done,ss

def gen_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase+string.digits,k=length))

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 টাস্ক করুন",callback_data="tasks"),InlineKeyboardButton("💰 ব্যালেন্স",callback_data="balance")],
        [InlineKeyboardButton("👥 রেফারেল",callback_data="referral"),InlineKeyboardButton("💸 উইথড্র",callback_data="withdraw")],
        [InlineKeyboardButton("📊 প্রোফাইল",callback_data="profile"),InlineKeyboardButton("📞 সাপোর্ট",callback_data="support")]
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 পরিসংখ্যান",callback_data="adm_stats"),InlineKeyboardButton("👥 ইউজার লিস্ট",callback_data="adm_users")],
        [InlineKeyboardButton("➕ টাস্ক যোগ",callback_data="adm_add_task"),InlineKeyboardButton("📋 টাস্ক ম্যানেজ",callback_data="adm_tasks")],
        [InlineKeyboardButton("💸 উইথড্র",callback_data="adm_withdrawals"),InlineKeyboardButton("🖼️ স্ক্রিনশট",callback_data="adm_screenshots")],
        [InlineKeyboardButton("⚙️ সেটিংস",callback_data="adm_settings"),InlineKeyboardButton("📢 ব্রডকাস্ট",callback_data="adm_broadcast")],
        [InlineKeyboardButton("💵 ব্যালেন্স দিন",callback_data="adm_give_balance"),InlineKeyboardButton("🏠 মেইন মেনু",callback_data="main_menu")]
    ])

def back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")]])

def back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 মেইন মেনু",callback_data="main_menu")]])

async def check_member(bot,user_id):
    try:
        m=await bot.get_chat_member(CHANNEL_USERNAME,user_id)
        return m.status in ['member','administrator','creator']
    except Exception:
        return False

async def start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    args=ctx.args
    referred_by=None
    if args and args[0].startswith("ref_"):
        try:
            rid=int(args[0][4:])
            if rid!=user.id: referred_by=rid
        except ValueError: pass
    existing=get_user(user.id)
    if not existing:
        is_new=create_user(user.id,user.username,user.full_name,referred_by)
        if is_new and referred_by:
            bonus=get_setting('referral_bonus')
            try:
                await ctx.bot.send_message(referred_by,f"🎉 *নতুন রেফারেল!*\n\n👤 *{user.full_name}* যোগ দিয়েছে!\n💰 আপনি *{bonus} টাকা* পেয়েছেন!",parse_mode='Markdown')
            except Exception: pass
    is_member=await check_member(ctx.bot,user.id)
    if not is_member:
        await update.message.reply_text(f"👋 স্বাগতম *{user.first_name}*!\n\n⚠️ বট ব্যবহার করতে চ্যানেলে জয়েন করুন।",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 চ্যানেল জয়েন করুন",url=CHANNEL_LINK)],[InlineKeyboardButton("✅ জয়েন করেছি",callback_data="check_join")]]))
        return
    db_user=get_user(user.id)
    if db_user and db_user[8]==1:
        await update.message.reply_text("❌ আপনার অ্যাকাউন্ট ব্যান।")
        return
    await update.message.reply_text(f"🤖 *ইয়ারনিং বট*\n\n👋 হ্যালো *{user.first_name}*!\n_{get_setting('welcome_msg')}_",parse_mode='Markdown',reply_markup=main_kb())

async def admin_cmd(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    await update.message.reply_text("⚙️ *অ্যাডমিন প্যানেল*",parse_mode='Markdown',reply_markup=admin_kb())

async def button(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    user=q.from_user
    data=q.data
    if data=="check_join":
        if await check_member(ctx.bot,user.id):
            if not get_user(user.id): create_user(user.id,user.username,user.full_name)
            await q.edit_message_text("✅ ধন্যবাদ! বটে স্বাগতম!",reply_markup=main_kb())
        else:
            await q.answer("⚠️ এখনও জয়েন করেননি!",show_alert=True)
        return
    db_user=get_user(user.id)
    if not db_user:
        await q.edit_message_text("❌ /start দিন।"); return
    if db_user[8]==1:
        await q.edit_message_text("❌ আপনার অ্যাকাউন্ট ব্যান।"); return

    if data=="main_menu":
        await q.edit_message_text(f"🤖 *ইয়ারনিং বট*\n\n👋 *{user.first_name}*",parse_mode='Markdown',reply_markup=main_kb())
    elif data=="balance":
        bonus=get_setting('referral_bonus')
        await q.edit_message_text(f"💰 *আপনার ব্যালেন্স*\n\n💵 বর্তমান: *{db_user[3]:.2f} টাকা*\n📈 মোট আয়: *{db_user[4]:.2f} টাকা*\n👥 রেফারেল: *{db_user[6]} জন*\n💰 রেফারেল আয়: *{db_user[6]*float(bonus):.2f} টাকা*",parse_mode='Markdown',reply_markup=back_main())
    elif data=="profile":
        me=await ctx.bot.get_me()
        ref_link=f"https://t.me/{me.username}?start=ref_{user.id}"
        await q.edit_message_text(f"📊 *আপনার প্রোফাইল*\n\n👤 নাম: *{db_user[2]}*\n🆔 ID: `{db_user[0]}`\n💰 ব্যালেন্স: *{db_user[3]:.2f} টাকা*\n📈 মোট আয়: *{db_user[4]:.2f} টাকা*\n👥 রেফারেল: *{db_user[6]} জন*\n📅 যোগদান: {db_user[7]}\n\n🔗 *রেফারেল লিংক:*\n`{ref_link}`",parse_mode='Markdown',reply_markup=back_main())
    elif data=="referral":
        me=await ctx.bot.get_me()
        ref_link=f"https://t.me/{me.username}?start=ref_{user.id}"
        bonus=get_setting('referral_bonus')
        await q.edit_message_text(f"👥 *রেফারেল সিস্টেম*\n\n✅ প্রতি রেফারে *{bonus} টাকা* পাবেন!\n\n🔗 *আপনার লিংক:*\n`{ref_link}`\n\n👥 রেফারেল: *{db_user[6]} জন*\n💰 রেফারেল আয়: *{db_user[6]*float(bonus):.2f} টাকা*",parse_mode='Markdown',reply_markup=back_main())
    elif data=="tasks":
        tasks=get_tasks(user.id)
        if not tasks:
            await q.edit_message_text("📋 *টাস্ক*\n\n✅ সব টাস্ক সম্পন্ন!",parse_mode='Markdown',reply_markup=back_main()); return
        kb=[]
        for t in tasks:
            icon="🖼️" if t[5]=='normal' else "🔑"
            kb.append([InlineKeyboardButton(f"{icon} {t[3]}৳ — {t[2][:30]}",callback_data=f"task_{t[0]}")])
        kb.append([InlineKeyboardButton("🔙 মেইন মেনু",callback_data="main_menu")])
        await q.edit_message_text(f"📋 *টাস্ক সমূহ* ({len(tasks)}টি)\n\n🖼️=Screenshot Task\n🔑=Code Task",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("task_"):
        tid=int(data[5:]); t=get_task(tid)
        if t:
            if already_completed(user.id,tid):
                await q.answer("✅ এই টাস্ক আগেই সম্পন্ন!",show_alert=True); return
            if t[5]=='normal':
                ctx.user_data['screenshot_task_id']=tid
                ctx.user_data['screenshot_step']=True
                await q.edit_message_text(f"🖼️ *Screenshot Task #{tid}*\n\n📝 *কাজ:* {t[2]}\n💰 *পুরস্কার:* {t[3]} টাকা\n\n1️⃣ লিংকে যান\n2️⃣ কাজ করুন\n3️⃣ Screenshot তুলুন\n4️⃣ এখানে পাঠান\n5️⃣ Admin approve করলে balance যাবে ✅",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 টাস্ক লিংকে যান",url=t[1])],[InlineKeyboardButton("❌ বাতিল",callback_data="tasks")]]))
            else:
                ctx.user_data['verify_task_id']=tid
                ctx.user_data['verify_step']=True
                await q.edit_message_text(f"🔑 *Code Task #{tid}*\n\n📝 *কাজ:* {t[2]}\n💰 *পুরস্কার:* {t[3]} টাকা\n\n1️⃣ লিংকে যান\n2️⃣ Verify Code খুঁজুন\n3️⃣ Code এখানে পাঠান\n4️⃣ Balance AUTO যোগ হবে! ✅",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 টাস্ক লিংকে যান",url=t[1])],[InlineKeyboardButton("❌ বাতিল",callback_data="tasks")]]))
    elif data=="withdraw":
        min_wd=float(get_setting('min_withdraw'))
        if db_user[3]<min_wd:
            await q.edit_message_text(f"💸 *উইথড্র*\n\n❌ ব্যালেন্স কম!\n💰 বর্তমান: *{db_user[3]:.2f} টাকা*\n⚠️ সর্বনিম্ন: *{min_wd:.0f} টাকা*",parse_mode='Markdown',reply_markup=back_main()); return
        await q.edit_message_text(f"💸 *উইথড্র*\n\n💰 ব্যালেন্স: *{db_user[3]:.2f} টাকা*\n\nমেথড বেছে নিন:",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 বিকাশ",callback_data="wd_bkash"),InlineKeyboardButton("💚 নগদ",callback_data="wd_nagad")],[InlineKeyboardButton("🔙 মেইন মেনু",callback_data="main_menu")]]))
    elif data in ["wd_bkash","wd_nagad"]:
        ctx.user_data['wd_method']="বিকাশ" if data=="wd_bkash" else "নগদ"
        ctx.user_data['wd_step']='number'
        await q.edit_message_text(f"📱 *{ctx.user_data['wd_method']} উইথড্র*\n\nনম্বর লিখুন (01XXXXXXXXX):",parse_mode='Markdown')
    elif data=="support":
        ctx.user_data['support']=True
        await q.edit_message_text("📞 *সাপোর্ট*\n\nসমস্যা লিখুন:",parse_mode='Markdown')
    elif data=="admin_menu":
        if user.id!=ADMIN_ID: return
        await q.edit_message_text("⚙️ *অ্যাডমিন প্যানেল*",parse_mode='Markdown',reply_markup=admin_kb())
    elif data=="adm_stats":
        if user.id!=ADMIN_ID: return
        total,active,pend,paid,tasks,done,ss=get_stats()
        await q.edit_message_text(f"📊 *পরিসংখ্যান*\n\n👥 মোট ইউজার: *{total}*\n✅ সক্রিয়: *{active}*\n📋 সক্রিয় টাস্ক: *{tasks}*\n✔️ টাস্ক সম্পন্ন: *{done}*\n🖼️ পেন্ডিং Screenshot: *{ss}*\n💸 পেন্ডিং উইথড্র: *{pend}*\n💰 মোট পেমেন্ট: *{paid:.2f} টাকা*\n\n⚙️ রেফারেল বোনাস: *{get_setting('referral_bonus')} টাকা*\n⚙️ সর্বনিম্ন উইথড্র: *{get_setting('min_withdraw')} টাকা*",parse_mode='Markdown',reply_markup=back_admin())
    elif data=="adm_screenshots":
        if user.id!=ADMIN_ID: return
        pending=get_pending_screenshots()
        if not pending:
            await q.edit_message_text("🖼️ কোনো পেন্ডিং screenshot নেই।",reply_markup=back_admin()); return
        kb=[[InlineKeyboardButton(f"#{s[0]} | {s[5]} | {s[7]:.0f}৳",callback_data=f"ss_{s[0]}")] for s in pending]
        kb.append([InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")])
        await q.edit_message_text(f"🖼️ *পেন্ডিং Screenshot* ({len(pending)}টি)",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("ss_"):
        if user.id!=ADMIN_ID: return
        sid=int(data[3:])
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute("SELECT s.*,u.full_name,t.description,t.reward FROM screenshot_tasks s JOIN users u ON s.user_id=u.user_id JOIN tasks t ON s.task_id=t.task_id WHERE s.id=?",(sid,))
        s=c.fetchone(); conn.close()
        if s:
            await ctx.bot.send_photo(chat_id=user.id,photo=s[3],caption=f"🖼️ *Screenshot #{sid}*\n\n👤 {s[9]}\n📋 {s[10]}\n💰 *{s[11]:.2f} টাকা*\n📅 {s[4]}",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve",callback_data=f"ssok_{sid}_{s[1]}_{s[2]}_{s[11]}"),InlineKeyboardButton("❌ Reject",callback_data=f"ssno_{sid}_{s[1]}_{s[2]}_{s[11]}")],[InlineKeyboardButton("🔙 পিছে",callback_data="adm_screenshots")]]))
    elif data.startswith("ssok_") or data.startswith("ssno_"):
        if user.id!=ADMIN_ID: return
        parts=data.split("_"); is_ok=data.startswith("ssok_")
        sid=int(parts[1]); uid=int(parts[2]); tid=int(parts[3]); reward=float(parts[4])
        process_screenshot(sid,'approved' if is_ok else 'rejected',uid,tid,reward)
        try:
            if is_ok:
                await ctx.bot.send_message(uid,f"✅ *Screenshot Approved!*\n\n💰 *{reward:.2f} টাকা* balance এ যোগ হয়েছে!\n💵 নতুন balance: *{get_user(uid)[3]:.2f} টাকা*",parse_mode='Markdown')
            else:
                await ctx.bot.send_message(uid,f"❌ *Screenshot Rejected!*\n\nসঠিকভাবে কাজ করে আবার চেষ্টা করুন।",parse_mode='Markdown')
        except Exception: pass
        await q.edit_message_text(f"Screenshot #{sid} {'✅ Approved' if is_ok else '❌ Rejected'}",reply_markup=back_admin())
    elif data=="adm_settings":
        if user.id!=ADMIN_ID: return
        await q.edit_message_text(f"⚙️ *সেটিংস*\n\n💰 রেফারেল বোনাস: *{get_setting('referral_bonus')} টাকা*\n💸 সর্বনিম্ন উইথড্র: *{get_setting('min_withdraw')} টাকা*",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 রেফারেল বোনাস",callback_data="set_ref")],[InlineKeyboardButton("💸 সর্বনিম্ন উইথড্র",callback_data="set_wd")],[InlineKeyboardButton("📝 Welcome মেসেজ",callback_data="set_welcome")],[InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")]]))
    elif data=="set_ref":
        if user.id!=ADMIN_ID: return
        ctx.user_data['admin_step']='set_ref'
        await q.edit_message_text(f"💰 বর্তমান: *{get_setting('referral_bonus')} টাকা*\n\nনতুন পরিমাণ লিখুন:",parse_mode='Markdown')
    elif data=="set_wd":
        if user.id!=ADMIN_ID: return
        ctx.user_data['admin_step']='set_wd'
        await q.edit_message_text(f"💸 বর্তমান: *{get_setting('min_withdraw')} টাকা*\n\nনতুন পরিমাণ লিখুন:",parse_mode='Markdown')
    elif data=="set_welcome":
        if user.id!=ADMIN_ID: return
        ctx.user_data['admin_step']='set_welcome'
        await q.edit_message_text("📝 নতুন welcome মেসেজ লিখুন:")
    elif data=="adm_users":
        if user.id!=ADMIN_ID: return
        users=get_all_users()
        msg=f"👥 *সকল ইউজার* ({len(users)} জন)\n\n"
        for u in users[:15]:
            s="🔴" if u[7]==1 else "🟢"
            msg+=f"{s} `{u[0]}` | {u[2]} | 💰{u[3]:.1f}৳ | 👥{u[5]}\n"
        if len(users)>15: msg+=f"\n...আরও {len(users)-15} জন"
        await q.edit_message_text(msg,parse_mode='Markdown',reply_markup=back_admin())
    elif data=="adm_add_task":
        if user.id!=ADMIN_ID: return
        await q.edit_message_text("➕ *নতুন টাস্ক যোগ*\n\nটাস্কের ধরন বেছে নিন:",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🖼️ Screenshot Task",callback_data="add_normal")],[InlineKeyboardButton("🔑 Code Task",callback_data="add_code")],[InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")]]))
    elif data in ["add_normal","add_code"]:
        if user.id!=ADMIN_ID: return
        ctx.user_data['task_type']='normal' if data=="add_normal" else 'code'
        ctx.user_data['admin_step']='task_link'
        await q.edit_message_text(f"➕ *{'Screenshot' if data=='add_normal' else 'Code'} Task যোগ*\n\nধাপ ১: *লিংক* পাঠান:",parse_mode='Markdown')
    elif data=="adm_tasks":
        if user.id!=ADMIN_ID: return
        tasks=get_tasks()
        if not tasks:
            await q.edit_message_text("📋 কোনো টাস্ক নেই।",reply_markup=back_admin()); return
        kb=[]
        for t in tasks:
            st="✅" if t[6]==1 else "❌"
            icon="🖼️" if t[5]=='normal' else "🔑"
            kb.append([InlineKeyboardButton(f"{st}{icon} #{t[0]} | {t[3]}৳ | {t[2][:20]}",callback_data=f"adm_task_{t[0]}")])
        kb.append([InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")])
        await q.edit_message_text(f"📋 *সকল টাস্ক* ({len(tasks)}টি)",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("adm_task_"):
        if user.id!=ADMIN_ID: return
        tid=int(data[9:]); t=get_task(tid)
        if t:
            conn=sqlite3.connect(DB_FILE); c=conn.cursor()
            c.execute("SELECT COUNT(*) FROM completed_tasks WHERE task_id=?",(tid,)); cnt=c.fetchone()[0]; conn.close()
            st="✅ চালু" if t[6]==1 else "❌ বন্ধ"
            tog_txt="❌ বন্ধ করুন" if t[6]==1 else "✅ চালু করুন"
            tog_cb=f"toff_{tid}" if t[6]==1 else f"ton_{tid}"
            code_info=f"🔑 Code: `{t[4]}`\n" if t[5]=='code' else "🖼️ Screenshot Task\n"
            await q.edit_message_text(f"📋 *টাস্ক #{tid}*\n\n📝 {t[2]}\n💰 *{t[3]} টাকা*\n{code_info}✔️ সম্পন্ন: *{cnt} জন*\n{st}",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tog_txt,callback_data=tog_cb)],[InlineKeyboardButton("🗑️ মুছে ফেলুন",callback_data=f"tdel_{tid}")],[InlineKeyboardButton("🔙 টাস্ক লিস্ট",callback_data="adm_tasks")]]))
    elif data.startswith("toff_") or data.startswith("ton_"):
        if user.id!=ADMIN_ID: return
        is_off=data.startswith("toff_"); tid=int(data.split("_")[1])
        toggle_task(tid,0 if is_off else 1)
        await q.answer(f"টাস্ক {'বন্ধ' if is_off else 'চালু'} হয়েছে!")
        t=get_task(tid)
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM completed_tasks WHERE task_id=?",(tid,)); cnt=c.fetchone()[0]; conn.close()
        st="✅ চালু" if t[6]==1 else "❌ বন্ধ"
        tog_txt="❌ বন্ধ করুন" if t[6]==1 else "✅ চালু করুন"
        tog_cb=f"toff_{tid}" if t[6]==1 else f"ton_{tid}"
        await q.edit_message_text(f"📋 *টাস্ক #{tid}*\n\n📝 {t[2]}\n💰 *{t[3]} টাকা*\n✔️ {cnt} জন\n{st}",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tog_txt,callback_data=tog_cb)],[InlineKeyboardButton("🗑️ মুছে ফেলুন",callback_data=f"tdel_{tid}")],[InlineKeyboardButton("🔙 টাস্ক লিস্ট",callback_data="adm_tasks")]]))
    elif data.startswith("tdel_"):
        if user.id!=ADMIN_ID: return
        tid=int(data[5:]); delete_task_db(tid)
        await q.edit_message_text("🗑️ টাস্ক মুছে ফেলা হয়েছে।",reply_markup=back_admin())
    elif data=="adm_withdrawals":
        if user.id!=ADMIN_ID: return
        pending=get_pending_withdrawals()
        if not pending:
            await q.edit_message_text("💸 পেন্ডিং উইথড্র নেই।",reply_markup=back_admin()); return
        kb=[[InlineKeyboardButton(f"#{w[0]} | {w[6]} | {w[2]:.0f}৳ | {w[3]}",callback_data=f"wdet_{w[0]}")] for w in pending]
        kb.append([InlineKeyboardButton("🔙 অ্যাডমিন মেনু",callback_data="admin_menu")])
        await q.edit_message_text(f"💸 *পেন্ডিং উইথড্র* ({len(pending)}টি)",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("wdet_"):
        if user.id!=ADMIN_ID: return
        wid=int(data[5:])
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute("SELECT w.id,w.user_id,w.amount,w.method,w.number,w.requested_at,u.full_name FROM withdrawals w JOIN users u ON w.user_id=u.user_id WHERE w.id=?",(wid,))
        w=c.fetchone(); conn.close()
        if w:
            await q.edit_message_text(f"💸 *উইথড্র #{wid}*\n\n👤 {w[6]} (`{w[1]}`)\n💰 *{w[2]:.2f} টাকা*\n📱 {w[3]}: `{w[4]}`\n📅 {w[5]}",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve",callback_data=f"wok_{wid}"),InlineKeyboardButton("❌ Reject",callback_data=f"wno_{wid}")],[InlineKeyboardButton("🔙 পিছে",callback_data="adm_withdrawals")]]))
    elif data.startswith("wok_") or data.startswith("wno_"):
        if user.id!=ADMIN_ID: return
        is_ok=data.startswith("wok_"); wid=int(data.split("_")[1])
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute("SELECT user_id,amount,method,number FROM withdrawals WHERE id=?",(wid,)); w=c.fetchone(); conn.close()
        if w:
            process_withdrawal(wid,'approved' if is_ok else 'rejected')
            try:
                if is_ok:
                    await ctx.bot.send_message(w[0],f"✅ *উইথড্র Approved!*\n\n💰 *{w[1]:.2f} টাকা* {w[2]} ({w[3]}) এ পাঠানো হয়েছে!",parse_mode='Markdown')
                else:
                    await ctx.bot.send_message(w[0],f"❌ *উইথড্র Rejected!*\n\n💰 *{w[1]:.2f} টাকা* ব্যালেন্সে ফেরত দেওয়া হয়েছে।",parse_mode='Markdown')
            except Exception: pass
            await q.edit_message_text(f"উইথড্র #{wid} {'✅ Approved' if is_ok else '❌ Rejected'}",reply_markup=back_admin())
    elif data=="adm_broadcast":
        if user.id!=ADMIN_ID: return
        ctx.user_data['admin_step']='broadcast'
        await q.edit_message_text("📢 সকলকে পাঠানোর মেসেজ লিখুন:")
    elif data=="adm_give_balance":
        if user.id!=ADMIN_ID: return
        ctx.user_data['admin_step']='give_id'
        await q.edit_message_text("💵 ইউজারের Telegram ID লিখুন:")

async def photo_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if not ctx.user_data.get('screenshot_step'): return
    tid=ctx.user_data.get('screenshot_task_id'); t=get_task(tid)
    if not t:
        ctx.user_data.clear()
        await update.message.reply_text("❌ টাস্ক পাওয়া যায়নি।",reply_markup=main_kb()); return
    if already_completed(user.id,tid):
        ctx.user_data.clear()
        await update.message.reply_text("⚠️ এই টাস্ক আগেই সম্পন্ন!",reply_markup=main_kb()); return
    file_id=update.message.photo[-1].file_id
    sid=add_screenshot(user.id,tid,file_id)
    ctx.user_data.clear()
    try:
        await ctx.bot.send_photo(chat_id=ADMIN_ID,photo=file_id,caption=f"🖼️ *নতুন Screenshot!*\n\n👤 {user.full_name} (`{user.id}`)\n📋 {t[2]}\n💰 *{t[3]:.2f} টাকা*\n🆔 #{sid}",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve",callback_data=f"ssok_{sid}_{user.id}_{tid}_{t[3]}"),InlineKeyboardButton("❌ Reject",callback_data=f"ssno_{sid}_{user.id}_{tid}_{t[3]}")]]))
    except Exception: pass
    await update.message.reply_text(f"✅ *Screenshot জমা হয়েছে!*\n\nAdmin approve করলে *{t[3]:.2f} টাকা* balance এ যাবে! 💰",parse_mode='Markdown',reply_markup=main_kb())

async def msg_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; text=update.message.text.strip()
    if ctx.user_data.get('verify_step'):
        tid=ctx.user_data.get('verify_task_id'); t=get_task(tid)
        if not t:
            ctx.user_data.clear()
            await update.message.reply_text("❌ টাস্ক পাওয়া যায়নি।",reply_markup=main_kb()); return
        if already_completed(user.id,tid):
            ctx.user_data.clear()
            await update.message.reply_text("⚠️ এই টাস্ক আগেই সম্পন্ন!",reply_markup=main_kb()); return
        if text.upper()==t[4].upper():
            ctx.user_data.clear(); complete_task(user.id,tid,t[3])
            new_bal=get_user(user.id)[3]
            await update.message.reply_text(f"🎉 *সঠিক Code!*\n\n✅ টাস্ক সম্পন্ন!\n💰 *+{t[3]} টাকা* যোগ হয়েছে!\n💵 নতুন Balance: *{new_bal:.2f} টাকা*",parse_mode='Markdown',reply_markup=main_kb())
        else:
            await update.message.reply_text(f"❌ *ভুল Code!*\n\nআবার চেষ্টা করুন।",parse_mode='Markdown',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 আবার লিংকে যান",url=t[1])],[InlineKeyboardButton("❌ বাতিল",callback_data="tasks")]]))
        return
    if ctx.user_data.get('wd_step')=='number':
        if len(text)==11 and text.isdigit() and text.startswith("01"):
            ctx.user_data['wd_number']=text; ctx.user_data['wd_step']='amount'
            db_user=get_user(user.id)
            await update.message.reply_text(f"✅ নম্বর সেভ: `{text}`\n\nকত টাকা উইথড্র করবেন?\nব্যালেন্স: *{db_user[3]:.2f}* | সর্বনিম্ন: *{get_setting('min_withdraw')} টাকা*",parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ সঠিক নম্বর দিন (01XXXXXXXXX)")
        return
    if ctx.user_data.get('wd_step')=='amount':
        try:
            amount=float(text); db_user=get_user(user.id); min_wd=float(get_setting('min_withdraw'))
            if amount<min_wd:
                await update.message.reply_text(f"❌ সর্বনিম্ন *{min_wd:.0f} টাকা*!",parse_mode='Markdown')
            elif amount>db_user[3]:
                await update.message.reply_text(f"❌ ব্যালেন্স কম! আপনার: *{db_user[3]:.2f}*",parse_mode='Markdown')
            else:
                method=ctx.user_data['wd_method']; number=ctx.user_data['wd_number']
                wid=add_withdrawal(user.id,amount,method,number); ctx.user_data.clear()
                try:
                    await ctx.bot.send_message(ADMIN_ID,f"💸 *নতুন উইথড্র!*\n\n👤 {user.full_name} (`{user.id}`)\n💰 *{amount:.2f} টাকা*\n📱 {method}: `{number}`\n🆔 #{wid}",parse_mode='Markdown')
                except Exception: pass
                await update.message.reply_text(f"✅ *উইথড্র রিকোয়েস্ট জমা!*\n\n💰 *{amount:.2f} টাকা* | 📱 {method}: `{number}`\n\nAdmin শীঘ্রই প্রক্রিয়া করবেন।",parse_mode='Markdown',reply_markup=main_kb())
        except ValueError:
            await update.message.reply_text("❌ শুধু সংখ্যা লিখুন")
        return
    if ctx.user_data.get('support'):
        ctx.user_data.clear()
        try:
            await ctx.bot.send_message(ADMIN_ID,f"📞 *সাপোর্ট*\n\n👤 {user.full_name} (`{user.id}`)\n📝 {text}",parse_mode='Markdown')
        except Exception: pass
        await update.message.reply_text("✅ মেসেজ পাঠানো হয়েছে!",reply_markup=main_kb()); return
    if user.id!=ADMIN_ID: return
    step=ctx.user_data.get('admin_step')
    if step=='set_ref':
        try:
            val=float(text); set_setting('referral_bonus',val); ctx.user_data.clear()
            await update.message.reply_text(f"✅ রেফারেল বোনাস *{val} টাকা*!",parse_mode='Markdown',reply_markup=admin_kb())
        except ValueError:
            await update.message.reply_text("❌ সংখ্যা লিখুন")
    elif step=='set_wd':
        try:
            val=float(text); set_setting('min_withdraw',val); ctx.user_data.clear()
            await update.message.reply_text(f"✅ সর্বনিম্ন উইথড্র *{val} টাকা*!",parse_mode='Markdown',reply_markup=admin_kb())
        except ValueError:
            await update.message.reply_text("❌ সংখ্যা লিখুন")
    elif step=='set_welcome':
        set_setting('welcome_msg',text); ctx.user_data.clear()
        await update.message.reply_text("✅ Welcome মেসেজ আপডেট!",reply_markup=admin_kb())
    elif step=='task_link':
        ctx.user_data['t_link']=text; ctx.user_data['admin_step']='task_desc'
        await update.message.reply_text("✅ লিংক সেভ!\n\nধাপ ২: *বিবরণ* লিখুন:",parse_mode='Markdown')
    elif step=='task_desc':
        ctx.user_data['t_desc']=text; ctx.user_data['admin_step']='task_reward'
        await update.message.reply_text("✅ বিবরণ সেভ!\n\nধাপ ৩: *পুরস্কার* লিখুন (টাকায়):",parse_mode='Markdown')
    elif step=='task_reward':
        try:
            reward=float(text); ctx.user_data['t_reward']=reward
            task_type=ctx.user_data.get('task_type','normal')
            if task_type=='normal':
                add_task_db(ctx.user_data['t_link'],ctx.user_data['t_desc'],reward,'normal')
                ctx.user_data.clear()
                await update.message.reply_text(f"✅ *Screenshot Task যোগ হয়েছে!*\n\n💰 পুরস্কার: *{reward} টাকা*",parse_mode='Markdown',reply_markup=admin_kb())
            else:
                ctx.user_data['admin_step']='task_code'
                auto_code=gen_code(); ctx.user_data['auto_code']=auto_code
                await update.message.reply_text(f"✅ পুরস্কার: *{reward} টাকা*\n\nধাপ ৪: *Verify Code* লিখুন:\nAuto code: `{auto_code}`\n_(AUTO লিখলে এই code ব্যবহার হবে)_",parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text("❌ সংখ্যা লিখুন")
    elif step=='task_code':
        code=ctx.user_data.get('auto_code',gen_code()) if text.upper()=='AUTO' else text.upper()
        add_task_db(ctx.user_data['t_link'],ctx.user_data['t_desc'],ctx.user_data['t_reward'],'code',code)
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ *Code Task যোগ হয়েছে!*\n\n🔑 Verify Code: `{code}`\n\n⚠️ এই code drop link এ রাখুন!",parse_mode='Markdown',reply_markup=admin_kb())
    elif step=='broadcast':
        users=get_all_users(); sent=failed=0
        for u in users:
            if u[7]==0:
                try:
                    await ctx.bot.send_message(u[0],f"📢 *বার্তা:*\n\n{text}",parse_mode='Markdown'); sent+=1
                except Exception: failed+=1
        ctx.user_data.clear()
        await update.message.reply_text(f"📢 *সম্পন্ন!*\n✅ {sent} জন | ❌ {failed} জন",parse_mode='Markdown',reply_markup=admin_kb())
    elif step=='give_id':
        try:
            uid=int(text)
            if get_user(uid):
                ctx.user_data['give_uid']=uid; ctx.user_data['admin_step']='give_amount'
                db_u=get_user(uid)
                await update.message.reply_text(f"👤 *{db_u[2]}*\n💰 বর্তমান: *{db_u[3]:.2f} টাকা*\n\nকত টাকা দিবেন?",parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
        except ValueError:
            await update.message.reply_text("❌ সঠিক ID লিখুন")
    elif step=='give_amount':
        try:
            amount=float(text); uid=ctx.user_data['give_uid']
            admin_give_balance(uid,amount); ctx.user_data.clear()
            db_u=get_user(uid)
            try:
                await ctx.bot.send_message(uid,f"🎁 *অ্যাডমিন বোনাস!*\n💰 *{amount} টাকা* যোগ হয়েছে!\n💵 নতুন: *{db_u[3]:.2f} টাকা*",parse_mode='Markdown')
            except Exception: pass
            await update.message.reply_text(f"✅ *{db_u[2]}* কে *{amount} টাকা* দেওয়া হয়েছে!",parse_mode='Markdown',reply_markup=admin_kb())
        except ValueError:
            await update.message.reply_text("❌ সংখ্যা লিখুন")

async def ban_cmd(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    if not ctx.args:
        await update.message.reply_text("ব্যবহার: /ban [id]"); return
    try:
        uid=int(ctx.args[0]); ban_user(uid,True)
        await update.message.reply_text(f"🔴 `{uid}` ব্যান হয়েছে।",parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ সঠিক ID দিন")

async def unban_cmd(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    if not ctx.args:
        await update.message.reply_text("ব্যবহার: /unban [id]"); return
    try:
        uid=int(ctx.args[0]); ban_user(uid,False)
        await update.message.reply_text(f"🟢 `{uid}` আনব্যান হয়েছে।",parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ সঠিক ID দিন")

async def reply_cmd(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    if len(ctx.args)<2:
        await update.message.reply_text("ব্যবহার: /reply [id] [মেসেজ]"); return
    try:
        uid=int(ctx.args[0]); msg=" ".join(ctx.args[1:])
        await ctx.bot.send_message(uid,f"📞 *অ্যাডমিন:*\n\n{msg}",parse_mode='Markdown')
        await update.message.reply_text("✅ পাঠানো হয়েছে।")
    except Exception as e:
        await update.message.reply_text(f"❌ ব্যর্থ: {e}")

def main():
    init_db()
    logger.info("✅ Bot starting...")
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(CommandHandler("ban",ban_cmd))
    app.add_handler(CommandHandler("unban",unban_cmd))
    app.add_handler(CommandHandler("reply",reply_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO,photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg_handler))
    logger.info("✅ Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
