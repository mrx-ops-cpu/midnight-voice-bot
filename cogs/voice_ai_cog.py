import discord
from discord.ext import commands, tasks
from discord.ext import voice_recv
import asyncio
import os
import tempfile
import speech_recognition as sr
from datetime import datetime

from core import config, utils


def convert_to_google_format(input_wav_path: str) -> str:
    """Конвертує WAV (стерео 48kHz) у моно 16kHz для Google Speech"""
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
        print(f"❌ Voice AI: Помилка конвертації: {e}")
        return input_wav_path


class VoiceAICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_recording = False
        self.sink = None
        self.tmp_path: str | None = None
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

        if not isinstance(vc, voice_recv.VoiceRecvClient):
            print("⚠️ Voice AI: Голосовий клієнт не підтримує прийом аудіо (потрібен VoiceRecvClient)")
            return

        try:
            # Створюємо тимчасовий WAV-файл
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                self.tmp_path = tmp_file.name

            self.sink = voice_recv.WaveSink(self.tmp_path)
            vc.listen(self.sink)
            self.is_recording = True
            print(f"🎙️ Voice AI: Запис розпочато в каналі {vc.channel.name}")

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

        print(f"🎙️ Voice AI: Автозупинення (тайм-аут {duration}с)")
        try:
            vc.stop_listening()
        except Exception:
            pass

        await self.finish_recording(vc)

    async def finish_recording(self, vc):
        """Обробляє завершений запис"""
        self.is_recording = False

        tmp_path = self.tmp_path
        self.tmp_path = None

        if not tmp_path or not os.path.exists(tmp_path):
            print("⚠️ Voice AI: Файл запису не знайдено")
            await self._restart_recording()
            return

        file_size = os.path.getsize(tmp_path)
        print(f"🎙️ Voice AI: Запис завершено, розмір файлу: {file_size} байт")

        # Якщо файл занадто малий — лише заголовок WAV, без звуку
        if file_size < 5000:
            print("⚠️ Voice AI: Файл занадто малий (тиша), пропускаємо")
            try: os.remove(tmp_path)
            except: pass
            await self._restart_recording()
            return

        try:
            # Конвертуємо у формат для Google
            google_wav = convert_to_google_format(tmp_path)
            print(f"🔄 Voice AI: Конвертовано: {google_wav}")

            await self.process_audio(google_wav, vc.guild)

        except Exception as e:
            print(f"❌ Voice AI: Помилка обробки: {e}")
            import traceback
            traceback.print_exc()
        finally:
            for p in [tmp_path, self.tmp_path]:
                try:
                    if p and os.path.exists(p):
                        os.remove(p)
                except:
                    pass

        await self._restart_recording()

    async def _restart_recording(self):
        """Перезапускає запис якщо увімкнено"""
        if config.GLOBAL_SETTINGS.get("voice_ai_enabled", False):
            print("🔄 Voice AI: Перезапуск через 2 секунди...")
            await asyncio.sleep(2)
            await self.start_voice_recording()

    async def process_audio(self, audio_path, guild):
        """Розпізнає мову та реагує на ключове слово"""
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
                    print(f"⏭️ Voice AI: Ключове слово '{keyword}' не знайдено в '{text}'")

            except sr.UnknownValueError:
                print("⚠️ Voice AI: Не вдалося розпізнати мову (тиша або шум)")
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
                        print(f"❌ Voice AI: Gemini помилка {response.status}")
                        return None

        except Exception as e:
            print(f"❌ Voice AI: Помилка ШІ: {e}")
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
