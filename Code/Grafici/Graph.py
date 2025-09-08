# import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import random

import sys
import os

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 
if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Week import Week
from CommonClass.OperatingRoomShedule import OperatingRoomShedule
from settings import Settings


def BoxPlotUnusedTime(weeks: list, title: str):
    data = []
    for w in weeks:
        # Calcola il tempo inutilizzato per ogni giorno della settimana
        unused_times = [
            sum(opRoom._max_time_per_day_ for opRoom in day.operatingRooms) - day.getTime()
            for day in w.dailySchedule
        ]
        data.append(go.Box(
            y=unused_times,
            name=f"Sett {w.weekNum}",
            boxmean='sd',
            marker_color='indianred'
        ))
    fig = go.Figure(data)
    fig.update_layout(
        title=title,
        yaxis_title="Tempo inutilizzato (minuti)",  
        xaxis_title="Settimane"                     
    )
    fig.show()
'''
# # Esempio di calcolo delle statistiche per capire cosa rappresenta il box plot
# df = pd.DataFrame({'Tempo_inutilizzato': [day._minute_of_the_day_ - day.getTime() for week in weeks for day in week.dailySchedule]})
# q1 = df['Tempo_inutilizzato'].quantile(0.25)
# median = df['Tempo_inutilizzato'].median()
# q3 = df['Tempo_inutilizzato'].quantile(0.75)
# iqr = q3 - q1
# lower_fence = q1 - 1.5 * iqr
# upper_fence = q3 + 1.5 * iqr
# mean = df['Tempo_inutilizzato'].mean()
# std = df['Tempo_inutilizzato'].std()
# min_val = df['Tempo_inutilizzato'].min()
# max_val = df['Tempo_inutilizzato'].max()

# print("Min:", min_val)
# print("Q1:", q1)
# print("Median:", median)
# print("Mean ± σ:", mean, "±", std)
# print("Q3:", q3)
# print("Upper Fence:", upper_fence)
# print("Lower Fence:", lower_fence)
# print("Max:", max_val)

'''

def PrintDailyGraph(operation : list[Week], title : str): 
    # estraggo i dati di una operazione dal formato json 
    weeks = operation
    # inizializzo il grafico
    fig = go.Figure()
    # imposto colori randomici per differenziare i pazienti
    #color_map = {p.id: f"hsl({random.randint(0, 360)}, 70%, 50%)" for week in weeks for p in week.patients()}
    all_patients = [p for week in weeks for p in week.patients()]
    num_patients = len(all_patients)

    # Gradazione di colori distribuiti uniformemente
    color_map = {
        p.id: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)"
        for i, p in enumerate(all_patients)
    }
    # la funzione si propaghera fino ai patients a seconda della struttura che abbiamo definito per gestire i pazieni e cosi gestire le colonne del grafo
    for week in weeks:
        fig = week.setTrace(fig, color_map)
    # adatto il grafico alla nuova struttura con i dati 
    fig.update_layout(
        barmode="stack",  
        title=title,
        showlegend=False,
        yaxis_title="Minuti Totali",
        xaxis_title="Giorni"
    )
    # mostro il risultato 
    fig.show()

def PrintLineGraph(operation : list[Week], title : str): 
    # estraggo i dati di una operazione dal formato json 
    # Escludo l'ultima settimana se non è completa
    weeks = operation[:-1]
    # inizializzo il grafico
    fig = go.Figure()
    days = [f"W:{week.weekNum}|Day:{day_obj.day.name}" for week in weeks for day_obj in week.dailySchedule ]
    room_ids = range(Settings.workstations_config[weeks[0].specialty])
    room_free_time = {room_id:[] for room_id in room_ids}
    room_patient = {room_id:[] for room_id in room_ids}
    for week in weeks: 

        # Dati per ogni room

        for day_obj in week.dailySchedule:
            for room_id in room_ids:
                room = next((r for r in day_obj.operatingRooms if r.id == room_id), None)
                if room:
                    time_used = room.getTime() #sum(p.mtb for p in room.daily_schedules)
                    free_time = Settings.daily_operation_limit - time_used
                    patient_count = len(room.daily_schedules)
                else:
                    free_time = Settings.daily_operation_limit
                    patient_count = 0

                room_free_time[room_id].append(free_time)
                room_patient[room_id].append(patient_count)

        # Grafico con doppio asse Y
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Linee: tempo libero per room
        for room_id, times in room_free_time.items():
            fig.add_trace(go.Scatter(
                x=days,
                y=times,
                name=f"Room:{room_id}-Tempo libero",
                mode='lines+markers',
                hovertemplate='%{y}<extra></extra>'
            ), secondary_y=False)

        # Barre: pazienti per room
        for room_id, counts in room_patient.items():
            fig.add_trace(go.Bar(
                x=days,
                y=counts,
                name=f"Room:{room_id}-Pazienti",
                opacity=0.6,
                hovertemplate='%{y}<extra></extra>'
            ), secondary_y=True)

    fig.update_layout(
        title=title,
        xaxis_title="Giorno",
        yaxis_title="Tempo libero (minuti)",
        template="plotly_white",
        barmode='group',
        #legend=dict(x=0.01, y=0.99)
    )

    fig.update_yaxes(
        title_text="Tempo libero (minuti)",
        secondary_y=False
    )
    fig.update_yaxes(
        title_text="Numero pazienti",
        secondary_y=True
    )

    fig.show()


def MakeGraphs(data : PatientListForSpecialties ):
    for op in data:
        #Grafico giornaliero per vedere la distribuzione dei pazienti
        PrintDailyGraph(data[op], op)
        #Grafico lineare per vedere l'andamento del tempo occupato
        PrintLineGraph(data[op], f"Andamento tempo occupato per {op}")

        
        # Rimuovo l'ultima settimana per il box plot perchè l'ultima settimana non è completa
        weeks_without_last = data[op][:-1] if len(data[op]) > 1 else data[op]
        # Box plot per vedere il tempo inutilizzato
        BoxPlotUnusedTime(weeks_without_last, f"Tempo inutilizzato per {op}")


if __name__ == "__main__":
    # file_path = "weekly_schedule.json"
    file_path = "Data\Records\seed-197558074\weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    ops = PatientListForSpecialties.from_dict(data)
    MakeGraphs(ops)