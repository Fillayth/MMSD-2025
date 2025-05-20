# -*- coding: utf-8 -*-
import os
import random
import csv
import numpy as np
import time

def set_seed(seed: int = None):
    """
    Imposta il seed per random e numpy.random per garantire la ripetibilità.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

def sample_from_distribution(
    distribution: str,
    return_type: type,
    low: float,
    high: float,
    mean: float,
    std: float
):
    """
    Restituisce un campione dalla distribuzione specificata.

    Args:
        distribution (str): 'uniform' o 'normal'.
        return_type (type): tipo di ritorno (int o float).
        low, high, mean, std: parametri della distribuzione.

    Returns:
        int o float: valore campionato.

    Raises:
        ValueError: se la distribuzione non è supportata.
    """
    if distribution == 'uniform':
        value = np.random.uniform(low, high)
    elif distribution == 'normal':
        value = np.random.normal(mean, std)
    else:
        raise ValueError("Distribuzione non supportata. Scegli tra 'uniform' e 'normal'.")

    if return_type == int:
        value = int(round(value))
        value = max(int(low), min(int(high), value))
    else:
        value = round(float(value), 4)
        value = max(float(low), min(float(high), value))
    return value

def generate_time(distribution: str, low: float, high: float, mean: float, std: float) -> float:
    """
    Genera un tempo in minuti secondo la distribuzione specificata.
    """
    return sample_from_distribution(
        distribution=distribution,
        return_type=float,
        low=low,
        high=high,
        mean=mean,
        std=std
    )

def generate_random_days_on_list(distribution: str, low: int, high: int, mean: float, std: float) -> int:
    """
    Genera un numero casuale di giorni di messa in lista.
    """
    return sample_from_distribution(
        distribution=distribution,
        return_type=int,
        low=low,
        high=high,
        mean=mean,
        std=std
    )

def generate_random_priority(distribution: str, low: int, high: int, mean: float, std: float) -> int:
    """
    Genera una priorità casuale secondo la distribuzione specificata.
    """
    return sample_from_distribution(
        distribution=distribution,
        return_type=int,
        low=low,
        high=high,
        mean=mean,
        std=std
    )

def generate_csv(
    file_name: str,
    num_records: int,
    priority_distribution: str,
    max_wait_days: int,
    utenti_per_giorno_distribution: str,
    utenti_per_giorno_low: int,
    utenti_per_giorno_high: int,
    utenti_per_giorno_mean: int,
    utenti_per_giorno_std: int,
    seed: int,
    time_distribution: str,
    time_low: float,
    time_high: float,
    time_mean: float,
    time_std: float,
    priority_low: int,
    priority_high: int,
    priority_mean: float,
    priority_std: float,
    giorni_lista_distribution: str,
    giorni_lista_low: int,
    giorni_lista_high: int,
    giorni_lista_mean: float,
    giorni_lista_std: float
) -> None:
    """
    Genera un file CSV con dati simulati di pazienti in lista d'attesa.

    Args:
        file_name (str): Nome del file CSV.
        num_records (int): Numero di record da generare.
        priority_distribution (str): Distribuzione per la priorità ('uniform' o 'normal').
        max_wait_days (int): Massimo giorni di attesa.
        utenti_per_giorno_distribution (str): Distribuzione utenti/giorno ('uniform' o 'normal').
        utenti_per_giorno_low (int): Min utenti/giorno.
        utenti_per_giorno_high (int): Max utenti/giorno.
        utenti_per_giorno_mean (int): Media utenti/giorno.
        utenti_per_giorno_std (int): Deviazione standard utenti/giorno.
        seed (int): Seed per la ripetibilità.
        time_distribution (str): Distribuzione per le tempistiche stimate ('uniform' o 'normal').
        time_low (float): Limite inferiore per le tempistiche stimate.
        time_high (float): Limite superiore per le tempistiche stimate.
        time_mean (float): Media per le tempistiche stimate.
        time_std (float): Deviazione standard per le tempistiche stimate.
        priority_low (int): Limite inferiore per la priorità.
        priority_high (int): Limite superiore per la priorità.
        priority_mean (float): Media per la priorità.
        priority_std (float): Deviazione standard per la priorità.
        giorni_lista_distribution (str): Distribuzione per i giorni di messa in lista ('uniform' o 'normal').
        giorni_lista_low (int): Limite inferiore per i giorni di messa in lista.
        giorni_lista_high (int): Limite superiore per i giorni di messa in lista.
        giorni_lista_mean (float): Media per i giorni di messa in lista.
        giorni_lista_std (float): Deviazione standard per i giorni di messa in lista.
    """
    # Se il seed non è fornito, generane uno randomico e usalo
    if seed is None:
        seed = int(time.time() * 1000) % (2**32 - 1)
    set_seed(seed)

    operation_types = ["Operazione A", "Operazione B", "Operazione C"]
    records = []
    id_paziente = 1
    giorno = 0

    # Generazione dei dati
    while id_paziente <= num_records:
        # Determina quanti utenti aggiungere oggi
        if utenti_per_giorno_distribution == 'uniform':
            utenti_oggi = random.randint(utenti_per_giorno_low, utenti_per_giorno_high)
        elif utenti_per_giorno_distribution == 'normal':
            utenti_oggi = int(round(np.random.normal(utenti_per_giorno_mean, utenti_per_giorno_std)))
            utenti_oggi = max(1, utenti_oggi)
        else:
            raise ValueError("Distribuzione utenti per giorno non supportata. Usa 'uniform' o 'normal'.")

        for _ in range(utenti_oggi):
            if id_paziente > num_records:
                break
            tipo_operazione = random.choice(operation_types)
            tempistiche_stimate = generate_time(
                time_distribution, time_low, time_high, time_mean, time_std
            )
            giorni_messa_in_lista = generate_random_days_on_list(
                giorni_lista_distribution, giorni_lista_low, giorni_lista_high, giorni_lista_mean, giorni_lista_std
            )
            priorita = generate_random_priority(
                priority_distribution, priority_low, priority_high, priority_mean, priority_std
            )
            records.append([
                id_paziente,
                tipo_operazione,
                tempistiche_stimate,
                giorni_messa_in_lista,
                priorita
            ])
            id_paziente += 1
        giorno += 1

    # Ordina i record in base ai giorni di messa in lista
    records.sort(key=lambda x: x[3])  # x[3] è 'Giorni di Messa in Lista'

    # Aggiorna l'ID paziente in modo consistente con il nuovo ordinamento
    for idx, record in enumerate(records, start=1):
        record[0] = idx

    # Scrittura su file CSV
    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Scrivi il seed come prima riga
        writer.writerow([f"SEED UTILIZZATO: {seed}"])
        # Scrivi l'intestazione delle colonne
        writer.writerow([
            "ID Paziente",
            "Tipo di Operazione",
            "Tempistiche Stimate (minuti)",
            "Giorni di Messa in Lista",
            "Giorni Massimi Attesa"
        ])
        writer.writerows(records)

if __name__ == "__main__":
    # Esempio di chiamata a generate_csv con spiegazione dei parametri:
    generate_csv(
        file_name="lista_attesa_simulata.csv",         # Nome del file CSV di output
        num_records=100,                               # Numero totale di pazienti da generare
        priority_distribution='normal',                # Distribuzione per la priorità ('uniform' o 'normal')
        max_wait_days=60,                              # Giorni massimi di attesa (non usato direttamente nei dati, solo informativo)
        utenti_per_giorno_distribution='normal',       # Distribuzione utenti/giorno ('uniform' o 'normal')
        utenti_per_giorno_low=5,                       # Minimo utenti inseriti in lista per giorno
        utenti_per_giorno_high=20,                     # Massimo utenti inseriti in lista per giorno
        utenti_per_giorno_mean=10,                     # Media utenti inseriti in lista per giorno (usato solo se distribuzione 'normal')
        utenti_per_giorno_std=4,                       # Deviazione standard utenti/giorno (usato solo se distribuzione 'normal')
        seed=3990858641,                               # Seed per la ripetibilità dei dati generati
        time_distribution='uniform',                   # Distribuzione per le tempistiche stimate ('uniform' o 'normal')
        time_low=5,                                    # Limite inferiore per le tempistiche stimate (minuti)
        time_high=180,                                 # Limite superiore per le tempistiche stimate (minuti)
        time_mean=30,                                  # Media per le tempistiche stimate (usato solo se distribuzione 'normal')
        time_std=10,                                   # Deviazione standard per le tempistiche stimate (usato solo se distribuzione 'normal')
        priority_low=1,                                # Limite inferiore per la priorità
        priority_high=60,                              # Limite superiore per la priorità
        priority_mean=30,                              # Media per la priorità (usato solo se distribuzione 'normal')
        priority_std=10,                               # Deviazione standard per la priorità (usato solo se distribuzione 'normal')
        giorni_lista_distribution='uniform',           # Distribuzione per i giorni di messa in lista ('uniform' o 'normal')
        giorni_lista_low=0,                            # Limite inferiore per i giorni di messa in lista
        giorni_lista_high=60,                          # Limite superiore per i giorni di messa in lista
        giorni_lista_mean=30,                          # Media per i giorni di messa in lista (usato solo se distribuzione 'normal')
        giorni_lista_std=10                            # Deviazione standard per i giorni di messa in lista (usato solo se distribuzione 'normal')
    )
    print("File 'lista_attesa_simulata.csv' generato con successo.")