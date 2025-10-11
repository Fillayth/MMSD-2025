import sys
import os
import pyomo.environ as pyo
import random
import csv


from typing import List 

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))
from CommonClass.Patient import Patient
from settings import Settings


def PyomoSolverOptimizer(patientsList: list[Patient], operatingRoom_count: int, startTime: int) -> List[Patient]:
        
    if not patientsList or len(patientsList) == 0:
        return []
    
    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit

    patientsList = sorted(patientsList, key = lambda p: p.id)

    model = pyo.ConcreteModel()

    model.I = pyo.Set(initialize = range(len(patientsList))) #set pazienti
    model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
    model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

    model.id_p = pyo.Param(model.I, initialize=[p.id for p in patientsList])
    model.dr = pyo.Param(model.I, initialize=[p.day for p in patientsList])
    model.mtb = pyo.Param(model.I, initialize=[p.mtb for p in patientsList])
    model.eot = pyo.Param(model.I, initialize=[p.eot for p in patientsList])

    model.s = pyo.Param(initialize = max_worktime_for_day)
    model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary )

    #regola: il paziente viene selezionato solo una volta
    def patient_once(model, i):
        return sum(model.ORs[i, t, k] for k in model.K for t in model.T )<= 1
    model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)

    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    def time_rule(model, k, t):
        return sum(model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s
    model.rule_max_ORs_time = pyo.Constraint(model.K, model.T, rule = time_rule)

    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    def objective_rule_M1(model):
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K )
    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)

    Settings.solver.solve(model, tee=Settings.solver_tee)

    assegnazioni = [(i,model.id_p[i], k, t, model.dr[i], model.mtb[i], pyo.value(model.ORs[i, t, k])) for i in model.I for k in model.K for t in model.T]
    scrivi_csv_incrementale(assegnazioni)

    return [Patient(
        id = model.id_p[i],
        eot = model.eot[i],
        day = model.dr[i],
        mtb = model.mtb[i],
        opDay= t,
        workstation= k,
        overdue=False)
        for i in model.I for k in model.K for t in model.T if pyo.value(model.ORs[i, t, k])==1]

def DailyPyomoSolverOptimizer(patientsList: list[Patient], operatingRoom_count: int, day: int) -> {List[Patient], bool}:
        
    if not patientsList or (len(patientsList) == 0):
        return [], True
    
    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit

    patientsList = sorted(patientsList, key = lambda p: p.id)

    model = pyo.ConcreteModel()

    model.I = pyo.Set(initialize = range(len(patientsList))) #set pazienti
    model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

    model.id_p = pyo.Param(model.I, initialize=[p.id for p in patientsList])
    model.dr = pyo.Param(model.I, initialize=[p.day for p in patientsList])
    model.mtb = pyo.Param(model.I, initialize=[p.mtb for p in patientsList])
    model.eot = pyo.Param(model.I, initialize=[p.eot for p in patientsList])

    model.ORs = pyo.Var(model.I, model.K, domain=pyo.Binary )

    #regola: il paziente viene selezionato solo una volta
    def patient_once(model, i):
        return sum(model.ORs[i, k] for k in model.K)<= 1
    model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)

    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    def time_rule(model, k):
        return sum(model.ORs[i, k] * model.eot[i] for i in model.I) <= max_worktime_for_day
    model.rule_max_ORs_time = pyo.Constraint(model.K, rule = time_rule)

    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    def objective_rule_M1(model):
        return sum(model.ORs[i, k] for i in model.I for k in model.K )
    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)

    Settings.solver.solve(model, tee=Settings.solver_tee)

    assegnazioni = [(i,model.id_p[i], k, day, model.dr[i], model.mtb[i], pyo.value(model.ORs[i, k])) for i in model.I for k in model.K]
    scrivi_csv_incrementale(assegnazioni)
    #imposto un flag che verifica se tutte le sale operatorie per tutta la giornata sono state riempite



    return [Patient(
        id = model.id_p[i],
        eot = model.eot[i],
        day = model.dr[i],
        mtb = model.mtb[i],
        opDay= day,
        workstation= k,
        overdue=False)
        for i in model.I for k in model.K if pyo.value(model.ORs[i, k])==1], flag


