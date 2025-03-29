#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from flask import Flask, render_template, request, flash, session, redirect, url_for, jsonify, make_response
try:
    from config import YOUTUBE_TRANSCRIPT_API_TOKEN # Importujeme len token
except ImportError:
    YOUTUBE_TRANSCRIPT_API_TOKEN = None # Fallback pre nasadenie
from youtube_transcript_bot import extract_video_id, get_transcript # Importujeme funkcie z bot skriptu
from translator import translator # Pridaný import prekladača
import time  # Pridaný import pre timestamp
import datetime  # Pre formátovanie dátumu
import requests  # Pre HTTP požiadavky na Telegram API
import os  # Pre prácu so súbormi

# Nastavenie logovania (podobné ako v botovi)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializácia Flask aplikácie
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nejake_velmi_tajne_heslo') # Používame environment variable alebo fallback

# Globálne premenné pre F1 prekladač
f1_translations = []
MAX_F1_TRANSLATIONS = 20  # Maximálny počet prekladov, ktoré sa uložia

# Filter pre formátovanie Unix timestamp na čitateľný dátum
@app.template_filter('datetime')
def format_datetime(value):
    if not value:
        return ""
    dt = datetime.datetime.fromtimestamp(value)
    return dt.strftime("%d.%m.%Y %H:%M:%S")

# Hlavná stránka s formulárom
@app.route('/', methods=['GET'])
def index():
    """Zobrazí hlavnú stránku s formulárom."""
    # Inicializácia histórie v session ak ešte neexistuje
    if 'history' not in session:
        session['history'] = []
    
    return render_template('index.html', history=session['history'], f1_translations=f1_translations)

