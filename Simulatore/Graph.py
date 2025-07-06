
# import matplotlib.pyplot as plt
import plotly.graph_objects as go
import json
import random

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass import Week, Operations

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

def MakeGraph(data : Operations ):
    for op in data:
        PrintDailyGraph(data[op], op)
   
if __name__ == "__main__":
    file_path = "weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    ops = Operations.from_dict(data)
    MakeGraph(ops)