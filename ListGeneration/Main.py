# -*- coding: utf-8 -*-
import os
import random
import datetime
import csv
import TimeGeneration  # Si assume che questo modulo sia definito correttamente e contenga la funzione `generate_time`

# Funzione per generare un nome casuale
def generate_random_name():
    # Definizione di liste di nomi e cognomi
    first_names = ["Mario", "Luigi", "Giulia", "Francesca", "Alessandro"]
    last_names = ["Rossi", "Bianchi", "Verdi", "Esposito", "Russo"]
    # Restituisce un nome completo casuale combinando un nome e un cognome
    return f"{random.choice(first_names)} {random.choice(last_names)}"

# Funzione per generare una data casuale nell'ultimo anno
def generate_random_date_within_last_year():
    # Calcola la data di inizio (un anno fa) e la data di fine (oggi)
    start_date = datetime.date.today() - datetime.timedelta(days=365)
    end_date = datetime.date.today()
    # Genera una data casuale tra start_date ed end_date
    random_date = start_date + datetime.timedelta(days=random.randint(0, (end_date - start_date).days))
    # Restituisce la data in formato stringa "YYYY-MM-DD"
    return random_date.strftime("%Y-%m-%d")

# Funzione per generare un file CSV con i campi specificati
def generate_csv(file_name, num_records):
    # Definizione dei possibili valori per il campo "Tipo di Operazione"
    operation_types = ["Operazione A", "Operazione B", "Operazione C"]
    records = []  # Lista per memorizzare i record generati

    # Generazione di ogni record
    for _ in range(num_records):
        # Genera un nome e cognome casuale
        nome_cognome = generate_random_name()
        # Seleziona un tipo di operazione casuale
        tipo_operazione = random.choice(operation_types)
        # Genera un tempo stimato casuale tra 5 e 60 minuti usando il modulo TimeGeneration
        tempistiche_stimate = TimeGeneration.generate_time('uniform', low=5, high=180)
        # Genera una data casuale nell'ultimo anno
        data_messa_in_lista = generate_random_date_within_last_year()
        # Aggiunge il record alla lista
        records.append([nome_cognome, tipo_operazione, tempistiche_stimate, data_messa_in_lista])

    # Ordinamento dei record per data (dal più vecchio al più recente)
    records.sort(key=lambda x: datetime.datetime.strptime(x[3], "%Y-%m-%d"))

    # Apertura del file CSV in modalità scrittura
    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Scrittura dell'intestazione del file CSV
        writer.writerow(["Nome e Cognome", "Tipo di Operazione", "Tempistiche Stimate (minuti)", "Data di Messa in Lista"])

        # Scrittura dei record ordinati nel file CSV
        writer.writerows(records)

# Esempio di utilizzo
if __name__ == "__main__":
    # Nome del file di output
    output_file = "ListaOperazioni.csv"
    # Numero di record da generare
    num_records = 1000
    # Genera il file CSV con i record specificati
    generate_csv(output_file, num_records)
    # Stampa un messaggio di conferma
    print(f"File CSV '{output_file}' generato con successo con {num_records} record.")