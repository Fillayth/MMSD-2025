import sys
import os
import pyomo.environ as pyo
import random
import csv

from datetime import datetime
from typing import List 

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))
from CommonClass.Patient import Patient
from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from settings import Settings
from Simulatore.Simulation import export_json_schedule

limited_ids = True
max_pat_len = 100 # a causa dei limiti della licenza del solver

def CreatePyomoModel(newPatientsList: list[Patient], operatingRoom_count: int, startTime: int, model: pyo.ConcreteModel = None) -> pyo.ConcreteModel:
    '''
    funzione per gestire il model in modo dinamico rimuovendo i giorni già passati e aggiungendo i nuovi pazienti
    in questo modo si evita di dover ricreare il modello ogni volta

    serve aggiungere anche un limite per il numero di pazienti gestibili a causa dei limiti della licenza del solver
    attualmente il limite è di 70 pazienti per volta

    argomenti:
    - newPatientsList: lista di nuovi pazienti da aggiungere al modello
    - operatingRoom_count: numero di sale operatorie disponibili per la specialità
    - startTime: giorno di inizio della settimana (0-4) 5 giorni lavorativi
    - model: modello pyomo esistente (se non esiste viene creato uno nuovo/ se esiste viene aggiornato rimuovendo i giorni passati e i pazienti assegnati e aggiungendo i nuovi pazienti)
    return model con i nuovi pazienti e i giorni aggiornati 
    '''
    if not newPatientsList or len(newPatientsList) == 0:
        return model
    
    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit

    newPatientsList = sorted(newPatientsList, key = lambda p: p.id)
    
    #regola: il paziente viene selezionato solo una volta
    def patient_once(model, i):
        return sum(model.ORs[i, t, k] for k in model.K for t in model.T )<= 1
    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    def time_rule(model, t, k):
        #print(f"Max worktime for day {t}, room {k}: {pyo.value(model.s[t, k])} minutes | Total assigned time: {sum(model.ORs[i, t, k] * model.eot[i] for i in model.I)} minutes \n")

        return sum( model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s[t, k]
    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    def objective_rule_M1(model):
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K )        


    if model is None:
        model = pyo.ConcreteModel()
        if limited_ids and len(newPatientsList) > max_pat_len: 
            newPatientsList = newPatientsList[:max_pat_len] #limite di 70 pazienti a causa dei limiti della licenza del solver
        model.I = pyo.Set(initialize = range(len(newPatientsList))) #set pazienti
        model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
        model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

        model.id_p = pyo.Param(model.I, initialize=[p.id for p in newPatientsList]) #set id pazienti 
        model.dr = pyo.Param(model.I, initialize=[p.day for p in newPatientsList])  #set giorni di arrivo pazienti
        model.mtb = pyo.Param(model.I, initialize=[p.mtb for p in newPatientsList]) #set giorni massimi di attesa pazienti
        model.eot = pyo.Param(model.I, initialize=[p.eot for p in newPatientsList]) #set estimated operation time pazienti

        model.s = pyo.Param(model.T, model.K, initialize = max_worktime_for_day) #set tempo massimo per sala operatoria
        model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary )  #variabile binaria di assegnazione pazienti a sale operatorie e giorni

        #regola: il paziente viene selezionato solo una volta
        model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)

        #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
        model.rule_max_ORs_time = pyo.Constraint(model.T, model.K, rule = time_rule)

        ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
        #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
        model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)
        return model
    else:
        #verifico che la lista dei nuovi pazienti non contenga pazienti già presenti nel modello se esistono li rimuovo da newPatientsList
        existing_ids = {pyo.value(model.id_p[i]) for i in model.I}
        newPatientsList = [p for p in newPatientsList if p.id not in existing_ids]
        if len(newPatientsList) == 0:
            return model
        
        #creo un nuovo modello con i pazienti I esistenti nel vecchio model e non assegnati e aggiungo i nuovi pazienti tenendo conto del limite di 70 pazienti e del tempo consumato nel modello precedente
        assigned_ids = {pyo.value(model.id_p[i]) for i in model.I if any(pyo.value(model.ORs[i, t, k])==1 for t in model.T for k in model.K)}
        unassigned_patients = [Patient(
            id = model.id_p[i],
            eot = model.eot[i],
            day = model.dr[i],
            mtb = model.mtb[i]) for i in model.I if model.id_p[i] not in assigned_ids]
        combined_patients = unassigned_patients + newPatientsList
        combined_patients = sorted(combined_patients, key = lambda p: p.id)

        
        if limited_ids and len(combined_patients) > max_pat_len:
                combined_patients = combined_patients[:max_pat_len] #limite di 70 pazienti a causa dei limiti della licenza del solver
        new_model = pyo.ConcreteModel()
        new_model.I = pyo.Set(initialize = range(len(combined_patients))) #set pazienti
        new_model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
        new_model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie
        new_model.id_p = pyo.Param(new_model.I, initialize=[p.id for p in combined_patients]) #set id pazienti
        new_model.dr = pyo.Param(new_model.I, initialize=[p.day for p in combined_patients])  #set giorni di arrivo pazienti
        new_model.mtb = pyo.Param(new_model.I, initialize=[p.mtb for p in combined_patients]) #set giorni massimi di attesa pazienti
        new_model.eot = pyo.Param(new_model.I, initialize=[p.eot for p in combined_patients]) #set estimated operation time pazienti
        #adeguo il set tempo massimo per sala operatoria alla situazione del model precedente 
        # new_model.s[t,k] = max_worktime_for_day - sum(pyo.value(model.ORs[i, t, k]) * pyo.value(model.eot[i]) for i in model.I) if t in model.T and k in model.K else max_worktime_for_day
        S_value = {}
        for t in new_model.T:
            for k in new_model.K:
                if t in model.T and k in model.K:
                    used_time = sum(pyo.value(model.ORs[i, t, k]) * pyo.value(model.eot[i]) for i in model.I)
                    S_value[(t, k)] = max_worktime_for_day - used_time
                else:
                    S_value[(t, k)] = max_worktime_for_day
        # new_model.s = pyo.Var(new_model.T, new_model.K, domain=pyo.NonNegativeReals) #set tempo massimo per sala operatoria
        def s_init(model, t, k):
            return S_value[(t, k)]
        new_model.s = pyo.Param(new_model.T, new_model.K, initialize = s_init)
            

        # new_model.s = pyo.Param(new_model.T, new_model.K, initialize = S_value)

        new_model.ORs = pyo.Var(new_model.I, new_model.T, new_model.K, domain=pyo.Binary )  #variabile binaria di assegnazione pazienti a sale operatorie e giorni
        new_model.rule_patient_once = pyo.Constraint(new_model.I, rule = patient_once)
        new_model.rule_max_ORs_time = pyo.Constraint(new_model.T, new_model.K, rule = time_rule)
        new_model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)

        return new_model
        
        

