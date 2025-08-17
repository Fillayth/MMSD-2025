import csv
import json

from typing import List 

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass.CommonClass import Patient, Week, PatientListForSpecialties

def read_and_split_by_operation_with_metadata(csv_file):
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        content = f.readlines()[2:] 
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

def group_daily_with_mtb_logic(ops_dict) ->List[Week]:
    day_for_week = 5 #valore statico, lo uso per impostare le settimane 
    weekNum = 0     #contatore della settimana in corso     
    #non è il contatore del giorno perchè si scatta di settimana in settimana ma lo uso come indicatore per valutare le urgenze  
    today_number = lambda wN: day_for_week * wN #weekNum      
    # le settimane da definire
    weeks: List[Week] = []
    # la settimana corrente 
    week = Week(weekNum)
    patients = ops_dict.copy()
    while patients:
        #ordino i pazienti in base all'urgenza 
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

def export_json_schedule(data, filepath, filename="weekly_schedule.json") -> str:
    if not os.path.exists(filepath):
        os.makedirs(filepath)
    file = os.path.join(filepath, filename)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {file}")
    return file

if __name__ == "__main__":
    schedule = PatientListForSpecialties()
    ops = read_and_split_by_operation_with_metadata("lista_attesa_simulata.csv")
    # si prendono in considerazione tutti gli utenti per una data Operazione
    for opName in schedule:
        schedule[opName] = group_daily_with_mtb_logic(ops[opName])

    #ck = len(ops["Operazione A"]) ==sum(len(b.patients) for a in schedule["Operazione A"] for b in a.dailySchedule)
    # dataForJson = {
    #     key: [w.to_dict() for w in weeks] for key, weeks in schedule.items()
    # }
    # export_json_schedule(dataForJson)
    export_json_schedule(schedule.to_dict(), os.getcwd())
    #export_json_schedule(schedule.to_dict())


