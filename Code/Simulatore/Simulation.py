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
from Simulatore.Optimizer import group_weekly_with_mtb_logic_optimized, optimize_daily_batch_cplex
from Simulatore.Optimizer import execute_week_with_rot, optimize_daily_batch_rot

# Reads the CSV file and organizes patient data by operation type
def read_and_split_by_operation_with_metadata(csv_file) :
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        result = {}
        for row in reader:
            specialty = row["Specialty"]
            if specialty not in result:
                result[specialty] = []
                #continue
            result[specialty].append(Patient(
                id=int(row["Patient ID"]),
                eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                day=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"]),
                rot=float(row["ROT (Real Operation Time in minutes)"])
            ))

    return result

def group_daily_with_mtb_logic(ops_dict: PatientListForSpecialties) ->PatientListForSpecialties:
    day_for_week = Settings.week_length_days #valore statico, lo uso per impostare le settimane 
    #non è il contatore del giorno perchè si scatta di settimana in settimana ma lo uso come indicatore per valutare le urgenze  
    today_number = lambda wN: day_for_week * wN #weekNum      
    # le settimane da definire
    weeks: PatientListForSpecialties = PatientListForSpecialties()
    # la settimana corrente 
    for op_type, patients in ops_dict.items():
        remaining = patients.copy()
        # remaining = patients.sort(key=lambda p: p.day).copy()
        week = Week(Settings.start_week_scheduling, op_type)
        weeks[op_type] = []
        workStation = 0
        while remaining:
            for_this_week = [p for p in remaining if p.day < today_number(week.weekNum)]
            #ordino i pazienti in base all'urgenza 
            ordered = sorted(for_this_week, key= lambda x: x.day + x.mtb - today_number(week.weekNum), reverse=False ) 
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
                # weeks[op_type].append(week)
                weeks[op_type].extend(week.patients())
                weekNum = week.weekNum+1
                workStation = 0
                week = Week(weekNum, op_type)
        #alla fine del cilo sui pazienti totali, inserisco anche l'ultima settimana nella lista
        weeks[op_type].extend(week.patients())
    return weeks

def group_daily_with_mtb_logic_optimized(
        ops_dict: PatientListForSpecialties,
        ) -> PatientListForSpecialties:
    
    result = PatientListForSpecialties()
    for op_type, patients in ops_dict.items():
        result[op_type] = optimize_daily_batch_cplex(patients, op_type)
        # print(f"Completed scheduling for specialty: {op_type}")
    return result

#region Organizzazione giornaliera con ROT

def group_daily_with_mtb_logic_rot(
    ops_dict: PatientListForSpecialties,
) -> PatientListForSpecialties:


    result = PatientListForSpecialties()
    day_for_week = Settings.week_length_days
    start_week = Settings.start_week_scheduling

    for op_type, patients in ops_dict.items():
        # sort patients by arrival day
        patient_list = sorted(patients, key=lambda p: p.day)
        remaining = patient_list.copy()

        scheduled: List[Patient] = []
        week_num = start_week

        # safeguard
        max_weeks = len(patients) * 2

        while remaining and week_num < max_weeks:
            week_start_day = week_num * day_for_week
            week_end_day = week_start_day + day_for_week - 1

            # === SAME weekly availability rule as before ===
            weekly_candidates = [p for p in remaining if p.day < week_start_day]

            if not weekly_candidates:
                week_num += 1
                continue

            # === SAME urgency logic ===
            ordered = sorted(
                weekly_candidates,
                key=lambda p: (
                    -(week_end_day - p.day >= p.mtb),  # overdue first
                    p.day + p.mtb
                )
            )

            # === SAME weekly capacity rule (EOT-based) ===
            weekly_selected = []
            weekly_time = 0

            for p in ordered:
                if weekly_time + p.eot <= Settings.weekly_operation_limit:
                    weekly_selected.append(p)
                    weekly_time += p.eot

            if not weekly_selected:
                week_num += 1
                continue

            # === ROT-BASED DAILY EXECUTION ===
            executed, overflow, _ = execute_week_with_rot(
                weekly_patients=weekly_selected,
                specialty=op_type,
                week_start_day=week_start_day,
                extra_time_pool=Settings.weekly_extra_time_pool,
            )

            # record results
            scheduled.extend(executed)

            executed_ids = {p.id for p in executed}
            remaining = [p for p in remaining if p.id not in executed_ids]

            # overflow patients stay in remaining automatically
            week_num += 1

        result[op_type] = scheduled

    return result

