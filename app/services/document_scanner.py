import os
import json
from google import genai
from google.genai import types

def extract_guest_data_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurata nelle variabili d'ambiente.")

    client = genai.Client(api_key=api_key)

    # Modelli attivi: tenta prima con gemini-3.8-flash, se risponde 503 passa a 1.5-flash
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-1.5-flash"
    ]

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

    last_error = None

    for model_name in models_to_try:
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
            return json.loads(clean_text)

        except Exception as e:
            last_error = e
            # Se gemini-3.8-flash risponde con 503 o picchi di traffico, passa a 1.5-flash
            err_str = str(e)
            if any(code in err_str for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"]):
                continue
            raise e

    raise Exception(f"Servizio OCR temporaneamente indisponibile: {str(last_error)}")