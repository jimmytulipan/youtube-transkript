#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import re
import requests
import base64
import json
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, YOUTUBE_TRANSCRIPT_API_TOKEN
from translator import translator

# Nastavenie logovania
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Načítanie OpenAI API kľúča z config.ini
def load_openai_api_key():
    import configparser
    config = configparser.ConfigParser()
    try:
        config.read('config.ini')
        api_key = config.get('api', 'openai_api_key')
        return api_key
    except Exception as e:
        logger.error(f"Nepodarilo sa načítať OpenAI API kľúč: {e}")
        return None

# Inicializácia OpenAI API klienta
openai.api_key = load_openai_api_key()

# Funkcia na sumarizáciu textu cez OpenAI API
async def summarize_text(text):
    """Sumarizuje text pomocou OpenAI API."""
    try:
        # Použitie sumarizácie z modulu translator
        return translator.summarize_text(text)
    except Exception as e:
        logger.error(f"Chyba pri sumarizácii textu: {e}")
        return f"Chyba pri sumarizácii textu: {str(e)}"

# Funkcia na získanie ID videa z YouTube URL
def extract_video_id(url):
    """Extrahuje YouTube video ID z rôznych formátov URL."""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    
    match = re.match(youtube_regex, url)
    if match:
        return match.group(6)
    return None

