#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Pomocné funkcie pre prácu s YouTube transkriptmi.
Extrahuje sa sem len potrebná funkcionalita z youtube_transcript_bot.py,
aby sme nemuseli importovať celý modul, ktorý závisí od python-telegram-bot.
"""

import re
import json
import aiohttp
import asyncio
import logging
import requests
import os
from typing import Dict, Any, List, Optional, Union

# Nastavenie logovania
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Najprv skúsime získať token z prostredia (Vercel), potom z .env, a nakoniec z config.py
YOUTUBE_TRANSCRIPT_API_TOKEN = os.environ.get('YOUTUBE_TRANSCRIPT_API_TOKEN')

# Ak nie je v prostredí, skúsime z config.py
if not YOUTUBE_TRANSCRIPT_API_TOKEN:
    try:
        from config import YOUTUBE_TRANSCRIPT_API_TOKEN  # Importujeme token
    except ImportError:
        logger.warning("Nepodarilo sa importovať YOUTUBE_TRANSCRIPT_API_TOKEN z config.py")
        YOUTUBE_TRANSCRIPT_API_TOKEN = None  # Fallback

# Kontrola, či máme token
if not YOUTUBE_TRANSCRIPT_API_TOKEN:
    logger.warning("YOUTUBE_TRANSCRIPT_API_TOKEN nie je nastavený. Získavanie transkriptov nebude fungovať.")


def extract_video_id(url: str) -> Optional[str]:
    """
    Extrahuje YouTube video ID z URL.
    
    Args:
        url: YouTube URL v rôznych formátoch
        
    Returns:
        Video ID alebo None, ak sa nepodarilo extrahovať
    """
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    
    youtube_regex_match = re.match(youtube_regex, url)
    
    if youtube_regex_match:
        return youtube_regex_match.group(6)
    
    return None


async def get_transcript(video_id: str) -> Dict[str, Any]:
    """
    Získa transkript pre zadané YouTube video ID.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Slovník obsahujúci transkript alebo chybovú správu
    """
    try:
        url = "https://www.youtube-transcript.io/api/transcripts"
        headers = {
            "Authorization": f"Basic {YOUTUBE_TRANSCRIPT_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {"ids": [video_id]}
        
        # Asynchrónny HTTP request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Chyba pri získavaní transkriptu: {response.status} - {await response.text()}")
                    return None
                
                return await response.json()
    
    except Exception as e:
        logger.error(f"Chyba pri získavaní transkriptu: {e}")
        return None


def get_transcript_sync(video_id: str) -> Dict[str, Any]:
    """
    Synchrónna verzia funkcie get_transcript.
    Používa sa, keď asyncio nie je dostupné.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Slovník obsahujúci transkript alebo chybovú správu
    """
    try:
        url = "https://www.youtube-transcript.io/api/transcripts"
        headers = {
            "Authorization": f"Basic {YOUTUBE_TRANSCRIPT_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {"ids": [video_id]}
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            logger.error(f"Chyba pri získavaní transkriptu: {response.status_code} - {response.text}")
            return None
            
        return response.json()
        
    except Exception as e:
        logger.error(f"Chyba pri získavaní transkriptu: {e}")
        return None 