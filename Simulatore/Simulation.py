import csv
import json

from typing import List 

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass import Patient, OperationPatient, WeekSchedule, Week, DailySchedule


def read_and_split_by_operation_with_metadata(csv_file):
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        content = f.readlines()[2:] 
        reader = csv.reader(content)
        lines = list(reader)

    #data_rows = lines[2:]

    ops = {"Operazione A": [], "Operazione B": [], "Operazione C": []}

    for row in lines:
        patient_id, op_type, eot, day, mtb = row
        # patient = {
        #     "id": int(patient_id),
        #     "eot": float(eot),
        #     "day": int(day),
        #     "mtb": int(mtb)
        # }
        # ops[op_type].append(patient)
        ops[op_type].append(Patient(
            id=int(patient_id),
            eot=float(eot),
            day=int(day),
            mtb=int(mtb)
            ))
    return ops

def group_daily_with_mtb_logic(ops_dict) ->List[Week]:
    day_for_week = 5
    weekNum = 0
    today_number = lambda wN: day_for_week * wN #weekNum  
    # le settimana da definire
    weeks: List[Week] = []
    patients = ops_dict.copy()
    week = Week(weekNum)
    while patients:
        ordered = sorted(patients, key= lambda x: x.day + x.mtb - today_number(weekNum), reverse=False ) 
        # serve far emergere i patient con eot piu alti nella cerchia dei piu urgenti per ottimizzare gli spazi 
        firstSet = [p for p in ordered if p.day + p.mtb <= today_number(weekNum + 2)] #today_number + ho impostato due settimane come cerchia
        secondSet = [p for p in ordered if p.day + p.mtb > today_number(weekNum + 2)] #prendo il resto 
        ordered = sorted(firstSet, key= lambda x: x.eot, reverse=True) + secondSet
        # ciclo i pazienti rimasti fino a riempire la settimana in coso 
        for p in ordered:
            # la funzione restituisce true se il paziente è stato inserito 
            if week.insertPatient(p):
                #rimuovo i pazieniti dalla lista provvisoria 
                patients.remove(p)
        ## se il ciclo finisce e i pazienti sono ancora presenti vuol dire che la settimana si è riempita
        ## e ne serve una nuova 
        if len(patients) > 0 :
            weeks.append(week)
            weekNum +=1
            week = Week(weekNum)
            #today_number += 5
    #alla fine del cilo sui pazienti totali, inserisco anche l'ultima settimana nella lista
    weeks.append(week)

    return weeks

def group_weekly_with_mtb_logic(ops_dict, weekly_limit=2400, week_length_days=5):
    grouped_schedule = {}

    for op_type, patients in ops_dict.items():
        remaining = patients.copy()
        week_number = 0
        grouped_schedule[op_type] = []

        while remaining:
            current_week_start = week_number * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            batch = []
            total_time = 0

            overdue_now = [p for p in remaining if current_week_end - p["day"] >= p["mtb"]]
            overdue_next = [p for p in remaining if next_week_end - p["day"] >= p["mtb"]
                            and p not in overdue_now]
            normal = [p for p in remaining if p not in overdue_now and p not in overdue_next]
            ordered = overdue_now + overdue_next + normal

            i = 0
            while i < len(ordered):
                p = ordered[i]
                if total_time + p["eot"] <= weekly_limit:
                    batch.append({
                        "id": p["id"],
                        "eot": round(p["eot"], 2),
                        "day": p["day"],
                        "mtb": p["mtb"],
                        "overdue": current_week_end - p["day"] >= p["mtb"]
                    })
                    total_time += p["eot"]
                    remaining.remove(p)
                    ordered.pop(i)
                else:
                    i += 1

            # Sort
            batch.sort(key=lambda x: x["eot"], reverse=True)

            grouped_schedule[op_type].append({
                "week": week_number + 1,
                "patients": batch
            })

            week_number += 1

    return grouped_schedule

def export_json_schedule(data, filename="weekly_schedule.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {filename}")

if __name__ == "__main__":
    # ops = read_and_split_by_operation_with_metadata("lista_attesa_simulata.csv")
    # schedule = group_weekly_with_mtb_logic(ops)
    # export_json_schedule(schedule)
    schedule = {
        "Operazione A":[],
        "Operazione B":[],
        "Operazione C":[],
    }
    ops = read_and_split_by_operation_with_metadata("lista_attesa_simulata.csv")
    # si prendono in considerazione tutti gli utenti per una data Operazione
    schedule["Operazione A"] = group_daily_with_mtb_logic(ops["Operazione A"])
    schedule["Operazione B"] = group_daily_with_mtb_logic(ops["Operazione B"])
    schedule["Operazione C"] = group_daily_with_mtb_logic(ops["Operazione C"])
    #ck = len(ops["Operazione A"]) ==sum(len(b.patients) for a in schedule["Operazione A"] for b in a.dailySchedule)
    dataForJson = {
        key: [w.to_dict() for w in weeks] for key, weeks in schedule.items()
    }
    export_json_schedule(dataForJson)
