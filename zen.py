import asyncio
import os
from telethon import TelegramClient, errors

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        # Session dosyası: telefon numarasına özel
        self.client = TelegramClient(f'session_{phone_number}', api_id, api_hash)

    async def safe_input(self, prompt: str) -> str:
        """Async ortamda güvenli input almak için."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input, prompt)

    async def ensure_authorized(self):
        """Oturum açık ve yetkilendirilmiş mi diye kontrol eder."""
        if not self.client.is_connected():
            await self.client.connect()
        if not await self.client.is_user_authorized():
            print("Telefon numaranızla giriş yapılıyor...")
            await self.client.send_code_request(self.phone_number)
            code = await self.safe_input('Telegram’dan gelen doğrulama kodunu girin: ')
            try:
                await self.client.sign_in(self.phone_number, code)
            except errors.SessionPasswordNeededError:
                password = await self.safe_input('İki faktörlü doğrulama şifrenizi girin: ')
                await self.client.sign_in(password=password)

    async def list_chats(self):
        await self.ensure_authorized()
        dialogs = await self.client.get_dialogs()
        filename = f"chats_of_{self.phone_number}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            for dialog in dialogs:
                chat_info = f"Chat ID: {dialog.id}, Title: {dialog.title}\n"
                print(chat_info.strip())
                f.write(chat_info)
        print(f"\n✅ Sohbet listesi '{filename}' dosyasına kaydedildi.")

    async def forward_messages_to_channel(self, source_chat_id, destination_channel_id, keywords):
        await self.ensure_authorized()

        # Son mesaj ID'sini al
        messages = await self.client.get_messages(source_chat_id, limit=1)
        last_message_id = messages[0].id if messages else 0

        print(f"🔍 Kaynak sohbetten ({source_chat_id}) mesajlar izleniyor...")
        print(f"📤 Hedef kanal: {destination_channel_id}")
        if keywords:
            print(f"🔑 Anahtar kelimeler: {', '.join(kw for kw in keywords if kw)}")
        else:
            print("📬 Tüm mesajlar iletilecek.")

        while True:
            try:
                messages = await self.client.get_messages(source_chat_id, min_id=last_message_id, limit=100)
                if not messages:
                    await asyncio.sleep(5)
                    continue

                # Mesajları eski → yeni sırayla işle
                for message in reversed(messages):
                    text = (message.text or "").strip()
                    if not text:
                        continue  # Boş mesajları atla

                    # Anahtar kelime kontrolü
                    should_forward = not keywords
                    if not should_forward:
                        text_lower = text.lower()
                        should_forward = any(
                            kw.strip().lower() in text_lower
                            for kw in keywords if kw.strip()
                        )

                    if should_forward:
                        try:
                            await self.client.send_message(destination_channel_id, text)
                            print(f"✅ İletildi: {text[:60]}{'...' if len(text) > 60 else ''}")
                        except Exception as e:
                            print(f"❌ İletme hatası: {e}")

                    last_message_id = max(last_message_id, message.id)

                await asyncio.sleep(5)

            except errors.FloodWaitError as e:
                print(f"⏳ Telegram sınırı: {e.seconds} saniye beklenmeli.")
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                print(f"❗ Beklenmeyen hata: {e}")
                await asyncio.sleep(10)

# Yardımcı fonksiyonlar

def read_credentials():
    if not os.path.exists("credentials.txt"):
        return None, None, None
    try:
        with open("credentials.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
            if len(lines) < 3:
                return None, None, None
            return lines[0], lines[1], lines[2]
    except Exception:
        return None, None, None

def write_credentials(api_id, api_hash, phone_number):
    with open("credentials.txt", "w", encoding="utf-8") as f:
        f.write(f"{api_id}\n{api_hash}\n{phone_number}\n")

async def main():
    api_id, api_hash, phone_number = read_credentials()
    if not all([api_id, api_hash, phone_number]):
        print("Lütfen Telegram API bilgilerinizi girin:")
        api_id = input("API ID: ").strip()
        api_hash = input("API Hash: ").strip()
        phone_number = input("Telefon Numarası (örn: +905551234567): ").strip()
        write_credentials(api_id, api_hash, phone_number)
        print("✅ Bilgiler credentials.txt dosyasına kaydedildi.\n")

    forwarder = TelegramForwarder(api_id, api_hash, phone_number)

    print("Seçenekler:")
    print("1. Sohbetleri Listele")
    print("2. Mesaj İlet (Anahtar Kelime ile filtreleme opsiyonel)")
    choice = input("Seçiminiz (1 veya 2): ").strip()

    if choice == "1":
        await forwarder.list_chats()
    elif choice == "2":
        try:
            source = int(input("Kaynak Sohbet ID'si: ").strip())
            dest = int(input("Hedef Kanal/Grup ID'si: ").strip())
            kw_input = input("Anahtar kelimeler (virgülle ayır, boş bırakırsan hepsini ilet): ").strip()
            keywords = [kw.strip() for kw in kw_input.split(",")] if kw_input else []
            await forwarder.forward_messages_to_channel(source, dest, keywords)
        except ValueError:
            print("❌ Geçersiz ID. Lütfen sadece sayı girin.")
    else:
        print("❌ Geçersiz seçim.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Program kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"\n💥 Kritik hata: {e}")
