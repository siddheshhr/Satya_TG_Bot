import logging
import os
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from PIL import Image
import pytesseract
import nltk

# Initialize NLP resources
nltk.download('punkt')

# Hard-coded tokens (for testing only; remove hard-coding for production)
TELEGRAM_TOKEN = ""
OPENROUTER_API_KEY = ""

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Welcome to Satya.ai! Send me news links, text, or images to find if it's the real deal."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Simply send a news link, text, or image to get started with the process")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.text:
        if any(entity.type == "url" for entity in message.entities):
            await handle_url(message)
        else:
            await handle_text(message)
    elif message.photo:
        await handle_image(message)

async def handle_url(message):
    url = message.text
    await message.reply_text(f"🔍 Analyzing article at {url}...")

    from newspaper import Article
    article = Article(url)
    try:
        article.download()
        article.parse()
        article.nlp()
        text = f"{article.title}\n\n{article.text}"
    except Exception as e:
        logger.error(f"Article parsing failed: {str(e)}")
        text = f"Error extracting article: {str(e)}"

    response = await analyze_content(text)
    await message.reply_markdown(response)
    
async def handle_text(message):
    text = message.text
    await message.reply_text("📝 Analyzing provided text...")
    response = await analyze_content(text)
    await message.reply_markdown(response)

async def handle_image(message):
    await message.reply_text("🖼 Processing image...")
    
    photo = await message.photo[-1].get_file()
    img_path = await photo.download_to_drive()
    
    try:
        text = pytesseract.image_to_string(Image.open(img_path))
        if not text.strip():
            return await message.reply_text("❌ No text found in image")
        
        response = await analyze_content(text)
        await message.reply_markdown(response)
    except Exception as e:
        logger.error(f"Image processing failed: {str(e)}")
        await message.reply_text("❌ Error processing image")

async def analyze_content(text):
    prompt = f"""Analyze this news content and provide:
1. Fake News Score (0-100) as [Score: X/100]
2. Brief fact-check summary
3. Potential red flags
4. Suggested verification sources

Content: {text[:3000]}"""  # Truncate if necessary

    try:
        # Instantiate an async client using the new SDK interface
        client = AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        completion = await client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        # Extract the content from the response
        result = completion.choices[0].message.content
        return format_response(result)
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return f"❌ Error analyzing content: {str(e)}"
    
def format_response(text):
    return f"🔍 **Analysis Result**\n\n{text}\n\n_Verified by Satya.ai_"

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    app.run_polling()
