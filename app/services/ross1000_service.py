from datetime import datetime, date
from typing import Dict, Any, List

class Ross1000Service:
    @staticmethod
    def generate_csv_lazio(property_code: str, movements: List[Dict[str, Any]]) -> str:
        """
        Genera il file standard delimitato da punto e virgola (;) per ROSS 1000 Lazio.
        Formato colonne: CODICE_STRUTTURA;DATA;TIPO_MOVIMENTO;CODICE_PROVENIENZA;NUMERO_PERSONE
        """
        lines = ["CODICE_STRUTTURA;DATA;TIPO_MOVIMENTO;CODICE_PROVENIENZA;NUMERO_PERSONE"]
        
        for m in movements:
            data_mov = m["date"].strftime("%d/%m/%Y") if isinstance(m["date"], (date, datetime)) else str(m["date"])
            tipo = m["type"] # 'ARRIVO' oppure 'PARTENZA'
            cod_luogo = str(m.get("provenance_code", "100000100")).strip()
            num = str(m.get("count", 1))
            
            lines.append(f"{property_code};{data_mov};{tipo};{cod_luogo};{num}")
            
        return "\r\n".join(lines) + "\r\n"