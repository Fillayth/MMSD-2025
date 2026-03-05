import os
from pyexpat import model
import sys

import pyomo.environ as pyo
import random
import csv

from typing import List 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve
from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Patient import Patient
from CommonClass.Week import Week
from settings import Settings

#region Funzioni di supporto

def PyomoModel_withROT(newPatientsList: list[Patient], operatingRoom_count: int, startTime: int) -> pyo.ConcreteModel:
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
        return None

    bigM = 10000  # grande abbastanza
    safety_factor = 0.20  # 20% riduzione capacità quando extra critici
    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit
    weekly_extra_time_pool = Settings.weekly_extra_time_pool

    newPatientsList = sorted(newPatientsList, key = lambda p: p.id)
    
    #regola: il paziente viene selezionato solo una volta
    def patient_once(model, i):
        return sum(model.ORs[i, t, k] for t in model.T for k in model.K )<= 1
        # return sum(model.ORs[i, t, k] for k in model.K for t in model.T )<= 1
    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    def time_rule(model, t, k):
        #print(f"Max worktime for day {t}, room {k}: {pyo.value(model.s[t, k])} minutes | Total assigned time: {sum(model.ORs[i, t, k] * model.eot[i] for i in model.I)} minutes \n")
        return sum( model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s[t, k]
    #regla: vincolo sul tempo massimo utilizzabile in una sala operatoria in un giorno
    def OR_time_limit(model, t, k):
        planned = sum(model.eot[i] * model.ORs[i, t, k] for i in model.I)
        return planned <= model.s[t, k] # .effective_s[t, k] + model.extra_used[t]
    #regola: Tempo reale utilizzato per giorno e sala
    def real_time_rule(model, t, k):
        return model.real_time[t, k] == sum(model.rot[i] * model.ORs[i, t, k] for i in model.I)
    #regola: Overload: quanto il ROT eccede la capacità base s[t,k]
    def overload_rule(m, t, k):
        # overload >= real_time - s, ma non può essere negativo
        return m.overload[t, k] >= m.real_time[t, k] - m.s[t, k]
    #regola: Extra giornaliero deve coprire la somma degli overload delle sale
    def extra_consumption_rule(m, t):
        return m.extra_used[t] >= sum(m.overload[t, k] for k in m.K)
    #regola:  Limite settimanale di extra usato
    def weekly_extra_limit_rule(m):
        return sum(m.extra_used[t] for t in m.T) <= m.extra

    #regola: Calcolo del consumo totale di extra time usato nella settimana
    def total_extra_used(model):
        return model.extra_used_week == sum(model.extra_used[t] for t in model.T)
    #regola: attivazione del trigger per gli extra critici
    def extra_critical_trigger(model):
        return model.extra_used_week - 0.5 * model.extra <= bigM * model.extra_critical
    #regola: calcolo dinamico della capacità effettiva giornaliera
    def effective_capacity(model, t, k):
       return model.effective_s[t, k] == model.s[t, k] - model.safety_factor * model.s[t, k] * model.extra_critical

    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    def objective_rule_M1(model):
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K )        
    


    model = pyo.ConcreteModel()
    model.I = pyo.Set(initialize = range(len(newPatientsList))) #set pazienti
    model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
    model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

    model.id_p = pyo.Param(model.I, initialize={i: newPatientsList[i].id  for i in range(len(newPatientsList))})
    model.dr   = pyo.Param(model.I, initialize={i: newPatientsList[i].day for i in range(len(newPatientsList))})
    model.mtb  = pyo.Param(model.I, initialize={i: newPatientsList[i].mtb for i in range(len(newPatientsList))})
    model.eot  = pyo.Param(model.I, initialize={i: newPatientsList[i].eot for i in range(len(newPatientsList))})
    model.rot  = pyo.Param(model.I, initialize={i: newPatientsList[i].rot for i in range(len(newPatientsList))})


    model.s = pyo.Param(model.T, model.K, initialize = max_worktime_for_day) #set tempo massimo per sala operatoria
    model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary )  #variabile binaria di assegnazione pazienti a sale operatorie e giorni
    
    # Extra settimanale disponibile
    model.extra = pyo.Param(initialize=weekly_extra_time_pool)
    # Variabile binaria che indica se siamo oltre metà degli extra
    model.extra_critical = pyo.Var(domain=pyo.Binary)
    # Capacità effettiva giornaliera (dinamica)
    model.effective_s = pyo.Var(model.T, model.K, domain=pyo.NonNegativeReals)
    # Fattore di sicurezza da applicare quando gli extra sono oltre metà
    model.safety_factor = pyo.Param(initialize=safety_factor)  # 20% riduzione capacità
    # Straordinario usato per ciascun giorno
    model.extra_used = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    # Tempo reale giornaliero per sala
    model.real_time = pyo.Var(model.T, model.K, domain=pyo.NonNegativeReals)
    # Overload (quanto il ROT eccede la capacità base s per sala e giorno)
    model.overload = pyo.Var(model.T, model.K, domain=pyo.NonNegativeReals)
    # Totale extra usato nella settimana
    model.extra_used_week = pyo.Var(domain=pyo.NonNegativeReals)



    #regola: il paziente viene selezionato solo una volta
    model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)
    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    # model.rule_max_ORs_time = pyo.Constraint(model.T, model.K, rule = time_rule)
    #regla: vincolo sul tempo massimo utilizzabile in una sala operatoria in un giorno
    model.OR_time_limit = pyo.Constraint(model.T, model.K, rule=OR_time_limit)
    #regola: Tempo reale utilizzato per giorno e sala
    model.real_time_rule = pyo.Constraint(model.T, model.K, rule=real_time_rule)
    #regola: Overload: quanto il ROT eccede la capacità base s[t,k]
    model.overload_rule = pyo.Constraint(model.T, model.K, rule=overload_rule)
    #regola: Extra giornaliero deve coprire la somma degli overload delle sale
    model.extra_consumption_rule = pyo.Constraint(model.T, rule=extra_consumption_rule)
    #regola:  Limite settimanale di extra usato
    model.weekly_extra_limit = pyo.Constraint(rule=weekly_extra_limit_rule)
    #regola: Calcolo del consumo totale di extra time usato nella settimana
    model.total_extra_used = pyo.Constraint(rule=total_extra_used)
    #regola: attivazione del trigger per gli extra critici
    model.extra_critical_trigger = pyo.Constraint(rule=extra_critical_trigger)
    #regola: calcolo dinamico della capacità effettiva giornaliera
    model.effective_capacity = pyo.Constraint(model.T, model.K, rule=effective_capacity)

    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)
    return model

