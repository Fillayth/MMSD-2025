
# import matplotlib.pyplot as plt
import plotly.graph_objects as go
import json
import csv
import random

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass import Patient, OperationPatient, WeekSchedule, Day, DailySchedule, Week

def PrintDailyGraph(operations : list, title : str): #operation = List[4][5][DailySchedule]
    fig = go.Figure()
    color_map = {p["id"]: f"hsl({random.randint(0, 360)}, 70%, 50%)" for week in operations for day in week["days"] for p in day["patients"]}
    for week in operations:
        for day in week["days"]:
            mins = sum(p["eot"] for p in day["patients"])
            for p in day["patients"]:
                patient = Patient(id=p["id"], eot=p["eot"], day=p["day"], mtb=p["mtb"])
                fig.add_trace(go.Bar(
                    x=[f"ZWeek:{week["week"]}|Day:{day["day"]}|ToTMin:{mins}"], 
                    y=[patient.eot], 
                    name=f"Patient {patient.id}",  
                    hoverinfo="text",  
                    text=[f"Patient {patient.id}: {int(patient.eot)}m {int((patient.eot % 1) * 60)}s"],  
                    marker=dict(color=color_map[patient.id]),  
                    cliponaxis=True,
                    textposition='inside'
                ))

    fig.update_layout(
        barmode="stack",  
        title=title,
        showlegend=False,
        yaxis_title="Minuti Totali",
        xaxis_title="Giorni"
    )

    fig.show()

def PrintDailyGraph(operations : list[Week], title : str): 
    weeks = [Week.from_dict(w) for w in data[title]]
    fig = go.Figure()
    color_map = {p.id: f"hsl({random.randint(0, 360)}, 70%, 50%)" for week in weeks for day in week.dailySchedule for p in day.patients}
    # per ogni settimana richiamo la funzione che crea la colonna del grafico
    # la funzione si propaghera fino ai patients a seconda della struttura che abbiamo definito per gestire i pazieni
    for week in weeks:
        fig = week.setTrace(fig, color_map)
    fig.update_layout(
        barmode="stack",  
        title=title,
        showlegend=False,
        yaxis_title="Minuti Totali",
        xaxis_title="Giorni"
    )

    fig.show()

def MakeGraph(data):
    PrintDailyGraph(data,"Operazione A")
    PrintDailyGraph(data,"Operazione B")    
    PrintDailyGraph(data,"Operazione C")
    # PrintDailyGraph(data["Operazione A"],"Operazione A")
    # PrintDailyGraph(data["Operazione B"],"Operazione B")    
    # PrintDailyGraph(data["Operazione C"],"Operazione C")

if __name__ == "__main__":
    file_path = "weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    
    # WeeklyGraph(data)
    # DailyGraph(data)
    MakeGraph(data)

    # csv_file = "lista_attesa_simulata.csv"
    # with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
    #     content = f.readlines()[2:] 
    #     reader = csv.reader(content)
    #     lines = list(reader)
    # ops = {"Operazione A": [], "Operazione B": [], "Operazione C": []}

    # for row in lines:
    #     patient_id, op_type, eot, day, mtb = row
    #     patient = {
    #         "id": int(patient_id),
    #         "eot": float(eot),
    #         "day": int(day),
    #         "mtb": int(mtb)
    #     }
    #     ops[op_type].append(patient)
    
    # DailyGraph(ops)



def PrintGraph(operations : list, title : str):
    fig = go.Figure()
    color_map = {p.id: f"hsl({random.randint(0, 360)}, 70%, 50%)" for w in operations for p in w.patients}
    for w in operations:
        mins = sum(p.eot for p in w.patients)
        for p in w.patients:
            fig.add_trace(go.Bar(
                x=[f"Sett {w.week} | ToT Min {mins}"], 
                y=[p.eot], 
                name=f"Patient {p.id}",  
                hoverinfo="text",  
                text=[f"Patient {p.id}: {int(p.eot)}m {int((p.eot % 1) * 60)}s"],  
                marker=dict(color=color_map[p.id]),  
                cliponaxis=True,
                textposition='inside'
            ))

    fig.update_layout(
        barmode="stack",  
        title=title,
        showlegend=False,
        yaxis_title="Minuti Totali",
        xaxis_title="Settimane"
    )

    fig.show()

def DailyGraph(data):
    weeks = WeekSchedule.Fill_Operation(data["Operazione A"])
    Ope = DailySchedule.Fill_Operation(weeks)
    PrintDailyGraph(Ope, "Operazione A")
    weeks = WeekSchedule.Fill_Operation(data["Operazione B"])
    Ope = DailySchedule.Fill_Operation(weeks)
    PrintDailyGraph(Ope,"Operazione B")    
    weeks = WeekSchedule.Fill_Operation(data["Operazione C"])
    Ope = DailySchedule.Fill_Operation(weeks)
    PrintDailyGraph(Ope, "Operazione C")

def WeeklyGraph(data):
    Ope = WeekSchedule.Fill_Operation(data["Operazione A"])
    PrintGraph(Ope, "Operazione A")
    Ope = WeekSchedule.Fill_Operation(data["Operazione B"])
    PrintGraph(Ope,"Operazione B")    
    Ope = WeekSchedule.Fill_Operation(data["Operazione C"])
    PrintGraph(Ope, "Operazione C")