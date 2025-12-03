import random
import csv
import numpy as np
import time
import os

def set_seed(seed):
    # Imposta il seed per random e numpy.random per garantire la ripetibilità.
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

def sample_from_distribution(distribution, return_type, mean=None, std=None, shape=None, scale=None):
    # Restituisce un campione dalla distribuzione specificata.
    # Supportate: 'lognormal', 'gamma', 'weibull', 'normal', 'poisson'.
    if distribution == 'lognormal':
        value = np.random.lognormal(mean, std)
    elif distribution == 'gamma':
        value = np.random.gamma(shape, scale)
    elif distribution == 'weibull':
        value = np.random.weibull(shape) * scale
    elif distribution == 'normal':
        value = np.random.normal(mean, std)
    elif distribution == 'poisson':
        value = np.random.poisson(mean)
    else:
        raise ValueError("Distribuzione non supportata. Scegli tra 'lognormal', 'gamma', 'weibull', 'normal', 'poisson'.")

    # Arrotonda il valore in base al tipo richiesto
    if return_type == int:
        value = int(round(value))
    else:
        value = round(float(value), 4)
    return value

def generate_time(K2_params, K7_params, K8_params, K9_params, K3_params):
    # Calcola il tempo totale di una procedura sommando i tempi generati per ciascuna fase.
    # Ogni fase usa la propria distribuzione e parametri.
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
    # Arrotonda il tempo totale a una cifra decimale
    return round(t_K2 + t_K7 + t_K8 + t_K9 + t_K3, 3)

def write_reports(patient_records, weekly_report, seed, project_root) -> tuple[str,str] : 
    # Gestisce la creazione delle directory e la scrittura dei file CSV dei pazienti e del report settimanale.
    # La cartella Records viene creata a pari livello della cartella RecordGeneration.
    # project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # records_dir = os.path.join(project_root, "Records")
    
    records_dir = os.path.join(project_root, "Records")
    seed_dir = os.path.join(records_dir, "seed-" + str(seed))
    os.makedirs(seed_dir, exist_ok=True)

    patients_filename = os.path.join(seed_dir, "Patient_Record.csv")
    weekly_filename = os.path.join(seed_dir, "Weekly_Report.csv")

    # Scrittura del file CSV dei pazienti
    with open(patients_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([
            "Patient ID",
            "Specialty",
            "EOT (Estimated Operation Time in minutes)",
            "Day (Day Added to Waiting List)",
            "MTB (Priority, max waiting days)",
            "ROT (Real Operation Time in minutes)"
        ])
        writer.writerows(patient_records)

    # Scrittura del file CSV del report settimanale
    with open(weekly_filename, mode='w', newline='', encoding='utf-8') as report_file:
        report_writer = csv.writer(report_file)
        report_writer.writerow(["Week", "Used Minutes", "Patients Registered"])
        report_writer.writerows(weekly_report)

    return patients_filename, weekly_filename

def generate_csv(
    specialties,
    weekly_hours,
    num_weeks,
    seed,
    specialty_params,
    people_distribution,
    priority_params,  # <-- nuovo parametro
    filepath
) -> tuple[str, str]:
    # Genera un file CSV con i dati simulati dei pazienti in lista d'attesa.
    # Genera anche un report settimanale con i minuti utilizzati e il numero di pazienti iscritti.
    if seed is None:
        seed = int(time.time() * 1000) % (2**32 - 1)
    set_seed(seed)  # Imposta il seed per la ripetibilità

    patient_records = []  # Lista che conterrà tutti i record dei pazienti
    patient_id = 1        # Contatore progressivo per assegnare un ID univoco a ogni paziente
    weekly_report = []    # Lista per il report dei minuti utilizzati e pazienti iscritti

    # Ciclo sulle settimane da simulare
    for week in range(num_weeks):
        weekly_minutes = np.random.normal(weekly_hours * 60, weekly_hours * 60 * 0.2)
        used_minutes = 0
        patients_in_week = 0

        # Ciclo sui giorni feriali (lunedì-venerdì)
        for weekday in range(1, 6):
            # Determina il numero di pazienti da generare oggi in base alla distribuzione scelta
            if people_distribution == 'normal':
                patients_today = int(round(np.random.normal(15, 5)))
                patients_today = max(1, patients_today)
            elif people_distribution == 'poisson':
                patients_today = np.random.poisson(25)
                patients_today = max(1, patients_today)
            else:
                patients_today = 1

            # Genera i dati per ogni paziente della giornata
            for _ in range(patients_today):
                if used_minutes >= weekly_minutes:
                    break

                operation_type = random.choice(specialties)
                params = specialty_params[operation_type]
                prio_params = priority_params[operation_type]  # Ottieni i parametri di priorità per la specialità

                estimated_time = generate_time(
                    params['K2'], params['K7'], params['K8'], params['K9'], params['K3']
                )
                real_time = round(estimated_time * np.random.uniform(0.8, 1.8), 3)
                priority = sample_from_distribution(
                    prio_params['distribution'], int, mean=prio_params['mean'], std=prio_params['std']
                )
                absolute_day = week * 5 + weekday

                patient_records.append([
                    patient_id,
                    operation_type,
                    estimated_time,
                    absolute_day,
                    priority,
                    real_time
                ])
                patient_id += 1
                used_minutes += estimated_time
                patients_in_week += 1

        weekly_report.append([
            week + 1,
            round(used_minutes, 2),
            patients_in_week
        ])

    patient_records.sort(key=lambda record: record[3])

    for idx, record in enumerate(patient_records):
        record[0] = idx + 1

    return write_reports(patient_records, weekly_report, seed, filepath)


if __name__ == "__main__":
    specialties = ["Specialty A", "Specialty B"]  # Esempio con più specialità
    weekly_hours = 80

    specialty_params = {
        "Specialty A": {
            'K2': {'distribution': 'lognormal', 'mean': 1.98, 'std': 0.50},
            'K7': {'distribution': 'gamma', 'shape': 3.25, 'scale': 4.22},
            'K8': {'distribution': 'lognormal', 'mean': 2.53, 'std': 0.72},
            'K9': {'distribution': 'lognormal', 'mean': 1.24, 'std': 0.60},
            'K3': {'distribution': 'lognormal', 'mean': 1.60, 'std': 0.67}
        },
        "Specialty B": {
            'K2': {'distribution': 'lognormal', 'mean': 2.10, 'std': 0.55},
            'K7': {'distribution': 'gamma', 'shape': 3.50, 'scale': 4.50},
            'K8': {'distribution': 'lognormal', 'mean': 2.70, 'std': 0.80},
            'K9': {'distribution': 'lognormal', 'mean': 1.30, 'std': 0.65},
            'K3': {'distribution': 'lognormal', 'mean': 1.70, 'std': 0.70}
        }
    }

    priority_params = {
        "Specialty A": {
            "distribution": "normal",
            "mean": 15,
            "std": 5
        },
        "Specialty B": {
            "distribution": "normal",
            "mean": 20,
            "std": 7
        }
    }

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=52,
        seed=None,
        specialty_params=specialty_params,
        people_distribution='poisson',
        priority_params=priority_params,  # <-- passa il nuovo dizionario
        filepath=project_root
    )
    print("File 'Patient_Record.csv' generato con successo.")