def scrivi_csv_incrementale(data, nome_file = "model_results.csv"):
    filepath = Settings.results_filepath 
    output_path = os.path.join(filepath, nome_file)
    with open(output_path, mode='a', newline='') as file:
        writer = csv.writer(file)        
        # intestazione solo se il file è vuoto
        if file.tell() == 0:
            writer.writerow(['indice_i', 'id_i', 'w', 'd', 'day', 'mtb', 'accettato'])
        for a, b, c, d, e, f, g in data :
            writer.writerow([a, b, c, d, e, f, g])

def indice_massimo_inferiore(lst, x):
    '''
    Restituisce l'indice del massimo valore in lst che è strettamente minore di x.
    Se nessun valore è minore di x, restituisce None.
    '''
    # Filtra solo i valori strettamente minori di x
    # candidati = [(i, val) for i, val in enumerate(lst) if val < x]
    
    # if not candidati:
    #     return None  # Nessun valore inferiore a x
    
    # # Trova il massimo tra i candidati
    # return max(candidati, key=lambda t: t[1])[0]
    for i in reversed(range(len(lst))):
        if lst[i] < x:
            return i
    return None

if __name__ == "__main__":
    print(f"Time start {datetime.now()}")
    #leggo la lista di pazienti
    nome_file = "patients_data.csv"
    filepath = Settings.results_filepath 
    output_path = os.path.join(filepath, nome_file)
    
    #max_pat_len = 70 # a causa dei limiti della licenza del solver
    
    patient_list = {}
    with open(output_path, mode='r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            specialty = row["Specialty"]
            if specialty not in patient_list:
                patient_list[specialty] = []
            patient_list[specialty].append(Patient(
                id=int(row["Patient ID"]),
                eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                day=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"])
            ))
    specialtyPatientList = PatientListForSpecialties()
    for key, value in patient_list.items():
        patient_list = sorted(value, key=lambda p: p.day)
        day_for_week = Settings.week_length_days #giorni lavorativi a settimana
        day_start = Settings.start_week_scheduling * day_for_week #inizio settimana lavorativa
        operating_rooms = Settings.workstations_config[key] #sale operatorie per specialità
        current_day = day_start
        weekly_patients = [p for p in patient_list if p.day < current_day] #lista di pazienti da schedulare nella settimana
        current_model = None
        result = []
        while len(weekly_patients) > 0:
            print(f"Scheduling for {key}, Week starting day {current_day}")
            current_model = CreatePyomoModel(weekly_patients, operating_rooms, current_day, current_model)
            #run solver
            Settings.solver.solve(current_model, tee=Settings.solver_tee)
            assignazioni = [(i,current_model.id_p[i], k, t, current_model.dr[i], current_model.mtb[i], pyo.value(current_model.ORs[i, t, k])) for i in current_model.I for k in current_model.K for t in current_model.T]
            scrivi_csv_incrementale(assignazioni, nome_file = f"model_results_{key.replace(' ', '_')}.csv")
            #rimuovo i pazienti assegnati dalla lista settimanale
            weekly_patients = [p for p in weekly_patients if p.id not in [current_model.id_p[i] for i in current_model.I if any(pyo.value(current_model.ORs[i, t, k])==1 for t in current_model.T for k in current_model.K)]]
            #stabilisco il giorno di inizio del prossimo ciclo sulla base dei giorni non completamente schedulati
            #calcolo la media dei tempi delle operazioni della lista dei pazienti schedulati
            avg_eot = sum(p.eot for p in patient_list if current_day - day_for_week <= p.day < current_day) / max(1, len([p for p in patient_list if current_day - day_for_week <= p.day < current_day]))
            #inserisco un range di tolleranza per evitare di riutilizzare lo stesso giorno in caso di errori di arrotondamento
            giorni_non_completamente_schedulati = [
                t
                for t in current_model.T
                for k in current_model.K
                if pyo.value(current_model.s[t, k]) - avg_eot < any(
                    sum(
                        pyo.value(current_model.ORs[i, t, k]) * pyo.value(current_model.eot[i])
                        for i in current_model.I
                    ) < pyo.value(current_model.s[t, k])
                    for k in current_model.K
                )
            ]
            if len(giorni_non_completamente_schedulati) > 0:
                next_day = min(giorni_non_completamente_schedulati)
                if next_day > current_day:
                    current_day = next_day
                else:
                    current_day += day_for_week
            else:
                current_day += day_for_week
            #se non ci sono giorni non completamente schedulati vado alla settimana successiva

            #aggiorno la lista dei pazienti settimanali
            weekly_patients.extend([p for p in patient_list if current_day - day_for_week <= p.day < current_day and p not in weekly_patients])
            # regisro i pazienti assegnati nel risultato finale
            result.extend([Patient(
                id = current_model.id_p[i],
                eot = current_model.eot[i],
                day = current_model.dr[i],
                mtb = current_model.mtb[i],
                opDay= t,
                workstation= k,
                overdue=False)
                for i in current_model.I for k in current_model.K for t in current_model.T if pyo.value(current_model.ORs[i, t, k])==1])
            #controllo per evitare loop infiniti
            if current_day > day_start + (Settings.weeks_to_fill + 2) * day_for_week:
                print(f"Reached the maximum scheduling period for {key}. Stopping further scheduling.")
                break
        #stampo i risultati in json
        #export_json_schedule([p.to_json() for p in result], f"schedule_{key.replace(' ', '_')}.json")
        specialtyPatientList[key] = result
        #print(f"Total scheduled patients for {key}: {len(result)}")
    export_json_schedule(specialtyPatientList.to_dict(), f"schedule_{key.replace(' ', '_')}.json")
        
