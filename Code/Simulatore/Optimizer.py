import csv
import math
import os
import sys
from typing import List

import pyomo.environ as pyo

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "CommonClass"))
)
from CommonClass.Patient import Patient
from settings import Settings


#region Model setup e debug
def PyomoModel_0(
    newPatientsList: list[Patient],
    operatingRoom_count: int,
    startTime: int,
) -> pyo.ConcreteModel:
    """Crea il modello Pyomo base EOT per una singola settimana."""
    if not newPatientsList:
        return None

    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit
    newPatientsList = sorted(newPatientsList, key=lambda p: p.id)

    def patient_once(model, i):
        return sum(model.ORs[i, t, k] for t in model.T for k in model.K) <= 1

    def daily_capacity_rule(model, t, k):
        # Ogni sala operatoria non può superare il limite di minuti giornaliero.
        return sum(model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s[t, k]

    def objective_rule_M1(model):
        # Obiettivo volutamente semplice: massimizza solo il numero di pazienti
        # schedulati. La compattazione verso l'inizio settimana viene fatta dopo
        # la soluzione, così il MIP resta molto più rapido.
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K)

    model = pyo.ConcreteModel()
    model.I = pyo.Set(initialize=range(len(newPatientsList)))
    model.T = pyo.Set(initialize=range(startTime, startTime + max_day_for_week))
    model.K = pyo.Set(initialize=range(1, operatingRoom_count + 1))

    model.id_p = pyo.Param(
        model.I,
        initialize={i: newPatientsList[i].id for i in range(len(newPatientsList))},
    )
    model.dr = pyo.Param(
        model.I,
        initialize={i: newPatientsList[i].day for i in range(len(newPatientsList))},
    )
    model.mtb = pyo.Param(
        model.I,
        initialize={i: newPatientsList[i].mtb for i in range(len(newPatientsList))},
    )
    model.eot = pyo.Param(
        model.I,
        initialize={i: newPatientsList[i].eot for i in range(len(newPatientsList))},
    )

    model.s = pyo.Param(model.T, model.K, initialize=max_worktime_for_day)
    model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary)

    model.rule_patient_once = pyo.Constraint(model.I, rule=patient_once)
    # Vincolo sul limite giornaliero per sala operatoria (unico, senza duplicati)
    model.rule_daily_capacity = pyo.Constraint(model.T, model.K, rule=daily_capacity_rule)

    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)
    return model


def scrivi_csv_incrementale(data, nome_file="model_results.csv"):
    """Utility di debug: append dei risultati del modello su CSV."""
    filepath = Settings.resultsData_folder
    output_path = os.path.join(filepath, nome_file)
    with open(output_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["indice_i", "id_i", "w", "d", "day", "mtb", "accettato"])
        for a, b, c, d, e, f, g in data:
            writer.writerow([a, b, c, d, e, f, g])


#endregion


#region Scheduling giornaliero EOT (CPLEX)
def optimize_daily_batch_cplex(patients: List[Patient], specialty: str) -> list[Patient]:
    """Schedula i pazienti per più settimane con modello EOT."""
    patient_list = sorted(patients, key=lambda p: p.day)
    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    operating_rooms = Settings.workstations_config[specialty]

    current_day = day_start
    weekly_patients = [p for p in patient_list if p.day < current_day]
    current_model = None
    result = []

    while len(weekly_patients) > 0:
        current_model = PyomoModel_0(weekly_patients, operating_rooms, current_day)
        Settings.solver.solve(current_model, tee=Settings.solver_tee)

        if False:  # debug
            print("Solver Status:", Settings.solver.status)
            print("Termination Condition:", Settings.solver.termination_condition)
            assignazioni = [
                (
                    i,
                    current_model.id_p[i],
                    k,
                    t,
                    current_model.dr[i],
                    current_model.mtb[i],
                    pyo.value(current_model.ORs[i, t, k]),
                )
                for i in current_model.I
                for k in current_model.K
                for t in current_model.T
            ]
            scrivi_csv_incrementale(
                assignazioni,
                nome_file=f"model_results_{specialty.replace(' ', '_')}.csv",
            )

        weekly_patients = [
            p
            for p in weekly_patients
            if p.id
            not in [
                current_model.id_p[i]
                for i in current_model.I
                if any(
                    pyo.value(current_model.ORs[i, t, k]) == 1
                    for t in current_model.T
                    for k in current_model.K
                )
            ]
        ]

        current_day += day_for_week
        weekly_patients.extend(
            [
                p
                for p in patient_list
                if current_day - day_for_week <= p.day < current_day and p not in weekly_patients
            ]
        )

        result.extend(
            [
                Patient(
                    id=current_model.id_p[i],
                    eot=current_model.eot[i],
                    day=current_model.dr[i],
                    mtb=current_model.mtb[i],
                    rot=patients[[p.id for p in patients].index(current_model.id_p[i])].rot,
                    opDay=t,
                    workstation=k,
                    overdue=False,
                )
                for i in current_model.I
                for k in current_model.K
                for t in current_model.T
                if pyo.value(current_model.ORs[i, t, k]) == 1
            ]
        )

        if current_day > day_start + (Settings.weeks_to_fill + 3) * day_for_week:
            print(
                f"Reached the maximum scheduling period for {specialty} and week "
                f"from {day_start} to {current_day}. Stopping further scheduling."
            )
            break

    return result


