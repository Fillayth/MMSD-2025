import pyomo.environ as pyo
import random

from typing import List 
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 
from settings import Settings
from CommonClass.CommonClass import Patient, Week, Specialty

def optimize_weekly_batch(patients, ws_count, weekly_limit, current_week_end):
    """Optimize assignment of patients to workstations for a single week."""
    if not patients or len(patients) == 0:
        return []

    model = pyo.ConcreteModel()
    model.P = range(len(patients))
    model.W = range(ws_count)

    # Decision variables: x[p, w] = 1 if patient p is assigned to workstation w
    model.x = pyo.Var(model.P, model.W, domain=pyo.Binary)

    # Priority: overdue patients get higher weight
    priorities = [
        patients[p].eot * (1 + max(0, current_week_end - patients[p].day - patients[p].mtb))
        for p in model.P
    ]

    # Objective: maximize total priority
    model.obj = pyo.Objective(
        expr=sum(model.x[p, w] * priorities[p] for p in model.P for w in model.W),
        sense=pyo.maximize
    )

    # Constraint: each patient assigned at most once
    model.patient_once = pyo.ConstraintList()
    for p in model.P:
        model.patient_once.add(sum(model.x[p, w] for w in model.W) <= 1)

    # Constraint: workstation weekly limit
    model.ws_limit = pyo.ConstraintList()
    for w in model.W:
        model.ws_limit.add(sum(model.x[p, w] * patients[p].eot for p in model.P) <= weekly_limit)

    # Solve
    solver = pyo.SolverFactory('cplex_direct')
    solver.solve(model, tee=False)

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

def optimize_daily_batch(patients: List[Patient], current_week: Week) -> list[Week]:
    """
    Ottimizza l'assegnazione dei pazienti alle sale operatorie e ai giorni della settimana,
    popolando un oggetto Week tramite insertPatient.
    """
    num_days = Settings.week_length_days
    ws_count = Settings.workstations_config[current_week.specialty.value]
    daily_limit = Settings.daily_operation_limit

    model = pyo.ConcreteModel()
    model.P = range(len(patients))
    model.W = range(ws_count)
    model.D = range(num_days)

    # x[p, w, d] = 1 se il paziente p è assegnato alla workstation w nel giorno d
    model.x = pyo.Var(model.P, model.W, model.D, domain=pyo.Binary)

    # Ogni paziente assegnato al massimo una volta
    model.patient_once = pyo.ConstraintList()
    for p in model.P:
        model.patient_once.add(sum(model.x[p, w, d] for w in model.W for d in model.D) <= 1)

    # Limite di tempo giornaliero per ogni sala operatoria
    model.ws_daily_limit = pyo.ConstraintList()
    for w in model.W:
        for d in model.D:
            model.ws_daily_limit.add(
                sum(model.x[p, w, d] * patients[p].eot for p in model.P) <= daily_limit
            )

    # Priorità: puoi personalizzare la logica
    priorities = [
        patients[p].eot * (1 + max(0, (current_week.weekNum + 1) * num_days - patients[p].day - patients[p].mtb))
        for p in model.P
    ]

    # Obiettivo: massimizza la priorità totale
    model.obj = pyo.Objective(
        expr=sum(model.x[p, w, d] * priorities[p] for p in model.P for w in model.W for d in model.D),
        sense=pyo.maximize
    )

    # Risolvi
    Settings.solver.solve(model, tee=False)

    # Popola la struttura Week
    weekList = [] 
    for p in model.P:
        for w in model.W:
            for d in model.D:
                if pyo.value(model.x[p, w, d]) > 0.5:
                    # Assegna il paziente al giorno e alla sala operatoria
                    patient = patients[p]
                    # Puoi aggiungere attributi al paziente se necessario
                    patient.workstation = w + 1
                    # Inserisci il paziente nella struttura Week
                    # La Week inserisce nei giorni e nelle sale operatorie tramite insertPatient
                    if (not current_week.insertPatient(patient)):
                        weekList.append(current_week)
                        current_week = Week(current_week.weekNum + 1, current_week.specialty)
                        # if(not current_week.insertPatient(patient)):
                        #     print("Errore: impossibile inserire il paziente anche in una nuova settimana")
                        #     raise Exception("Errore: impossibile inserire il paziente anche in una nuova settimana")
                        current_week.insertPatient(patient)
    return weekList

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

        while remaining:
            current_week_start = week_number * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            # Only consider patients that have arrived
            available_patients = [p for p in remaining if p.day <= current_week_start]

            # Skip week if no patients available yet
            if not available_patients:
                week_number += 1
                continue

            # Split into overdue now, overdue next, normal
            overdue_now = [p for p in available_patients if current_week_end - p.day >= p.mtb]
            overdue_next = [p for p in available_patients if next_week_end - p.day >= p.mtb and p not in overdue_now]
            normal = [p for p in available_patients if p not in overdue_now and p not in overdue_next]

            ordered_patients = overdue_now + overdue_next + normal

            # Optimize assignment
            batch = optimize_weekly_batch(ordered_patients, ws_count, weekly_limit, current_week_end)

            # Remove assigned patients from remaining
            assigned_ids = {p['id'] for p in batch}
            remaining = [p for p in remaining if p.id not in assigned_ids]

            grouped_schedule[op_type].append({
                "week": week_number + 1,
                "patients": batch
            })

            week_number += 1

    return grouped_schedule