def group_daily_with_mtb_logic_optimized_rot(
    ops_dict: PatientListForSpecialties,
) -> PatientListForSpecialties:
    
    result = PatientListForSpecialties()
    overflows = PatientListForSpecialties()
    #overflows = {}
    extra_times = {}
    for op_type, patients in ops_dict.items():
        data = optimize_daily_batch_rot(patients, op_type)
        result[op_type] = data[op_type]["patients"]
        # overflows[op_type] = data[op_type]["overflow"]
        for w in data[op_type]["overflow"]:
            overflows[op_type].extend(w)
            overflows[op_type].append(Patient(
                id=-1,
                eot=0,
                day=0,
                mtb=0,
                rot=0
            ))
            # for p in w:
            #     overflows[op_type].append(p)
        extra_times[op_type] = data[op_type]["extra_time_left"]
    # salvo i dati di overflow e extra time in due file json separati
    # verifico che la cartella esista
    if not os.path.exists(f"./Data/Rot/"):
        os.makedirs(f"./Data/Rot/")
    # salvo l'extratime
    with open(f"./Data/Rot/{op_type}_extra_time.json", "w", encoding="utf-8") as f:
        json.dump(extra_times, f, indent=4)
    # salvo l'overflow
    with open(f"./Data/Rot/{op_type}_overflow.json", "w", encoding="utf-8") as f:
        json.dump(overflows.to_json(), f, indent=4)

    # print(f"Completed scheduling for specialty: {op_type}")
    return result

#endregion
   
def export_json_schedule(data, filepath, filename="weekly_schedule.json") -> str:
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    file = os.path.join(filepath, filename)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {file}")
    return file

def ExportCSVResults(data: PatientListForSpecialties):
    for op, values in data.items():
        if not os.path.exists(Settings.resultsData_folder):
            os.makedirs(Settings.resultsData_folder)
        filename = Settings.resultsData_folder + Settings.results_filename
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Seed","Patient ID", "EOT", "Day", "MTB", "Workstation", "Overdue", "Scheduled Day"])
            for p in values:
                writer.writerow([Settings.seed ,p.id, p.eot, p.day, p.mtb, p.workstation, p.overdue, p.opDay]) 
                    #uso Settings.seed perchè so che nel main è stato usato, altimenti sarebbe più sicuro usare GetSeed
        print(f"CSV results exported to {filename}")

def ExportCSVAnalysisResults(schedule: PatientListForSpecialties, dirPath: str):
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)
    output_path = os.path.join(dirPath, "schedule_analysis.csv")
    with open(output_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Specialty", "Week", "Schedueld Patients / Current Patients", "Average Waiting Time (days)", "Average Priority"])
        
        #inizio della settimana di partenza
        start_week = Settings.start_week_scheduling
        #lunghezza della settimana
        week_length = Settings.week_length_days
        for specialty, all_patients in schedule.items():
            #calcolo l'ultimo giorno dell'ultima settimana in base all'ultimo giorno di operazione dei pazienti
            end_weeks = max((p.day for p in all_patients), default=0) // week_length + 1
            # ciclo per ogni settimana
            for week_num in range(start_week, end_weeks + 1):
                # seleziono i pazienti che sono arrivati entro la fine della settimana corrente
                weekly_patients = [p for p in all_patients if p.day <= (week_num * week_length) and (p.day > ((week_num - 1) * week_length))]
                # seleziono i pazienti schedulati per la settimana corrente
                scheduled_patients = [p for p in weekly_patients if (p.opDay <= (week_num * week_length)) and (p.opDay >= ((week_num - 1) * week_length + 1))]
                # salto le settimane senza pazienti operati
                if not scheduled_patients:
                    continue
                #ciclo per i pazienti della settimana corrente
                avg_waiting_time = 0
                for p in scheduled_patients:
                    waiting_time_days = p.opDay - p.day
                    if waiting_time_days < 0:
                        raise ValueError(f"Calculated negative waiting time for patient ID {p.id}. Check scheduling logic.")
                    avg_waiting_time += waiting_time_days
                total_patients = len(weekly_patients)
                avg_waiting_time = avg_waiting_time / len(scheduled_patients)
                avg_priority = sum(p.mtb for p in scheduled_patients) / len(scheduled_patients)
                writer.writerow([specialty, week_num, f"{len(scheduled_patients)}/{total_patients}", f"{avg_waiting_time:.2f}", f"{avg_priority:.2f}"])
                
    print(f"Schedule results exported to {output_path}")

# Main program execution
if __name__ == "__main__":


    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\..\\Data", "Records", "seed-1"))
    csv_path = os.path.join(base_dir, "Patient_Record.csv")

    spc = read_and_split_by_operation_with_metadata(csv_path)
    # schedule = PatientListForSpecialties()
    # schedule = group_daily_with_mtb_logic_optimized(spc)
    schedule = group_daily_with_mtb_logic(spc)
    # normalizzo il risultato di group_daily_with_mtb_logic per allinearlo a quello di group_daily_with_mtb_logic_optimized verificando che non ci siano doppioni
    data = {key: [p.to_dict() for p in values] for key, values in schedule.items()}
    # rimuovo i doppioni
    for key in data:
        unique_patients = {}
        for patient in data[key]:
            if patient['id'] not in unique_patients:
                unique_patients[patient['id']] = patient
        data[key] = list(unique_patients.values())
    # se il data proviene da group_daily_with_mtb_logic_optimized si usera data.to_dict()
    # export_json_schedule(schedule.to_dict(), base_dir)
    export_json_schedule(data, base_dir)
    ExportCSVResults(schedule)
    #ExportCSVAnalysisResults(data, base_dir)