#endregion


#region Resequencing ROT (supporto realtime)
def compute_w_tilde(p: Patient, today: int, phi: int) -> float:
    r"""Calcola $\tilde{w}_i = (t_i + \phi) / MTB_i$."""
    waiting_time = max(0, today - p.day)
    if p.mtb <= 0:
        return math.inf
    return (waiting_time + phi) / p.mtb


def best_fit_order_low_priority(low_priority, remaining_capacity_eot):
    """Ordina i pazienti low-priority con approccio greedy best-fit."""
    ordered = []
    remaining = low_priority[:]
    local_capacity = remaining_capacity_eot

    while remaining and local_capacity > 0:
        feasible = [item for item in remaining if item["patient"].eot <= local_capacity]
        if not feasible:
            break

        best = min(feasible, key=lambda x: local_capacity - x["patient"].eot)
        ordered.append(best)
        remaining.remove(best)
        local_capacity -= best["patient"].eot

    remaining.sort(key=lambda x: x["original_idx"])
    ordered.extend(remaining)
    return ordered


def resequence_remaining_patients(
    candidates: List[Patient],
    today: int,
    remaining_capacity_eot: float,
    week_start_day: int,
    week_days: int,
) -> List[Patient]:
    """Riordina i pazienti rimanenti secondo la priorità del prossimo orizzonte."""
    if not candidates:
        return []

    next_horizon_start = week_start_day + week_days
    phi = next_horizon_start - today
    eps = 1e-9

    enriched = []
    for idx, patient in enumerate(candidates):
        w_tilde = compute_w_tilde(patient, today, phi)
        enriched.append({"patient": patient, "w_tilde": w_tilde, "original_idx": idx})

    high_priority = [x for x in enriched if x["w_tilde"] > 1.0 + eps]
    borderline = [x for x in enriched if abs(x["w_tilde"] - 1.0) <= eps]
    low_priority = [x for x in enriched if x["w_tilde"] < 1.0 - eps]

    high_priority.sort(key=lambda x: x["w_tilde"], reverse=True)
    borderline.sort(key=lambda x: x["original_idx"])

    ordered = []
    residual_after_high = remaining_capacity_eot

    for item in high_priority:
        ordered.append(item)
        residual_after_high -= item["patient"].eot

    for item in borderline:
        ordered.append(item)
        residual_after_high -= item["patient"].eot

    if residual_after_high > 0:
        ordered.extend(best_fit_order_low_priority(low_priority, residual_after_high))
    else:
        low_priority.sort(key=lambda x: x["original_idx"])
        ordered.extend(low_priority)

    return [x["patient"] for x in ordered]


#endregion


