import plotly.graph_objects as go
from plotly.graph_objects import Figure
from dataclasses import dataclass

import sys
import os

if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

@dataclass
class Patient:
    def __init__(self, id: int, eot: float, day: int, mtb: int, workstation: int = -1, overdue: bool = False):
        self.id = id
        self.eot = eot
        self.day = day
        self.mtb = mtb
        self.workstation = workstation
        self.overdue = overdue

    #region: Funzioni Grafiche
    def setTrace (self, figure: Figure, color_map, text: str, mins: float) -> Figure:
        figure.add_trace(go.Bar(
            x=[text + f"|ToTMin:{mins}"],
            y=[self.eot],
            name=f"Patient {self.id}",
            hoverinfo="text",
            text=[f"Patient {self.id}: {int(self.eot)}m {int((self.eot % 1) * 60)}s"],
            marker=dict(color=color_map[self.id]),
            cliponaxis=True,
            textposition='inside'
        ))
        return figure
    #endregion
    #region: Funzioni Json
    def to_dict(self):
        return {
            "id": self.id,
            "eot": self.eot,
            "day": self.day,
            "mtb": self.mtb,
            "workstation": self.workstation,
            "overdue": self.overdue
        }
    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'], data['workstation'], data['overdue'])
    
    #endregion