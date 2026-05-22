import discord
from discord.ext import commands, tasks, voice_recv
import asyncio
import os
import tempfile
import struct
import wave
import speech_recognition as sr
from datetime import datetime

from core import config, utils

# --- Кастомний sink для збору PCM-аудіо ---
class PCMCollectorSink(voice_recv.AudioSink):
    """Збирає сирий PCM від кожного користувача окремо"""
    
    def __init__(self):
        super().__init__()
        # { user_id: [bytes, bytes, ...] }
        self.audio_data: dict[int, list[bytes]] = {}
    
    def wants_opus(self) -> bool:
        return False  # Хочемо декодований PCM
    
    def write(self, user: discord.Member | None, data: voice_recv.VoiceData):
        if user is None:
            return
        uid = user.id
        if uid not in self.audio_data:
            self.audio_data[uid] = []
        self.audio_data[uid].append(data.pcm)
    
    def cleanup(self):
        self.audio_data.clear()


def pcm_to_wav(pcm_bytes: bytes) -> str:
    """Зберігає PCM-дані у WAV-файл і повертає шлях"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)        # Стерео (Discord завжди 2 канали)
        wf.setsampwidth(2)        # 16-bit PCM
        wf.setframerate(48000)    # 48 kHz
        wf.writeframes(pcm_bytes)
    
    return path


def convert_to_google_format(input_wav_path: str) -> str:
    """Конвертує стерео 48kHz WAV у моно 16kHz WAV для Google Speech"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(input_wav_path)
        audio = audio.set_channels(1)        # Моно
        audio = audio.set_frame_rate(16000)  # 16 kHz
        audio = audio.set_sample_width(2)    # 16-bit
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name
        audio.export(out_path, format="wav")
        return out_path
    except Exception as e:
        print(f"❌ Voice AI: Помилка конвертації аудіо: {e}")
        return input_wav_path  # Повертаємо оригінал якщо конвертація зламалась


