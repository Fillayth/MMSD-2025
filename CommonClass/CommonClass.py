from plotly.graph_objects import Figure 
import plotly.graph_objects as go 
from dataclasses import dataclass
from typing import List 

from enum import Enum

class Day(Enum):
    Lun = 0
    Mar = 1
    Mer = 2
    Gio = 3
    Ven = 4

@dataclass
class Patient:
    def __init__(self, id: int, eot: float, day: int, mtb: int):
        self.id = id
        self.eot = eot
        self.day = day
        self.mtb = mtb
    
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

    def to_dict(self):
        return {
            "id": self.id,
            "eot": self.eot,
            "day": self.day,
            "mtb": self.mtb
        }
    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'])

@dataclass
class OperationPatient(Patient):
    overdue: int

    def to_dict(self):
        # return {
        #     "id": self.id,
        #     "eot": self.eot,
        #     "day": self.day,
        #     "mtb": self.mtb,
        #     "overdue": self.overdue
        # }        
        d = super().to_dict()
        d.update({'overdue': self.overdue})
        return d
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['id'], data['eot'], data['day'], data['mtb'], data['overdue'])

@dataclass
class DailySchedule:
    day: Day
    patients: List[OperationPatient]
    _minute_of_the_day_: int = 480
    
    def getTime(self) -> int: 
        return sum(p.eot for p in self.patients)

    def insertPatient(self, patient: OperationPatient) -> bool:
        if patient.eot + sum(p.eot for p in self.patients) > self._minute_of_the_day_:
            return False
        else:
            self.patients.append(patient)
            return True

    def setTrace (self, figure: Figure, color_map, text: str) -> Figure:
        mins = sum(p.eot for p in self.patients)
        for p in self.patients:
            figure = p.setTrace(figure, color_map, text + f"|Day:{self.day.name}", mins)
        return figure

    def to_dict(self):
        return {
            "day":self.day.name,
            "patients":[p.to_dict() for p in self.patients]
        }
    
    @classmethod
    def from_dict(cls, data):
        patients = [Patient.from_dict(p) for p in data['patients']]
        return cls(Day[data['day']], patients)
    
    # def Fill_Operation(weeks: List[WeekSchedule]):
    #     week = []
    #     for w in weeks:
    #         week.append(DailySchedule.group_daily(w.patients))
    #     return week
    def group_daily(patientsList: list[OperationPatient]):
        daily_minute = 8*60
        days_for_week = 5
        remaining = sorted(patientsList, key=lambda p: p.eot)
        daily_schedules = [
            DailySchedule(day=Day.Lun, patients=[]),
            DailySchedule(day=Day.Mar, patients=[]),
            DailySchedule(day=Day.Mer, patients=[]),
            DailySchedule(day=Day.Gio, patients=[]),
            DailySchedule(day=Day.Ven, patients=[]),
            ]
        
        dayNum=0
        run = 0
        leng = len(remaining)
        while remaining and run <= leng * days_for_week:
            if remaining[0].eot + daily_schedules[dayNum].getTime() <= daily_minute :
                daily_schedules[dayNum].patients.append(remaining[0])
                remaining.remove(remaining[0])
            if dayNum < days_for_week - 1:
                dayNum += 1
            else:
                dayNum = 0
            run += 1

        return daily_schedules

    def group_daily_with_mtb_logic(patients, daily_limit=60*8, week_length_days=5):
        grouped_schedule = []

        # for op_type, patients in ops_dict.items():
        #     remaining = patients.copy()
        #     week_number = 0
        #     grouped_schedule[op_type] = []
        remaining = patients.copy()
        day_number = 0
        run = 0
        leng= len(patients)
        while remaining and run <= leng:
            run += 1
            current_day_start = day_number * week_length_days
            current_day_end = current_day_start + week_length_days - 1
            next_day_end = current_day_end + week_length_days

            batch = []
            total_time = 0

            overdue_now = [p for p in remaining if current_day_end - p["day"] >= p["mtb"]]
            overdue_next = [p for p in remaining if next_day_end - p["day"] >= p["mtb"]
                            and p not in overdue_now]
            normal = [p for p in remaining if p not in overdue_now and p not in overdue_next]
            ordered = overdue_now + overdue_next + normal

            i = 0
            while i < len(ordered):
                p = ordered[i]
                if total_time + p["eot"] <= daily_limit:
                    batch.append({
                        "id": p["id"],
                        "eot": round(p["eot"], 2),
                        "day": p["day"],
                        "mtb": p["mtb"],
                        "overdue": current_day_end - p["day"] >= p["mtb"]
                    })
                    total_time += p["eot"]
                    remaining.remove(p)
                    ordered.pop(i)
                else:
                    i += 1

            # Sort
            batch.sort(key=lambda x: x["eot"], reverse=True)

            grouped_schedule.append(WeekSchedule(week=week_number + 1, patients=batch)) #àserve impostare la divisione in giorni 

            week_number += 1

        return grouped_schedule
    
    def Fill_Operation(patients: List):
        week = []
        res = DailySchedule.group_daily_with_mtb_logic(patients=patients)
        return res
  


@dataclass
class Week:
    def __init__(self, weekNum: int):
        self.weekNum = weekNum
        self.dailySchedule = [
            DailySchedule(day=Day.Lun, patients=[]),
            DailySchedule(day=Day.Mar, patients=[]),
            DailySchedule(day=Day.Mer, patients=[]),
            DailySchedule(day=Day.Gio, patients=[]),
            DailySchedule(day=Day.Ven, patients=[]),
            ]
    def __init__(self, weekNum: int, dailySchedule: list[DailySchedule]):
        self.weekNum = weekNum
        self.dailySchedule = dailySchedule

    def getDay (self, day: Day) -> DailySchedule:
        return [d for d in self.dailySchedule if d.day == day]
    
    def getDays(self) -> List[DailySchedule]:
        return self.dailySchedule

    def insertPatient(self, patient: OperationPatient) -> bool:
        # #per mantenere il bool sull urgenza 
        # p = OperationPatient(patient)
        # p.overdue = (self.weekNum + 1) * 5 >= patient.day+patient.mtb
             
        for d in self.dailySchedule:
            if d.insertPatient(patient=patient):
                return True
        # se non ritorna true, vuoldire che nella settimana non c'è spazio
        return False

    def setTrace (self, figure: Figure, color_map) -> Figure:
        for day in self.dailySchedule:
            figure = day.setTrace(figure, color_map, f"Week:{self.weekNum}")
        return figure

    def to_dict(self):
        return {
            "week":self.weekNum,
            "days":[day.to_dict() for day in self.dailySchedule]
        }
    @classmethod
    def from_dict(cls, data):
        days = [DailySchedule.from_dict(d) for d in data ["days"]]
        return cls(data['week'], days)    

@dataclass
class WeekSchedule:
    week: int
    patients: List[OperationPatient]
    
    def Fill_Operation(list: List):
        weeks=[]
        for w in list:
            patients = [OperationPatient(**patient) for patient in w["patients"]]
            weeks.append(WeekSchedule(week=w["week"], patients=patients))
        return weeks


    