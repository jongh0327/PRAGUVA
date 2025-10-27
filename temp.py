import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)

model = genai.GenerativeModel(config.GEMINI_MODEL)

try:
    response = model.generate_content(
        "What’s the latest NASA Mars mission?",
        tools=[{"google_search_retrieval": {}}]
    )
    print(response.text)
except Exception as e:
    print("Error:", e)