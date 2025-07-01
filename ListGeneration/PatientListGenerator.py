import random
import csv
import numpy as np
import time

def set_seed(seed):
    """Imposta il seed per random e numpy.random per garantire la ripetibilità."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

def sample_from_distribution(distribution, return_type, mean=None, std=None, shape=None, scale=None):
    """
    Restituisce un campione dalla distribuzione specificata.
    Supportate: 'lognormal', 'gamma', 'weibull', 'normal', 'poisson'.
    """
    if distribution == 'lognormal':
        # mean e std sono la media e la deviazione standard della variabile lognormale osservata
        value = np.random.lognormal(mean, std)
    elif distribution == 'gamma':
        # shape e scale sono i parametri fondamentali della gamma
        value = np.random.gamma(shape, scale)
    elif distribution == 'weibull':
        # shape e scale sono i parametri fondamentali della weibull
        value = np.random.weibull(shape) * scale
    elif distribution == 'normal':
        value = np.random.normal(mean, std)
    elif distribution == 'poisson':
        value = np.random.poisson(mean)
    else:
        raise ValueError("Distribuzione non supportata. Scegli tra 'lognormal', 'gamma', 'weibull', 'normal', 'poisson'.")

    # Restituisce il valore come int o float a seconda della richiesta
    if return_type == int:
        value = int(round(value))
    else:
        value = round(float(value), 4)
    return value

def generate_time(K2_params, K7_params, K8_params, K9_params, K3_params):
    """
    Somma i tempi generati per K2, K7, K8, K9, K3 usando le rispettive distribuzioni.
    Ogni chiamata a sample_from_distribution usa i parametri specifici per la distribuzione scelta.
    """
    t_K2 = sample_from_distribution(
        K2_params['distribution'], float, mean=K2_params.get('mean'), std=K2_params.get('std'),
        shape=K2_params.get('shape'), scale=K2_params.get('scale')
    )
    t_K7 = sample_from_distribution(
        K7_params['distribution'], float, mean=K7_params.get('mean'), std=K7_params.get('std'),
        shape=K7_params.get('shape'), scale=K7_params.get('scale')
    )
    t_K8 = sample_from_distribution(
        K8_params['distribution'], float, mean=K8_params.get('mean'), std=K8_params.get('std'),
        shape=K8_params.get('shape'), scale=K8_params.get('scale')
    )
    t_K9 = sample_from_distribution(
        K9_params['distribution'], float, mean=K9_params.get('mean'), std=K9_params.get('std'),
        shape=K9_params.get('shape'), scale=K9_params.get('scale')
    )
    t_K3 = sample_from_distribution(
        K3_params['distribution'], float, mean=K3_params.get('mean'), std=K3_params.get('std'),
        shape=K3_params.get('shape'), scale=K3_params.get('scale')
    )
    return round(t_K2 + t_K7 + t_K8 + t_K9 + t_K3, 4)

def generate_csv(
    file_name,
    num_days,
    utenti_per_giorno_distribution,
    utenti_per_giorno_mean,
    utenti_per_giorno_std,
    seed,
    K2_params,
    K7_params,
    K8_params,
    K9_params,
    K3_params,
    priority_distribution,
    priority_mean,
    priority_std
):
    """
    Genera un file CSV con dati simulati di pazienti in lista d'attesa.
    La messa in lista può avvenire ogni giorno (inclusi sabato e domenica).
    """
    if seed is None:
        seed = int(time.time() * 1000) % (2**32 - 1)
    set_seed(seed)

    operation_types = ["Operazione A", "Operazione B", "Operazione C"]
    records = []
    id_paziente = 1

    for giorno in range(num_days):
        # Determina il numero di pazienti da generare oggi
        if utenti_per_giorno_distribution == 'normal':
            utenti_oggi = int(round(np.random.normal(utenti_per_giorno_mean, utenti_per_giorno_std)))
            utenti_oggi = max(1, utenti_oggi)
        elif utenti_per_giorno_distribution == 'poisson':
            utenti_oggi = np.random.poisson(utenti_per_giorno_mean)
            utenti_oggi = max(1, utenti_oggi)
        else:
            raise ValueError("Distribuzione utenti per giorno non supportata. Usa 'normal' o 'poisson'.")

        # Genera i dati per ogni paziente della giornata
        for _ in range(utenti_oggi):
            tipo_operazione = random.choice(operation_types)
            tempistiche_stimate = generate_time(K2_params, K7_params, K8_params, K9_params, K3_params)
            giorno_messa_in_lista = giorno  # Il giorno di messa in lista è quello corrente
            priorita = sample_from_distribution(
                priority_distribution, int, mean=priority_mean, std=priority_std
            )

            records.append([
                id_paziente,
                tipo_operazione,
                tempistiche_stimate,
                giorno_messa_in_lista,
                priorita
            ])
            id_paziente += 1

    # Ordina i record in base ai giorni di messa in lista
    records.sort(key=lambda record: record[3])

    # Aggiorna l'ID paziente in modo consistente con il nuovo ordinamento
    for idx, record in enumerate(records):
        record[0] = idx + 1

    # Scrivi il file CSV
    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["SEED UTILIZZATO: " + str(seed)])
        writer.writerow([
            "ID Paziente",
            "Tipo di Operazione",
            "EOT (Tempistiche Stimate in minuti)",
            "Day (Giorno di Messa in Lista)",
            "MTB (Priorità, giorni massimi di attesa)"
        ])
        writer.writerows(records)

if __name__ == "__main__":
    # Esempio di parametri per le distribuzioni usata operazione (1-653):
    # - lognormal e normal: mean e std
    # - gamma e weibull: shape e scale
    
    K2_params = {'distribution': 'lognormal', 'mean': 1.980694593, 'std': 0.5021391517} #Anesthesia Induction Time
    K7_params = {'distribution': 'gamma', 'shape': 3.25036037, 'scale': 4.22461821} #Surgical Lead-In
    K8_params = {'distribution': 'lognormal', 'mean': 2.529958165, 'std': 0.7196641252} #Incision-to-Closure Time
    K9_params = {'distribution': 'lognormal', 'mean': 1.238535974, 'std': 0.6021773292} #Surgical Lead-out
    K3_params = {'distribution': 'lognormal', 'mean': 1.59782238, 'std': 0.6741858934} #Anesthesia Emergency Time

    generate_csv(
        file_name="lista_attesa_simulata.csv",
        num_days=1000,  # Numero di giorni consecutivi da simulare
        utenti_per_giorno_distribution='poisson',
        utenti_per_giorno_mean=5,
        utenti_per_giorno_std=2,
        seed=None,  # Imposta il seed a None per generare un seed casuale
        K2_params=K2_params,
        K7_params=K7_params,
        K8_params=K8_params,
        K9_params=K9_params,
        K3_params=K3_params,
        priority_distribution='normal',
        priority_mean=15,
        priority_std=5
    )
    print("File 'lista_attesa_simulata.csv' generato con successo.")