def PyomoModel_0(newPatientsList: list[Patient], operatingRoom_count: int, startTime: int) -> pyo.ConcreteModel:
    if not newPatientsList or len(newPatientsList) == 0:
        return None

    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit
    
    newPatientsList = sorted(newPatientsList, key = lambda p: p.id)
    
    #regola: il paziente viene selezionato solo una volta
    def patient_once(model, i):
        return sum(model.ORs[i, t, k] for t in model.T for k in model.K )<= 1
        # return sum(model.ORs[i, t, k] for k in model.K for t in model.T )<= 1
    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    def time_rule(model, t, k):
        #print(f"Max worktime for day {t}, room {k}: {pyo.value(model.s[t, k])} minutes | Total assigned time: {sum(model.ORs[i, t, k] * model.eot[i] for i in model.I)} minutes \n")
        return sum( model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s[t, k]
    #regla: vincolo sul tempo massimo utilizzabile in una sala operatoria in un giorno
    def OR_time_limit(model, t, k):
        planned = sum(model.eot[i] * model.ORs[i, t, k] for i in model.I)
        return planned <= model.s[t, k] # .effective_s[t, k] + model.extra_used[t]
    
    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    def objective_rule_M1(model):
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K )        
    


    model = pyo.ConcreteModel()
    model.I = pyo.Set(initialize = range(len(newPatientsList))) #set pazienti
    model.T = pyo.Set(initialize = range(startTime, startTime + max_day_for_week)) #set sale operatorie 
    model.K = pyo.Set(initialize = range(1, operatingRoom_count+1)) #set sale operatorie 

    model.id_p = pyo.Param(model.I, initialize={i: newPatientsList[i].id  for i in range(len(newPatientsList))})
    model.dr   = pyo.Param(model.I, initialize={i: newPatientsList[i].day for i in range(len(newPatientsList))})
    model.mtb  = pyo.Param(model.I, initialize={i: newPatientsList[i].mtb for i in range(len(newPatientsList))})
    model.eot  = pyo.Param(model.I, initialize={i: newPatientsList[i].eot for i in range(len(newPatientsList))})
    

    model.s = pyo.Param(model.T, model.K, initialize = max_worktime_for_day) #set tempo massimo per sala operatoria
    model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary )  #variabile binaria di assegnazione pazienti a sale operatorie e giorni
    
    


    #regola: il paziente viene selezionato solo una volta
    model.rule_patient_once = pyo.Constraint(model.I, rule = patient_once)
    #regola: il tempo massimo per una sessione nella sala operatoria non deve essere superato
    model.rule_max_ORs_time = pyo.Constraint(model.T, model.K, rule = time_rule)
    #regla: vincolo sul tempo massimo utilizzabile in una sala operatoria in un giorno
    model.OR_time_limit = pyo.Constraint(model.T, model.K, rule=OR_time_limit)
    
    ##obiettivo: il tenpo di attesa dr+mdb-t deve essere il minore possibile 
    #obiettivo: massimizzare l'occupazione delle sale operatorie ORs
    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)
    return model

