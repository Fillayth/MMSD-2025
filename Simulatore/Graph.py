
# import matplotlib.pyplot as plt
import plotly.graph_objects as go
import json
import random
from typing import List 

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 

from CommonClass import Patient, Week


def Fill_Operation(list: List):
    weeks =[]
    for w in list:
        patients = [Patient(**patient) for patient in w["patients"]]
        weeks.append(Week(week=w["week"], patients=patients))
    return weeks

def PrintGraph(operation : list, title : str):
    fig = go.Figure()
    color_map = {p.id: f"hsl({random.randint(0, 360)}, 70%, 50%)" for w in operation for p in w.patients}
    for w in operation:
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

if __name__ == "__main__":
    file_path = "weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)

    Ope = Fill_Operation(data["Operazione A"])
    PrintGraph(Ope, "Operazione A")
    Ope = Fill_Operation(data["Operazione B"])
    PrintGraph(Ope,"Operazione B")    
    Ope = Fill_Operation(data["Operazione C"])
    PrintGraph(Ope, "Operazione C")
