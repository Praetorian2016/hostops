import os
import json
import time
from google import genai
from google.genai import types

def extract_guest_data_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)
    model_name = "gemini-3.8-flash"

    prompt = """
    Analizza l'immagine di questo documento di identità (passaporto, carta d'identità o patente) 
    ed estrai i dati anagrafici dell'ospite.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON valido (senza markdown o blocchi ```json) con queste chiavi esatte:
    {
        "first_name": "Nome",
        "last_name": "Cognome",
        "gender": "M o F",
        "birth_date": "YYYY-MM-DD",
        "birth_place": "Comune o Stato estero di nascita",
        "birth_place_code": "Codice catasto o codice stato se presente, altrimenti stringa vuota",
        "citizenship": "Stato di cittadinanza",
        "citizenship_code": "Codice stato di cittadinanza se presente, altrimenti stringa vuota",
        "doc_type": "IDENTITA, PASSAPORTO o PATENTE",
        "doc_number": "Numero del documento",
        "doc_issuer": "Autorità di rilascio"
    }
    """

    # Fino a 3 tentativi con pausa progressiva per superare l'errore 503 di sovraccarico
    max_retries = 3
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)

            # Normalizzazione chiavi per evitare KeyError
            default_keys = [
                "first_name", "last_name", "gender", "birth_date", 
                "birth_place", "birth_place_code", "citizenship", 
                "citizenship_code", "doc_type", "doc_number", "doc_issuer"
            ]
            for key in default_keys:
                if key not in data or data[key] is None:
                    data[key] = ""

            return data

        except Exception as e:
            last_exception = e
            err_str = str(e)
            
            # Se è un errore di sovraccarico (503/429/UNAVAILABLE), attende prima di riprovare
            if any(code in err_str for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"]):
                if attempt < max_retries - 1:
                    sleep_time = (attempt + 1) * 1.5  # Pausa di 1.5s la prima volta, poi 3s
                    print(f"[OCR Retry] Sovraccarico temporaneo su {model_name}. Tentativo {attempt + 1} fallito. Attesa di {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
            
            # Se è un altro errore non temporaneo, solleva subito l'eccezione
            raise e

    raise Exception(f"Servizio OCR occupato dopo {max_retries} tentativi: {str(last_exception)}")