# Spracovanie formulára
@app.route('/process', methods=['POST'])
def process_url():
    """Spracuje odoslaný YouTube URL."""
    youtube_url = request.form.get('youtube_url')
    
    if not youtube_url:
        flash("Prosím, zadajte YouTube URL.", "error")
        return render_template('index.html', history=session.get('history', []), f1_translations=f1_translations)

    # Kontrola, či ide o YouTube URL (jednoduchá)
    if "youtube" not in youtube_url and "youtu.be" not in youtube_url:
        flash("Zadaný text nevyzerá ako platná YouTube URL.", "error")
        return render_template('index.html', submitted_url=youtube_url, history=session.get('history', []), f1_translations=f1_translations)

    # Extrahovanie Video ID
    video_id = extract_video_id(youtube_url)
    if not video_id:
        flash("Nepodarilo sa extrahovať Video ID z URL. Skontrolujte odkaz.", "error")
        return render_template('index.html', submitted_url=youtube_url, history=session.get('history', []), f1_translations=f1_translations)

    logger.info(f"Spracovávam Video ID: {video_id}")
    
    transcript_text = ""
    error_message = None
    
    try:
        # Získanie transkriptu - voláme asynchrónnu funkciu synchrónne
        # Poznámka: Pre produkčné nasadenie by bolo lepšie použiť ASGI server (napr. Uvicorn, Hypercorn)
        # a async Flask, ale pre jednoduchosť použijeme asyncio.run()
        transcript_data = asyncio.run(get_transcript(video_id))

        if not transcript_data:
            error_message = "Nepodarilo sa získať transkript. Video možno nemá titulky alebo nastala chyba API."
        else:
            # Spracovanie transkriptu (podobne ako v botovi, ale zjednodušené)
            transcript_segments = []
            if isinstance(transcript_data, dict):
                 # Skúšame nájsť transkript v odpovedi
                for vid_id, video_data in transcript_data.items():
                    if isinstance(video_data, dict) and "transcript" in video_data:
                        transcript = video_data["transcript"]
                        transcript_segments.extend(transcript)
                        break
            elif isinstance(transcript_data, list):
                for item in transcript_data:
                    if isinstance(item, dict):
                        if "tracks" in item and isinstance(item["tracks"], list) and len(item["tracks"]) > 0:
                            for track in item["tracks"]:
                                if "transcript" in track and isinstance(track["transcript"], list):
                                    transcript_segments.extend(track["transcript"])
                                    break # Predpokladáme, že prvý nájdený je ten správny
                        elif "transcript" in item and isinstance(item["transcript"], list):
                            transcript_segments.extend(item["transcript"])

            if not transcript_segments:
                 error_message = "Transkript bol získaný, ale neobsahuje žiadne textové segmenty."
            else:
                # Zostavenie textu
                for segment in transcript_segments:
                    if isinstance(segment, dict) and "text" in segment:
                        transcript_text += segment["text"] + " "
                
                transcript_text = transcript_text.strip()

                if not transcript_text:
                    error_message = "Transkript neobsahuje žiadny čitateľný text."
                else:
                    # Voliteľný preklad:
                    enable_translation = False # Nastav na True, ak chceš prekladať
                    if enable_translation and translator.is_available():
                        logger.info("Prekladám text...")
                        try:
                           translated = translator.translate_text(transcript_text)
                           if translated: # Skontroluj, či preklad vrátil nejaký text
                               transcript_text = translated
                           else:
                               logger.warning("Preklad vrátil prázdny reťazec, použije sa originálny text.")
                        except Exception as translate_err:
                            logger.error(f"Chyba pri preklade: {translate_err}")
                            flash("Nastala chyba počas prekladu textu.", "warning") # Informuj užívateľa
                    elif enable_translation and not translator.is_available():
                        logger.warning("Prekladač nie je dostupný (deep-translator nie je nainštalovaný?), vraciam originálny text.")
                        flash("Preklad nie je dostupný.", "warning")

                    # Získaj názov videa pre históriu z prvých slov transkriptu
                    # Vyberieme prvých 5-8 slov na vytvorenie výstižného názvu
                    words = transcript_text.split()
                    if len(words) > 8:
                        video_title = " ".join(words[:8]) + "..."
                    else:
                        video_title = " ".join(words) + "..."
                    
                    # Obmedzíme dĺžku názvu na max 50 znakov
                    if len(video_title) > 50:
                        video_title = video_title[:47] + "..."
                    
                    # Pridaj do histórie
                    if 'history' not in session:
                        session['history'] = []
                    
                    # Kontrola, či už URL nie je v histórii
                    for item in session['history']:
                        if item['url'] == youtube_url:
                            # Ak áno, odstráň ho (neskôr pridáme na začiatok)
                            session['history'].remove(item)
                            break
                    
                    # Pridaj nový záznam na začiatok histórie
                    new_entry = {
                        'url': youtube_url,
                        'video_id': video_id,
                        'title': video_title
                    }
                    
                    # Pridaj na začiatok a obmedz dĺžku histórie na 10 položiek
                    session['history'].insert(0, new_entry)
                    if len(session['history']) > 10:
                        session['history'] = session['history'][:10]
                    
                    # Aktualizuj session
                    session.modified = True

    except Exception as e:
        logger.error(f"Chyba pri spracovaní URL {youtube_url} (Video ID: {video_id}): {e}", exc_info=True)
        error_message = f"Nastala neočakávaná chyba pri spracovaní: {e}"

    if error_message:
        flash(error_message, "error")
        
    return render_template('index.html', transcript=transcript_text, submitted_url=youtube_url, history=session.get('history', []), f1_translations=f1_translations)

# Nový endpoint pre F1 prekladače
@app.route('/f1translator/receive', methods=['POST'])
def receive_f1_translation():
    """Endpoint pre prijímanie preložených textov z F1 prekladača."""
    global f1_translations
    
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Žiadne dáta neboli prijaté."}), 400
            
        english_text = data.get('english')
        slovak_text = data.get('slovak')
        timestamp = data.get('timestamp', time.time())
        
        if not english_text or not slovak_text:
            return jsonify({"status": "error", "message": "Chýbajú povinné polia."}), 400
            
        # Pridaj preklad do zoznamu prekladov
        translation_entry = {
            "english": english_text,
            "slovak": slovak_text,
            "timestamp": timestamp
        }
        
        # Pridaj na začiatok zoznamu
        f1_translations.insert(0, translation_entry)
        
        # Obmedz veľkosť zoznamu
        if len(f1_translations) > MAX_F1_TRANSLATIONS:
            f1_translations = f1_translations[:MAX_F1_TRANSLATIONS]
            
        logger.info(f"Prijatý nový F1 preklad: {english_text[:30]}... -> {slovak_text[:30]}...")
        
        return jsonify({"status": "success", "message": "Preklad bol úspešne prijatý."}), 200
        
    except Exception as e:
        logger.error(f"Chyba pri spracovaní F1 prekladu: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Nastala chyba pri spracovaní: {str(e)}"}), 500

