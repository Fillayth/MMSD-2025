import json

def estrai_id_e_specialta(file_path):
    """Legge il file JSON e mappa ogni ID alla sua specialità."""
    mappa_id_specialta = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for specialty, patients in data.items():
            for p in patients:
                patient_id = p.get('id')
                if patient_id is not None:
                    mappa_id_specialta[patient_id] = specialty
                    
        return mappa_id_specialta
    except FileNotFoundError:
        print(f"Errore: Il file '{file_path}' non è stato trovato.")
        return None
    except json.JSONDecodeError:
        print(f"Errore: Il file '{file_path}' non è un JSON valido.")
        return None

def confronta_json(file1, file2):
    print(f"--- Confronto tra '{file1}' e '{file2}' ---\n")
    
    # Estrai i dati da entrambi i file
    dati_file1 = estrai_id_e_specialta(file1)
    dati_file2 = estrai_id_e_specialta(file2)
    
    if dati_file1 is None or dati_file2 is None:
        return

    # Trasforma gli ID in set (insiemi) per fare operazioni matematiche di confronto
    ids_file1 = set(dati_file1.keys())
    ids_file2 = set(dati_file2.keys())
    
    # 1. ID presenti nel File 1 ma non nel File 2
    solo_in_file1 = ids_file1 - ids_file2
    if solo_in_file1:
        print(f"❌ {len(solo_in_file1)} ID presenti solo in '{file1}' (mancano nel secondo):")
        for pid in sorted(solo_in_file1):
            print(f"  - ID: {pid} (Specialità: {dati_file1[pid]})")
    else:
        print(f"✅ Nessun ID esclusivo di '{file1}'.")
        
    print("-" * 40)

    # 2. ID presenti nel File 2 ma non nel File 1
    solo_in_file2 = ids_file2 - ids_file1
    if solo_in_file2:
        print(f"❌ {len(solo_in_file2)} ID presenti solo in '{file2}' (mancano nel primo):")
        for pid in sorted(solo_in_file2):
            print(f"  - ID: {pid} (Specialità: {dati_file2[pid]})")
    else:
        print(f"✅ Nessun ID esclusivo di '{file2}'.")

    print("-" * 40)

    # 3. ID presenti in entrambi ma con specialità diverse (conflitti di classificazione)
    id_comuni = ids_file1.intersection(ids_file2)
    conflitti = []
    
    for pid in id_comuni:
        if dati_file1[pid] != dati_file2[pid]:
            conflitti.append((pid, dati_file1[pid], dati_file2[pid]))
            
    if conflitti:
        print(f"⚠️ {len(conflitti)} ID presenti in entrambi i file ma con Specialità DIVERSE:")
        for pid, spec1, spec2 in sorted(conflitti):
            print(f"  - ID: {pid} | Nel File 1: '{spec1}' | Nel File 2: '{spec2}'")
    else:
        print("✅ Nessun conflitto di specialità per gli ID in comune.")

    # Riepilogo finale
    if not solo_in_file1 and not solo_in_file2 and not conflitti:
        print("\n🎉 I due file sono identici per quanto riguarda gli ID dei pazienti!")

# --- Configurazione dei file da confrontare ---
# Sostituisci questi nomi con i percorsi dei tuoi due file JSON
file_originale = 'weekly_schedule.json'
file_modificato = 'restored_schedule.json' 

confronta_json(file_originale, file_modificato)