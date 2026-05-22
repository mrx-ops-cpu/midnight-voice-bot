import discord
from discord.ext import commands, tasks
import asyncio
import os
import tempfile
import speech_recognition as sr
from datetime import datetime
from pydub import AudioSegment
import io

from core import config, utils

class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_recording = False
        self.sink = None
        self.recording_task = None
        self.check_voice_status.start()
        
    def cog_unload(self):
        if self.recording_task:
            self.recording_task.cancel()
        self.check_voice_status.cancel()
            
    async def start_voice_recording(self):
        """Запускає запис голосового каналу"""
        if self.is_recording:
            print("⚠️ Voice AI: Запис вже йде")
            return
            
        vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
        if not vc:
            print("❌ Voice AI: Бот не у голосовому каналі")
            return
            
        try:
            self.sink = discord.sinks.WaveSink()
            vc.start_recording(self.sink, self.finish_recording, vc)
            self.is_recording = True
            print(f"🎙️ Voice AI: Запис розпочато в каналі {vc.channel.name}")
            
            # Автоматично зупиняємо запис через 30 секунд якщо мовчання
            asyncio.create_task(self.auto_stop_recording(vc))
        except Exception as e:
            print(f"❌ Voice AI: Помилка запису: {e}")
            import traceback
            traceback.print_exc()
            
    async def auto_stop_recording(self, vc):
        """Автоматично зупиняє запис через налаштований час"""
        duration = config.VOICE_AI_RECORD_DURATION
        await asyncio.sleep(duration)
        if self.is_recording and vc.is_recording():
            try:
                vc.stop_recording()
                print(f"🎙️ Voice AI: Автозупинення запису (тайм-аут {duration}с)")
            except:
                pass
            
    async def finish_recording(self, sink, vc):
        """Обробляє завершений запис"""
        self.is_recording = False
        print(f"🎙️ Voice AI: Запис завершено, отримано {len(sink.audio_data)} аудіо-файлів")
        
        try:
            for user_id, audio in sink.audio_data.items():
                if user_id == self.bot.user.id:
                    print(f"⏭️ Voice AI: Пропускаю аудіо бота")
                    continue
                    
                print(f"🎤 Voice AI: Обробка аудіо користувача {user_id}")
                
                # Зберігаємо аудіо у файл
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                audio.file.seek(0)
                with open(tmp_path, "wb") as f:
                    f.write(audio.file.read())
                    
                print(f"📁 Voice AI: Аудіо збережено в {tmp_path}")
                
                # Обробляємо аудіо
                await self.process_audio(user_id, tmp_path, vc.guild)
                
                # Видаляємо тимчасовий файл
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    print(f"🗑️ Voice AI: Тимчасовий файл видалено")
                    
        except Exception as e:
            print(f"❌ Voice AI: Помилка обробки запису: {e}")
            import traceback
            traceback.print_exc()
            
        # Перезапускаємо запис якщо увімкнено
        if config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            print("🔄 Voice AI: Перезапуск запису через 2 секунди...")
            await asyncio.sleep(2)
            await self.start_voice_recording()
            
    async def process_audio(self, user_id, audio_path, guild):
        """Обробляє аудіо та розпізнає мову"""
        try:
            print(f"🔍 Voice AI: Початок розпізнавання мови з {audio_path}")
            recognizer = sr.Recognizer()
            
            # Налаштовуємо розпізнавання для кращої якості
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            with sr.AudioFile(audio_path) as source:
                audio = recognizer.record(source)
                
            try:
                # Розпізнаємо українську мову
                text = recognizer.recognize_google(audio, language="uk-UA")
                print(f"🎤 Voice AI: Розпізнано текст: '{text}'")
                
                # Перевіряємо ключове слово
                keyword = config.VOICE_AI_KEYWORD.lower()
                print(f"🔑 Voice AI: Пошук ключового слова '{keyword}'")
                
                if keyword in text.lower():
                    # Видаляємо ключове слово
                    question = text.lower().replace(keyword, "").strip()
                    print(f"✅ Voice AI: Ключове слово знайдено! Запит: '{question}'")
                    
                    if question:
                        print(f"🤖 Voice AI: Відправка запиту до ШІ...")
                        response = await self.get_ai_response(question)
                        
                        if response:
                            print(f"🔊 Voice AI: Отримано відповідь: '{response}'")
                            print(f"🔊 Voice AI: Озвучування відповіді...")
                            await utils.play_tts(response, guild, self.bot)
                            print(f"✅ Voice AI: Відповідь озвучено")
                        else:
                            print(f"❌ Voice AI: ШІ не повернув відповідь")
                    else:
                        print(f"⚠️ Voice AI: Порожній запіт після видалення ключового слова")
                else:
                    print(f"⏭️ Voice AI: Ключове слово не знайдено, пропускаємо")
                            
            except sr.UnknownValueError:
                print("⚠️ Voice AI: Не вдалося розпізнати мову (UnknownValueError)")
            except sr.RequestError as e:
                print(f"❌ Voice AI: Помилка розпізнавання (RequestError): {e}")
                
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
                print("❌ Voice AI: Токен Gemini не знайдено в змінних середовища")
                return "❌ Токен Gemini не налаштовано"
                
            print(f"🔑 Voice AI: Токен Gemini знайдено")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={token}"
            
            system_style = "Ти на діскорд сервері з ГТА5 під назвою 'MidNight'. Веди себе добре та відповідай коротко українською мовою. Максимум 1-2 речення."
            
            payload = {
                "system_instruction": {
                    "parts": [{"text": system_style}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }
            
            headers = {"Content-Type": "application/json"}
            
            print(f"📤 Voice AI: Відправка запиту до Gemini API...")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    print(f"📥 Voice AI: Отримано відповідь від Gemini API, статус: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        try:
                            result = data["candidates"][0]["content"]["parts"][0]["text"]
                            print(f"✅ Voice AI: Успішно отримано відповідь від Gemini")
                            return result
                        except (KeyError, IndexError) as e:
                            print(f"❌ Voice AI: Помилка парсингу відповіді Gemini: {e}")
                            return "❌ Помилка обробки відповіді"
                    else:
                        error_text = await response.text()
                        print(f"❌ Voice AI: Gemini API повернув помилку {response.status}: {error_text}")
                        return f"❌ Помилка API: {response.status}"
                        
        except Exception as e:
            print(f"❌ Voice AI: Критична помилка ШІ: {e}")
            import traceback
            traceback.print_exc()
            return "❌ Сталася помилка"
            
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Слідкує за змінами у голосових каналах"""
        if not config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            return
            
        if member.bot:
            return
            
        # Якщо користувач приєднався до войсу
        if not before.channel and after.channel:
            print(f"👤 Voice AI: Користувач {member.name} приєднався до {after.channel.name}")
            vc = discord.utils.get(self.bot.voice_clients, guild=member.guild)
            if vc and vc.channel.id == after.channel.id:
                print(f"🎙️ Voice AI: Користувач приєднався до каналу бота, спроба запуску запису")
                # Починаємо запис якщо ще не записуємо
                if not self.is_recording:
                    await self.start_voice_recording()
                    
        # Якщо бот приєднався до каналу
        if member.id == self.bot.user.id and after.channel:
            print(f"🤖 Voice AI: Бот приєднався до {after.channel.name}")
            await asyncio.sleep(2)
            if not self.is_recording:
                await self.start_voice_recording()
                
    @tasks.loop(seconds=30)
    async def check_voice_status(self):
        """Періодично перевіряє статус голосового ШІ"""
        if not config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            if self.is_recording:
                print("🛑 Voice AI: Голосовий ШІ вимкнено, зупинення запису")
                vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
                if vc:
                    vc.stop_recording()
                self.is_recording = False
            return
            
        vc = discord.utils.get(self.bot.voice_clients, guild=self.bot.guilds[0])
        if vc and not self.is_recording:
            print(f"🔄 Voice AI: Періодична перевірка - бот у войсі, запуск запису")
            await self.start_voice_recording()
        elif not vc:
            print(f"⚠️ Voice AI: Періодична перевірка - бот не у войсі")
            
    @check_voice_status.before_loop
    async def before_check_voice_status(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceAICog(bot))
