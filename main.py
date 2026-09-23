import os
import html
import time
import requests
import threading
import io
import base64
import qrcode
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ---------------------------------------------------------
# KONFIGURASI BOT & KLIKQRIS
# ---------------------------------------------------------
TOKEN = os.getenv("BOT_TOKEN", "8804489343:AAFIDoxsGrMbnnzsA-PEl6Ao8QqEhXl7B64")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8953615855"))

# Kredensial Resmi KlikQRIS
API_KEY = "CsWwaNbQvdtMbrEtgBiE3wGqvvjzsP349thFRjgt"
ID_MERCHANT = "179009297448"

# Endpoint API KlikQRIS
BASE_URL = "https://klikqris.com/api"
CREATE_TRANSACTION_URL = f"{BASE_URL}/qris/create"
CHECK_TRANSACTION_URL = f"{BASE_URL}/qris/check"  # Endpoint untuk cek status pembayaran

# List ID 11 Grup VIP
ALL_GROUP_IDS = [
    -1003721629607,
    -1003646177202,
    -1003727409464,
    -1003713991635,
    -1003839151133,
    -1003561794613,
    -1003634689467,
    -1003853297361,
    -1004451939488,
    -1004486985873,
    -1003813292350
]

bot = telebot.TeleBot(TOKEN)
PRICE_VIP = 1000  # Sesuaikan harga (1000 untuk test / 85000 untuk normal)

# ---------------------------------------------------------
# HELPER UNTUK MENGHASILKAN GAMBAR QR CODE
# ---------------------------------------------------------
def generate_qr_stream(qr_data):
    if str(qr_data).startswith("data:image"):
        header, base64_str = qr_data.split(",", 1)
        image_bytes = base64.b64decode(base64_str)
        bio = io.BytesIO(image_bytes)
        bio.name = 'qris.png'
        return bio
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = io.BytesIO()
    bio.name = 'qris.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ---------------------------------------------------------
