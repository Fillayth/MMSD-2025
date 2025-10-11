from collections import defaultdict
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from plotly.subplots import make_subplots

import json

import sys
import os

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CommonClass'))) ## se si crea un file comune in MMSD-2025 che poi orchestra tutte le risorse questo comando non serve 
if os.path.basename(__file__) != "main.py":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', 'Code')))

from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Week import Week
from CommonClass.Patient import Patient
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

def PrintWaitingTimeBoxPlotGraph(weeks: list, title: str):
    data = []
    #organizzo i dati per estrarre i tempi di attesa
    df = pd.DataFrame([{
        "ID": p.id, "Data inserimento": p.day, "MTB": p.mtb, "Data operazione": w.getNumberOpDayByPatientID(p.id)
        } for w in weeks for p in w.patients()])
    df['Tempo_attesa'] = df['Data operazione'] - df['Data inserimento']
    #df['Tempo_attesa'] = df['Tempo_attesa'].dt.days
    for w in weeks:
        # Calcola il tempo inutilizzato per ogni giorno della settimana
        waiting_times = df[df['Data operazione'].between((w.weekNum - 1) * Settings.week_length_days + 1, w.weekNum * Settings.week_length_days)]['Tempo_attesa']
        data.append(go.Box(
            y=waiting_times,
            name=f"Sett {w.weekNum}",
            boxmean='sd',
            marker_color='indianred'
        ))
    fig = go.Figure(data)
    fig.update_layout(
        title=title,
        yaxis_title="Tempo di attesa (giorni)",
        xaxis_title="Settimane"
    )
    fig.show()
def PrintWaitingTimeBoxPlotGraph_v2(operations: PatientListForSpecialties, basetitle: str):
    week_len = Settings.week_length_days
    for op, patients in operations.items():
        title = basetitle + op
        data = []
        #organizzo i dati per estrarre i tempi di attesa
        df = pd.DataFrame([{
            "ID": p.id, "Data inserimento": p.day, "MTB": p.mtb, "Data operazione": p.opDay
            } for p in patients])
        df['Tempo_attesa'] = df['Data operazione'] - df['Data inserimento']
        #df['Tempo_attesa'] = df['Tempo_attesa'].dt.days
        lastWeek = max(p.opDay for p in patients) % week_len + 1
        for weekNum in range(lastWeek):
            # Calcola il tempo inutilizzato per ogni giorno della settimana
            waiting_times = df[df['Data operazione'].between((weekNum - 1) * Settings.week_length_days + 1, weekNum * Settings.week_length_days)]['Tempo_attesa']
            data.append(go.Box(
                y=waiting_times,
                name=f"Sett {weekNum}",
                boxmean='sd',
                marker_color='indianred'
            ))
        fig = go.Figure(data)
        fig.update_layout(
            title=title,
            yaxis_title="Tempo di attesa (giorni)",
            xaxis_title="Settimane"
        )
        fig.show()