class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_recording = False
        self.sink: PCMCollectorSink | None = None
        self.check_voice_status.start()
        
    def cog_unload(self):
        self.check_voice_status.cancel()
            
    async def start_voice_recording(self):
        """Запускає запис голосового каналу через voice_recv"""
        if self.is_recording:
            print("⚠️ Voice AI: Запис вже йде")
            return
            
        if not self.bot.guilds:
            return
            
        vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
        if not vc:
            print("❌ Voice AI: Бот не у голосовому каналі")
            return
            
        # Переконуємось що це VoiceRecvClient
        if not isinstance(vc, voice_recv.VoiceRecvClient):
            print("⚠️ Voice AI: Голосовий клієнт не підтримує прийом аудіо")
            return
            
        try:
            self.sink = PCMCollectorSink()
            vc.listen(self.sink)
            self.is_recording = True
            print(f"🎙️ Voice AI: Запис розпочато в каналі {vc.channel.name}")
            
            # Автоматично зупиняємо через налаштований час
            asyncio.create_task(self.auto_stop_recording(vc))
        except Exception as e:
            print(f"❌ Voice AI: Помилка запису: {e}")
            import traceback
            traceback.print_exc()
            
    async def auto_stop_recording(self, vc):
        """Чекає і зупиняє запис"""
        duration = config.VOICE_AI_RECORD_DURATION
        await asyncio.sleep(duration)
        
        if not self.is_recording:
            return
            
        print(f"🎙️ Voice AI: Автозупинення запису (тайм-аут {duration}с)")
        
        try:
            vc.stop_listening()
        except Exception:
            pass
        
        await self.finish_recording(self.sink, vc)
            
    async def finish_recording(self, sink: PCMCollectorSink, vc):
        """Обробляє завершений запис"""
        self.is_recording = False
        
        if sink is None or not sink.audio_data:
            print("⚠️ Voice AI: Немає аудіо-даних")
            if config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
                await asyncio.sleep(2)
                await self.start_voice_recording()
            return
        
        print(f"🎙️ Voice AI: Запис завершено, {len(sink.audio_data)} користувачів")
        
        try:
            for user_id, pcm_chunks in sink.audio_data.items():
                if user_id == self.bot.user.id:
                    continue
                
                if not pcm_chunks:
                    continue
                    
                print(f"🎤 Voice AI: Обробка аудіо користувача {user_id}")
                
                # Зберігаємо PCM у WAV
                raw_pcm = b"".join(pcm_chunks)
                
                # Перевіряємо чи є взагалі звук (не тільки нулі)
                if all(b == 0 for b in raw_pcm[:200]):
                    print(f"⏭️ Voice AI: Тиша від {user_id}, пропускаємо")
                    continue
                
                wav_path = pcm_to_wav(raw_pcm)
                print(f"📁 Voice AI: WAV збережено: {wav_path}")
                
                # Конвертуємо для Google
                google_wav = convert_to_google_format(wav_path)
                
                # Обробляємо аудіо
                await self.process_audio(user_id, google_wav, vc.guild)
                
                # Прибираємо тимчасові файли
                for p in [wav_path, google_wav]:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except:
                        pass
                        
        except Exception as e:
            print(f"❌ Voice AI: Помилка обробки запису: {e}")
            import traceback
            traceback.print_exc()
        
        # Перезапускаємо запис
        if config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            print("🔄 Voice AI: Перезапуск запису через 2 секунди...")
            await asyncio.sleep(2)
            await self.start_voice_recording()
            
    async def process_audio(self, user_id, audio_path, guild):
        """Обробляє аудіо та розпізнає мову"""
        try:
            print(f"🔍 Voice AI: Розпізнавання з {audio_path}")
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 200
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
                
            try:
                text = recognizer.recognize_google(audio, language="uk-UA")
                print(f"🎤 Voice AI: Розпізнано: '{text}'")
                
                keyword = config.VOICE_AI_KEYWORD.lower()
                
                if keyword in text.lower():
                    question = text.lower().replace(keyword, "").strip()
                    print(f"✅ Voice AI: Ключове слово знайдено! Запит: '{question}'")
                    
                    if question:
                        response = await self.get_ai_response(question)
                        if response:
                            print(f"🔊 Voice AI: Озвучування відповіді...")
                            await utils.play_tts(response, guild, self.bot)
                    else:
                        print("⚠️ Voice AI: Порожній запит після ключового слова")
                else:
                    print(f"⏭️ Voice AI: Ключове слово '{keyword}' не знайдено")
                            
            except sr.UnknownValueError:
                print("⚠️ Voice AI: Не вдалося розпізнати мову")
            except sr.RequestError as e:
                print(f"❌ Voice AI: Помилка Google API: {e}")
                
        except Exception as e:
            print(f"❌ Voice AI: Помилка обробки аудіо: {e}")
            import traceback
            traceback.print_exc()
            
    async def get_ai_response(self, prompt):
        """Отримує відповідь від Gemini API"""
        try:
            import aiohttp
            token = os.environ.get("GEMINI_API_KEY")
            if not token:
                print("❌ Voice AI: GEMINI_API_KEY не знайдено")
                return None
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={token}"
            payload = {
                "system_instruction": {"parts": [{"text": "Ти на діскорд сервері з ГТА5 'MidNight'. Відповідай коротко українською. Максимум 2 речення."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        print(f"❌ Voice AI: Gemini API помилка {response.status}")
                        return None
                        
        except Exception as e:
            print(f"❌ Voice AI: Критична помилка ШІ: {e}")
            return None
            
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            return
        if member.bot:
            return
            
        if not before.channel and after.channel:
            vc = discord.utils.get(self.bot.voice_clients, guild=member.guild)
            if vc and vc.channel.id == after.channel.id and not self.is_recording:
                await self.start_voice_recording()
                    
        if member.id == self.bot.user.id and after.channel:
            print(f"🤖 Voice AI: Бот приєднався до {after.channel.name}")
            await asyncio.sleep(2)
            if not self.is_recording:
                await self.start_voice_recording()
                
    @tasks.loop(seconds=30)
    async def check_voice_status(self):
        if not config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            if self.is_recording:
                print("🛑 Voice AI: Вимкнено, зупинення запису")
                if self.bot.guilds:
                    vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
                    if vc and isinstance(vc, voice_recv.VoiceRecvClient):
                        try: vc.stop_listening()
                        except: pass
                self.is_recording = False
            return
            
        if not self.bot.guilds:
            return
            
        vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
        if vc and not self.is_recording:
            print("🔄 Voice AI: Бот у войсі, запуск запису")
            await self.start_voice_recording()
        elif not vc:
            self.is_recording = False
            print("⚠️ Voice AI: Бот не у войсі")
            
    @check_voice_status.before_loop
    async def before_check_voice_status(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceAICog(bot))
