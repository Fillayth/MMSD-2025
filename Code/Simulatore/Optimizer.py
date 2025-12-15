import os
import sys

import pyomo.environ as pyo
import random
import csv

from typing import List 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve
from CommonClass.Patient import Patient
from CommonClass.Week import Week
from settings import Settings

#region Funzioni di supporto
limited_ids = False
max_pat_len = 1000 # a causa dei limiti della licenza del solver

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


#endregion

#region Ottimizzazione settimanale con Pyomo e CPLEX
def optimize_weekly_batch(patients, ws_count, weekly_limit, current_week_end):
    """Optimize assignment of patients to workstations for a single week."""
    if not patients or len(patients) == 0:
        return []

    model = pyo.ConcreteModel()
    model.P = range(len(patients))
    model.W = range(ws_count)

    # Decision variables: x[p, w] = 1 if patient p is assigned to workstation w
    model.x = pyo.Var(model.P, model.W, domain=pyo.Binary)

    # Helper vars: workload per workstation
    model.ws_load = pyo.Var(model.W, domain=pyo.NonNegativeReals)

    # Priority: overdue patients get higher weight
    priorities = [
        patients[p].eot * (1 + max(0, current_week_end - patients[p].day - patients[p].mtb))
        for p in model.P
    ]

    # Objective: maximize total priority + small balancing term
    model.obj = pyo.Objective(
        expr=sum(model.x[p, w] * priorities[p] for p in model.P for w in model.W)
             - 0.01 * sum((model.ws_load[w] - weekly_limit/ws_count)**2 for w in model.W),
        sense=pyo.maximize
    )

    # Constraint: each patient assigned at most once
    model.patient_once = pyo.ConstraintList()
    for p in model.P:
        model.patient_once.add(sum(model.x[p, w] for w in model.W) <= 1)

    # Constraint: workstation load and weekly limit
    model.ws_limit = pyo.ConstraintList()
    for w in model.W:
        model.ws_limit.add(model.ws_load[w] == sum(model.x[p, w] * patients[p]["eot"] for p in model.P))
        model.ws_limit.add(model.ws_load[w] <= weekly_limit)

    # Solve
    solver = pyo.SolverFactory('cplex')
    results = solver.solve(model, tee=False)

    if (results.solver.status != pyo.SolverStatus.ok) or (results.solver.termination_condition != pyo.TerminationCondition.optimal):
        print("Warning: solver failed, skipping assignment this week.")
        return []

    # Extract assignment
    batch = []
    for p in model.P:
        for w in model.W:
            if pyo.value(model.x[p, w]) > 0.5:
                batch.append({
                    "id": patients[p].id,
                    "eot": round(patients[p].eot, 2),
                    "day": patients[p].day,
                    "mtb": patients[p].mtb,
                    "workstation": w + 1,
                    "overdue": current_week_end - patients[p].day >= patients[p].mtb
                })
    return batch

def group_weekly_with_mtb_logic_optimized(ops_dict, weekly_limit=Settings.weekly_operation_limit, week_length_days=Settings.week_length_days, workstations_per_type=None, seed=None):
    """Groups patients into weekly batches using Pyomo/CPLEX optimization."""
    if seed is not None:
        random.seed(seed)

    grouped_schedule = {}

    for op_type, patients in ops_dict.items():
        ws_count = workstations_per_type.get(op_type, 1)
        remaining = patients.copy()
        week_number = 0
        grouped_schedule[op_type] = []

        max_weeks = len(patients) * 2  # hard cap safeguard

        while remaining and week_number < max_weeks:
            current_week_start = week_number * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            # Pazienti disponibili: solo quelli arrivati PRIMA dell'inizio della settimana corrente
            available_patients = [p for p in remaining if p.day < current_week_start]

            # Skip week if no patients available yet
            if not available_patients:
                grouped_schedule[op_type].append({
                    "week": week_number,
                    "patients": []
                })
                week_number += 1
                continue

            # Split into overdue now, overdue next, normal
            overdue_now = [p for p in available_patients if current_week_end - p.day >= p.mtb]
            overdue_next = [p for p in available_patients if next_week_end - p.day >= p.mtb and p not in overdue_now]
            normal = [p for p in available_patients if p not in overdue_now and p not in overdue_next]

            ordered_patients = overdue_now + overdue_next + normal

            # Optimize assignment
            batch = optimize_weekly_batch(ordered_patients, ws_count, weekly_limit, current_week_end)

            if not batch:
                # No assignments this week → advance week
                grouped_schedule[op_type].append({
                    "week": week_number + 1,
                    "patients": []
                })

                # Safety: if ALL patients are available but still no assignment → stop
                if all(p["day"] <= current_week_end for p in remaining):
                    raise RuntimeError(
                        f"Week {week_number+1}: Solver assigned no patients even though all are available."
                    )

                week_number += 1
                continue

            # Remove assigned patients from remaining
            assigned_ids = {p['id'] for p in batch}
            remaining = [p for p in remaining if p.id not in assigned_ids]

            grouped_schedule[op_type].append({
                "week": week_number + 1,
                "patients": batch
            })

            week_number += 1

        if week_number >= max_weeks and remaining:
            raise RuntimeError(
                f"Aborted: hit week cap ({max_weeks}) for {op_type} but still have {len(remaining)} patients unscheduled."
            )

    return grouped_schedule