# Stránka s F1 prekladmi
@app.route('/f1translations', methods=['GET'])
def show_f1_translations():
    """Zobrazí stránku s prekladmi z F1 vysielačiek."""
    return render_template('f1translations.html', f1_translations=f1_translations)

# API pre získanie F1 prekladov v JSON formáte
@app.route('/api/f1translations', methods=['GET'])
def get_f1_translations():
    """Vráti F1 preklady v JSON formáte."""
    return jsonify({
        "translations": f1_translations,
        "count": len(f1_translations)
    })

# Endpoint pre sumarizáciu textu
@app.route('/summarize', methods=['POST'])
def summarize():
    """Endpoint pre sumarizáciu textu."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Chýba text na sumarizáciu."}), 400
            
        text = data['text']
        if not text or len(text.strip()) < 10:
            return jsonify({"error": "Text je príliš krátky na sumarizáciu."}), 400
        
        # Zavoláme funkciu na sumarizáciu z prekladača
        summary = translator.summarize_text(text)
        
        if not summary:
            return jsonify({"error": "Nepodarilo sa vytvoriť sumarizáciu."}), 500
            
        logger.info(f"Vykonaná sumarizácia textu (dĺžka textu: {len(text)} znakov, dĺžka súhrnu: {len(summary)} znakov)")
        
        return jsonify({"summary": summary}), 200
        
    except Exception as e:
        logger.error(f"Chyba pri sumarizácii textu: {e}", exc_info=True)
        return jsonify({"error": f"Nastala chyba pri sumarizácii: {str(e)}"}), 500

# Endpoint pre podrobnú sumarizáciu textu
@app.route('/detailed_summarize', methods=['POST'])
def detailed_summarize():
    """Endpoint pre podrobnú sumarizáciu textu."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Chýba text na podrobnú sumarizáciu."}), 400
            
        text = data['text']
        if not text or len(text.strip()) < 10:
            return jsonify({"error": "Text je príliš krátky na podrobnú sumarizáciu."}), 400
        
        # Zavoláme funkciu na podrobnú sumarizáciu z prekladača
        summary = translator.detailed_summarize_text(text)
        
        if not summary:
            return jsonify({"error": "Nepodarilo sa vytvoriť podrobnú sumarizáciu."}), 500
            
        logger.info(f"Vykonaná podrobná sumarizácia textu (dĺžka textu: {len(text)} znakov, dĺžka súhrnu: {len(summary)} znakov)")
        
        return jsonify({"summary": summary}), 200
        
    except Exception as e:
        logger.error(f"Chyba pri podrobnej sumarizácii textu: {e}", exc_info=True)
        return jsonify({"error": f"Nastala chyba pri podrobnej sumarizácii: {str(e)}"}), 500

