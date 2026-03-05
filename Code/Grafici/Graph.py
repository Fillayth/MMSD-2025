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

class Graphs:
    folderPath: str
    ShowFigures: bool = True
    def __init__(self, folderPath: str = os.path.dirname(os.path.abspath(__file__)) + "/Images"):
        if not os.path.exists(folderPath):
            os.makedirs(folderPath) 
        self.folderPath = folderPath

    def ShowFigure(self, fig: go.Figure, name: str = "grafico"):
        fig.write_html(f"{self.folderPath}/{name}.html")
        if self.ShowFigures:
            fig.show()

    def BoxPlotUnusedTime(self, weeks: PatientListForSpecialties, title: str):
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
        for op, patients in weeks.items():
            # divido i pazienti per sala operatoria
            or_rooms = list(set([p.workstation for p in patients]))
            for operationRoom, or_patients in {room_id: [p for p in patients if p.workstation == room_id + 1] 
                                                  for room_id in range(len(or_rooms))}.items():
                data = []
                lastWeek = max(p.opDay for p in patients) % Settings.week_length_days
                for weekNum in range(lastWeek + 1):
                    # Calcola il tempo inutilizzato per ogni giorno della settimana
                    unused_times = []
                    for day in range(weekNum * Settings.week_length_days, (weekNum + 1) * Settings.week_length_days):
                        dailyPatients = [p for p in or_patients if p.opDay == day]
                        time_used = sum(p.eot for p in dailyPatients)
                        free_time = Settings.daily_operation_limit - time_used
                        unused_times.append(free_time)
                    data.append(go.Box(
                        y=unused_times,
                        name=f"Sett {weekNum}",
                        boxmean='sd',
                        marker_color='indianred'
                    ))
        fig = go.Figure(data)
        fig.update_layout(
            title=title,
            yaxis_title="Tempo inutilizzato (minuti)",  
            xaxis_title="Settimane"                     
        )
        self.ShowFigure(fig, name="BoxPlotUnusedTime")
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

    def PrintWaitingTimeBoxPlotGraph(self, operations: PatientListForSpecialties, basetitle: str):
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
            lastWeek = max(p.opDay for p in patients) % week_len
            for weekNum in range(lastWeek + 1):
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
            self.ShowFigure(fig, name=f"WaitingTimeBoxPlot_{op}")

    def PrintDailyBoxGraph(self, operation: PatientListForSpecialties, baseTitle: str, plan_eot: dict | None = None):
        limite_massimo = Settings.daily_operation_limit

        for op, patients_real in operation.items():
            xline = Settings.week_length_days * Settings.workstations_config[op]
            title = baseTitle + op

        # --- piano EOT (lista di dict) ---
        plan_list = plan_eot.get(op, []) if plan_eot is not None else None

        fig = go.Figure()

        # Colori: usa l’unione degli ID (piano + reale) così restano coerenti
        ids = set()
        for p in patients_real:
            ids.add(p.id)
        if plan_list is not None:
            for pp in plan_list:
                if isinstance(pp, dict) and "id" in pp:
                    ids.add(pp["id"])

        ids = sorted(ids)
        num_patients = max(1, len(ids))
        color_map_progressive = {
            pid: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)"
            for i, pid in enumerate(ids)
        }

        # range settimane (come prima)
        last_day_real = max(p.opDay for p in patients_real) if patients_real else 0
        last_day_plan = max((pp.get("opDay", 0) for pp in plan_list), default=0) if plan_list is not None else 0
        last_day = max(last_day_real, last_day_plan)
        num_weeks = (last_day // Settings.week_length_days) + 1

        # linea limite
        shape_limite_massimo = [dict(
            type="line",
            x0=-0.5, x1=xline - 0.5,
            y0=limite_massimo, y1=limite_massimo,
            line=dict(color="red", width=2, dash="dash"),
        )]

        shapes_by_week = {}
        trace_idx_by_week = {w: [] for w in range(num_weeks)}

        # --- costruisco TRACES per settimana (visivo identico: EOT front + ROT back) ---
        for weekNum in range(num_weeks):
            shapes = []
            extra_time_pool = Settings.weekly_extra_time_pool

            for day in range(weekNum * Settings.week_length_days, (weekNum + 1) * Settings.week_length_days):
                for room_id in range(Settings.workstations_config[op]):

                    # REAL (ROT) -> pazienti reali
                    real_day_room = [p for p in patients_real if p.workstation == room_id + 1 and p.opDay == day]
                    minsRot = round(sum(p.rot for p in real_day_room), 2)

                    # PLAN (EOT) -> dict dal piano, se disponibile; altrimenti fallback: usa gli stessi pazienti reali
                    if plan_list is not None:
                        plan_day_room = [
                            pp for pp in plan_list
                            if pp.get("workstation", None) == room_id + 1 and pp.get("opDay", None) == day
                        ]
                    else:
                        plan_day_room = None

                    mins = 0.0
                    if plan_day_room is not None:
                        mins = round(sum(float(pp.get("eot", 0) or 0) for pp in plan_day_room), 2)
                    else:
                        mins = round(sum(p.eot for p in real_day_room), 2)

                    # x identico: tot EOT e tot ROT nella label
                    xtext = f"W:{weekNum}|D:{day}|OR:{room_id+1}|<br>ToTMin:{mins}|<br>RoTMin:{minsRot}"

                    # --- FRONT: EOT per paziente (dal piano se c’è) ---
                    if plan_day_room is not None:
                        for pp in plan_day_room:
                            pid = pp.get("id", None)
                            if pid is None:
                                continue
                            peot = float(pp.get("eot", 0) or 0)
                            pday = pp.get("day", None)
                            pmtb = pp.get("mtb", None)

                            fig.add_trace(go.Bar(
                                x=[xtext],
                                y=[peot],
                                name=f"Patient {pid}",
                                hoverinfo="text",
                                text=[f"Patient {pid}: {int(peot)}m {int((peot % 1) * 60)}s"],
                                hovertemplate=f'D:{pday}|MTB:{pmtb}<extra></extra>',
                                marker=dict(color=color_map_progressive.get(pid, "gray")),
                                cliponaxis=True,
                                textposition='inside',
                                offsetgroup="front",
                                visible=(weekNum == Settings.start_week_scheduling)
                            ))
                            trace_idx_by_week[weekNum].append(len(fig.data) - 1)
                    else:
                        # fallback: comportamento vecchio (usa i pazienti reali per EOT)
                        for p in real_day_room:
                            fig.add_trace(go.Bar(
                                x=[xtext],
                                y=[p.eot],
                                name=f"Patient {p.id}",
                                hoverinfo="text",
                                text=[f"Patient {p.id}: {int(p.eot)}m {int((p.eot % 1) * 60)}s"],
                                hovertemplate=f'D:{p.day}|MTB:{p.mtb}<extra></extra>',
                                marker=dict(color=color_map_progressive.get(p.id, "gray")),
                                cliponaxis=True,
                                textposition='inside',
                                offsetgroup="front",
                                visible=(weekNum == Settings.start_week_scheduling)
                            ))
                            trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                    # --- BACK: ROT per paziente (sempre dal reale) ---
                    for p in real_day_room:
                        fig.add_trace(go.Bar(
                            x=[xtext],
                            y=[p.rot],
                            name=f"Patient {p.id} ROT",
                            hoverinfo="text",
                            text=[f"Patient {p.id} ROT: {int(p.rot)}m {int((p.rot % 1) * 60)}s"],
                            hovertemplate=f'D:{p.day}|MTB:{p.mtb}<extra></extra>',
                            marker=dict(color=color_map_progressive.get(p.id, "gray"), opacity=0.3),
                            cliponaxis=True,
                            textposition='inside',
                            offsetgroup="back",
                            offset=-0.2,
                            visible=(weekNum == Settings.start_week_scheduling)
                        ))
                        trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                # linea extra giornaliero (come prima, basata sui ROT reali)
                dayNumInWeek = day % Settings.week_length_days
                x0 = dayNumInWeek * Settings.workstations_config[op] - 0.5
                x1 = (dayNumInWeek + 1) * Settings.workstations_config[op] - 0.5

                shapes.append(dict(
                    type="line",
                    x0=x0, x1=x1,
                    y0=limite_massimo + extra_time_pool, y1=limite_massimo + extra_time_pool,
                    line=dict(color="green", width=2, dash="dash"),
                ))

                val = (limite_massimo * Settings.workstations_config[op]) - sum(p.rot for p in patients_real if p.opDay == day)
                extra_time_pool = (extra_time_pool + val) if val < 0 else 0

            shapes_by_week[weekNum] = shapes

        # --- bottoni settimana: visibilità corretta anche se PLAN e REAL hanno num barre diverso ---
        buttons = []
        total_traces = len(fig.data)
        for weekNum in range(num_weeks):
            visible = [False] * total_traces
            for idx in trace_idx_by_week[weekNum]:
                if 0 <= idx < total_traces:
                    visible[idx] = True

            buttons.append(dict(
                label=f"Settimana {weekNum}",
                method="update",
                args=[
                    {"visible": visible},
                    {"title": title, "shapes": shape_limite_massimo + shapes_by_week[weekNum]}
                ]
            ))

        # overlay identico a prima
        fig.update_layout(barmode="overlay")
        fig.update_xaxes(showticklabels=True)
        fig.update_traces(showlegend=False, hoverinfo="skip", selector=dict(offsetgroup="back"))

        fig.add_annotation(
            x=xline - 1, y=limite_massimo,
            text=f"{limite_massimo} minuti (limite giornaliero)",
            showarrow=False,
            yshift=10,
            font=dict(color="red")
        )
        fig.add_annotation(
            x=0.5, y=Settings.weekly_extra_time_pool + limite_massimo,
            text="minuti massimi di straordinario disponibili",
            showarrow=False,
            yshift=10,
            font=dict(color="green")
        )

        fig.update_layout(
            updatemenus=[dict(
                active=0,
                buttons=buttons,
                x=0.95,
                y=1.1,
                xanchor='right',
                yanchor='top'
            )],
            barmode="stack",  # come prima nel tuo layout finale
            title=title,
            showlegend=False,
            yaxis_title="Minuti Totali",
            xaxis_title="Giorni",
        )

        self.ShowFigure(fig, name=f"DailyBoxGraph_{op}")

    def PrintTrendLineGraph(self, operation : PatientListForSpecialties, baseTitle : str): 
        # estraggo i dati di una operazione dal formato json 
        # inizializzo il grafico
        for op, patients in operation.items():
            title = baseTitle + op
            fig = go.Figure()
            #ordino i pazienti per giorno e per room
            patients = sorted(patients, key=lambda p: (p.opDay, p.workstation))
            # Creo le etichette per i giorni
            # calcolo il numero dell'ultimo giorno della settiamana dell' ultimo giorno operato
            last_day = max(p.opDay for p in patients)
            num_weeks = (last_day // Settings.week_length_days) + 1
            days_title = [f"Day:{day}" for day in range(num_weeks * Settings.week_length_days)]
            #calcolo il giorno di inizio della schedulazione
            start_index = 0
            if Settings.start_week_scheduling >= 1:
                start_day = f"Day:{(Settings.start_week_scheduling) * Settings.week_length_days}"
                #trovo l'indice del giorno nell'elenco days_title
                if start_day in days_title:
                    start_index = days_title.index(start_day)
                

            # Inizializzo le strutture dati per il calcolo del tempo libero e del numero di pazienti 
            room_ids = range(Settings.workstations_config[op])
            room_free_time = {room_id+1:[] for room_id in room_ids}
            room_patient = {room_id+1:[] for room_id in room_ids}
            days = max([p.opDay for p in patients])
            
            for d in range(days):
                for room_id in room_ids:
                    dailyPatients = [p for p in patients if p.workstation == room_id+1 and p.opDay == d]
                    time_used = sum(p.eot for p in dailyPatients )
                    patient_count = len(dailyPatients)
                    free_time = Settings.daily_operation_limit - time_used
                    room_free_time[room_id+1].append(free_time)
                    room_patient[room_id+1].append(patient_count)
            # Grafico con doppio asse Y
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            # Barre: pazienti per room
            for room_id, counts in room_patient.items():
                fig.add_trace(go.Bar(
                    x=days_title,
                    y=counts,
                    name=f"OR:{room_id}-Numero di Pazienti",
                    opacity=0.6,
                    hovertemplate='%{y}<extra>P</extra>'
                ), secondary_y=True)
            # Linee: tempo libero per room
            for room_id, times in room_free_time.items():
                fig.add_trace(go.Scatter(
                    x=days_title,
                    y=times,
                    name=f"OR:{room_id}-Tempo libero residuo",
                    mode='lines+markers',
                    hovertemplate='%{y}<extra>MIN</extra>'
                ), secondary_y=False)
            if Settings.start_week_scheduling >= 1:
                fig.add_vline(
                    x=start_index - 0.5,
                    line=dict(color="orange", width=2, dash="dash"),
                    annotation_text="Inizio Schedulazione",
                    annotation_position="top right",
                    annotation_font_color="orange"
                )
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
            self.ShowFigure(fig, name=f"TrendLineGraph_{op}")

    # def PrintWaitingListLineGraph(self, weeks : list[Week], title : str): 
    #     # Escludo l'ultima settimana se non è completa
    #     #weeks = operation[:-1]
    #     all_patients = [p for week in weeks for p in week.patients()]
    #     new_patient_list = defaultdict(list)
    #     resolved_list = defaultdict(list)
    #     for p in all_patients:
    #         #estraggo la lista di attesa
    #         new_patient_list[p.day].append(p.id)
    #         #estraggo la lista dei risolti dalle settimane
    #         for week in weeks:
    #             day = week.getNumberOpDayByPatientID(p.id)
    #             if day != -1:
    #                 resolved_list[day].append(p.id)
    #                 break
    #     # ordino le liste per giorno
    #     new_patient_list = dict(sorted(new_patient_list.items()))
    #     resolved_list = dict(sorted(resolved_list.items()))
    #     #eseguo i conti dei pazienti nelle liste
    #     new_patient_count = {day: len(ids) for day, ids in new_patient_list.items()}
    #     resolved_count = {day: len(ids) for day, ids in resolved_list.items()}
    #     # imposto la linea per la differenze tra i pazienti in attesa e quelli risolti
    #     waiting_count = {}
    #     total_waiting = 0   
    #     max_day = max(max(new_patient_count.keys(), default=0), max(resolved_count.keys(), default=0))
    #     for day in range(1, max_day + 1):
    #         total_waiting += new_patient_count.get(day, 0)
    #         total_waiting -= resolved_count.get(day, 0)
    #         waiting_count[day] = total_waiting
    #     # inizializzo il grafico
    #     fig = go.Figure()
    #     fig.add_trace(go.Scatter(
    #         x=list(new_patient_count.keys()),
    #         y=list(new_patient_count.values()),
    #         mode='lines+markers',
    #         name='Pazienti Aggiunti',
    #         line=dict(color='blue'),
    #         hovertemplate='%{y}<extra>Pazienti Aggiunti</extra>'
    #     ))
    #     fig.add_trace(go.Scatter(
    #         x=list(resolved_count.keys()),
    #         y=list(resolved_count.values()),
    #         mode='lines+markers',
    #         name='Pazienti operati',
    #         line=dict(color='green'),
    #         hovertemplate='%{y}<extra>Pazienti operati</extra>'
    #     ))
    #     fig.add_trace(go.Scatter(
    #         x=list(waiting_count.keys()),
    #         y=list(waiting_count.values()),
    #         mode='lines+markers',
    #         name='Pazienti in attesa',
    #         line=dict(color='red'),
    #         hovertemplate='%{y}<extra>Pazienti in attesa</extra>'
    #     ))
    #     #aggiungo linea verticale per l'inizio della schedulazione
    #     if Settings.start_week_scheduling >= 1:
    #         start_day = (Settings.start_week_scheduling) * Settings.week_length_days
    #         fig.add_vline(
    #             x=start_day,
    #             line=dict(color="orange", width=2, dash="dash"),
    #             annotation_text="Inizio Schedulazione",
    #             annotation_position="top right",
    #             annotation_font_color="orange"
    #         )
    #     fig.update_layout(
    #         title=title,
    #         xaxis_title="Giorno",
    #         yaxis_title="Numero di Pazienti",
    #         template="plotly_white",
    #         hovermode='x unified'
    #     )
    #     self.ShowFigure(fig, name="WaitingListLineGraph")

    def PrintWaitingListLineGraph(self, operations : PatientListForSpecialties, baseTitle : str): 
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
            # Aggiungo le tre linee al grafico
            # Linea dei pazienti aggiunti
            fig.add_trace(go.Scatter(
                x=list(new_patient_count.keys()),
                y=list(new_patient_count.values()),
                mode='lines+markers',
                name='Pazienti Aggiunti',
                line=dict(color='blue'),
                hovertemplate='%{y}<extra>Pazienti Aggiunti</extra>'
            ))
            # Linea dei pazienti operati
            fig.add_trace(go.Scatter(
                x=list(resolved_count.keys()),
                y=list(resolved_count.values()),
                mode='lines+markers',
                name='Pazienti operati',
                line=dict(color='green'),
                hovertemplate='%{y}<extra>Pazienti operati</extra>'
            ))
            # Linea dei pazienti in attesa
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
            self.ShowFigure(fig, name=f"WaitingListLineGraph_{op}")

  

    def MakeGraphs(self, data: PatientListForSpecialties, showGraphs: bool = True, plan_eot: dict | None = None):
        self.ShowFigures = showGraphs
        self.PrintDailyBoxGraph(data, "Distribuzione dei pazienti per ", plan_eot=plan_eot)
        self.PrintTrendLineGraph(data, "Andamento tempo occupato per ")
        self.PrintWaitingListLineGraph(data, "Andamento lista d'attesa per ")
        self.PrintWaitingTimeBoxPlotGraph(data, "Tempi di attesa per ")
     #self.BoxPlotUnusedTime(data, "Tempi medi non utilizzati per ") #utilizza ancora le classi delle settimane per i dati 

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
    file_path = "Data\\Records\\seed-1\\weekly_schedule.json"
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        data = json.load(f)
    ops = PatientListForSpecialties.from_dict(data)
    gr = Graphs()
    gr.MakeGraphs(ops)