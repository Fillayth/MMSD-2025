import csv
import json
import sys
import os
import random
from typing import List 

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))
from CommonClass.Patient import Patient
from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Week import Week
from settings import Settings
from Simulatore.Optimizer import group_weekly_with_mtb_logic_optimized, optimize_daily_batch as opt_daily

# Reads the CSV file and organizes patient data by operation type
def read_and_split_by_operation_with_metadata(csv_file) -> PatientListForSpecialties:
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        content = f.readlines()[2:]  # Skip the first two header lines
        reader = csv.reader(content)
        lines = list(reader)

    spc = PatientListForSpecialties()

    for row in lines:
        patient_id, sp_type, eot, day, mtb = row
        #qui ci vorrebbe un throw ex se sp_type non è corretto 
        spc[sp_type].append(Patient(
            id=int(patient_id),
            eot=float(eot),
            day=int(day),
            mtb=int(mtb)
            ))
    return spc

def group_daily_with_mtb_logic(ops_dict: PatientListForSpecialties) ->List[Week]:
    day_for_week = Settings.week_length_days #valore statico, lo uso per impostare le settimane 
    #non è il contatore del giorno perchè si scatta di settimana in settimana ma lo uso come indicatore per valutare le urgenze  
    today_number = lambda wN: day_for_week * wN #weekNum      
    # le settimane da definire
    weeks: PatientListForSpecialties = PatientListForSpecialties()
    # la settimana corrente 
    for op_type, patients in ops_dict.items():
        remaining = patients.copy()
        week = Week(0, op_type)
        weeks[op_type] = []
        workStation = 0
        while remaining:
            #ordino i pazienti in base all'urgenza 
            ordered = sorted(remaining, key= lambda x: x.day + x.mtb - today_number(week.weekNum), reverse=False ) 
            # serve far emergere i patient con eot piu alti nella cerchia dei piu urgenti per ottimizzare gli spazi 
            firstSet = [p for p in ordered if p.day + p.mtb <= today_number(week.weekNum + 2)] #today_number + ho impostato due settimane come cerchia
            secondSet = [p for p in ordered if p.day + p.mtb > today_number(week.weekNum + 2)] #prendo il resto 
            ordered = sorted(firstSet, key= lambda x: x.eot, reverse=True) + secondSet
            # ciclo i pazienti rimasti fino a riempire la settimana in coso 
            
            for p in ordered:
                # la funzione restituisce true se il paziente è stato inserito 
                p.workstation = workStation
                if week.insertPatient(p):
                    #rimuovo i pazieniti dalla lista provvisoria 
                    remaining.remove(p)
                elif workStation < Settings.workstations_config[op_type]:
                    workStation =+ 1
                    p.workstation = workStation
                    week.insertPatient(p)
                else:
                    break
            ## se il ciclo finisce e i pazienti sono ancora presenti vuol dire che la settimana si è riempita
            ## e ne serve una nuova 
            if len(remaining) > 0 :
                weeks[op_type].append(week)
                weekNum = week.weekNum+1
                workStation = 0
                week = Week(weekNum, op_type)
                #today_number += 5
        #alla fine del cilo sui pazienti totali, inserisco anche l'ultima settimana nella lista
        weeks[op_type].append(week)

    return weeks

def group_daily_with_mtb_logic_optimized(
        ops_dict: List[Patient],
        week_length_days=Settings.week_length_days, 
        ) -> PatientListForSpecialties :
    
    result = PatientListForSpecialties()
    for op_type, patients in ops_dict.items():
        remaining = patients.copy()
        current_week = Week(0, op_type)
        result[op_type] = []

        while remaining:
            current_week_start = current_week.weekNum * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            # Only consider patients that have arrived
            available_patients = [p for p in remaining if p.day <= current_week_start]

            # Skip week if no patients available yet
            if not available_patients:
                result[op_type].append(current_week)
                numWeek = current_week.weekNum + 1
                current_week = Week(numWeek, op_type) 
                continue

            # Split into overdue now, overdue next, normal
            overdue_now = [p for p in available_patients if current_week_end - p.day >= p.mtb]
            overdue_next = [p for p in available_patients if next_week_end - p.day >= p.mtb and p not in overdue_now]
            normal = [p for p in available_patients if p not in overdue_now and p not in overdue_next]

            ordered_patients = overdue_now + overdue_next + normal

            # Optimize assignment
            batch = opt_daily(ordered_patients, current_week)

            if batch:
                current_week = batch[-1]
            
            for week in batch[:-1]:
                result[op_type].append(week)


            # Remove assigned patients from remaining
            assigned_ids = {p.id for week in batch for p in week.patients()}
            remaining = [p for p in remaining if p.id not in assigned_ids]
            print(f"Remaining count: {len(remaining)}")
            print(f"Assigned this round: {len(assigned_ids)}")
            print(f"Current week: {current_week.weekNum}")
            print(f"Batch size: {len(batch)}")


    
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
    schedule = PatientListForSpecialties()
    spc = read_and_split_by_operation_with_metadata("lista_attesa_simulata.csv")
    # si prendono in considerazione tutti gli utenti per una data Operazione
    for spcName in schedule:
        schedule[spcName] = group_daily_with_mtb_logic(spc[spcName])

    # Call the optimized scheduling function
    schedule = group_weekly_with_mtb_logic_optimized(
        spc,
        weekly_limit=Settings.weekly_operation_limit,
        week_length_days=5,
        workstations_per_type=Settings.workstations_config,
        seed=2915453889
    )


    export_json_schedule(schedule.to_dict(), os.getcwd())





