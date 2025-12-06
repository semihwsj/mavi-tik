import asyncio
import os
import re
from telethon import TelegramClient, errors

class CAExtractor:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient(f'session_{phone_number}', api_id, api_hash)

    async def safe_input(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input, prompt)

    async def ensure_authorized(self):
        if not self.client.is_connected():
            await self.client.connect()
        if not await self.client.is_user_authorized():
            print("🔐 Telegram hesabıyla giriş yapılıyor...")
            await self.client.send_code_request(self.phone_number)
            code = await self.safe_input('Doğrulama kodunu girin: ')
            try:
                await self.client.sign_in(self.phone_number, code)
            except errors.SessionPasswordNeededError:
                password = await self.safe_input('2FA şifrenizi girin: ')
                await self.client.sign_in(password=password)

    async def list_chats(self):
        await self.ensure_authorized()
        dialogs = await self.client.get_dialogs()
        filename = f"chats_of_{self.phone_number}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            for dialog in dialogs:
                info = f"Chat ID: {dialog.id}, Title: {dialog.title}\n"
                print(info.strip())
                f.write(info)
        print(f"\n✅ Sohbet listesi '{filename}' dosyasına kaydedildi.")

    async def extract_and_forward_ca(self, source_chat_id, destination_channel_id):
        await self.ensure_authorized()
        messages = await self.client.get_messages(source_chat_id, limit=1)
        last_message_id = messages[0].id if messages else 0

        print(f"🔍 Kaynak sohbet: {source_chat_id}")
        print(f"📤 Hedef kanal: {destination_channel_id}")
        print("🚀 Sadece '...pump' formatındaki CA'lar iletiliyor.\n")

        while True:
            try:
                messages = await self.client.get_messages(source_chat_id, min_id=last_message_id, limit=50)
                if not messages:
                    await asyncio.sleep(5)
                    continue

                for message in reversed(messages):
                    ca = None
                    text = (message.text or "").strip()

                    if text:
                        for line in text.splitlines():
                            line = line.strip()
                            # Geçerli CA: sadece harf/rakam + en az 30 karakter + 'pump' ile bitmeli
                            if (
                                line.endswith('pump') and
                                len(line) >= 30 and
                                re.fullmatch(r'[A-Za-z0-9]{30,}pump', line)
                            ):
                                ca = line
                                break  # İlk geçerli CA'yı al

                    if ca:
                        try:
                            await self.client.send_message(destination_channel_id, ca)
                            print(f"✅ CA iletildi: {ca}")
                        except Exception as e:
                            print(f"❌ İletme hatası: {e}")
                    else:
                        print("ℹ️ CA bulunamadı — mesaj atlandı.")

                    last_message_id = max(last_message_id, message.id)

                await asyncio.sleep(5)

            except (ConnectionError, OSError, errors.ConnectionError, errors.ServerError) as e:
                print(f"🔌 Bağlantı hatası: {e}")
                print("🔁 Yeniden bağlanılıyor...")
                await self.client.disconnect()
                await asyncio.sleep(10)
                await self.ensure_authorized()
                continue

            except errors.FloodWaitError as e:
                print(f"⏳ FloodWait: {e.seconds} saniye bekle.")
                await asyncio.sleep(e.seconds + 10)

            except KeyboardInterrupt:
                print("\n⏹️  Kullanıcı tarafından durduruldu.")
                break

            except Exception as e:
                print(f"❗ Beklenmeyen hata: {e}")
                await asyncio.sleep(10)

# --- Kimlik Bilgileri Yönetimi ---

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

# --- Ana Program ---

async def main():
    api_id, api_hash, phone_number = read_credentials()
    if not all([api_id, api_hash, phone_number]):
        print("📝 Lütfen Telegram API bilgilerinizi girin:")
        api_id = input("API ID: ").strip()
        api_hash = input("API Hash: ").strip()
        phone_number = input("Telefon Numarası (örn: +905551234567): ").strip()
        write_credentials(api_id, api_hash, phone_number)
        print("✅ Bilgiler kaydedildi.\n")

    extractor = CAExtractor(api_id, api_hash, phone_number)

    print("Seçenekler:")
    print("1. Sohbetleri Listele (ID öğrenmek için)")
    print("2. CA Ayıklayıcıyı Başlat")
    choice = input("Seçiminiz (1 veya 2): ").strip()

    if choice == "1":
        await extractor.list_chats()
    elif choice == "2":
        try:
            source = int(input("Kaynak Sohbet ID'si: ").strip())
            dest = int(input("Hedef Kanal ID'si: ").strip())
            await extractor.extract_and_forward_ca(source, dest)
        except ValueError:
            print("❌ Lütfen geçerli sayısal ID girin.")
    else:
        print("❌ Geçersiz seçim.")

# --- Başlat ---

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Program kullanıcı tarafından sonlandırıldı.")
    except Exception as e:
        print(f"\n💥 Kritik hata: {e}")