def PrintDailyBoxGraph(operation : list[Week], title : str): 
    # estraggo i dati di una operazione dal formato json 
    weeks = operation
    # inizializzo il grafico
    fig = go.Figure()
    buttons = []
    all_patients = [p for week in weeks for p in week.patients()]
    num_patients = len(all_patients)
    # Gradazione di colori distribuiti uniformemente
    color_map_progressive = {
        p.id: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)" #
        for i, p in enumerate(sorted(all_patients, key=lambda x: x.id))
    }
    i = 0
    for week in weeks:
        visible = [False] * sum(len(week.patients()) for week in weeks)
        text = f"W:{week.weekNum}" 
        for day in week.dailySchedule:
            for r in day.operatingRooms:
                mins = round(r.getTime(), 2)
                for p in r.daily_schedules:
                    fig.add_trace(go.Bar(
                        x=[text + f"|OR:{r.id}|D:{day.day.name}|ToTMin:{mins}"],
                        y=[p.eot],
                        name=f"Patient {p.id}",
                        hoverinfo="text",
                        text=[f"Patient {p.id}: {int(p.eot)}m {int((p.eot % 1) * 60)}s"],
                        hovertemplate=f'D:{p.day}|MTB:{p.mtb}<extra></extra>',
                        marker=dict(color=color_map_progressive[p.id]),
                        cliponaxis=True,
                        textposition='inside',
                        visible=(week.weekNum == Settings.start_week_scheduling)
                    ))
                    visible[i] = True
                    i += 1
        buttons.append(dict(
            label=f"Settimana {week.weekNum}",
            method="update",
            args=[{"visible": visible},
                  {"title": title}]
                #   {"title": f"{title} - Settimana {week.weekNum}"}]
        ))
    # Aggiungo la linea del limite massimo
    limite_massimo = Settings.daily_operation_limit
    xline = len(weeks[0].dailySchedule) * len(weeks[0].dailySchedule[0].operatingRooms)
    fig.add_shape(
        type="line",
        x0=-0.5, x1=xline - 0.5 ,  # Estendo la linea su tutto l'asse X
        y0=limite_massimo, y1=limite_massimo,
        line=dict(color="red", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=xline - 1, y=limite_massimo,
        text=f"{limite_massimo} minuti (limite giornaliero)",
        showarrow=False,
        yshift=10,
        font=dict(color="red")
    )
    # mostro il risultato 
    fig.update_layout(
        updatemenus=[dict(
            active=0,
            buttons=buttons,
            x=0.95,
            y=1.1,
            xanchor='right',
            yanchor='top'
        )],
        barmode="stack",  
        title=title,
        showlegend=False,
        yaxis_title="Minuti Totali",
        xaxis_title="Giorni",
    )
    fig.show()
def PrintDailyBoxGraph_v2(operation : PatientListForSpecialties, baseTitle : str): 
    week_len = Settings.week_length_days
    week_start = Settings.start_week_scheduling
    for op, patients in operation.items():
        workstation_len = Settings.workstations_config[op]
        title = baseTitle = op 
        fig = go.Figure()
        buttons = []
        num_patients = len(patients)
        # Gradazione di colori distribuiti uniformemente
        color_map_progressive = {
            p.id: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)" #
            for i, p in enumerate(sorted(patients, key=lambda x: x.id))
        }
        i = 0
        summ = 0
        lastWeek = max(p.opDay for p in patients) % week_len
        for weekNum in range(lastWeek):
            visible = [False] * len(patients)
            weeklyPatients = [p for p in patients if p.opDay >= week_len*weekNum and p.opDay < week_len*(weekNum + 1)]
            summ += len(weeklyPatients)
            text = f"W:{weekNum}" 
            mins = [round(sum(p.eot for p in weeklyPatients if p.workstation == workstation), 2)
                for workstation in range(workstation_len)]
            for p in weeklyPatients:
                fig.add_trace(go.Bar(
                    x=[text + f"|OR:{p.workstation}|D:{p.opDay}|ToTMin:{mins[p.workstation]}"],
                    y=[p.eot],
                    name=f"Patient {p.id}",
                    hoverinfo="text",
                    text=[f"Patient {p.id}: {int(p.eot)}m {int((p.eot % 1) * 60)}s"],
                    hovertemplate=f'D:{p.opDay}|MTB:{p.mtb}<extra></extra>',
                    marker=dict(color=color_map_progressive[p.id]),
                    cliponaxis=True,
                    textposition='inside',
                    visible=(weekNum == Settings.start_week_scheduling)
                ))
                visible[i] = True
                i += 1
            buttons.append(dict(
                label=f"Settimana {weekNum}",
                method="update",
                args=[{"visible": visible},
                    {"title": title}]
                    #   {"title": f"{title} - Settimana {week.weekNum}"}]
            ))
        # Aggiungo la linea del limite massimo
        limite_massimo = Settings.daily_operation_limit
        xline = week_len * workstation_len
        fig.add_shape(
            type="line",
            x0=-0.5, x1=xline - 0.5 ,  # Estendo la linea su tutto l'asse X
            y0=limite_massimo, y1=limite_massimo,
            line=dict(color="red", width=2, dash="dash"),
        )
        fig.add_annotation(
            x=xline - 1, y=limite_massimo,
            text=f"{limite_massimo} minuti (limite giornaliero)",
            showarrow=False,
            yshift=10,
            font=dict(color="red")
        )
        # mostro il risultato 
        fig.update_layout(
            updatemenus=[dict(
                active=0,
                buttons=buttons,
                x=0.95,
                y=1.1,
                xanchor='right',
                yanchor='top'
            )],
            barmode="stack",  
            title=title,
            showlegend=False,
            yaxis_title="Minuti Totali",
            xaxis_title="Giorni",
        )
        fig.show()

