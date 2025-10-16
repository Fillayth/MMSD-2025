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
def read_and_split_by_operation_with_metadata(csv_file) :
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        result = {}
        # for row in reader:
        #     result.append({
        #         "Specialty": row["Specialty"],
        #         "id": int(row["Patient ID"]),
        #         "eot": float(row["EOT (Estimated Operation Time in minutes)"]),
        #         "day": int(row["Day (Day Added to Waiting List)"]),
        #         "mtb": int(row["MTB (Priority, max waiting days)"])
        #     })
        for row in reader:
            specialty = row["Specialty"]
            if specialty not in result:
                result[specialty] = []
            result[specialty].append(Patient(
                id=int(row["Patient ID"]),
                eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                day=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"])
            ))
        # spc = []

        # for row in reader:
        #     sp_type = row["Specialty"].strip()
        #     spc[sp_type].append(Patient(
        #         id=int(row["Patient ID"]),
        #         eot=float(row["EOT (Estimated Operation Time in minutes)"]),
        #         day=int(row["Day (Day Added to Waiting List)"]),
        #         mtb=int(row["MTB (Priority, max waiting days)"])
        #     ))
    return result

def group_daily_with_mtb_logic(ops_dict: PatientListForSpecialties) ->List[Week]:
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
                weeks[op_type].append(week)
                weekNum = week.weekNum+1
                workStation = 0
                week = Week(weekNum, op_type)
                #today_number += 5
        #alla fine del cilo sui pazienti totali, inserisco anche l'ultima settimana nella lista
        weeks[op_type].append(week)
    return weeks

def group_daily_with_mtb_logic_optimized(
        ops_dict: PatientListForSpecialties,
        ) -> PatientListForSpecialties:
    
    result = PatientListForSpecialties()
    for op_type, patients in ops_dict.items():
        result[op_type] = opt_daily(patients, op_type)
        # print(f"Completed scheduling for specialty: {op_type}")
    return result
   
def export_json_schedule(data, filepath, filename="weekly_schedule.json") -> str:
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    file = os.path.join(filepath, filename)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {file}")
    return file

def ExportCSVResults(data: PatientListForSpecialties):
    for op, weeks in data.items():
        
        filename = Settings.results_filepath + Settings.results_filename
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Seed","Patient ID", "EOT", "Day", "MTB", "Workstation", "Overdue", "Scheduled Day"])
            for week in weeks:
                for p in week.patients():
                    scheduled_day = week.getNumberOpDayByPatientID(p.id)
                    writer.writerow([Settings.seed ,p.id, p.eot, p.day, p.mtb, p.workstation, p.overdue, scheduled_day]) 
                        #uso Settings.seed perchè so che nel main è stato usato, altimenti sarebbe più sicuro usare GetSeed
        print(f"CSV results exported to {filename}")

# Function to export in CVS format the analysis on the schedule results
def ExportCSVAnalysisResults(schedule: PatientListForSpecialties, dirPath: str):
    """
    Export the schedule results to a CSV file.

    Args:
        schedule (PatientListForSpecialties): The schedule data to export.
    """
    
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)
    output_path = os.path.join(dirPath, "schedule_analysis.csv")
    with open(output_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Specialty", "Week", "Schedueld Patients / Current Patients", "Average Waiting Time (days)", "Average Priority"])
        
        for specialty, weeks in schedule.items():
            if weeks is None or not (isinstance(weeks, list) and all(isinstance(w, Week)for w in weeks)) or len(weeks) == 0:
                continue
            all_patients = [p for week in weeks for p in week.patients()]
            if not all_patients:
                continue
            for week in weeks:
                if len(week.patients()) <= 0:
                    continue
                avg_waiting_time = 0
                weekly_patients = [p for p in all_patients if p.day <= (week.weekNum * Settings.week_length_days) and week.getNumberOpDayByPatientID(p.id) >= ((week.weekNum - 1) * Settings.week_length_days)]
                for p in week.patients():
                    waiting_time_days = week.getNumberOpDayByPatientID(p.id) - p.day
                    # waiting time calcolato come differenza tra il giorno in cui è stato operato e il giorno in cui è arrivato 
                    if waiting_time_days < 0:
                        raise ValueError(f"Calculated negative waiting time for patient ID {p.id}. Check scheduling logic.")
                    avg_waiting_time += waiting_time_days
                    # Debugging output
                    # print(f"Patient ID: {p.id}, Waiting Time: {p.waiting_time_days} days")
                    # print(f"Patient ID: {p.id}, Scheduled Day: {week.getNumberOpDayByPatientID(p.id)}, Arrival Day: {p.day}, Waiting Time: {p.waiting_time_days} days")
                # total patients forse e' da correggere calcolando i pazienti presenti nella lista alla fine della settimana
                total_patients = len(weekly_patients)
                #total_patients = len(week.patients())
                avg_waiting_time = avg_waiting_time / total_patients
                avg_priority = sum(p.mtb for p in week.patients()) / total_patients
                writer.writerow([specialty, week.weekNum, f"{len(week.patients())}/{total_patients}", f"{avg_waiting_time:.2f}", f"{avg_priority:.2f}"])
                        
    print(f"Schedule results exported to {output_path}")


# Main program execution
if __name__ == "__main__":


    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\..\\Data", "Records", "seed-1"))
    csv_path = os.path.join(base_dir, "Patient_Record.csv")

    spc = read_and_split_by_operation_with_metadata(csv_path)



    # daily grouping (still uses Patient objects)
    schedule = PatientListForSpecialties()

    # for op_type, patients in spc.items():
    #     spc_selected[op_type] = [p for p in sorted(patients, key=lambda p: p.id) if p.id <= 190]
    spc_selected = [value for id, value in enumerate(spc) if id <= 190]
    # schedule = group_daily_with_mtb_logic(spc)

    #raggruppo i valori di spc per specyalty
    patient_list = {}
    # i = 0
    for row in sorted(spc, key=lambda r: r["Specialty"]):
        specialty = row["Specialty"]
        if specialty not in patient_list:
            patient_list[specialty] = []
        patient_list[specialty].append(Patient(
            id=row["id"],
            eot=row["eot"],
            day=row["day"],
            mtb=row["mtb"]
        ))
        # i+=1
        # if i == 190:
        #     break



    schedule = group_daily_with_mtb_logic_optimized(patient_list)
    data = {key: [v.to_dict() for v in values] for key, values in schedule.items()}
    export_json_schedule(data, base_dir)
    ExportCSVAnalysisResults(data, base_dir)




