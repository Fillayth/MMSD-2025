# import matplotlib.pyplot as plt
import plotly.graph_objects as go
import json
import random

import sys
import os

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass.CommonClass import Week, PatientListForSpecialties

def BoxPlotUnusedTime(weeks: list, title: str):
    data = []
    for w in weeks:
        # Calcola il tempo inutilizzato per ogni giorno della settimana
        unused_times = [
            day._minute_of_the_day_ - day.getTime()
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


def PrintDailyGraph(operation : list[Week], title : str): 
    # estraggo i dati di una operazione dal formato json 
    weeks = operation
    # inizializzo il grafico
    fig = go.Figure()
    # imposto colori randomici per differenziare i pazienti
    color_map = {p.id: f"hsl({random.randint(0, 360)}, 70%, 50%)" for week in weeks for day in week.dailySchedule for p in day.patients}
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

def MakeGraph(data : PatientListForSpecialties ):
    for op in data:
        PrintDailyGraph(data[op], op)
        # Rimuovo l'ultima settimana per il box plot perchè l'ultima settimana non è completa
        weeks_without_last = data[op][:-1] if len(data[op]) > 1 else data[op]
        BoxPlotUnusedTime(weeks_without_last, f"Tempo inutilizzato per {op}")

if __name__ == "__main__":
    file_path = "weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    ops = PatientListForSpecialties.from_dict(data)
    MakeGraph(ops)