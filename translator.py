#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Pomocný modul pre preklad transkriptov z angličtiny do slovenčiny.
Poznámka: Pre plnú funkčnosť tohto modulu je potrebné mať nainštalovaný
balíček pre preklad - napr. deep-translator alebo openai.
"""

import logging
import configparser
from typing import List, Dict, Any

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logging.warning("Balíček 'deep-translator' nie je nainštalovaný. Preklad nebude dostupný.")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("Balíček 'openai' nie je nainštalovaný. OpenAI preklad nebude dostupný.")

class TranscriptTranslator:
    """Trieda pre preklad transkriptov z angličtiny do slovenčiny."""
    
    def __init__(self):
        """Inicializácia prekladača."""
        self.translator = None
        self.openai_client = None
        self.openai_available = False
        
        # Inicializácia Google prekladača
        if TRANSLATOR_AVAILABLE:
            try:
                self.translator = GoogleTranslator(source='en', target='sk')
            except Exception as e:
                logging.error(f"Chyba pri inicializácii prekladača: {e}")
        
        # Inicializácia OpenAI prekladača
        if OPENAI_AVAILABLE:
            try:
                # Načítanie OpenAI API kľúča z config.ini alebo environment premennej
                api_key = None
                
                # 1. Skúsime načítať z config.ini
                try:
                    config = configparser.ConfigParser()
                    config.read('config.ini')
                    api_key = config.get('api', 'openai_api_key', fallback=None)
                    if api_key:
                        logging.info("OpenAI API kľúč načítaný z config.ini")
                except Exception as config_err:
                    logging.warning(f"Nepodarilo sa načítať OpenAI API kľúč z config.ini: {config_err}")
                
                # 2. Ak nemáme kľúč z config.ini, skúsime environment premennú
                if not api_key:
                    import os
                    api_key = os.environ.get('OPENAI_API_KEY')
                    if api_key:
                        logging.info("OpenAI API kľúč načítaný z environment premennej")
                
                if api_key:
                    openai.api_key = api_key
                    self.openai_client = openai.OpenAI(api_key=api_key)
                    self.openai_available = True
                    logging.info("OpenAI prekladač úspešne inicializovaný")
                else:
                    logging.warning("OpenAI API kľúč nie je nastavený ani v config.ini ani v environment premennej")
            except Exception as e:
                logging.error(f"Chyba pri inicializácii OpenAI klienta: {e}")
    
    def is_available(self) -> bool:
        """Vráti True, ak je aspoň jeden prekladač dostupný."""
        return self.translator is not None or self.openai_available
    
    def translate_text(self, text: str) -> str:
        """Preloží text z angličtiny do slovenčiny."""
        if not self.is_available():
            return text
        
        # Skúsime preklad cez OpenAI ak je dostupný
        if self.openai_available:
            try:
                return self._translate_with_openai(text)
            except Exception as e:
                logging.error(f"Chyba pri OpenAI preklade textu: {e}")
                # Fallback na Google prekladač
        
        # Ak OpenAI nie je dostupný alebo zlyhalo, skúsime Google prekladač
        if self.translator:
            try:
                # Rozdelíme text na menšie časti, aby sa zmestil do limitu Google Translator
                max_chunk_size = 5000
                if len(text) <= max_chunk_size:
                    return self.translator.translate(text)
                
                # Rozdelenie textu na vety a preklad po častiach
                chunks = []
                current_chunk = ""
                for sentence in text.split('. '):
                    if len(current_chunk) + len(sentence) + 2 <= max_chunk_size:
                        current_chunk += sentence + '. '
                    else:
                        chunks.append(current_chunk)
                        current_chunk = sentence + '. '
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                translated_text = ""
                for chunk in chunks:
                    translated_text += self.translator.translate(chunk) + " "
                    
                return translated_text.strip()
                
            except Exception as e:
                logging.error(f"Chyba pri Google preklade textu: {e}")
        
        # Ak sme tu, obidva preklady zlyhali
        return text
    
    def _translate_with_openai(self, text: str) -> str:
        """Preloží text pomocou OpenAI API."""
        if not self.openai_client:
            return text
        
        try:
            # Rozdelenie textu na menšie časti pre OpenAI
            max_chunk_size = 4000  # OpenAI má vyšší limit ako Google
            
            if len(text) <= max_chunk_size:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Si prekladateľ špecializujúci sa na preklad z angličtiny do slovenčiny. Preklad by mal byť plynulý a zachovávať význam a štýl originálu. DÔLEŽITÉ: Tvoja odpoveď musí vždy začínať priamo prekladom bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií ako 'Samozrejme', 'Prosím', 'Tu je preklad', 'Preklad:', atď. Nikdy nepridávaj takéto úvodné frázy."},
                        {"role": "user", "content": f"Preložte nasledujúci text z angličtiny do slovenčiny. Iba preklad, žiadne dodatočné vysvetlenia alebo úvody:\n\n{text}"}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                return response.choices[0].message.content.strip()
            
            # Pre dlhšie texty ich rozdelíme na menšie časti
            chunks = []
            current_chunk = ""
            for sentence in text.split('. '):
                if len(current_chunk) + len(sentence) + 2 <= max_chunk_size:
                    current_chunk += sentence + '. '
                else:
                    chunks.append(current_chunk)
                    current_chunk = sentence + '. '
            
            if current_chunk:
                chunks.append(current_chunk)
            
            translated_text = ""
            for chunk in chunks:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Si prekladateľ špecializujúci sa na preklad z angličtiny do slovenčiny. Preklad by mal byť plynulý a zachovávať význam a štýl originálu. DÔLEŽITÉ: Tvoja odpoveď musí vždy začínať priamo prekladom bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií ako 'Samozrejme', 'Prosím', 'Tu je preklad', 'Preklad:', atď. Nikdy nepridávaj takéto úvodné frázy."},
                        {"role": "user", "content": f"Preložte nasledujúci text z angličtiny do slovenčiny. Iba preklad, žiadne dodatočné vysvetlenia alebo úvody:\n\n{chunk}"}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                translated_text += response.choices[0].message.content.strip() + " "
            
            return translated_text.strip()
            
        except Exception as e:
            logging.error(f"Chyba pri OpenAI preklade: {e}")
            raise
    
    def summarize_text(self, text: str) -> str:
        """Sumarizuje text pomocou OpenAI API."""
        if not self.openai_available:
            return "Sumarizácia nie je dostupná - OpenAI API nie je nakonfigurované."
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Si asistent špecializujúci sa na sumarizáciu textov. Tvojou úlohou je vytvoriť výstižnú a informatívnu sumarizáciu poskytnutého textu v slovenčine. Zachovaj kľúčové myšlienky, fakty a hlavné body. DÔLEŽITÉ: Tvoja odpoveď musí vždy začínať priamo sumarizáciou bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií ako 'Samozrejme', 'Prosím', 'Tu je sumarizácia', 'Sumarizácia:', atď. Nikdy nepridávaj takéto úvodné frázy."},
                    {"role": "user", "content": f"Sumarizuj nasledujúci text v slovenčine bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií:\n\n{text}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"Chyba pri sumarizácii textu: {e}")
            return f"Chyba pri sumarizácii textu: {str(e)}"
    
    def detailed_summarize_text(self, text: str) -> str:
        """Vytvorí podrobnú sumarizáciu textu pomocou OpenAI API s limitom 4000 tokenov."""
        if not self.openai_available:
            return "Podrobná sumarizácia nie je dostupná - OpenAI API nie je nakonfigurované."
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Si asistent špecializujúci sa na podrobnú sumarizáciu textov. Tvojou úlohou je vytvoriť komplexnú, informatívnu a podrobnú sumarizáciu poskytnutého textu v slovenčine. Zachovaj všetky dôležité detaily, kľúčové myšlienky, fakty a hlavné body. Rozdeľ text do tematických celkov s podnadpismi, ak je to vhodné. DÔLEŽITÉ: Tvoja odpoveď musí vždy začínať priamo sumarizáciou bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií ako 'Samozrejme', 'Prosím', 'Tu je sumarizácia', 'Sumarizácia:', atď. Nikdy nepridávaj takéto úvodné frázy."},
                    {"role": "user", "content": f"Vytvor podrobnú sumarizáciu nasledujúceho textu v slovenčine bez akýchkoľvek úvodných fráz alebo zdvorilostných formulácií. Sumarizácia by mala byť obsiahla a detailná, zachyť čo najviac relevantných informácií:\n\n{text}"}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"Chyba pri podrobnej sumarizácii textu: {e}")
            return f"Chyba pri podrobnej sumarizácii textu: {str(e)}"
    
    def text_to_speech(self, text: str, voice: str = "alloy", style: str = "default") -> bytes:
        """Prevádza text na reč pomocou OpenAI API.
        
        Args:
            text: Text, ktorý sa má previesť na reč
            voice: Hlas, ktorý sa má použiť (alloy, echo, fable, onyx, nova, shimmer)
            style: Štýl výslovnosti (default, slovak, clear, friendly, formal)
            
        Returns:
            Zvukový súbor vo formáte bytes
        """
        if not self.openai_available:
            logging.error("Text-to-speech nie je dostupný - OpenAI API nie je nakonfigurované.")
            return None
        
        # Dostupné hlasy
        AVAILABLE_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in AVAILABLE_VOICES:
            logging.warning(f"Neplatný hlas: {voice}, použije sa predvolený hlas 'alloy'")
            voice = "alloy"
        
        # Štýly pre inštrukcie hlasu
        VOICE_STYLES = {
            "default": "Hovor prirodzene.",
            "slovak": "Hovor ako rodený Slovák s výbornou výslovnosťou slovenčiny.",
            "clear": "Hovor veľmi jasne a artikuluj každé slovo, najmä slovenské znaky ako ď, ť, ň, ľ, š, č, ž.",
            "friendly": "Hovor priateľským a vrelým tónom.",
            "formal": "Hovor formálne a profesionálne."
        }
        
        if style not in VOICE_STYLES:
            logging.warning(f"Neplatný štýl: {style}, použije sa predvolený štýl 'default'")
            style = "default"
        
        try:
            # Maximálny počet znakov pre jeden vstup do OpenAI API
            MAX_INPUT_CHARS = 4000
            
            # Ak text presahuje maximálnu dĺžku, skrátime ho
            if len(text) > MAX_INPUT_CHARS:
                logging.warning(f"Text je príliš dlhý ({len(text)} znakov). Bude skrátený na {MAX_INPUT_CHARS} znakov.")
                text = text[:MAX_INPUT_CHARS]
            
            # Pridanie inštrukcie pre štýl výslovnosti ako prefix k textu
            voice_style = VOICE_STYLES[style]
            if style != "default":
                styled_text = f"{voice_style}\n\n{text}"
            else:
                styled_text = text
            
            # Generovanie hlasovej správy pomocou OpenAI TTS API
            speech_response = self.openai_client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=styled_text,
                response_format="mp3"
            )
            
            # Získanie audio dát
            audio_data = speech_response.content
            
            return audio_data
            
        except Exception as e:
            logging.error(f"Chyba pri prevode textu na reč: {e}")
            return None
    
    def translate_transcript(self, transcript: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Preloží všetky textové časti transkriptu."""
        if not self.is_available():
            return transcript
        
        try:
            for segment in transcript:
                if "text" in segment:
                    segment["text"] = self.translate_text(segment["text"])
            return transcript
        except Exception as e:
            logging.error(f"Chyba pri preklade transkriptu: {e}")
            return transcript


# Inicializácia globálneho prekladača
translator = TranscriptTranslator() 