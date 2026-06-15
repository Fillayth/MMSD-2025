import json
import csv

# 1. Carica il file JSON originale
json_file_path = 'weekly_schedule.json'
csv_file_path = 'Patient_Record.csv'

# Struttura dati finale (dizionario che conterrà le liste di pazienti per specialità)
data = {}

with open(csv_file_path, mode='r', encoding='utf-8') as f:
    # DictReader mappa automaticamente l'intestazione del CSV come chiavi dei dizionari di riga
    reader = csv.DictReader(f)
    
    for row in reader:
        # Estrai la specialità (sarà la nostra chiave principale nel JSON)
        specialty = row["Specialty"]
        
        # Converte le stringhe del CSV nei tipi di dato corretti (int, float)
        # in modo da non avere numeri racchiusi tra virgolette nel JSON
        patient_data = {
            "id": int(row["Patient ID"]),
            "eot": float(row["EOT (Estimated Operation Time in minutes)"]),
            "rot": float(row["ROT (Real Operation Time in minutes)"]),
            "day": int(row["Day (Day Added to Waiting List)"]),
            "mtb": int(row["MTB (Priority, max waiting days)"])
        }
        
        # Se la specialità non esiste ancora nel dizionario, inizializza una lista vuota
        if specialty not in data:
            data[specialty] = []
            
        # Aggiunge il paziente alla lista della sua specialità
        data[specialty].append(patient_data)

# Scrive il dizionario finale in un file formato JSON ben formattato (indentato)
with open(json_file_path, mode='w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print(f"Conversione completata! Creato il file '{json_file_path}'")

# with open(json_file_path, 'r', encoding='utf-8') as f:
#     data = json.load(f)

# # 2. Definisci i nomi delle colonne esattamente come richiesto
# headers = [
#     "Patient ID",
#     "Specialty",
#     "EOT (Estimated Operation Time in minutes)",
#     "Day (Day Added to Waiting List)",
#     "MTB (Priority, max waiting days)",
#     "ROT (Real Operation Time in minutes)"
# ]

# rows = []

# # 3. Estrai e mappa i dati ciclando sulle chiavi (Specialty) e sulla lista di pazienti
# for specialty_name, patients in data.items():
#     for p in patients:
#         row = [
#             p.get('id'),                         # Patient ID
#             specialty_name,                      # Specialty (es. "Specialty A")
#             p.get('eot'),                        # EOT
#             p.get('day'),                        # Day
#             p.get('mtb'),                        # MTB
#             p.get('rot')                         # ROT
#         ]
#         rows.append(row)

# # 4. Scrivi i dati nel nuovo file CSV
# with open(csv_file_path, mode='w', newline='', encoding='utf-8') as f:
#     writer = csv.writer(f)
#     writer.writerow(headers) # Scrive l'intestazione
#     writer.writerows(rows)   # Scrive tutte le righe dei dati

# print(f"Conversione completata! Creato il file '{csv_file_path}' con {len(rows)} righe.")