#region Simulazione settimanale ROT
def clean_week_with_rot(
    patients: List[Patient],
    specialty: str,
    week_start_day: int,
    extra_time_pool: float,
):
    """Esegue la settimana in logica realtime e produce statistiche di esecuzione."""
    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days
    operationRoom_num = Settings.workstations_config[specialty]

    executed = []
    overflow_to_next_week = []
    remeaning_extra_time_pool = extra_time_pool
    carryover = []

    stats = {
        "week_start_day": week_start_day,
        "daily": {},
        "shifted_within_week": 0,
        "overflow_to_next_week": 0,
    }

    for today in range(week_start_day, week_start_day + week_days):
        daily_patients = [p for p in patients if p.opDay == today]
        if carryover:
            daily_patients.extend(carryover)
            carryover = []

        not_executed_today = []

        for opRoom in range(operationRoom_num):
            room_patients = [p for p in daily_patients if p.workstation == opRoom + 1]
            planned_order = [p.id for p in room_patients]

            rot_sum = 0
            remaining = room_patients[:]
            executed_order = []

            while remaining:
                remaining_capacity_eot = (day_limit + remeaning_extra_time_pool) - rot_sum
                if remaining_capacity_eot <= 0:
                    break

                resequenced = resequence_remaining_patients(
                    candidates=remaining,
                    today=today,
                    remaining_capacity_eot=remaining_capacity_eot,
                    week_start_day=week_start_day,
                    week_days=week_days,
                )

                if not resequenced:
                    break

                next_p = resequenced[0]
                if next_p.eot > remaining_capacity_eot:
                    break

                rot_sum += next_p.rot
                executed.append(next_p)
                executed_order.append(next_p.id)
                remaining.remove(next_p)

            shifted_ids = [p.id for p in remaining]
            swap_positions = 0
            m = min(len(planned_order), len(executed_order))
            for idx in range(m):
                if planned_order[idx] != executed_order[idx]:
                    swap_positions += 1

            key = f"day_{today}_room_{opRoom + 1}"
            stats["daily"][key] = {
                "planned_order": planned_order,
                "executed_order": executed_order,
                "shifted_to_next_day": shifted_ids,
                "executed_count": len(executed_order),
                "shifted_count": len(shifted_ids),
                "swap_positions": swap_positions,
            }

            if rot_sum > day_limit:
                remeaning_extra_time_pool -= (rot_sum - day_limit)

            not_executed_today.extend(remaining)

        next_day = today + 1
        last_day = week_start_day + week_days - 1

        if today < last_day:
            stats["shifted_within_week"] += len(not_executed_today)
            for patient in not_executed_today:
                patient.opDay = next_day
                carryover.append(patient)
        else:
            stats["overflow_to_next_week"] += len(not_executed_today)
            overflow_to_next_week.extend(not_executed_today)

    return executed, overflow_to_next_week, remeaning_extra_time_pool, stats


def simulate_week_rot(planned_patients: List[Patient], specialty: str, week_start_day: int):
    """Wrapper della simulazione ROT con extra time settimanale da Settings."""
    executed, overflow, extra_time_left, week_stats = clean_week_with_rot(
        patients=planned_patients,
        specialty=specialty,
        week_start_day=week_start_day,
        extra_time_pool=Settings.weekly_extra_time_pool,
    )
    return executed, overflow, extra_time_left, week_stats


#endregion


#region Orchestrazione EOT + ROT
def compact_eot_schedule_to_week_start(
    planned_patients: List[Patient],
    specialty: str,
    week_start_day: int,
) -> List[Patient]:
    """
    Compatta un piano EOT già fattibile verso l'inizio della settimana.

    Il MIP seleziona rapidamente *quali* pazienti schedulare. Questa funzione,
    lavorando su una soluzione già fattibile, prova poi a spostare ogni paziente
    nel primo slot precedente disponibile senza mai violare il limite giornaliero
    per sala operatoria.
    """
    if not planned_patients:
        return []

    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days
    operating_rooms = Settings.workstations_config[specialty]

    used_time = {
        (day, room): 0.0
        for day in range(week_start_day, week_start_day + week_days)
        for room in range(1, operating_rooms + 1)
    }

    for patient in planned_patients:
        used_time[(patient.opDay, patient.workstation)] += patient.eot

    ordered_patients = sorted(
        planned_patients,
        key=lambda p: (p.opDay, -p.eot, p.workstation, p.id),
    )

    for patient in ordered_patients:
        current_slot = (patient.opDay, patient.workstation)
        used_time[current_slot] -= patient.eot

        best_slot = current_slot
        moved = False

        for day in range(week_start_day, patient.opDay + 1):
            for room in range(1, operating_rooms + 1):
                if used_time[(day, room)] + patient.eot <= day_limit:
                    best_slot = (day, room)
                    moved = True
                    break
            if moved:
                break

        patient.opDay, patient.workstation = best_slot
        used_time[best_slot] += patient.eot

    planned_patients.sort(key=lambda p: (p.opDay, p.workstation, p.id))
    return planned_patients