# Endpoint pre text-to-speech
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    """Endpoint pre prevod textu na reč."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Chýba text na prevod na reč."}), 400
            
        text = data['text']
        if not text or len(text.strip()) < 2:
            return jsonify({"error": "Text je príliš krátky na prevod na reč."}), 400
        
        # Voliteľné parametre
        voice = data.get('voice', 'alloy')
        style = data.get('style', 'slovak')  # Predvolene použijeme slovenský štýl
        
        # Dostupné hlasy a štýly
        available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        available_styles = ["default", "slovak", "clear", "friendly", "formal"]
        
        # Validácia parametrov
        if voice not in available_voices:
            voice = "alloy"  # Predvolený hlas
        
        if style not in available_styles:
            style = "slovak"  # Predvolený štýl
        
        # Zavoláme funkciu na prevod textu na reč z prekladača
        audio_data = translator.text_to_speech(text, voice, style)
        
        if not audio_data:
            return jsonify({"error": "Nepodarilo sa vytvoriť hlasovú nahrávku."}), 500
            
        logger.info(f"Vykonaný prevod textu na reč (dĺžka textu: {len(text)} znakov, hlas: {voice}, štýl: {style})")
        
        # Vytvoríme odpoveď s audio súborom
        response = make_response(audio_data)
        response.headers.set('Content-Type', 'audio/mpeg')
        response.headers.set('Content-Disposition', 'attachment', filename='speech.mp3')
        
        return response
        
    except Exception as e:
        logger.error(f"Chyba pri prevode textu na reč: {e}", exc_info=True)
        return jsonify({"error": f"Nastala chyba pri prevode textu na reč: {str(e)}"}), 500

# Nový endpoint pre odoslanie audio súboru do Telegram bota
@app.route('/send_podcast_to_telegram', methods=['POST'])
def send_podcast_to_telegram():
    """Endpoint pre odoslanie podcastu do Telegram bota."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({"error": "Chýba text na prevod na reč."}), 400
            
        text = data['text']
        if not text or len(text.strip()) < 2:
            return jsonify({"error": "Text je príliš krátky na prevod na reč."}), 400
        
        # Voliteľné parametre
        voice = data.get('voice', 'alloy')
        style = data.get('style', 'slovak')
        chat_id = data.get('chat_id', '1175143262') # Predvolený chat ID (ak nie je špecifikovaný, použijeme 1175143262)
        
        # Dostupné hlasy a štýly
        available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        available_styles = ["default", "slovak", "clear", "friendly", "formal"]
        
        # Validácia parametrov
        if voice not in available_voices:
            voice = "alloy"  # Predvolený hlas
        
        if style not in available_styles:
            style = "slovak"  # Predvolený štýl
        
        # Telegram bot token
        TELEGRAM_BOT_TOKEN = "7835385356:AAECh9m0uwk9gTySrZRKD_k7HFpdRZM0Mco"
        
        # Zavoláme funkciu na prevod textu na reč z prekladača
        audio_data = translator.text_to_speech(text, voice, style)
        
        if not audio_data:
            return jsonify({"error": "Nepodarilo sa vytvoriť hlasovú nahrávku."}), 500
            
        # Dočasne uložíme súbor
        temp_file_path = "temp_podcast.mp3"
        with open(temp_file_path, "wb") as f:
            f.write(audio_data)
        
        # Odošleme audio súbor do Telegram bota
        files = {
            'audio': ('podcast.mp3', open(temp_file_path, 'rb'), 'audio/mpeg')
        }
        
        caption = "Podcast vygenerovaný z transkriptu YouTube videa"
        
        # Odoslanie audio súboru cez Telegram Bot API
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
        response = requests.post(
            telegram_url,
            data={
                'chat_id': chat_id,
                'caption': caption,
                'title': 'YouTube podcast'
            },
            files=files
        )
        
        # Zmažeme dočasný súbor
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        # Skontrolujeme odpoveď z Telegram API
        telegram_response = response.json()
        
        if response.status_code == 200 and telegram_response.get('ok'):
            logger.info(f"Podcast úspešne odoslaný do Telegram bota (chat_id: {chat_id})")
            return jsonify({
                "success": True,
                "message": "Podcast bol úspešne odoslaný do Telegram bota",
                "telegram_response": telegram_response
            }), 200
        else:
            error_msg = telegram_response.get('description', 'Neznáma chyba')
            logger.error(f"Chyba pri odosielaní podcastu do Telegram bota: {error_msg}")
            return jsonify({
                "success": False,
                "error": f"Chyba pri odosielaní podcastu: {error_msg}",
                "telegram_response": telegram_response
            }), 400
        
    except Exception as e:
        logger.error(f"Chyba pri odosielaní podcastu do Telegram bota: {e}", exc_info=True)
        return jsonify({"error": f"Nastala chyba pri odosielaní podcastu: {str(e)}"}), 500

# Prezbrojovanie histórie - opätovné spracovanie URL z histórie
@app.route('/replay/<video_id>', methods=['GET'])
def replay_from_history(video_id):
    """Opätovne spracuje URL z histórie podľa video_id."""
    # Nájdi URL v histórii
    found_url = None
    if 'history' in session:
        for item in session['history']:
            if item['video_id'] == video_id:
                found_url = item['url']
                break
    
    if found_url:
        # Manuálne vytvori POST request
        return process_url_with_form_data(found_url)
    else:
        flash("Záznam v histórii sa nenašiel.", "error")
        return redirect(url_for('index'))

