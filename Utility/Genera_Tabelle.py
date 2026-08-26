import sys
import json
import re
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent / "Code"
if str(CODE_DIR) not in sys.path:
    sys.path.append(str(CODE_DIR))

from Grafici.Graph import Graphs
from CommonClass.PatientListForSpecialties import PatientListForSpecialties

_ROOT_PATH = Path(__file__).parent.parent  
_DATA_FOLDER = "./Data/"
_DATA_PATH = _ROOT_PATH / _DATA_FOLDER
_SCHEDULING_FILE_NAME = "weekly_schedule.json"
_ROT_FOLDER = "./rot_cplex"


def carica_dati_da_json(path_file)-> PatientListForSpecialties:
    """Carica i dati dei pazienti da un file JSON."""
    with open(path_file, 'r', encoding='utf-8') as f:
        contenuto = json.load(f)
    return PatientListForSpecialties.from_dict(contenuto)

def carica_settings_seed(cartella_seed: Path) -> dict:
    """Cerca e carica il file settings_[seed] (JSON o PY) presente nella cartella del seed."""
    if not cartella_seed.exists() or not cartella_seed.is_dir():
        return {}

    nome_seed = cartella_seed.name
    
    # Cerca il file settings nella cartella del seed
    candidati = []
    
    # 1. Cerca file che contengono il nome del seed (es. settings_seed-1.py, settings_1.json)
    candidati.extend(list(cartella_seed.glob(f"settings*{nome_seed}*.py")))
    candidati.extend(list(cartella_seed.glob(f"settings*{nome_seed}*.json")))
    
    # 2. Cerca qualsiasi file settings_*.py o settings_*.json nella cartella
    candidati.extend(list(cartella_seed.glob("settings_*.py")))
    candidati.extend(list(cartella_seed.glob("settings_*.json")))
    
    # 3. Cerca file settings.py o settings.json generici nella cartella del seed
    candidati.extend(list(cartella_seed.glob("settings.py")))
    candidati.extend(list(cartella_seed.glob("settings.json")))

    if not candidati:
        return {}

    file_settings = candidati[0]

    # Caricamento da file JSON
    if file_settings.suffix == ".json":
        try:
            with open(file_settings, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # I file generati dal simulatore salvano la configurazione sotto
                # "settings"; il core delle tabelle riceve invece direttamente
                # il dizionario dei parametri.
                return settings.get("settings", settings)
        except Exception as e:
            print(f"Errore nel caricamento del file JSON {file_settings}: {e}")
            return {}

    return {}

def crea_scenari_per_tabella(cartella_dati=_DATA_PATH, nome_file=_SCHEDULING_FILE_NAME):
    """
    Legge i file base e 'rot' per ogni seed, li ordina numericamente
    e crea il dizionario 'scenari' pronto per MostraTabellaConfrontoPlotly.
    """
    percorso_base = Path(cartella_dati)
    dati_grezzi = {}
    settings_per_seed = {}
    
    for percorso_file in percorso_base.rglob(nome_file):
        try:
            pazienti_obj = carica_dati_da_json(percorso_file)
            is_rot = (percorso_file.parent.name == _ROT_FOLDER.strip("./"))

            cartella_seed = percorso_file.parent.parent if is_rot else percorso_file.parent
            nome_seed = cartella_seed.name

            if nome_seed not in dati_grezzi:
                dati_grezzi[nome_seed] = {}
                settings_per_seed[nome_seed] = carica_settings_seed(cartella_seed)
                
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
    scenari_settings = {}
    
    for seed in seed_ordinati:
        cfg = settings_per_seed.get(seed, {})

        if "base" in dati_grezzi[seed]:
            scenari[f"{seed}"] = dati_grezzi[seed]["base"]
            scenari_settings[f"{seed}"] = cfg
            
        if "rot" in dati_grezzi[seed]:
            scenari[f"{seed} Post"] = dati_grezzi[seed]["rot"]
            scenari_settings[f"{seed} Post"] = cfg

    return scenari, scenari_settings

def Genera_tabelle(cartella_dati=_DATA_PATH, nome_file=_SCHEDULING_FILE_NAME):
    scenari, scenari_settings = crea_scenari_per_tabella(cartella_dati, nome_file)
    cartella_output = Path(cartella_dati) / "tabelle"
    cartella_output.mkdir(parents=True, exist_ok=True)
    
    graph = Graphs(str(cartella_output))
    graph.MostraTabellaConfrontoPlotlyDaDati(scenari, scenari_settings=scenari_settings)

if __name__ == "__main__":
    Genera_tabelle(_DATA_PATH, _SCHEDULING_FILE_NAME)
    