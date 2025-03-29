# YouTube Transkript

Webová aplikácia na získavanie a prácu s YouTube transkriptmi videí. Umožňuje extrahovať transkript, vytvárať sumarizácie a generovať podcasty zo slovenských videí.

## Funkcie

- Extrahovanie transkriptov z YouTube videí
- Sumarizácia textov (stručná aj podrobná)
- Konverzia textu na audio (podcast)
- Odosielanie podcastov na Telegram
- Preklad F1 rádiových komunikácií (špeciálna sekcia)

## Technológie

- Python (Flask)
- JavaScript
- HTML/CSS
- OpenAI API
- YouTube Transcript API
- Text-to-Speech (gTTS)
- Telegram API

## Online verzia

Aplikácia je dostupná online na adrese: [YouTube Transkript](https://youtube-transkript.vercel.app)

## Lokálne spustenie

1. Nainštalujte Python 3.8+
2. Nainštalujte závislosti: `pip install -r requirements.txt`
3. Spustite aplikáciu: `python web_app.py`
4. Otvorte prehliadač na adrese: `http://127.0.0.1:5000/`

## Nasadenie na Vercel

1. **Vytvorte účet na Vercel**
   - Zaregistrujte sa na [Vercel](https://vercel.com)

2. **Pripravte projekt pre Vercel**
   - Uistite sa, že máte tieto súbory:
     - `vercel.json` - konfigurácia pre Vercel
     - `requirements.txt` - zoznam Python závislostí
     - `web_app.py` - hlavný súbor aplikácie

3. **Nahranie na GitHub**
   - Vytvorte nové GitHub repozitár
   - Nahrajte všetky súbory projektu

4. **Nasadenie na Vercel**
   - V Dashboarde Vercel kliknite na "Add New Project"
   - Importujte projekt z GitHub repozitára
   - Nastavte environment variables (ak sú potrebné):
     - `SECRET_KEY` - tajný kľúč pre Flask
     - `YOUTUBE_TRANSCRIPT_API_TOKEN` - API token (ak používate)
     - `OPENAI_API_KEY` - OpenAI API kľúč
   - Kliknite na "Deploy"

5. **Aktualizácia nasadenia**
   - Po nahraní zmien do GitHub repozitára Vercel automaticky aktualizuje nasadenie

## Prispievanie

Príspevky sú vítané! Pre väčšie zmeny, prosím, najprv otvorte issue pre diskusiu o navrhovaných zmenách.

## Licencia

[MIT](https://choosealicense.com/licenses/mit/) 