def plan_week_eot(patients: List[Patient], specialty: str, week_start_day: int) -> List[Patient]:
    """Crea il piano settimanale EOT (deterministico, senza swap)."""
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
            overdue=False,
        )
        for i in model.I
        for k in model.K
        for t in model.T
        if pyo.value(model.ORs[i, t, k]) == 1
    ]

    planned = compact_eot_schedule_to_week_start(planned, specialty, week_start_day)
    planned.sort(key=lambda p: (p.opDay, p.workstation, p.id))
    return planned


def optimize_daily_batch_rot_both(patients: List[Patient], specialty: str):
    """Esegue doppio flusso: piano EOT e realizzato ROT con statistiche realtime."""
    patient_list = sorted(patients, key=lambda p: p.day)
    patient_by_id = {p.id: p for p in patient_list}

    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    current_day = day_start

    weekly_patients = [p for p in patient_list if p.day < current_day]

    result = {
        specialty: {
            "plan_eot": [],
            "realized_rot": [],
            "overflow": [],
            "extra_time_left": [],
            "realtime_stats": [],
        }
    }

    while len(patient_list) > 0:
        week_start = current_day
        print(f"Scheduling for {specialty}, Week starting day {current_day}")

        if not weekly_patients:
            current_day += day_for_week
            if current_day >= day_start + Settings.weeks_to_fill * day_for_week:
                print(
                    f"Reached the maximum scheduling period for {specialty}. "
                    f"Stopping further scheduling."
                )
                break
            weekly_patients.extend(
                [
                    p
                    for p in patient_list
                    if current_day - day_for_week <= p.day < current_day and p not in weekly_patients
                ]
            )
            continue

        planned = plan_week_eot(weekly_patients, specialty, current_day)
        result[specialty]["plan_eot"].extend(planned)

        executed, overflow, extra_left, week_stats = simulate_week_rot(
            planned,
            specialty,
            current_day,
        )
        result[specialty]["realized_rot"].extend(executed)
        result[specialty]["overflow"].append(overflow)
        result[specialty]["extra_time_left"].append(extra_left)
        result[specialty]["realtime_stats"].append(week_stats)

        weekly_ids = {p.id for p in weekly_patients}
        planned_ids = {p.id for p in planned}
        executed_ids = {p.id for p in executed}
        overflow_ids = {p.id for p in overflow}

        not_planned_ids = weekly_ids - planned_ids
        carryover_ids = (planned_ids - executed_ids) | overflow_ids | not_planned_ids
        carryover_count = len(carryover_ids)

        weekly_patients = [
            patient_by_id[pid]
            for pid in carryover_ids
            if pid in patient_by_id
        ]
        weekly_patients.sort(key=lambda p: p.day)

        current_day += day_for_week
        existing_ids = {p.id for p in weekly_patients}
        new_arrivals = [
            p
            for p in patient_list
            if current_day - day_for_week <= p.day < current_day and p.id not in existing_ids
        ]
        weekly_patients.extend(
            new_arrivals
        )

        print(
            f"[WEEK SUMMARY] {specialty} | start_day={week_start} | "
            f"weekly_in={len(weekly_ids)} | planned={len(planned_ids)} | executed={len(executed_ids)} | "
            f"overflow={len(overflow_ids)} | not_planned={len(not_planned_ids)} | "
            f"carryover_next={carryover_count} | new_arrivals={len(new_arrivals)} | "
            f"next_week_in={len(weekly_patients)}"
        )

        if current_day >= day_start + Settings.weeks_to_fill * day_for_week:
            print(
                f"Reached the maximum scheduling period for {specialty}. "
                f"Stopping further scheduling."
            )
            break

    return result


#endregion