# MENU & HANDLER UTAMA BOT
# ---------------------------------------------------------
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 Beli Paket VIP 11 Grup (Rp 1.000)"))
    markup.add(KeyboardButton("⭐ Testimoni"), KeyboardButton("❓ Bantuan"))
    markup.add(KeyboardButton("📞 Hubungi Admin"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(
        message, 
        "Halo! Selamat datang di bot WarungDosa.\n\n"
        "🔥 <b>Paket Hemat:</b> Dapatkan akses ke <b>11 Grup VIP Sekaligus</b> hanya dengan <b>Rp 1.000</b>!\n\n"
        "Silakan gunakan tombol menu di bawah untuk mulai:", 
        parse_mode="HTML", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text in ["🛒 Beli Paket VIP 11 Grup (Rp 1.000)", "🛒 Beli Paket VIP 11 Grup (Rp 85.000)"])
def handle_buy_menu(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Tampilkan QRIS Pembayaran", callback_data="generate_qris"))
    
    bot.send_message(
        chat_id,
        "Anda memilih <b>Paket VIP 11 Grup Sekaligus (Rp 1.000)</b>.\n\nKlik tombol di bawah untuk membuat QR Code pembayaran otomatis:",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "⭐ Testimoni")
def handle_testimoni(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Buka Channel Testimoni", url="https://t.me/testiwarungdosaa"))
    bot.send_message(
        message.chat.id,
        "⭐ <b>Testimoni Pelanggan WarungDosa</b>\n\nKlik tombol di bawah untuk melihat kumpulan testimoni lengkap kami:",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "❓ Bantuan")
def handle_faq(message):
    bot.reply_to(
        message,
        "💡 <b>Panduan & FAQ:</b>\n\n"
        "1. Klik menu <b>'🛒 Beli Paket VIP 11 Grup'</b>.\n"
        "2. Klik tombol <b>'💳 Tampilkan QRIS Pembayaran'</b>.\n"
        "3. Scan & bayar QRIS yang muncul via E-Wallet/Bank.\n"
        "4. Setelah pembayaran terdeteksi, bot akan otomatis mengirimkan 11 link invite VIP!",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda message: message.text == "📞 Hubungi Admin")
def handle_contact_admin(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💬 Chat Admin Sekarang", url="https://t.me/WarungDosa"))
    bot.send_message(
        message.chat.id,
        "💬 Silakan hubungi Admin kami jika Anda mengalami kendala:",
        reply_markup=markup
    )

# ---------------------------------------------------------
# LOOP CEK PEMBAYARAN OTOMATIS (BACKGROUND THREAD)
# ---------------------------------------------------------
def check_payment_loop(chat_id, order_id, photo_message_id):
    """Mengecek status pembayaran ke KlikQRIS setiap 5 detik (Maksimal 10 menit)"""
    timeout = 600  # Waktu tunggu 10 menit
    start_time = time.time()
    
    headers = {
        "x-api-key": API_KEY,
        "id_merchant": ID_MERCHANT,
        "Content-Type": "application/json"
    }
    
    payload = {
        "order_id": order_id,
        "id_merchant": ID_MERCHANT
    }
    
    while time.time() - start_time < timeout:
        time.sleep(5)  # Cek setiap 5 detik
        try:
            res = requests.post(CHECK_TRANSACTION_URL, json=payload, headers=headers, timeout=5)
            res_data = res.json()
            
            data_res = res_data.get("data", res_data)
            status = str(data_res.get("status", "")).upper()
            is_paid = data_res.get("paid") is True or status in ["PAID", "SUCCESS", "BERHASIL", "COMPLETED", "200"]
            
            if is_paid:
                # 1. Hapus gambar QRIS yang ditampilkan sebelumnya
                try:
                    bot.delete_message(chat_id, photo_message_id)
                except Exception:
                    pass

                # 2. Buat 11 link invite grup VIP (sekali pakai)
                generated_links = []
                for group_id in ALL_GROUP_IDS:
                    try:
                        invite = bot.create_chat_invite_link(chat_id=group_id, member_limit=1)
                        generated_links.append(invite.invite_link)
                    except Exception as e:
                        print(f"Gagal buat link grup {group_id}: {e}")
                
                if generated_links:
                    links_text = "\n".join([f"• {link}" for link in generated_links])
                else:
                    links_text = "Gagal membuat link otomatis. Silakan hubungi admin."

                # 3. Kirim link ke pembeli
                bot.send_message(
                    chat_id,
                    f"✅ <b>Pembayaran Berhasil Diterima!</b>\n\n"
                    f"Berikut adalah link akses ke 11 Grup VIP (Sekali Pakai):\n\n{links_text}\n\n"
                    f"<b>Catatan:</b>\n"
                    f"- Link hanya dapat digunakan 1x per grup.\n"
                    f"- Selamat bergabung!",
                    parse_mode="HTML"
                )
                
                # 4. Notifikasi ke Admin
                try:
                    bot.send_message(
                        ADMIN_ID,
                        f"💰 <b>Pembayaran Masuk!</b>\nUser ID: <code>{chat_id}</code>\nOrder ID: <code>{order_id}</code>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                
                break  # Stop loop setelah pembayaran terverifikasi
                
        except Exception as e:
            print(f"Error polling payment ({order_id}): {e}")

# ---------------------------------------------------------
# PROCESS REQUEST QRIS KE KLIKQRIS
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data == "generate_qris")
def process_generate_qris(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    bot.send_chat_action(chat_id, 'upload_photo')
    
    order_id = f"WD-{user_id}-{int(time.time())}"
    
    headers = {
        "x-api-key": API_KEY,
        "id_merchant": ID_MERCHANT,
        "Content-Type": "application/json"
    }
    
    payload = {
        "order_id": order_id,
        "amount": PRICE_VIP,
        "id_merchant": ID_MERCHANT,
        "keterangan": f"VIP 11 Grup User {user_id}"
    }
    
    try:
        response = requests.post(CREATE_TRANSACTION_URL, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        
        is_success = response.status_code in [200, 201] or res_data.get("status") in [True, "SUCCESS", "PENDING", 200, 201] or res_data.get("success") is True
        
        if is_success:
            data_res = res_data.get("data", res_data)
            
            qr_content = (
                data_res.get("qr_content") or 
                data_res.get("qris_content") or 
                data_res.get("qris_image") or 
                data_res.get("qr_url") or 
                data_res.get("qris_url") or 
                data_res.get("qr_code") or 
                data_res.get("image")
            )
            
            raw_amount = data_res.get("total_amount") or data_res.get("amount") or PRICE_VIP
            try:
                total_amount = int(float(str(raw_amount)))
            except (ValueError, TypeError):
                total_amount = PRICE_VIP
            
            caption_text = (
                f"<b>VIP WarungDosa - Rp {total_amount:,}</b>💵\n\n"
                "Silakan scan QRIS di atas menggunakan e-wallet / m-banking pilihan Anda.\n\n"
                "⏱️ <i>Sistem akan memverifikasi pembayaran secara otomatis. Setelah terbayar, link 11 grup VIP akan langsung dikirimkan ke sini!</i>"
            )
            
            sent_msg = None
            if qr_content:
                qr_photo_stream = generate_qr_stream(str(qr_content))
                sent_msg = bot.send_photo(chat_id, qr_photo_stream, caption=caption_text, parse_mode="HTML")
            else:
                direct_url = data_res.get("direct_url") or data_res.get("checkout_url") or ""
                sent_msg = bot.send_message(chat_id, f"{caption_text}\n\n🔗 <b>Link Pembayaran:</b> {direct_url}", parse_mode="HTML")

            bot.answer_callback_query(call.id)
            
            # MENGAKTIFKAN Pengecekan Otomatis via Background Thread
            if sent_msg:
                threading.Thread(
                    target=check_payment_loop,
                    args=(chat_id, order_id, sent_msg.message_id),
                    daemon=True
                ).start()
            
        else:
            error_msg = res_data.get("message", "Gagal memproses QRIS.")
            bot.send_message(chat_id, f"Gagal membuat QRIS: {error_msg}")
            bot.answer_callback_query(call.id, "Gagal memuat QRIS!", show_alert=True)
            
    except requests.exceptions.ConnectionError:
        bot.send_message(chat_id, "❌ Terjadi masalah koneksi/DNS ke server KlikQRIS.")
    except Exception as e:
        print(f"Error QRIS: {e}")
        bot.send_message(chat_id, "Terjadi kesalahan sistem pembayaran. Silakan hubungi admin.")

# ---------------------------------------------------------
# RUNNING BOT
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Bot berjalan...")
    bot.infinity_polling()