# Funkcia na získanie transkriptu cez API
async def get_transcript(video_id):
    """Získa transkript YouTube videa cez API."""
    url = "https://www.youtube-transcript.io/api/transcripts"
    
    # Použitie API tokenu tak, ako je odporúčané na webstránke API dokumentácie
    headers = {
        "Authorization": f"Basic {YOUTUBE_TRANSCRIPT_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"ids": [video_id]}
    
    try:
        logger.info(f"Odosielam požiadavku na API pre video ID: {video_id}")
        logger.info(f"Používam API token: {YOUTUBE_TRANSCRIPT_API_TOKEN[:5]}...")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        # Zalogujeme status kód a odpoveď pre debugovanie
        logger.info(f"API status kód: {response.status_code}")
        logger.info(f"API odpoveď hlavičky: {response.headers}")
        
        # Skúsime získať odpoveď aj v prípade chyby
        try:
            response_data = response.json()
            logger.info(f"API raw odpoveď: {json.dumps(response_data)[:500]}...")
        except Exception as e:
            logger.error(f"Nepodarilo sa spracovať odpoveď ako JSON: {e}")
            logger.info(f"Raw odpoveď: {response.text[:500]}...")
        
        # Skontrolujeme odpoveď
        response.raise_for_status()
        data = response.json()
        
        # Skontrolujeme, či odpoveď má očakávaný formát
        logger.info(f"Odpoveď z API prijatá, typ odpovede: {type(data)}")
        
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Chyba pri získavaní transkriptu: {e}")
        return None

# Telegram príkazy
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Odošle správu pri spustení príkazu /start."""
    await update.message.reply_text(
        'Ahoj! Pošli mi YouTube odkaz a ja ti pošlem transkript v slovenčine.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Odošle nápovedu."""
    await update.message.reply_text(
        'Jednoducho pošli odkaz na YouTube video a ja ti pošlem jeho prepis v slovenčine.'
    )

async def process_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spracuje YouTube odkaz a vráti transkript."""
    message_text = update.message.text
    
    # Kontrola, či správa obsahuje "youtube" alebo "youtu.be"
    if "youtube" not in message_text and "youtu.be" not in message_text:
        return
    
    # Získanie ID videa
    video_id = extract_video_id(message_text)
    if not video_id:
        await update.message.reply_text("Nepodarilo sa extrahovať ID videa. Prosím, skontroluj odkaz.")
        return
    
    await update.message.reply_text("Získavam transkript, čakaj prosím...")
    
    # Získanie transkriptu
    transcript_data = await get_transcript(video_id)
    if not transcript_data:
        await update.message.reply_text("Nepodarilo sa získať transkript. Video možno nemá titulky alebo nastala chyba.")
        return
    
    logger.info(f"Získaný transcript_data: {type(transcript_data)}")
    
    try:
        # Spracovanie transkriptu
        transcript_text = ""
        transcript_segments = []
        
        # Logujeme pre debug
        logger.info(f"Typ transcript_data: {type(transcript_data)}")
        if isinstance(transcript_data, dict):
            logger.info(f"Kľúče v dict: {transcript_data.keys()}")
        elif isinstance(transcript_data, list):
            logger.info(f"Dĺžka listu: {len(transcript_data)}")
            if len(transcript_data) > 0:
                logger.info(f"Prvý prvok: {transcript_data[0]}")
        
        # Upravené spracovanie odpovede z API - očakávame, že môže vrátiť buď dict alebo list
        if isinstance(transcript_data, dict):
            # Pre prípad, že API vracia dict
            if video_id in transcript_data:
                # Odpoveď vo formáte {"video_id": {"transcript": [...]}}
                video_data = transcript_data[video_id]
                if isinstance(video_data, dict) and "transcript" in video_data:
                    transcript = video_data["transcript"]
                    transcript_segments.extend(transcript)
            else:
                # Skúšame nájsť prvý kľúč, ktorý obsahuje transkript
                for vid_id, video_data in transcript_data.items():
                    if isinstance(video_data, dict) and "transcript" in video_data:
                        transcript = video_data["transcript"]
                        transcript_segments.extend(transcript)
                        break
        elif isinstance(transcript_data, list):
            # Pre prípad, že API vracia list
            for item in transcript_data:
                if isinstance(item, dict):
                    # Skontrolujeme, či item obsahuje "tracks" pole s transkriptom
                    if "tracks" in item and isinstance(item["tracks"], list) and len(item["tracks"]) > 0:
                        for track in item["tracks"]:
                            if "transcript" in track and isinstance(track["transcript"], list):
                                transcript_segments.extend(track["transcript"])
                                logger.info(f"Našiel som transkript v tracks!")
                                break
                    # Alebo skontrolujeme, či položka sama obsahuje transkript
                    elif "transcript" in item and isinstance(item["transcript"], list):
                        transcript_segments.extend(item["transcript"])
        else:
            # Ak API vráti úplne iný formát, zalogujeme to pre debug
            logger.error(f"Neočakávaný formát odpovede: {type(transcript_data)}")
            await update.message.reply_text("Nastala chyba pri spracovaní transkriptu (neznámy formát odpovede).")
            return
        
        # Kontrola, či máme nejaké segmenty
        if not transcript_segments:
            logger.warning("Transkript neobsahuje žiadne segmenty.")
            await update.message.reply_text("Transkript neobsahuje žiadny text.")
            return
        
        logger.info(f"Počet segmentov: {len(transcript_segments)}")
        logger.info(f"Prvý segment: {transcript_segments[0] if transcript_segments else 'žiadny'}")
        
        # Teraz skontrolujeme, či segmenty majú správny formát
        valid_segments = []
        for segment in transcript_segments:
            if isinstance(segment, dict) and "text" in segment:
                valid_segments.append(segment)
            else:
                logger.warning(f"Ignorujem neplatný segment: {segment}")
        
        if not valid_segments:
            logger.warning("Žiadne platné segmenty s textom.")
            await update.message.reply_text("Nepodarilo sa nájsť žiadny text v transkripte.")
            return
        
        transcript_segments = valid_segments
        
        # Informácia o získaní transkriptu
        await update.message.reply_text("Transkript získaný, posielam text...")
        
        # Zostavenie textu transkriptu bez prekladu
        for segment in transcript_segments:
            if "text" in segment:
                transcript_text += segment["text"] + " "
        
        # Kontrola, či máme nejaký text
        if not transcript_text.strip():
            logger.warning("Po spracovaní segmentov je výsledný text prázdny.")
            await update.message.reply_text("Nepodarilo sa extrahovať text z transkriptu.")
            return
        
        logger.info(f"Dĺžka výsledného textu: {len(transcript_text)}")
        
        # Uloženie transkriptu do kontextu pre prípadnú sumarizáciu
        if not hasattr(context.user_data, "transcripts"):
            context.user_data["transcripts"] = {}
        context.user_data["transcripts"][video_id] = transcript_text
        
        # Rozdelenie transkriptu na menšie časti ak je príliš dlhý
        max_message_length = 4000  # Upravená hodnota podľa oficiálneho limitu Telegram API (4096 znakov)
        if len(transcript_text) <= max_message_length:
            # Pridáme tlačidlo pre sumarizáciu
            keyboard = [
                [InlineKeyboardButton("📝 Sumarizovať", callback_data=f"summarize_{video_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(transcript_text, reply_markup=reply_markup)
        else:
            # Odošleme informáciu o tom, že odpoveď bude rozdelená na viacero častí
            await update.message.reply_text(f"Transkript je dlhý ({len(transcript_text)} znakov), posielam ho po častiach.")
            
            # Rozdelíme text na menšie časti, ale rešpektujeme celé vety
            chunks = []
            current_chunk = ""
            
            # Rozdelíme text na vety
            sentences = re.split(r'([.!?]\s+)', transcript_text)
            
            # Spájame vety, až kým nedosiahneme limit
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                # Pridáme aj interpunkciu a medzeru, ak existuje
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                # Ak by pridanie novej vety prekročilo limit, vytvoríme nový chunk
                if len(current_chunk + sentence) > max_message_length:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = sentence
                    else:
                        # Ak je samotná veta dlhšia než limit, musíme ju rozdeliť
                        if len(sentence) > max_message_length:
                            words = sentence.split()
                            temp_chunk = ""
                            for word in words:
                                if len(temp_chunk + " " + word) > max_message_length:
                                    chunks.append(temp_chunk)
                                    temp_chunk = word
                                else:
                                    temp_chunk += " " + word if temp_chunk else word
                            if temp_chunk:
                                current_chunk = temp_chunk
                        else:
                            current_chunk = sentence
                else:
                    current_chunk += sentence
            
            # Pridáme posledný chunk, ak existuje
            if current_chunk:
                chunks.append(current_chunk)
            
            # Odošleme jednotlivé časti
            for i, chunk in enumerate(chunks):
                try:
                    # Pre poslednú časť pridáme tlačidlo sumarizácie
                    if i == len(chunks) - 1:
                        keyboard = [
                            [InlineKeyboardButton("📝 Sumarizovať", callback_data=f"summarize_{video_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(f"Časť {i+1}/{len(chunks)}:\n\n{chunk}", reply_markup=reply_markup)
                    else:
                        await update.message.reply_text(f"Časť {i+1}/{len(chunks)}:\n\n{chunk}")
                    
                    # Pridáme malú pauzu medzi správami, aby sme nepreťažili API
                    if i < len(chunks) - 1:
                        import asyncio
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Chyba pri odosielaní časti {i+1}: {e}")
                    await update.message.reply_text(f"Nastala chyba pri odosielaní časti {i+1}. Skúste požiadať o kratší úsek videa.")
                    break
    
    except Exception as e:
        logger.error(f"Chyba pri spracovaní transkriptu: {e}", exc_info=True)
        await update.message.reply_text("Nastala chyba pri spracovaní transkriptu.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spracovanie tlačidla pre sumarizáciu."""
    query = update.callback_query
    await query.answer()
    
    # Získanie ID videa z callback_data
    if query.data.startswith("summarize_"):
        video_id = query.data.replace("summarize_", "")
        
        # Kontrola, či máme uložený transkript pre toto video
        if not hasattr(context.user_data, "transcripts") or video_id not in context.user_data["transcripts"]:
            await query.edit_message_text(text="Nemám k dispozícii transkript pre toto video.")
            return
        
        # Získanie transkriptu
        transcript_text = context.user_data["transcripts"][video_id]
        
        # Informujeme používateľa, že prebiehka sumarizácia
        await query.edit_message_text(text="Sumarizujem transkript, čakaj prosím...")
        
        # Sumarizácia textu
        summary = await summarize_text(transcript_text)
        
        # Odoslanie sumarizovaného textu
        if len(summary) <= 4000:
            await query.edit_message_text(text=f"📝 Sumarizácia:\n\n{summary}")
        else:
            # Ak je sumarizácia príliš dlhá, rozdelíme ju
            await query.edit_message_text(text="Sumarizácia je dlhá, posielam ju ako novú správu...")
            await query.message.reply_text(summary[:4000])
            if len(summary) > 4000:
                await query.message.reply_text(summary[4000:])

def main():
    """Spustí bota."""
    # Vytvorenie aplikácie
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Pridanie handleriv
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_youtube_url))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Spustenie bota
    application.run_polling()

if __name__ == '__main__':
    main() 