def PrintTrendLineGraph(operation : list[Week], title : str): 
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
                name=f"OR:{room_id}-Tempo libero residuo",
                mode='lines+markers',
                hovertemplate='%{y}<extra>MIN</extra>'
            ), secondary_y=False)
        # Barre: pazienti per room
        for room_id, counts in room_patient.items():
            fig.add_trace(go.Bar(
                x=days,
                y=counts,
                name=f"OR:{room_id}-Numero di Pazienti",
                opacity=0.6,
                hovertemplate='%{y}<extra>P</extra>'
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
def PrintTrendLineGraph_v2(operation : PatientListForSpecialties, baseTitle : str): 
    # estraggo i dati di una operazione dal formato json 
    # inizializzo il grafico
    for op, patients in operation.items():
        title = baseTitle = op
        fig = go.Figure()
        days_title = [f"Day:{patient.day}" for patient in patients]
        room_ids = range(Settings.workstations_config[op])
        room_free_time = {room_id:[] for room_id in room_ids}
        room_patient = {room_id:[] for room_id in room_ids}
        days = max([p.day for p in patients])
        for d in range(days):
            for room_id in room_ids:
                dailyPatients = [p for p in patients if p.workstation == room_id and p.day == d]
                time_used = sum(p.eot for p in dailyPatients )
                patient_count = len(dailyPatients)
                free_time = Settings.daily_operation_limit - time_used
                room_free_time[room_id].append(free_time)
                room_patient[room_id].append(patient_count)
            # Grafico con doppio asse Y
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            # Linee: tempo libero per room
            for room_id, times in room_free_time.items():
                fig.add_trace(go.Scatter(
                    x=days_title,
                    y=times,
                    name=f"OR:{room_id}-Tempo libero residuo",
                    mode='lines+markers',
                    hovertemplate='%{y}<extra>MIN</extra>'
                ), secondary_y=False)
            # Barre: pazienti per room
            for room_id, counts in room_patient.items():
                fig.add_trace(go.Bar(
                    x=days_title,
                    y=counts,
                    name=f"OR:{room_id}-Numero di Pazienti",
                    opacity=0.6,
                    hovertemplate='%{y}<extra>P</extra>'
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

def PrintWaitingListLineGraph(weeks : list[Week], title : str): 
    # Escludo l'ultima settimana se non è completa
    #weeks = operation[:-1]
    all_patients = [p for week in weeks for p in week.patients()]
    new_patient_list = defaultdict(list)
    resolved_list = defaultdict(list)
    for p in all_patients:
        #estraggo la lista di attesa
        new_patient_list[p.day].append(p.id)
        #estraggo la lista dei risolti dalle settimane
        for week in weeks:
            day = week.getNumberOpDayByPatientID(p.id)
            if day != -1:
                resolved_list[day].append(p.id)
                break
    # ordino le liste per giorno
    new_patient_list = dict(sorted(new_patient_list.items()))
    resolved_list = dict(sorted(resolved_list.items()))
    #eseguo i conti dei pazienti nelle liste
    new_patient_count = {day: len(ids) for day, ids in new_patient_list.items()}
    resolved_count = {day: len(ids) for day, ids in resolved_list.items()}
    # imposto la linea per la differenze tra i pazienti in attesa e quelli risolti
    waiting_count = {}
    total_waiting = 0   
    max_day = max(max(new_patient_count.keys(), default=0), max(resolved_count.keys(), default=0))
    for day in range(1, max_day + 1):
        total_waiting += new_patient_count.get(day, 0)
        total_waiting -= resolved_count.get(day, 0)
        waiting_count[day] = total_waiting
    # inizializzo il grafico
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(new_patient_count.keys()),
        y=list(new_patient_count.values()),
        mode='lines+markers',
        name='Pazienti Aggiunti',
        line=dict(color='blue'),
        hovertemplate='%{y}<extra>Pazienti Aggiunti</extra>'
    ))
    fig.add_trace(go.Scatter(
        x=list(resolved_count.keys()),
        y=list(resolved_count.values()),
        mode='lines+markers',
        name='Pazienti operati',
        line=dict(color='green'),
        hovertemplate='%{y}<extra>Pazienti operati</extra>'
    ))
    fig.add_trace(go.Scatter(
        x=list(waiting_count.keys()),
        y=list(waiting_count.values()),
        mode='lines+markers',
        name='Pazienti in attesa',
        line=dict(color='red'),
        hovertemplate='%{y}<extra>Pazienti in attesa</extra>'
    ))
    #aggiungo linea verticale per l'inizio della schedulazione
    if Settings.start_week_scheduling >= 1:
        start_day = (Settings.start_week_scheduling) * Settings.week_length_days
        fig.add_vline(
            x=start_day,
            line=dict(color="orange", width=2, dash="dash"),
            annotation_text="Inizio Schedulazione",
            annotation_position="top right",
            annotation_font_color="orange"
        )
    fig.update_layout(
        title=title,
        xaxis_title="Giorno",
        yaxis_title="Numero di Pazienti",
        template="plotly_white",
        hovermode='x unified'
    )
    fig.show()
def PrintWaitingListLineGraph_v2(operations : PatientListForSpecialties, baseTitle : str): 
    for op, patients in operations.items():
        title = baseTitle = op
        new_patient_list = defaultdict(list)
        resolved_list = defaultdict(list)
        for p in patients:
            #estraggo la lista di attesa
            new_patient_list[p.day].append(p.id)
            #estraggo la lista dei risolti dalle settimane
            if p.opDay != -1:
                resolved_list[p.opDay].append(p.id)            
        # ordino le liste per giorno
        new_patient_list = dict(sorted(new_patient_list.items()))
        resolved_list = dict(sorted(resolved_list.items()))
        #eseguo i conti dei pazienti nelle liste
        new_patient_count = {day: len(ids) for day, ids in new_patient_list.items()}
        resolved_count = {day: len(ids) for day, ids in resolved_list.items()}
        # imposto la linea per la differenze tra i pazienti in attesa e quelli risolti
        waiting_count = {}
        total_waiting = 0   
        max_day = max(max(new_patient_count.keys(), default=0), max(resolved_count.keys(), default=0))
        for day in range(1, max_day + 1):
            total_waiting += new_patient_count.get(day, 0)
            total_waiting -= resolved_count.get(day, 0)
            waiting_count[day] = total_waiting
        # inizializzo il grafico
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(new_patient_count.keys()),
            y=list(new_patient_count.values()),
            mode='lines+markers',
            name='Pazienti Aggiunti',
            line=dict(color='blue'),
            hovertemplate='%{y}<extra>Pazienti Aggiunti</extra>'
        ))
        fig.add_trace(go.Scatter(
            x=list(resolved_count.keys()),
            y=list(resolved_count.values()),
            mode='lines+markers',
            name='Pazienti operati',
            line=dict(color='green'),
            hovertemplate='%{y}<extra>Pazienti operati</extra>'
        ))
        fig.add_trace(go.Scatter(
            x=list(waiting_count.keys()),
            y=list(waiting_count.values()),
            mode='lines+markers',
            name='Pazienti in attesa',
            line=dict(color='red'),
            hovertemplate='%{y}<extra>Pazienti in attesa</extra>'
        ))
        #aggiungo linea verticale per l'inizio della schedulazione
        if Settings.start_week_scheduling >= 1:
            start_day = (Settings.start_week_scheduling) * Settings.week_length_days
            fig.add_vline(
                x=start_day,
                line=dict(color="orange", width=2, dash="dash"),
                annotation_text="Inizio Schedulazione",
                annotation_position="top right",
                annotation_font_color="orange"
            )
        fig.update_layout(
            title=title,
            xaxis_title="Giorno",
            yaxis_title="Numero di Pazienti",
            template="plotly_white",
            hovermode='x unified'
        )
        fig.show()