def pick_next_patient_realtime(candidates, today, remaining_capacity_eot):
    """
    Sceglie il prossimo paziente tra quelli disponibili OGGI (candidates),
    usando solo info note ex-ante sul prossimo caso: MTB + EOT.
    """
    feasible = []
    for p in candidates:
        if p.eot <= remaining_capacity_eot:
            feasible.append(p)

    if not feasible:
        return None

    feasible.sort(key=lambda p: (
        (p.day + p.mtb) - today,  # slack MTB: più piccolo = più urgente
        p.eot                     # poi EOT più piccolo (massimizza count)
    ))

    return feasible[0]

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
    filepath = Settings.resultsData_folder 
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

#region Ottimizzazione giornaliera con Pyomo e CPLEX
def optimize_daily_batch_cplex(patients: List[Patient], specialty: str) -> list[Patient]:
    """
    Ottimizza l'assegnazione dei pazienti alle sale operatorie e ai giorni della settimana,
    popolando un oggetto Week tramite insertPatient.
    Return: restituisce tutta la lista dei pazienti schedulati giornalmente in piu settimane
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
        #print(f"Scheduling for {specialty}, Week starting day {current_day}")
        current_model = PyomoModel_0(weekly_patients, operating_rooms, current_day)
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
            rot = patients[[p.id for p in patients].index(current_model.id_p[i])].rot,
            opDay= t,
            workstation= k,
            overdue=False)
            for i in current_model.I for k in current_model.K for t in current_model.T if pyo.value(current_model.ORs[i, t, k])==1])
        #controllo per evitare loop infiniti
        if current_day > day_start + (Settings.weeks_to_fill + 3) * day_for_week:
            print(f"Reached the maximum scheduling period for {specialty} and week from {day_start} to {current_day}. Stopping further scheduling.")
            break
    return result
#endregion

#region Ottimizzazione con ROT e Overflow Time

def execute_week_with_rot(
    weekly_patients: list[Patient],
    specialty: str,
    week_start_day: int,
    extra_time_pool: float,
):
    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days

    # shortest EOT first (as specified)
    patients = sorted(weekly_patients, key=lambda p: p.eot)

    executed_patients = []
    overflow_to_next_week = []

    current_day = week_start_day
    remaining_day_time = day_limit

    for patient in patients:
        eot = patient.eot
        # rot = getattr(patient, "rot", eot)
        rot = patient.rot if patient.rot is not None else eot
        #print(f"eot = {eot}, rot = {rot}")

        while True:
            # --- No more days in this week ---
            if current_day >= week_start_day + week_days:
                print(
                    f"[NEXT WEEK] Patient {patient.id} "
                    f"cannot be scheduled in week starting day {week_start_day}"
                )
                overflow_to_next_week.append(patient)
                break

            # --- Planning feasibility check (EOT-based) ---
            if eot > remaining_day_time:
                print(
                    f"[NEXT DAY] Patient {patient.id} | "
                    f"EOT={eot:.2f} > remaining day time={remaining_day_time:.2f}"
                )
                current_day += 1
                remaining_day_time = day_limit
                continue

            # --- ROT deviation ---
            delta = rot - eot
            #print(f"delta = {delta}")

            # --- Overflow eligibility ---
            in_first_half = remaining_day_time >= (day_limit / 2)

            if delta > 0 and in_first_half and extra_time_pool > 0:
                used_overflow = min(delta / 2, extra_time_pool)

                extra_time_pool -= used_overflow

                print(
                    f"[OVERFLOW USED] Patient {patient.id} | "
                    f"Day {current_day} | "
                    f"Day total={day_limit} | "
                    f"Remaining before={remaining_day_time:.2f} | "
                    f"ROT-EOT={delta:.2f} | "
                    f"Overflow used={used_overflow:.2f} | "
                    f"Pool left={extra_time_pool:.2f}"
                )

            elif delta > 0:
                # ROT exceeds EOT but overflow not allowed → shift patient
                print(
                    f"[NEXT DAY - NO OVERFLOW] Patient {patient.id} | "
                    f"ROT-EOT={delta:.2f} | "
                    f"Remaining={remaining_day_time:.2f}"
                )
                current_day += 1
                remaining_day_time = day_limit
                continue

            # --- Patient executed ---
            remaining_day_time -= eot
            patient.opDay = current_day
            executed_patients.append(patient)
            break

    return executed_patients, overflow_to_next_week, extra_time_pool

def simulate_week_rot(planned_patients: List[Patient], specialty: str, week_start_day: int):
    # Sequencing check / realtime logic vive in clean_week_with_rot
    executed, overflow, extra_time_left, week_stats = clean_week_with_rot(
        patients=planned_patients,
        specialty=specialty,
        week_start_day=week_start_day,
        extra_time_pool=Settings.weekly_extra_time_pool
    )
    return executed, overflow, extra_time_left, week_stats

def plan_week_eot(patients: List[Patient], specialty: str, week_start_day: int) -> List[Patient]:
    operating_rooms = Settings.workstations_config[specialty]

    model = PyomoModel_0(patients, operating_rooms, week_start_day)
    Settings.solver.solve(model, tee=Settings.solver_tee)

    planned = [
        Patient(
            id=model.id_p[i],
            eot=model.eot[i],
            day=model.dr[i],
            mtb=model.mtb[i],
            rot=patients[[p.id for p in patients].index(model.id_p[i])].rot,
            opDay=t,
            workstation=k,
            overdue=False
        )
        for i in model.I for k in model.K for t in model.T
        if pyo.value(model.ORs[i, t, k]) == 1
    ]

    # Solo determinismo (NON swap): rende l'output stabile
    planned.sort(key=lambda p: (p.opDay, p.workstation, p.id))
    return planned

def clean_week_with_rot(
        patients: List[Patient],
        specialty: str,
        week_start_day: int,
        extra_time_pool: float,
    ):
    # variabili utili
    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days
    operationRoom_num = Settings.workstations_config[specialty]

    # risultati
    executed = []
    overflow_to_next_week = []
    remeaning_extra_time_pool = extra_time_pool

    # pazienti slittati dal giorno precedente (da aggiungere al giorno corrente)
    carryover = []

    # stats settimanali
    stats = {
        "week_start_day": week_start_day,
        "daily": {},  # key: "day_<today>_room_<room>"
        "shifted_within_week": 0,
        "overflow_to_next_week": 0
    }

    # per ogni giorno della settimana
    for today in range(week_start_day, week_start_day + week_days):

        # pazienti previsti per oggi + quelli slittati da ieri
        daily_patients = [p for p in patients if p.opDay == today]
        if carryover:
            daily_patients.extend(carryover)
            carryover = []

        # pazienti non eseguiti oggi (da slittare a domani o overflow)
        not_executed_today = []

        # per ogni sala
        for opRoom in range(operationRoom_num):

            room_patients = [p for p in daily_patients if p.workstation == opRoom + 1]

            # ordine "planned" (quello che arriva dal solver / input)
            planned_order = [p.id for p in room_patients]

            # tempo reale consumato (ROT) finora in questa sala oggi
            rot_sum = 0

            # lista locale dei non ancora eseguiti (solo pazienti di OGGI per questa sala)
            remaining = room_patients[:]

            # ordine realmente eseguito (realtime)
            executed_order = []

            while True:

                # capacità residua valutata EX-ANTE con EOT:
                # giorno base + extra rimanente - tempo reale già consumato
                remaining_capacity_eot = (day_limit + remeaning_extra_time_pool) - rot_sum

                if remaining_capacity_eot <= 0:
                    break

                next_p = pick_next_patient_realtime(remaining, today, remaining_capacity_eot)

                if next_p is None:
                    break

                # eseguo next_p: ora conosco il ROT reale di questo caso (monitoraggio realtime)
                rot_sum += next_p.rot
                executed.append(next_p)
                executed_order.append(next_p.id)
                remaining.remove(next_p)

            shifted_ids = [p.id for p in remaining]

            # metrica swap semplice: posizioni diverse tra planned e executed (sui primi m elementi)
            swap_positions = 0
            m = min(len(planned_order), len(executed_order))
            for idx in range(m):
                if planned_order[idx] != executed_order[idx]:
                    swap_positions += 1

            key = f"day_{today}_room_{opRoom+1}"
            stats["daily"][key] = {
                "planned_order": planned_order,
                "executed_order": executed_order,
                "shifted_to_next_day": shifted_ids,
                "executed_count": len(executed_order),
                "shifted_count": len(shifted_ids),
                "swap_positions": swap_positions
            }

            # aggiornamento extra pool a fine sala (consumo extra solo se rot_sum supera day_limit)
            if rot_sum > day_limit:
                remeaning_extra_time_pool = remeaning_extra_time_pool - (rot_sum - day_limit)

            # quelli rimasti in questa sala oggi non sono stati eseguiti
            not_executed_today.extend(remaining)

        # sposto a domani (se domani è dentro la settimana), altrimenti overflow settimana dopo
        next_day = today + 1
        last_day = week_start_day + week_days - 1

        if today < last_day:
            stats["shifted_within_week"] += len(not_executed_today)
            for p in not_executed_today:
                p.opDay = next_day
                carryover.append(p)
        else:
            stats["overflow_to_next_week"] += len(not_executed_today)
            overflow_to_next_week.extend(not_executed_today)

    return executed, overflow_to_next_week, remeaning_extra_time_pool, stats

def optimize_daily_batch_rot(patients: List[Patient], specialty: str) -> list[Patient]:
    """ 
    Utilizza il modello cplex per impostare secondo i tempi eot la schedulazione settimanale 
    e sulla soluzione del modello viene applicata la logica sul ROT + extra-time in modalità realtime:
    - si lavora solo con i pazienti previsti nella giornata
    - si decide chi eseguire oggi e chi spostare a domani (entro la settimana)
    - a fine settimana, ciò che resta va in overflow alla settimana successiva
    """

    patient_list = sorted(patients, key=lambda p: p.day)
    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    operating_rooms = Settings.workstations_config[specialty]

    current_day = day_start
    weekly_patients = [p for p in patient_list if p.day < current_day]

    result = {
        specialty: {
            "patients": [],
            "overflow": [],
            "extra_time_left": [],
            "realtime_stats": []
        }
    }

    # ciclo finché ci sono pazienti da schedulare
    while len(patient_list) > 0:

        print(f"Scheduling for {specialty}, Week starting day {current_day}")

        # 1) Solver: assegna pazienti a giorni e sale usando EOT
        model = PyomoModel_0(weekly_patients, operating_rooms, current_day)
        Settings.solver.solve(model, tee=Settings.solver_tee)

        if False:  # debug
            print("Solver Status:", Settings.solver.status)
            print("Termination Condition:", Settings.solver.termination_condition)
            assignazioni = [
                (i, model.id_p[i], k, t, model.dr[i], model.mtb[i], pyo.value(model.ORs[i, t, k]))
                for i in model.I for k in model.K for t in model.T
            ]
            scrivi_csv_incrementale(assignazioni, nome_file=f"model_results_{specialty.replace(' ', '_')}.csv")

        # estraggo pazienti schedulati dal solver
        scheduled_patients = [
            Patient(
                id=model.id_p[i],
                eot=model.eot[i],
                day=model.dr[i],
                mtb=model.mtb[i],
                rot=patients[[p.id for p in patients].index(model.id_p[i])].rot,
                opDay=t,
                workstation=k,
                overdue=False
            )
            for i in model.I for k in model.K for t in model.T
            if pyo.value(model.ORs[i, t, k]) == 1
        ]

        # 2) Esecuzione realtime nella settimana (decide oggi vs domani) + logging stats
        executed, overflow, extra_time_pool, week_stats = clean_week_with_rot(
            patients=scheduled_patients,
            specialty=specialty,
            week_start_day=current_day,
            extra_time_pool=Settings.weekly_extra_time_pool,
        )

        # 3) Aggiorno la lista settimanale con nuovi arrivi settimana successiva
        current_day += day_for_week
        weekly_patients.extend([
            p for p in patient_list
            if current_day - day_for_week <= p.day < current_day and p not in weekly_patients
        ])

        # rimuovo solo i pazienti eseguiti dalla lista settimanale
        weekly_patients = [p for p in weekly_patients if p.id not in [ep.id for ep in executed]]

        # 4) Salvo risultati settimana
        result[specialty]["patients"].extend(executed)
        result[specialty]["overflow"].append(overflow)
        result[specialty]["extra_time_left"].append(extra_time_pool)
        result[specialty]["realtime_stats"].append(week_stats)

        # controllo per evitare loop infiniti
        if current_day >= day_start + (Settings.weeks_to_fill) * day_for_week:
            print(f"Reached the maximum scheduling period for {specialty}. Stopping further scheduling.")
            break

    return result

def optimize_daily_batch_rot_both(patients: List[Patient], specialty: str):
    patient_list = sorted(patients, key=lambda p: p.day)

    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    current_day = day_start

    weekly_patients = [p for p in patient_list if p.day < current_day]

    result = {
        specialty: {
            "plan_eot": [],          # piano EOT (NO swap)
            "realized_rot": [],      # eseguiti ROT (swap SOLO qui)
            "overflow": [],
            "extra_time_left": [],
            "realtime_stats": []
        }
    }

    while len(patient_list) > 0:
        print(f"Scheduling for {specialty}, Week starting day {current_day}")

        # RAMO A: piano EOT
        planned = plan_week_eot(weekly_patients, specialty, current_day)
        result[specialty]["plan_eot"].extend(planned)

        # RAMO B: realizzato ROT
        executed, overflow, extra_left, week_stats = simulate_week_rot(planned, specialty, current_day)
        result[specialty]["realized_rot"].extend(executed)
        result[specialty]["overflow"].append(overflow)
        result[specialty]["extra_time_left"].append(extra_left)
        result[specialty]["realtime_stats"].append(week_stats)

        # avanzamento settimana
        current_day += day_for_week
        weekly_patients.extend([
            p for p in patient_list
            if current_day - day_for_week <= p.day < current_day and p not in weekly_patients
        ])

        # rimuovo solo gli eseguiti ROT
        executed_ids = {p.id for p in executed}
        weekly_patients = [p for p in weekly_patients if p.id not in executed_ids]

        if current_day >= day_start + (Settings.weeks_to_fill) * day_for_week:
            print(f"Reached the maximum scheduling period for {specialty}. Stopping further scheduling.")
            break

    return result

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
