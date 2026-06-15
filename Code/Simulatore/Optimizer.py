"""Scheduler module for EOT planning and ROT execution.

This module contains the weekly EOT model, utility helpers, ROT resequencing
logic, weekly ROT simulation, and the main EOT+ROT orchestration flow.
"""

import csv
import copy
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

import pyomo.environ as pyo

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "CommonClass"))
)
from CommonClass.Patient import Patient
from settings import Settings


#region Model setup and debug helpers
def PyomoModel_0(
    new_patients: List[Patient],
    operating_room_count: int,
    start_time: int,
) -> Optional[pyo.ConcreteModel]:
    """Build the base EOT model for one weekly scheduling horizon.

    The model assigns each patient to at most one OR/day slot. It also enforces
    that the total EOT assigned to each operating room and day does not exceed the
    daily operation limit.
    """
    if not new_patients:
        return None

    max_day_for_week = Settings.week_length_days
    max_worktime_for_day = Settings.daily_operation_limit
    patients_sorted = sorted(new_patients, key=lambda patient: patient.id)

    def patient_once(model, patient_index):
        return sum(model.ORs[patient_index, t, k] for t in model.T for k in model.K) <= 1

    def daily_capacity_rule(model, t, k):
        return sum(model.ORs[i, t, k] * model.eot[i] for i in model.I) <= model.s[t, k]

    def objective_rule_M1(model):
        """Maximize the number of patients assigned in the week."""
        return sum(model.ORs[i, t, k] for i in model.I for t in model.T for k in model.K)
        
        #"""Maximize the total assigned EOT time in the week.

        #This objective encourages the model to fill daily OR capacity and reduce
        #unused idle minutes, instead of only maximizing the count of patients.
        #"""
        #return sum(
        #    model.ORs[i, t, k] * model.eot[i]
        #    for i in model.I
        #    for t in model.T
        #    for k in model.K
        #)
    
    model = pyo.ConcreteModel()
    model.I = pyo.Set(initialize=range(len(patients_sorted)))
    model.T = pyo.Set(initialize=range(start_time, start_time + max_day_for_week))
    model.K = pyo.Set(initialize=range(1, operating_room_count + 1))

    model.id_p = pyo.Param(
        model.I,
        initialize={i: patients_sorted[i].id for i in range(len(patients_sorted))},
    )
    model.dr = pyo.Param(
        model.I,
        initialize={i: patients_sorted[i].day for i in range(len(patients_sorted))},
    )
    model.mtb = pyo.Param(
        model.I,
        initialize={i: patients_sorted[i].mtb for i in range(len(patients_sorted))},
    )
    model.eot = pyo.Param(
        model.I,
        initialize={i: patients_sorted[i].eot for i in range(len(patients_sorted))},
    )

    model.s = pyo.Param(model.T, model.K, initialize=max_worktime_for_day)
    model.ORs = pyo.Var(model.I, model.T, model.K, domain=pyo.Binary)

    model.rule_patient_once = pyo.Constraint(model.I, rule=patient_once)
    model.rule_daily_capacity = pyo.Constraint(model.T, model.K, rule=daily_capacity_rule)
    model.Objective = pyo.Objective(rule=objective_rule_M1, sense=pyo.maximize)

    return model


def scrivi_csv_incrementale(data, nome_file: str = "model_results.csv") -> None:
    """Append model assignment data to a debug CSV file."""
    filepath = Settings.resultsData_folder
    os.makedirs(filepath, exist_ok=True)
    output_path = os.path.join(filepath, nome_file)

    with open(output_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["indice_i", "id_i", "w", "d", "day", "mtb", "accettato"])
        for a, b, c, d, e, f, g in data:
            writer.writerow([a, b, c, d, e, f, g])


#endregion


#region EOT weekly scheduling

