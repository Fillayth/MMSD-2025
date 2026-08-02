import sys
import json
import re
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent / "Code"
if str(CODE_DIR) not in sys.path:
    sys.path.append(str(CODE_DIR))

from Grafici.Graph import Graphs
from CommonClass.PatientListForSpecialties import PatientListForSpecialties

_ROOT_PATH = Path(__file__).parent.parent  # Assuming this file is in Utility/Genera_Tabelle.py
_DATA_FOLDER = "./Data/"
_DATA_PATH = _ROOT_PATH / _DATA_FOLDER
_SCHEDULING_FILE_NAME = "weekly_schedule.json"
_ROT_FOLDER = "./rot_cplex"


def carica_dati_da_json(path_file)-> PatientListForSpecialties:
    with open(path_file, 'r', encoding='utf-8') as f:
        contenuto = json.load(f)
    return PatientListForSpecialties.from_dict(contenuto)


def crea_scenari_per_tabella(cartella_dati=_DATA_PATH, nome_file=_SCHEDULING_FILE_NAME):
    """
    Legge i file base e 'rot' per ogni seed, li ordina numericamente
    e crea il dizionario 'scenari' pronto per MostraTabellaConfrontoPlotly.
    """
    percorso_base = Path(cartella_dati)
    dati_grezzi = {}
    
    for percorso_file in percorso_base.rglob(nome_file):
        try:
            pazienti_obj = carica_dati_da_json(percorso_file)
            is_rot = (percorso_file.parent.name == _ROT_FOLDER.strip("./"))
            nome_seed = percorso_file.parent.parent.name if is_rot else percorso_file.parent.name
            
            if nome_seed not in dati_grezzi:
                dati_grezzi[nome_seed] = {}
                
            chiave_tipo = "rot" if is_rot else "base"
            dati_grezzi[nome_seed][chiave_tipo] = pazienti_obj
                
        except Exception as e:
            print(f"Errore leggendo {percorso_file}: {e}")

    # Funzione di supporto per estrarre il numero dal nome del seed (es. "seed-1" -> 1)
    # Serve per ordinare correttamente (1, 2, 3... 10) invece di (1, 10, 2, 3)
    def estrai_numero_seed(nome):
        numeri = re.findall(r'\d+', nome)
        return int(numeri[0]) if numeri else 0

    seed_ordinati = sorted(dati_grezzi.keys(), key=estrai_numero_seed)

    scenari = {}
    
    for seed in seed_ordinati:
        if "base" in dati_grezzi[seed]:
            scenari[f"{seed}"] = dati_grezzi[seed]["base"]
            
        if "rot" in dati_grezzi[seed]:
            scenari[f"{seed} Rot"] = dati_grezzi[seed]["rot"]

    return scenari

def Genera_tabelle(cartella_dati=_DATA_PATH, nome_file=_SCHEDULING_FILE_NAME):
    scenari = crea_scenari_per_tabella(cartella_dati, nome_file)
    cartella_output = Path(cartella_dati) / "tabelle"
    cartella_output.mkdir(parents=True, exist_ok=True)
    
    graph = Graphs(str(cartella_output))
    graph.MostraTabellaConfrontoPlotly(scenari)

if __name__ == "__main__":
    Genera_tabelle(_DATA_PATH, _SCHEDULING_FILE_NAME)
    