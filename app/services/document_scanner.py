import os
import json
from google import genai
from google.genai import types

def extract_guest_data_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)

    prompt = """
    Analizza l'immagine di questo documento di identità (passaporto, carta d'identità o patente) 
    ed estrai i dati anagrafici essenziali dell'ospite per la registrazione di pubblica sicurezza.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON valido con i seguenti campi esatti:
    {
        "first_name": "Nome",
        "last_name": "Cognome",
        "gender": "M o F",
        "birth_date": "YYYY-MM-DD",
        "birth_place": "Comune o Stato estero di nascita",
        "citizenship": "Stato di cittadinanza (es. ITALIA, STATI UNITI, GERMANIA)",
        "doc_type": "IDENTITA, PASSAPORTO o PATENTE",
        "doc_number": "Numero del documento",
        "doc_issuer": "Autorità o Comune di rilascio"
    }
    Non aggiungere markdown (senza ```json o testo di commento). Solo il JSON puro.
    """

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_text)