def optimize_daily_batch_cplex(patients: List[Patient], specialty: str) -> List[Patient]:
    """Schedule patients in EOT batches by weekly horizon."""
    patient_list = sorted(patients, key=lambda patient: patient.day)
    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    operating_rooms = Settings.workstations_config[specialty]

    current_day = day_start
    weekly_patients = [patient for patient in patient_list if patient.day < current_day]
    result: List[Patient] = []

    while weekly_patients:
        eot_model = PyomoModel_0(weekly_patients, operating_rooms, current_day)
        Settings.solver.solve(eot_model, tee=Settings.solver_tee)

        if False:  # debug block
            print("Solver Status:", Settings.solver.status)
            print("Termination Condition:", Settings.solver.termination_condition)
            assignments = [
                (
                    i,
                    eot_model.id_p[i],
                    k,
                    t,
                    eot_model.dr[i],
                    eot_model.mtb[i],
                    pyo.value(eot_model.ORs[i, t, k]),
                )
                for i in eot_model.I
                for k in eot_model.K
                for t in eot_model.T
            ]
            scrivi_csv_incrementale(
                assignments,
                nome_file=f"model_results_{specialty.replace(' ', '_')}.csv",
            )

        scheduled_ids = {
            eot_model.id_p[i]
            for i in eot_model.I
            if any(pyo.value(eot_model.ORs[i, t, k]) == 1 for t in eot_model.T for k in eot_model.K)
        }

        weekly_patients = [patient for patient in weekly_patients if patient.id not in scheduled_ids]

        current_day += day_for_week
        weekly_patients.extend(
            [
                patient
                for patient in patient_list
                if current_day - day_for_week <= patient.day < current_day and patient not in weekly_patients
            ]
        )

        result.extend(
            [
                Patient(
                    id=eot_model.id_p[i],
                    eot=eot_model.eot[i],
                    day=eot_model.dr[i],
                    mtb=eot_model.mtb[i],
                    rot=[patient for patient in patients if patient.id == eot_model.id_p[i]][0].rot,
                    opDay=t,
                    workstation=k,
                    overdue=False,
                )
                for i in eot_model.I
                for k in eot_model.K
                for t in eot_model.T
                if pyo.value(eot_model.ORs[i, t, k]) == 1
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


#region ROT resequencing helpers

def compute_w_tilde(p: Patient, today: int, phi: int) -> float:
    """Compute the priority score used for ROT resequencing."""
    waiting_time = max(0, today - p.day)
    if p.mtb <= 0:
        return math.inf
    return (waiting_time + phi) / p.mtb


def best_fit_order_low_priority(
    low_priority: List[Dict[str, object]],
    remaining_capacity_eot: float,
) -> List[Dict[str, object]]:
    """Pack low-priority patients greedily into any leftover EOT capacity."""
    ordered: List[Dict[str, object]] = []
    remaining = low_priority[:]
    local_capacity = remaining_capacity_eot

    while remaining and local_capacity > 0:
        feasible = [item for item in remaining if item["patient"].eot <= local_capacity]
        if not feasible:
            break

        best = min(feasible, key=lambda item: local_capacity - item["patient"].eot)
        ordered.append(best)
        remaining.remove(best)
        local_capacity -= best["patient"].eot

    remaining.sort(key=lambda item: item["original_idx"])
    ordered.extend(remaining)
    return ordered


def resequence_remaining_patients(
    candidates: List[Patient],
    today: int,
    remaining_capacity_eot: float,
    week_start_day: int,
    week_days: int,
) -> List[Patient]:
    """Reorder remaining patients for the next real-time horizon.

    High-priority patients are moved first, then borderline patients are kept
    in their original order. Leftover capacity is used to pack low-priority
    patients with a best-fit heuristic.
    """
    if not candidates:
        return []

    next_horizon_start = week_start_day + week_days
    phi = next_horizon_start - today
    eps = 1e-9

    enriched: List[Dict[str, object]] = []
    for idx, patient in enumerate(candidates):
        enriched.append(
            {
                "patient": patient,
                "w_tilde": compute_w_tilde(patient, today, phi),
                "original_idx": idx,
            }
        )

    high_priority = [item for item in enriched if item["w_tilde"] > 1.0 + eps]
    borderline = [item for item in enriched if abs(item["w_tilde"] - 1.0) <= eps]
    low_priority = [item for item in enriched if item["w_tilde"] < 1.0 - eps]

    high_priority.sort(key=lambda item: item["w_tilde"], reverse=True)
    borderline.sort(key=lambda item: item["original_idx"])

    ordered: List[Dict[str, object]] = []
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
        low_priority.sort(key=lambda item: item["original_idx"])
        ordered.extend(low_priority)

    return [item["patient"] for item in ordered]


#endregion


#region ROT weekly simulation

def overtime_with_rot(
    next_p: Patient,
    rot_sum: float,
    today: int,
    day_limit: float,
    remeaning_extra_time_pool: float,
) -> Tuple[bool, float]:
    """Return whether the next patient can be executed and the updated extra-time pool."""
    time_left = day_limit - rot_sum
    if next_p.rot <= time_left:
        return True, remeaning_extra_time_pool

    overtime_needed = next_p.rot - time_left
    if remeaning_extra_time_pool >= overtime_needed:
        remeaning_extra_time_pool -= overtime_needed
        return True, remeaning_extra_time_pool

    return False, remeaning_extra_time_pool


def execute_rot_schedule(
    planned_patients: List[Patient],
    specialty: str,
    week_start_day: int,
    extra_time_pool: float,
) -> Tuple[List[Patient], List[Patient], float, Dict[str, object]]:
    """Execute a single week's ROT plan from an EOT schedule."""
    return clean_week_with_rot(planned_patients, specialty, week_start_day, extra_time_pool)


def clean_week_with_rot(
    patients: List[Patient],
    specialty: str,
    week_start_day: int,
    extra_time_pool: float,
) -> Tuple[List[Patient], List[Patient], float, Dict[str, object]]:
    """Simulate one week of ROT execution and collect execution statistics."""
    day_limit = Settings.daily_operation_limit
    week_days = Settings.week_length_days
    operating_rooms = Settings.workstations_config[specialty]

    executed: List[Patient] = []
    overflow_to_next_week: List[Patient] = []
    remeaning_extra_time_pool = extra_time_pool

    stats: Dict[str, object] = {
        "week_start_day": week_start_day,
        "daily": {},
        "shifted_within_week": 0,
        "overflow_to_next_week": 0,
    }

    for today in range(week_start_day, week_start_day + week_days):
        daily_patients = [p for p in patients if p.opDay == today]
        not_executed_today: List[Patient] = []

        for room_index in range(operating_rooms):
            room_patients = sorted(
                [p for p in daily_patients if p.workstation == room_index + 1],
                key=lambda p: p.id,
            )
            planned_order = [p.id for p in room_patients]

            rot_sum = 0.0
            remaining = room_patients[:]
            executed_order: List[int] = []
            first_patient = True

            while remaining:
                remaining_capacity_eot = (day_limit + remeaning_extra_time_pool) - rot_sum
                if remaining_capacity_eot <= 0:
                    break

                if first_patient:
                    next_p = remaining[0]
                    first_patient = False
                else:
                    resequenced = resequence_remaining_patients(
                        candidates=remaining,
                        today=today,
                        remaining_capacity_eot=remaining_capacity_eot,
                        week_start_day=week_start_day,
                        week_days=week_days,
                    )

                    if not resequenced:
                        break

                    actual_available = day_limit - rot_sum
                    feasible_candidates = [
                        candidate
                        for candidate in resequenced
                        if candidate.rot <= actual_available + remeaning_extra_time_pool
                    ]
                    if not feasible_candidates:
                        break

                    no_overtime = [
                        candidate for candidate in feasible_candidates if candidate.rot <= actual_available
                    ]
                    if no_overtime:
                        next_p = no_overtime[0]
                    else:
                        next_p = min(
                            feasible_candidates,
                            key=lambda p: (p.rot - actual_available, p.rot),
                        )

                can_execute, remeaning_extra_time_pool = overtime_with_rot(
                    next_p,
                    rot_sum,
                    today,
                    day_limit,
                    remeaning_extra_time_pool,
                )
                if not can_execute:
                    break

                rot_sum += next_p.rot
                executed.append(next_p)
                executed_order.append(next_p.id)
                remaining.remove(next_p)

            shifted_ids = [p.id for p in remaining]
            swap_positions = sum(
                1
                for idx in range(min(len(planned_order), len(executed_order)))
                if planned_order[idx] != executed_order[idx]
            )

            stats[f"day_{today}_room_{room_index + 1}"] = {
                "planned_order": planned_order,
                "executed_order": executed_order,
                "shifted_to_next_day": shifted_ids,
                "executed_count": len(executed_order),
                "shifted_count": len(shifted_ids),
                "swap_positions": swap_positions,
            }

            not_executed_today.extend(remaining)

        stats["overflow_to_next_week"] += len(not_executed_today)
        overflow_to_next_week.extend(not_executed_today)

    return executed, overflow_to_next_week, remeaning_extra_time_pool, stats

#endregion


#region EOT + ROT orchestration

def compact_eot_schedule_to_week_start(
    planned_patients: List[Patient],
    specialty: str,
    week_start_day: int,
) -> List[Patient]:
    """Compact a feasible EOT plan toward the beginning of the week.

    The function preserves feasibility while moving patients earlier when
    capacity allows. It considers both day and room capacity.
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
        key=lambda patient: (patient.opDay, -patient.eot, patient.workstation, patient.id),
    )

    for patient in ordered_patients:
        current_slot = (patient.opDay, patient.workstation)
        used_time[current_slot] -= patient.eot

        best_slot = current_slot
        for day in range(week_start_day, patient.opDay + 1):
            for room in range(1, operating_rooms + 1):
                if used_time[(day, room)] + patient.eot <= day_limit:
                    best_slot = (day, room)
                    break
            if best_slot != current_slot:
                break

        patient.opDay, patient.workstation = best_slot
        used_time[best_slot] += patient.eot

    planned_patients.sort(key=lambda patient: (patient.opDay, patient.workstation, patient.id))
    return planned_patients


def plan_week_eot(patients: List[Patient], specialty: str, week_start_day: int) -> List[Patient]:
    """Build the weekly EOT plan and compact it toward the start of the week."""
    operating_rooms = Settings.workstations_config[specialty]

    model = PyomoModel_0(patients, operating_rooms, week_start_day)
    #Settings.solver.options['mipgap'] = 0.01
    Settings.solver.options['timelimit'] = 300
    Settings.solver.solve(model, tee=Settings.solver_tee)

    planned = [
        Patient(
            id=model.id_p[i],
            eot=model.eot[i],
            day=model.dr[i],
            mtb=model.mtb[i],
            rot=[patient for patient in patients if patient.id == model.id_p[i]][0].rot,
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
    planned.sort(key=lambda patient: (patient.opDay, patient.workstation, patient.id))
    return planned





def reallocate_week_with_rot_overtime(
    planned_patients: List[Patient],
    specialty: str,
    week_start_day: int,
) -> Tuple[List[Patient], List[Patient]]:

    if not planned_patients:
        return [], []

    operating_rooms = Settings.workstations_config[specialty]

    patients_sorted = sorted(planned_patients, key=lambda p: p.id)

    model = pyo.ConcreteModel()

    model.I = pyo.Set(initialize=range(len(patients_sorted)))
    model.T = pyo.Set(
        initialize=range(
            week_start_day,
            week_start_day + Settings.week_length_days
        )
    )
    model.K = pyo.Set(
        initialize=range(1, operating_rooms + 1)
    )

    model.rot = pyo.Param(
        model.I,
        initialize={
            i: patients_sorted[i].rot
            for i in model.I
        }
    )

    model.id_p = pyo.Param(
        model.I,
        initialize={
            i: patients_sorted[i].id
            for i in model.I
        }
    )

    model.x = pyo.Var(
        model.I,
        model.T,
        model.K,
        domain=pyo.Binary
    )

    model.overtime = pyo.Var(
        model.T,
        model.K,
        domain=pyo.NonNegativeReals
    )

    def patient_once(model, i):
        return sum(
            model.x[i, t, k]
            for t in model.T
            for k in model.K
        ) <= 1

    model.patient_once = pyo.Constraint(
        model.I,
        rule=patient_once
    )

    def capacity_rule(model, t, k):
        return (
            sum(
                model.rot[i] * model.x[i, t, k]
                for i in model.I
            )
            <=
            Settings.daily_operation_limit
            + model.overtime[t, k]
        )

    model.capacity = pyo.Constraint(
        model.T,
        model.K,
        rule=capacity_rule
    )

    def overtime_pool_rule(model):
        return (
            sum(
                model.overtime[t, k]
                for t in model.T
                for k in model.K
            )
            <=
            Settings.weekly_extra_time_pool
        )

    model.overtime_pool = pyo.Constraint(
        rule=overtime_pool_rule
    )



    model.obj = pyo.Objective(
        expr=sum(
            (1000 - t) * model.x[i, t, k]
            for i in model.I
            for t in model.T
            for k in model.K
        ),
        sense=pyo.maximize
    )

    # Settings.solver.options['mipgap'] = 0.01
    Settings.solver.options['timelimit'] = 300
    Settings.solver.solve(
        model,
        tee=Settings.solver_tee
    )

    scheduled = []
    overflow = []

    scheduled_ids = set()

    for i in model.I:
        assigned = False

        for t in model.T:
            for k in model.K:

                if pyo.value(model.x[i, t, k]) > 0.5:

                    p = copy.deepcopy(patients_sorted[i])

                    p.opDay = t
                    p.workstation = k

                    scheduled.append(p)

                    scheduled_ids.add(p.id)

                    assigned = True
                    break

            if assigned:
                break

    for p in patients_sorted:

        if p.id not in scheduled_ids:

            overflow.append(copy.deepcopy(p))

    scheduled.sort(
        key=lambda p: (
            p.opDay,
            p.workstation,
            p.id
        )
    )

    return scheduled, overflow






def optimize_daily_batch_rot_both(patients: List[Patient], specialty: str) -> Dict[str, object]:
    """Run the combined EOT planning and ROT execution workflow."""
    patient_list = sorted(patients, key=lambda patient: patient.day)
    patient_by_id = {patient.id: patient for patient in patient_list}

    day_for_week = Settings.week_length_days
    day_start = Settings.start_week_scheduling * day_for_week
    current_day = day_start

    weekly_patients = [patient for patient in patient_list if patient.day < current_day]

    result: Dict[str, object] = {
        specialty: {
            "plan_eot": [],
            "realized_rot": [],
            "overflow": [],
            "extra_time_left": [],
            "realtime_stats": [],
            "weekly_summary": [],
        }
    }

    while patient_list:
        week_start = current_day
        print(f"Scheduling for {specialty}, week starting day {week_start}")

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
                    patient
                    for patient in patient_list
                    if current_day - day_for_week <= patient.day < current_day and patient not in weekly_patients
                ]
            )
            continue

        planned = plan_week_eot(weekly_patients, specialty, current_day)
        result[specialty]["plan_eot"].extend(copy.deepcopy(planned))

        executed, overflow, extra_left, week_stats = execute_rot_schedule(
            planned,
            specialty,
            current_day,
            Settings.weekly_extra_time_pool,
        )

        result[specialty]["realized_rot"].extend(executed)
        result[specialty]["overflow"].append(overflow)
        result[specialty]["extra_time_left"].append(extra_left)
        result[specialty]["realtime_stats"].append(week_stats)

        weekly_ids = {patient.id for patient in weekly_patients}
        planned_ids = {patient.id for patient in planned}
        executed_ids = {patient.id for patient in executed}
        overflow_ids = {patient.id for patient in overflow}

        not_planned_ids = weekly_ids - planned_ids
        carryover_ids = (planned_ids - executed_ids) | overflow_ids | not_planned_ids
        carryover_count = len(carryover_ids)

        weekly_patients = [
            patient_by_id[pid]
            for pid in carryover_ids
            if pid in patient_by_id
        ]
        weekly_patients.sort(key=lambda patient: patient.day)

        current_day += day_for_week
        existing_ids = {patient.id for patient in weekly_patients}
        new_arrivals = [
            patient
            for patient in patient_list
            if current_day - day_for_week <= patient.day < current_day and patient.id not in existing_ids
        ]
        weekly_patients.extend(new_arrivals)

        summary = {
            "specialty": specialty,
            "start_day": week_start,
            "weekly_in": len(weekly_ids),
            "planned": len(planned_ids),
            "executed": len(executed_ids),
            "overflow": len(overflow_ids),
            "not_planned": len(not_planned_ids),
            "carryover_next": carryover_count,
            "new_arrivals": len(new_arrivals),
            "next_week_in": len(weekly_patients),
        }

        result[specialty]["weekly_summary"].append(summary)

        print(
            f"[WEEK SUMMARY] {specialty} | start_day={week_start} | "
            f"weekly_in={summary['weekly_in']} | planned={summary['planned']} | executed={summary['executed']} | "
            f"overflow={summary['overflow']} | not_planned={summary['not_planned']} | "
            f"carryover_next={summary['carryover_next']} | new_arrivals={summary['new_arrivals']} | "
            f"next_week_in={summary['next_week_in']}"
        )

        if current_day >= day_start + Settings.weeks_to_fill * day_for_week:
            print(
                f"Reached the maximum scheduling period for {specialty}. "
                f"Stopping further scheduling."
            )
            break

    return result


#endregion
