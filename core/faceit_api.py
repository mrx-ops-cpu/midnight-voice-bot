import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

async def generate_ruiner_comment(kd: float, adr: int) -> str:
    prompt = f"""
    Ти - саркастичний ігровий коментатор.
    Грайвець щойно закінчив матч у CS2 з жахливою статистикою: K/D = {kd}, ADR = {adr}.
    Напиши ОДНЕ коротке, смішне, токсичне (але без матюків) і саркастичне речення, 
    яке висміює його гру і називає "🤡 Головним руїнером матчу".
    """
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Помилка ШІ: {e}")
        return "🤡 Головний руїнер матчу! Навіть боти грають краще."

async def get_profile(nickname: str) -> dict:
    return {
        "elo": 2150,
        "level": 10,
        "kd": 1.25,
        "winrate": 55
    }

async def get_last_match(nickname: str) -> dict:
    return {
        "score": "13-10",
        "kd": 1.45,
        "elo_diff": "+25"
    }