def process_url_with_form_data(url):
    """Pomocná funkcia na simuláciu POST požiadavky s URL."""
    # Toto je len jednoduchý hack - v reálnej aplikácii by bolo lepšie
    # použiť redirect s POST parametrom alebo inú metódu
    class MockForm:
        def get(self, key):
            return url if key == 'youtube_url' else None
    
    request.form = MockForm()
    return process_url()

# Nový endpoint pre získanie Telegram Chat ID
@app.route('/get_telegram_chat_id', methods=['POST'])
def get_telegram_chat_id():
    """Endpoint pre získanie Telegram Chat ID pre zadaného používateľa alebo skupinu."""
    try:
        data = request.json
        if not data or 'username' not in data:
            return jsonify({"error": "Chýba používateľské meno alebo ID skupiny."}), 400
            
        username = data.get('username')
        if not username:
            return jsonify({"error": "Používateľské meno nemôže byť prázdne."}), 400
        
        # Telegram bot token
        TELEGRAM_BOT_TOKEN = "7835385356:AAECh9m0uwk9gTySrZRKD_k7HFpdRZM0Mco"
        
        # Kontrola, či je to platný formát Telegram mena alebo ID
        if username.startswith('@'):
            # Je to používateľské meno
            username = username[1:]  # Odstránime @ zo začiatku
        
        # Skúsime pomocou getChat API metódy získať ID
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChat"
        
        # Skúsime najprv ako chat_id (ak je to číselná hodnota)
        try_as_id = username.lstrip('-')
        if try_as_id.isdigit():
            # Ak je to číslo (ID), skúsime priamo ako chat_id
            response = requests.post(
                telegram_url,
                data={"chat_id": username}
            )
            
            telegram_response = response.json()
            
            if response.status_code == 200 and telegram_response.get('ok'):
                chat_info = telegram_response.get('result', {})
                chat_id = chat_info.get('id')
                chat_type = chat_info.get('type')
                chat_title = chat_info.get('title', 'Neznámy názov')
                
                return jsonify({
                    "success": True,
                    "message": f"Chat ID úspešne nájdené",
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "chat_title": chat_title
                }), 200
        
        # Skúsime ako používateľské meno
        response = requests.post(
            telegram_url,
            data={"chat_id": f"@{username}"}
        )
        
        telegram_response = response.json()
        
        if response.status_code == 200 and telegram_response.get('ok'):
            chat_info = telegram_response.get('result', {})
            chat_id = chat_info.get('id')
            chat_type = chat_info.get('type')
            chat_title = chat_info.get('title', chat_info.get('first_name', 'Neznámy názov'))
            
            return jsonify({
                "success": True,
                "message": f"Chat ID úspešne nájdené",
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_title": chat_title
            }), 200
        else:
            error_msg = telegram_response.get('description', 'Nepodarilo sa nájsť zadaný chat.')
            
            # Poskytneme pomoc používateľovi
            help_message = """
            Na získanie Telegram Chat ID:
            1. Pre súkromnú konverzáciu:
               - Pridajte si bot do kontaktov (@getmyid_bot)
               - Napíšte mu /start a získate svoje ID
            
            2. Pre skupinu:
               - Pridajte bot do skupiny 
               - Napíšte @getmyid_bot do skupiny
               - Bot vám vráti ID skupiny
               
            3. Pre kanál:
               - Pridajte bot ako administrátora kanálu
               - Odošlite správu v kanáli a získate ID
            """
            
            return jsonify({
                "success": False,
                "error": f"Nepodarilo sa získať Chat ID: {error_msg}",
                "help": help_message
            }), 400
        
    except Exception as e:
        logger.error(f"Chyba pri získavaní Telegram Chat ID: {e}", exc_info=True)
        return jsonify({"error": f"Nastala chyba pri získavaní Chat ID: {str(e)}"}), 500

# WSGI handler pre Vercel - TOTO TREBA PRE VERCEL
app = app 