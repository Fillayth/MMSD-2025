import csv
import json
import sys
import os

from typing import List 
from Code.Simulatore.Optimizer import group_weekly_with_mtb_logic_optimized


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass')))

from Code.CommonClass.CommonClass import Patient, Week, PatientListForSpecialties


# Reads the CSV file and organizes patient data by operation type
def read_and_split_by_operation_with_metadata(csv_file):
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        spc = PatientListForSpecialties()

        for row in reader:
            sp_type = row["Specialty"].strip()
            spc[sp_type].append(Patient(
                id=int(row["Patient ID"]),
                eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                day=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"])
            ))
    return spc


def group_daily_with_mtb_logic(ops_dict) -> List[Week]:
    day_for_week = 5  # static value, used for weeks
    weekNum = 0
    today_number = lambda wN: day_for_week * wN
    weeks: List[Week] = []
    week = Week(weekNum)
    patients = ops_dict.copy()

    while patients:
        ordered = sorted(patients, key=lambda x: x.day + x.mtb - today_number(weekNum), reverse=False)
        firstSet = [p for p in ordered if p.day + p.mtb <= today_number(weekNum + 2)]
        secondSet = [p for p in ordered if p.day + p.mtb > today_number(weekNum + 2)]
        ordered = sorted(firstSet, key=lambda x: x.eot, reverse=True) + secondSet

        for p in ordered:
            if week.insertPatient(p):
                patients.remove(p)

        if len(patients) > 0:
            weeks.append(week)
            weekNum += 1
            week = Week(weekNum)

    weeks.append(week)
    return weeks


def export_json_schedule(data, filepath, filename="weekly_schedule.json") -> str:
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    file = os.path.join(filepath, filename)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {file}")
    return file


# Main program execution
if __name__ == "__main__":


    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Records", "seed-3109030607"))
    csv_path = os.path.join(base_dir, "Patient_Record.csv")

    spc = read_and_split_by_operation_with_metadata(csv_path)

    # ---- convert Patient objects -> dicts for the optimizer ----
    ops_for_optimizer = {}
    for specialty, patients in spc.items():
        ops_for_optimizer[specialty] = [
            {
                "id": p.id,
                "eot": p.eot,
                "day": p.day,
                "mtb": p.mtb
            }
            for p in patients
        ]

    # daily grouping (still uses Patient objects)
    schedule = PatientListForSpecialties()
    for spcName in schedule:
        schedule[spcName] = group_daily_with_mtb_logic(spc[spcName])

    workstations_config = {
        "Specialty A": 2,
        "Specialty B": 3,
        "Specialty C": 1
    }

    # ---- pass dict version to optimizer ----
    schedule = group_weekly_with_mtb_logic_optimized(
        ops_for_optimizer,
        weekly_limit=8400,
        week_length_days=5,
        workstations_per_type=workstations_config,
        seed=3109030607
    )

    #ck = len(ops["Operazione A"]) ==sum(len(b.patients) for a in schedule["Operazione A"] for b in a.dailySchedule)
    # dataForJson = {
    #     key: [w.to_dict() for w in weeks] for key, weeks in schedule.items()
    # }
    # export_json_schedule(dataForJson)
    #export_json_schedule(schedule.to_dict(), os.getcwd())
    #export_json_schedule(schedule.to_dict())

    export_json_schedule(schedule, os.getcwd())


    