#creo una funzione per definire il model pyomo e senza risolverlo e permettre di espanderlo nei giorni successivi 
def CreatePyomoModel(newPatientsList: list[Patient], operatingRoom_count: int, startTime: int, model: pyo.ConcreteModel = pyo.ConcreteModel()) -> pyo.ConcreteModel:
    if not newPatientsList or len(newPatientsList) == 0:
        return model
    
    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit

    newPatientsList = sorted(newPatientsList, key = lambda p: p.id)

    if not hasattr(model, 'I'):
        model.I = pyo.Set(initialize = range(len(newPatientsList))) #set pazienti
        model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
        model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

        model.id_p = pyo.Param(model.I, initialize=[p.id for p in newPatientsList])
        model.dr = pyo.Param(model.I, initialize=[p.day for p in newPatientsList])
        model.mtb = pyo.Param(model.I, initialize=[p.mtb for p in newPatientsList])
        model.eot = pyo.Param(model.I, initialize=[p.eot for p in newPatientsList])

        model.s = pyo.Param(initialize = max_worktime_for_day)
        model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary )

        #regola: il paziente viene selezionato solo una volta
        def patient_once(model, i):
            return sum(model.ORs[i, t, k] for k in model.K for t in model.T )<= 1
        model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)

        #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
        def time_rule(model, k, t):
            return sum(model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s
        model.rule_max_ORs_time = pyo.Constraint(model.K, model.T, rule = time_rule)

        ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
        #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
        def objective_rule_M1(model):
            return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K )
        
        model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)
    else:
        current_index = max(model.I) + 1
        new_index = range(current_index, current_index + len(newPatientsList))
        model.I = model.I | pyo.Set(initialize = new_index)

        for i, p in zip(new_index, newPatientsList):
            model.id_p[i] = p.id
            model.dr[i] = p.day
            model.mtb[i] = p.mtb
            model.eot[i] = p.eot
        
    return model

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
    #leggo la lista di pazienti
    nome_file = "patients_data.csv"
    filepath = Settings.results_filepath 
    output_path = os.path.join(filepath, nome_file)
    
    max_pat_len = 70 # a causa dei limiti della licenza del solver
    
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

    for key, value in patient_list.items():
        patients = sorted(value, key= lambda p: p.day)
        end_week = 5 
        len_weekly_list = indice_massimo_inferiore([p.day for p in patients], 5)
        or_count = Settings.workstations_config[key]
        currentPatients = patients[0: len_weekly_list]
        num_week = 1 
        while patients or len(patients) > 0 :
            s_len = len(currentPatients)
            result = []
             #limito il numero di pazienti per volta
            if len(currentPatients)>max_pat_len:
                day_count = num_week * end_week
                weekly_patients = [p for p in currentPatients if p.day <= day_count]
                while day_count < (num_week+1)*end_week:
                    if len(weekly_patients) > max_pat_len:
                        cut_count = 0
                        flag = False
                        week_pat_count = len(weekly_patients)
                        # finche ci sono pazienti settimanali più pazienti di quelli gestibili o il tempo limite giornaliero viene raggiunto eseguo l'ottimizzazione giornaliera
                        while not (week_pat_count < max_pat_len or flag):                        
                            cut_pat = weekly_patients[cut_count:max_pat_len + cut_count]
                            res, flag = DailyPyomoSolverOptimizer(cut_pat, or_count, day_count)
                            week_pat_count -= len(res)
                            result.extend(res)
                            cut_count += max_pat_len
                    else:
                        result, _ = DailyPyomoSolverOptimizer(weekly_patients, or_count, day_count)
                    day_count += 1    
                    
            else : 
                result = PyomoSolverOptimizer(currentPatients, or_count, startTime = end_week*num_week)        
            patients = [x for x in patients if x not in result]
            num_week += 1
            len_weekly_list = indice_massimo_inferiore([p.day for p in patients], end_week*num_week)
            e_len = len(patients)
            currentPatients = patients[0: len_weekly_list + 1] if len_weekly_list is not None else []
            print(f"{key}|s:{s_len}|f:{e_len}")

    # todo : correggere il flag di ritorno per le ottimizzazioni giornaliere 