def MakeGraphs(data : PatientListForSpecialties ):
    PrintDailyBoxGraph_v2(data, "Distribuzione dei pazienti per " )
    PrintTrendLineGraph_v2(data, "Andamento tempo occupato per " )
    PrintWaitingListLineGraph_v2(data, "Andamento lista d'attesa per ")
    PrintWaitingTimeBoxPlotGraph_v2(data, "Tempi di attesa per ")
    # for op in data:
        
        
    #     # Rimuovo l'ultima settimana per il box plot perchè l'ultima settimana non è completa
    #     # weeks_without_last = data[op][:-1] if len(data[op]) > 1 else data[op]
    #     # # Box plot per vedere il tempo inutilizzato
    #     # BoxPlotUnusedTime(weeks_without_last, f"Tempi medi non utilizzati per {op}")
        
    #     # #Grafico lineare per vedere l'andamento del tempo occupato
    #     PrintTrendLineGraph(data[op], f"Andamento tempo occupato per {op}")
    #     #Grafico giornaliero per vedere la distribuzione dei pazienti
    #     PrintDailyBoxGraph(data[op], f"Distribuzione dei pazienti per {op}")

    #     #Grafico lineare per vedere l'andamento della lista d'attesa
    #     PrintWaitingListLineGraph(data[op], f"Andamento lista d'attesa per {op}")

    #     # Box plot per vedere il tempo di attesa
    #     PrintWaitingTimeBoxPlotGraph(data[op], f"Tempi di attesa per {op}")



if __name__ == "__main__":
    # file_path = "weekly_schedule.json"
    file_path = "Data\\Records\seed-1\weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    ops = PatientListForSpecialties.from_dict(data)
    
    MakeGraphs(ops)