#endregion

#region Ottimizzazione giornaliera con Pyomo e CPLEX_Direct
     
def optimize_daily_batch_cplex_direct(patients: List[Patient], specialty: str) -> list[Patient]:
    """
    Ottimizza l'assegnazione dei pazienti alle sale operatorie e ai giorni della settimana,
    popolando un oggetto Week tramite insertPatient.
    """
    patient_list = sorted(patients, key=lambda p: p.day)
    day_for_week = Settings.week_length_days #giorni lavorativi a settimana
    day_start = Settings.start_week_scheduling * day_for_week #inizio settimana lavorativa
    operating_rooms = Settings.workstations_config[specialty] #sale operatorie per specialità
    current_day = day_start
    weekly_patients = [p for p in patient_list if p.day < current_day] #lista di pazienti da schedulare nella settimana
    current_model = None
    result = []
    while len(weekly_patients) > 0:
        print(f"Scheduling for {specialty}, Week starting day {current_day}")
        current_model = CreatePyomoModel(weekly_patients, operating_rooms, current_day, current_model)
        #run solver
        Settings.solver.solve(current_model, tee=Settings.solver_tee)
        if False: #debug
            print("Solver Status:", Settings.solver.status)
            print("Termination Condition:", Settings.solver.termination_condition)
            assignazioni = [(i,current_model.id_p[i], k, t, current_model.dr[i], current_model.mtb[i], pyo.value(current_model.ORs[i, t, k])) for i in current_model.I for k in current_model.K for t in current_model.T]
            scrivi_csv_incrementale(assignazioni, nome_file = f"model_results_{specialty.replace(' ', '_')}.csv")
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
            print(f"Reached the maximum scheduling period for {specialty}. Stopping further scheduling.")
            break
    return result

#endregion

#region Ottimizzazione giornaliera con Pyomo e CPLEX
def optimize_daily_batch_cplex(patients: List[Patient], specialty: str) -> list[Patient]:
    """
    Ottimizza l'assegnazione dei pazienti alle sale operatorie e ai giorni della settimana,
    popolando un oggetto Week tramite insertPatient.
    """
    patient_list = sorted(patients, key=lambda p: p.day)
    day_for_week = Settings.week_length_days #giorni lavorativi a settimana
    day_start = Settings.start_week_scheduling * day_for_week #inizio settimana lavorativa
    operating_rooms = Settings.workstations_config[specialty] #sale operatorie per specialità
    current_day = day_start
    weekly_patients = [p for p in patient_list if p.day < current_day] #lista di pazienti da schedulare nella settimana
    current_model = None
    result = []
    while len(weekly_patients) > 0:
        print(f"Scheduling for {specialty}, Week starting day {current_day}")
        current_model = CreatePyomoModel(weekly_patients, operating_rooms, current_day, None)
        #run solver
        Settings.solver.solve(current_model, tee=Settings.solver_tee)
        if False: #debug
            print("Solver Status:", Settings.solver.status)
            print("Termination Condition:", Settings.solver.termination_condition)
            assignazioni = [(i,current_model.id_p[i], k, t, current_model.dr[i], current_model.mtb[i], pyo.value(current_model.ORs[i, t, k])) for i in current_model.I for k in current_model.K for t in current_model.T]
            scrivi_csv_incrementale(assignazioni, nome_file = f"model_results_{specialty.replace(' ', '_')}.csv")
        #rimuovo i pazienti assegnati dalla lista settimanale
        weekly_patients = [p for p in weekly_patients if p.id not in [current_model.id_p[i] for i in current_model.I if any(pyo.value(current_model.ORs[i, t, k])==1 for t in current_model.T for k in current_model.K)]]
        current_day += day_for_week
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
            print(f"Reached the maximum scheduling period for {specialty}. Stopping further scheduling.")
            break
    return result
#endregion

#region Ottimizzazione giornaliera con ROT e Overflow Time

def execute_week_with_rot(
    weekly_patients: list[Patient],
    specialty: str,
    week_start_day: int,
    extra_time_pool: float,
):
    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days

    patients = sorted(weekly_patients, key=lambda p: p.eot)

    executed_patients = []
    overflow_to_next_week = []

    current_day = week_start_day
    remaining_day_time = day_limit

    for patient in patients:
        rot = getattr(patient, "rot", patient.eot)
        eot = patient.eot

        while True:
            if current_day >= week_start_day + week_days:
                overflow_to_next_week.append(patient)
                break

            if rot <= remaining_day_time:
                remaining_day_time -= rot
                patient.opDay = current_day
                executed_patients.append(patient)
                break

            overflow = rot - remaining_day_time
            compensable = overflow / 2

            if extra_time_pool > 0 and remaining_day_time > 0:
                used_extra = min(compensable, extra_time_pool)
                extra_time_pool -= used_extra

                patient.opDay = current_day
                executed_patients.append(patient)
                remaining_day_time = 0
                break

            current_day += 1
            remaining_day_time = day_limit

    return executed_patients, overflow_to_next_week, extra_time_pool

#endregion

#region Ottimizzazione settimanale con ROT e Overflow time

def group_daily_with_mtb_logic_rot(
    ops_dict,
    weekly_limit=Settings.weekly_operation_limit,
    week_length_days=Settings.week_length_days,
    weekly_extra_time=Settings.weekly_extra_time_pool,
    seed=None,
):
    """
    Same structure as group_daily_with_mtb_logic_optimized, but:
    - weekly selection uses EOT (unchanged)
    - daily execution uses ROT + weekly extra-time pool
    """

    if seed is not None:
        random.seed(seed)

    final_schedule = {}

    for op_type, patients in ops_dict.items():
        remaining = sorted(patients, key=lambda p: p.day)
        week_number = 0
        final_schedule[op_type] = []

        max_weeks = len(patients) * 2  # safety cap

        while remaining and week_number < max_weeks:
            week_start_day = week_number * week_length_days
            week_end_day = week_start_day + week_length_days - 1

            # Patients available for weekly selection (UNCHANGED)
            weekly_candidates = [p for p in remaining if p.day < week_start_day]

            if not weekly_candidates:
                final_schedule[op_type].append({
                    "week": week_number + 1,
                    "patients": []
                })
                week_number += 1
                continue

            # === WEEKLY SELECTION USING EOT (UNCHANGED LOGIC) ===
            ordered = sorted(
                weekly_candidates,
                key=lambda p: (
                    -(week_end_day - p.day >= p.mtb),  # overdue first
                    p.day
                )
            )

            weekly_eot_sum = 0
            weekly_selected = []

            for p in ordered:
                if weekly_eot_sum + p.eot <= weekly_limit:
                    weekly_selected.append(p)
                    weekly_eot_sum += p.eot

            if not weekly_selected:
                week_number += 1
                continue

            # === DAILY EXECUTION USING ROT ===
            executed, overflow, remaining_extra = execute_week_with_rot(
                weekly_patients=weekly_selected,
                specialty=op_type,
                week_start_day=week_start_day,
                extra_time_pool=weekly_extra_time,
            )

            # Record executed patients
            final_schedule[op_type].append({
                "week": week_number + 1,
                "patients": executed,
                "extra_time_left": round(remaining_extra, 2),
            })

            # Remove executed patients
            executed_ids = {p.id for p in executed}
            remaining = [p for p in remaining if p.id not in executed_ids]

            # Overflow patients go to next week (already still in remaining)
            week_number += 1

        if week_number >= max_weeks and remaining:
            raise RuntimeError(
                f"ROT scheduling aborted for {op_type}: still {len(remaining)} patients unscheduled."
            )

    return final_schedule

#endregion
