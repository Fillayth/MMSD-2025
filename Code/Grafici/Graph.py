"""Modulo per la generazione di grafici Plotly dalle liste di pazienti per specialità.

Gestisce la visualizzazione dei dati di schedulazione operatoria attraverso:
- Box plot dei tempi inutilizzati
- Grafici giornalieri con pianificazione EOT e reale ROT
- Linee di tendenza del carico operatorio
- Grafici della lista d'attesa
- Tabelle di confronto tra scenari
"""

from __future__ import annotations
from collections import defaultdict
import json
import os
import sys
import copy

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

if os.path.basename(__file__) != "main.py":
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "Code"))
    )

from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from settings import Settings


def CreateScheduleWithReplanned(schedule: dict, plan_eot_input: dict | None) -> dict:
    """Crea una nuova istanza dello schedule integrando i dati di pianificazione EOT.

    Risolve anche il problema dei pazienti (come l'ID 1398) presenti SOLO nel piano
    di ripianificazione (plan_eot) e originariamente assenti dallo schedule di base.
    """
    cloned_schedule = copy.deepcopy(schedule)

    if not plan_eot_input:
        return cloned_schedule

    # 1. AUTO-FIX: Estrazione della sezione corretta se passato l'intero file JSON
    if isinstance(plan_eot_input, dict) and "plan_eot" in plan_eot_input:
        plan_eot = plan_eot_input["plan_eot"]
    else:
        plan_eot = plan_eot_input

    for op, patients in cloned_schedule.items():
        plan_list = plan_eot.get(op, [])
        if not plan_list:
            continue

        # 2. Mappa dei ripianificati indicizzata per ID (stringa)
        latest_plan_by_id = {}
        for pp in plan_list:
            if not isinstance(pp, dict):
                continue
            pid = pp.get("id", None)
            if pid is None:
                continue
            latest_plan_by_id[str(pid)] = pp

        updated_patients = []
        seen_ids = set()

        # 3. Aggiornamento dei pazienti ESISTENTI nello schedule originale
        for p in patients:
            is_dict = isinstance(p, dict)
            p_id = p.get("id") if is_dict else getattr(p, "id", None)

            if p_id is None:
                continue

            p_id_str = str(p_id)

            if p_id_str in latest_plan_by_id:
                pp = latest_plan_by_id[p_id_str]

                # Aggiorna i campi del record esistente
                if is_dict:
                    p["opDay"] = pp.get("opDay", p.get("opDay"))
                    p["workstation"] = pp.get("workstation", p.get("workstation"))
                    p["eot"] = float(pp.get("eot", 0) or p.get("eot", 0))
                    p["day"] = pp.get("day", p.get("day"))
                    if "mtb" in pp:
                        p["mtb"] = pp["mtb"]
                    if "rot" in pp:
                        p["rot"] = float(pp["rot"] or p.get("rot", 0))
                else:
                    p.opDay = pp.get("opDay", p.opDay)
                    p.workstation = pp.get("workstation", p.workstation)
                    p.eot = float(pp.get("eot", 0) or p.eot)
                    p.day = pp.get("day", p.day)
                    if "mtb" in pp:
                        p.mtb = pp["mtb"]
                    if "rot" in pp:
                        p.rot = float(pp["rot"] or p.rot)

            if p_id_str not in seen_ids:
                seen_ids.add(p_id_str)
                updated_patients.append(p)

        # 4. FIX FONDAMENTALE: Aggiunta dei pazienti MANCANTI (Presenti solo in plan_eot)
        # Questo blocco intercetta l'ID 1398 e lo inserisce nello schedule finale
        for pid_str, pp in latest_plan_by_id.items():
            if pid_str not in seen_ids:
                seen_ids.add(pid_str)

                # Identifichiamo se lo schedule usa Dizionari o Oggetti custom (es. istanze di Patient)
                is_dict_mode = True
                if patients and not isinstance(patients[0], dict):
                    is_dict_mode = False

                if is_dict_mode:
                    # Se lavoriamo con JSON/Dizionari grezzi
                    new_p = {
                        "id": pp.get("id"),
                        "eot": float(pp.get("eot", 0) or 0),
                        "rot": float(pp.get("rot", 0) or 0),
                        "day": pp.get("day", 0),
                        "mtb": pp.get("mtb", 0),
                        "opDay": pp.get("opDay", -1),
                        "workstation": pp.get("workstation", 0),
                        "overdue": pp.get("overdue", False),
                    }
                    updated_patients.append(new_p)
                else:
                    # Se lavoriamo con Oggetti, cloniamo il tipo e i metodi di un elemento esistente
                    try:
                        new_p = copy.deepcopy(patients[0])
                        new_p.id = pp.get("id")
                        new_p.opDay = pp.get("opDay", -1)
                        new_p.workstation = pp.get("workstation", 0)
                        new_p.eot = float(pp.get("eot", 0) or 0)
                        new_p.rot = float(pp.get("rot", 0) or 0)
                        new_p.day = pp.get("day", 0)
                        new_p.mtb = pp.get("mtb", 0)
                        new_p.overdue = pp.get("overdue", False)
                        updated_patients.append(new_p)
                    except Exception:
                        pass

        cloned_schedule[op] = updated_patients

    return cloned_schedule


class Graphs:
    """Gestore della creazione di grafici Plotly per l'analisi della schedulazione operatoria."""

    folderPath: str
    ShowFigures: bool = False

    def __init__(
        self, folderPath: str = os.path.dirname(os.path.abspath(__file__)) + "/Images"
    ):
        """Inizializza il gestore dei grafici.

        Args:
            folderPath: Percorso della cartella dove salvare i grafici HTML (default: Images/)
        """
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)
        self.folderPath = folderPath

    def ShowFigure(self, fig: go.Figure, name: str = "grafico") -> None:
        """Salva il grafico in HTML e opzionalmente lo visualizza.

        Args:
            fig: Figura Plotly da salvare
            name: Nome del file HTML (senza estensione)
        """
        fig.write_html(f"{self.folderPath}/{name}.html")
        if self.ShowFigures:
            fig.show()

    def _get_color_map(self, ids: list[int]) -> dict[int, str]:
        """Genera una mappa colori progressiva HSL per gli ID pazienti.

        Args:
            ids: Lista ordinata di ID pazienti

        Returns:
            Dizionario {id: colore_hsl}
        """
        num_patients = max(1, len(ids))
        return {
            pid: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)"
            for i, pid in enumerate(ids)
        }

    def _create_limit_line_shape(
        self, x0: float, x1: float, y: float, color: str = "red"
    ) -> dict:
        """Crea una forma linea per il grafico Plotly.

        Args:
            x0, x1: Coordinate X inizio e fine
            y: Coordinata Y
            color: Colore della linea

        Returns:
            Dizionario shape per Plotly
        """
        return {
            "type": "line",
            "x0": x0,
            "x1": x1,
            "y0": y,
            "y1": y,
            "line": {"color": color, "width": 2, "dash": "dash"},
        }

    def _get_free_time_per_day(
        self, patients: list, day: int, metric: str = "eot"
    ) -> float:
        """Calcola il tempo libero in una sala per un determinato giorno.

        Args:
            patients: Lista pazienti della sala
            day: Numero del giorno
            metric: Metrica da usare ('eot' o 'rot')

        Returns:
            Tempo libero in minuti
        """
        daily_patients = [p for p in patients if p.opDay == day]
        time_used = sum(getattr(p, metric, 0) for p in daily_patients)
        return Settings.daily_operation_limit - time_used

    def BoxPlotUnusedTime(self, weeks: PatientListForSpecialties, title: str) -> None:
        """Crea un box plot del tempo inutilizzato per settimana e per sala operatoria.

        Args:
            weeks: PatientListForSpecialties con i dati dei pazienti
            title: Titolo del grafico
        """
        data = []

        for op, patients in weeks.items():
            if not patients:
                continue

            # Calcolo ultimo giorno e numero settimane
            last_week = (
                max((p.opDay for p in patients), default=0) // Settings.week_length_days
            )

            for weekNum in range(last_week + 1):
                # Calcola tempo libero per ogni giorno della settimana
                unused_times = [
                    self._get_free_time_per_day(patients, day)
                    for day in range(
                        weekNum * Settings.week_length_days,
                        (weekNum + 1) * Settings.week_length_days,
                    )
                ]

                data.append(
                    go.Box(
                        y=unused_times,
                        name=f"{op} - Sett {weekNum}",
                        boxmean="sd",
                        marker_color="indianred",
                    )
                )

        if data:
            fig = go.Figure(data)
            fig.update_layout(
                title=title,
                yaxis_title="Tempo inutilizzato (minuti)",
                xaxis_title="Settimane",
            )
            self.ShowFigure(fig, name="BoxPlotUnusedTime")

    """
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

    """

    def PrintWaitingTimeBoxPlotGraph_withEOTplanned(
        self,
        operations: PatientListForSpecialties,
        basetitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea box plot dei tempi di attesa per settimana e specialità, integrando i dati pianificati.

        Args:
            operations: PatientListForSpecialties con i dati reali
            basetitle: Titolo base del grafico
            plan_eot: Dizionario contenente la programmazione pianificata EOT
            use_rot_as_primary: Se True usa i dati reali, altrimenti usa il pianificato (EOT)
        """
        for op, patients_real in operations.items():
            if not patients_real:
                continue

            title = basetitle + op

            # --- 1. Estrazione e pulizia dati PIANIFICATI (EOT) ---
            plan_list = plan_eot.get(op, []) if plan_eot is not None else None
            if plan_list is not None:
                latest_plan_by_id = {}
                for pp in plan_list:
                    if not isinstance(pp, dict):
                        continue
                    pid = pp.get("id", None)
                    if pid is None:
                        continue
                    latest_plan_by_id[pid] = pp
                plan_list = list(latest_plan_by_id.values())

            # --- 2. Selezione del Dataset e Deduplicazione ID ---
            rows = []
            if use_rot_as_primary or plan_list is None:
                # Dati REALI: garantiamo l'unicità dell'ID paziente
                seen_ids = set()
                for p in patients_real:
                    if p.id not in seen_ids:
                        seen_ids.add(p.id)
                        rows.append(
                            {
                                "ID": p.id,
                                "Data inserimento": p.day,
                                "MTB": getattr(p, "mtb", None),
                                "Data operazione": p.opDay,
                            }
                        )
            else:
                # Dati PIANIFICATI (già deduplicati globalmente per ID nel punto 1)
                for pp in plan_list:
                    rows.append(
                        {
                            "ID": pp.get("id"),
                            "Data inserimento": pp.get("day", 0),
                            "MTB": pp.get("mtb", None),
                            "Data operazione": pp.get("opDay", -1),
                        }
                    )

            # --- 3. Costruzione DataFrame e calcolo metriche ---
            df = pd.DataFrame(rows)

            # Consideriamo solo i pazienti che hanno effettivamente una data di operazione valida
            df = df[df["Data operazione"] != -1].dropna(subset=["Data operazione"])

            if df.empty:
                continue

            df["Tempo_attesa"] = df["Data operazione"] - df["Data inserimento"]

            # Calcola il numero massimo di settimane basandosi sul dataset scelto
            last_week = int(df["Data operazione"].max() // Settings.week_length_days)

            # --- 4. Generazione dei Box Plot per Settimana ---
            data = []
            for weekNum in range(last_week + 1):
                # Manteniamo la logica di segmentazione originaria dei giorni della settimana
                week_start = (weekNum - 1) * Settings.week_length_days + 1
                week_end = weekNum * Settings.week_length_days

                waiting_times = df[df["Data operazione"].between(week_start, week_end)][
                    "Tempo_attesa"
                ]

                data.append(
                    go.Box(
                        y=waiting_times,
                        name=f"Sett {weekNum}",
                        boxmean="sd",
                        marker_color="indianred",
                    )
                )

            # --- 5. Costruzione del Grafico Layout ---
            fig = go.Figure(data)

            metric_label = (
                "Dati REALI (ROT)" if use_rot_as_primary else "Dati PIANIFICATI (EOT)"
            )
            fig.update_layout(
                title=f"{title} - {metric_label}",
                yaxis_title="Tempo di attesa (giorni)",
                xaxis_title="Settimane",
                template="plotly_white",
            )

            self.ShowFigure(fig, name=f"WaitingTimeBoxPlot_withEOTplanned_{op}")

    def PrintWaitingTimeBoxPlotGraph(
        self,
        operations: PatientListForSpecialties,
        basetitle: str,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea box plot dei tempi di attesa per settimana e specialità.

        Args:
            operations: PatientListForSpecialties con i dati
            basetitle: Titolo base del grafico
            use_rot_as_primary: Non utilizzato in questo metodo (mantenuto per compatibilità)
        """
        for op, patients in operations.items():
            if not patients:
                continue

            title = basetitle + op
            data = []

            # Costruisci DataFrame con dati di pazienti
            df = pd.DataFrame(
                [
                    {
                        "ID": p.id,
                        "Data inserimento": p.day,
                        "MTB": p.mtb,
                        "Data operazione": p.opDay,
                    }
                    for p in patients
                ]
            )
            df["Tempo_attesa"] = df["Data operazione"] - df["Data inserimento"]

            # Calcola numero di settimane
            last_week = (
                max((p.opDay for p in patients), default=0) // Settings.week_length_days
            )

            for weekNum in range(last_week + 1):
                # Filtra tempi di attesa per settimana
                week_start = (weekNum - 1) * Settings.week_length_days + 1
                week_end = weekNum * Settings.week_length_days
                waiting_times = df[df["Data operazione"].between(week_start, week_end)][
                    "Tempo_attesa"
                ]

                data.append(
                    go.Box(
                        y=waiting_times,
                        name=f"Sett {weekNum}",
                        boxmean="sd",
                        marker_color="indianred",
                    )
                )

            fig = go.Figure(data)
            fig.update_layout(
                title=title,
                yaxis_title="Tempo di attesa (giorni)",
                xaxis_title="Settimane",
            )
            self.ShowFigure(fig, name=f"WaitingTimeBoxPlot_{op}")

    def PrintDailyBoxGraph_withEOTplanned(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ):
        limite_massimo = Settings.daily_operation_limit

        for op, patients_real in operation.items():
            if not patients_real:
                continue
            xline = Settings.week_length_days * Settings.workstations_config[op]
            title = baseTitle + op

            # --- Pianificato EOT (lista di dict)  ---
            plan_list = plan_eot.get(op, []) if plan_eot is not None else None
            if plan_list is not None:
                latest_plan_by_id = {}
                for pp in plan_list:
                    if not isinstance(pp, dict):
                        continue
                    pid = pp.get("id", None)
                    if pid is None:
                        continue
                    latest_plan_by_id[pid] = pp
                plan_list = sorted(
                    latest_plan_by_id.values(),
                    key=lambda pp: (
                        pp.get("opDay", 0),
                        pp.get("workstation", 0),
                        pp.get("id", 0),
                    ),
                )

            fig = go.Figure()

            # Colori: usa l’unione degli ID (pianificato + reale) così restano coerenti
            ids = set(p.id for p in patients_real)
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
            last_day_plan = (
                max((pp.get("opDay", 0) for pp in plan_list), default=0)
                if plan_list is not None
                else 0
            )
            last_day = max(last_day_real, last_day_plan)
            num_weeks = (last_day // Settings.week_length_days) + 1

            # linea limite
            shape_limite_massimo = [
                dict(
                    type="line",
                    x0=-0.5,
                    x1=xline - 0.5,
                    y0=limite_massimo,
                    y1=limite_massimo,
                    line=dict(color="red", width=2, dash="dash"),
                )
            ]

            shapes_by_week = {}
            trace_idx_by_week = {w: [] for w in range(num_weeks)}

            # --- costruisco TRACES per settimana (visivo identico: EOT front + ROT back) ---
            for weekNum in range(num_weeks):
                shapes = []
                extra_time_pool = Settings.weekly_extra_time_pool

                for day in range(
                    weekNum * Settings.week_length_days,
                    (weekNum + 1) * Settings.week_length_days,
                ):
                    for room_id in range(Settings.workstations_config[op]):

                        # REAL (ROT) -> pazienti reali
                        real_day_room = [
                            p
                            for p in patients_real
                            if p.workstation == room_id + 1 and p.opDay == day
                        ]
                        minsRot = round(sum(p.rot for p in real_day_room), 2)

                        # PLAN (EOT) -> dict dal pianificato, se disponibile; altrimenti fallback: usa gli stessi pazienti reali
                        if plan_list is not None:
                            plan_day_room = [
                                pp
                                for pp in plan_list
                                if pp.get("workstation", None) == room_id + 1
                                and pp.get("opDay", None) == day
                            ]
                        else:
                            plan_day_room = None

                        mins = 0.0
                        if plan_day_room is not None:
                            mins = round(
                                sum(
                                    float(pp.get("eot", 0) or 0) for pp in plan_day_room
                                ),
                                2,
                            )
                        else:
                            mins = round(sum(p.eot for p in real_day_room), 2)

                        # Determina quale valore usare come primario e secondario
                        primary_mins = minsRot if use_rot_as_primary else mins
                        secondary_label = (
                            "EOT (pianificato)" if use_rot_as_primary else "ROT (reale)"
                        )
                        primary_label = (
                            "ROT (reale)" if use_rot_as_primary else "EOT (pianificato)"
                        )

                        # x identico: tot EOT e tot ROT nella label
                        xtext = f"W:{weekNum}|D:{day}|OR:{room_id+1}|<br>ToTMin:{mins}|<br>RoTMin:{minsRot}"

                        # --- FRONT: Metrica primaria (EOT se not use_rot_as_primary, ROT altrimenti) ---
                        if use_rot_as_primary:
                            # ROT come primario (sempre dal reale)
                            for p in real_day_room:
                                fig.add_trace(
                                    go.Bar(
                                        x=[xtext],
                                        y=[p.rot],
                                        name=f"Patient {p.id}",
                                        text=[
                                            f"Patient {p.id}: {int(p.rot)}m {int((p.rot % 1) * 60)}s"
                                        ],
                                        hovertemplate=f"Paziente {p.id}<br>ROT: {p.rot:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>ROT (reale)</extra>",
                                        marker=dict(
                                            color=color_map_progressive.get(
                                                p.id, "gray"
                                            )
                                        ),
                                        cliponaxis=True,
                                        textposition="inside",
                                        offsetgroup="front",
                                        visible=(
                                            weekNum == Settings.start_week_scheduling
                                        ),
                                    )
                                )
                                trace_idx_by_week[weekNum].append(len(fig.data) - 1)
                        elif plan_day_room is not None:
                            for pp in plan_day_room:
                                pid = pp.get("id", None)
                                if pid is None:
                                    continue
                                peot = float(pp.get("eot", 0) or 0)
                                pday = pp.get("day", None)
                                pmtb = pp.get("mtb", None)

                                fig.add_trace(
                                    go.Bar(
                                        x=[xtext],
                                        y=[peot],
                                        name=f"Patient {pid}",
                                        text=[
                                            f"Patient {pid}: {int(peot)}m {int((peot % 1) * 60)}s"
                                        ],
                                        hovertemplate=f"Paziente {pid}<br>EOT: {peot:.2f} min<br>D:{pday}|MTB:{pmtb}<extra>EOT (pianificato)</extra>",
                                        marker=dict(
                                            color=color_map_progressive.get(pid, "gray")
                                        ),
                                        cliponaxis=True,
                                        textposition="inside",
                                        offsetgroup="front",
                                        visible=(
                                            weekNum == Settings.start_week_scheduling
                                        ),
                                    )
                                )
                                trace_idx_by_week[weekNum].append(len(fig.data) - 1)
                        else:
                            for p in real_day_room:
                                fig.add_trace(
                                    go.Bar(
                                        x=[xtext],
                                        y=[p.eot],
                                        name=f"Patient {p.id}",
                                        text=[
                                            f"Patient {p.id}: {int(p.eot)}m {int((p.eot % 1) * 60)}s"
                                        ],
                                        hovertemplate=f"Paziente {p.id}<br>EOT: {p.eot:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>EOT (pianificato)</extra>",
                                        marker=dict(
                                            color=color_map_progressive.get(
                                                p.id, "gray"
                                            )
                                        ),
                                        cliponaxis=True,
                                        textposition="inside",
                                        offsetgroup="front",
                                        visible=(
                                            weekNum == Settings.start_week_scheduling
                                        ),
                                    )
                                )
                                trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                        # --- BACK: Metrica secondaria (ROT se not use_rot_as_primary, EOT altrimenti) ---
                        if use_rot_as_primary:
                            if plan_day_room is not None:
                                for pp in plan_day_room:
                                    pid = pp.get("id", None)
                                    if pid is None:
                                        continue
                                    peot = float(pp.get("eot", 0) or 0)
                                    pday = pp.get("day", None)
                                    pmtb = pp.get("mtb", None)

                                    fig.add_trace(
                                        go.Bar(
                                            x=[xtext],
                                            y=[peot],
                                            name=f"Patient {pid} EOT",
                                            text=[
                                                f"Patient {pid} EOT: {int(peot)}m {int((peot % 1) * 60)}s"
                                            ],
                                            hovertemplate=f"Paziente {pid}<br>EOT: {peot:.2f} min<br>D:{pday}|MTB:{pmtb}<extra>EOT (pianificato)</extra>",
                                            marker=dict(
                                                color=color_map_progressive.get(
                                                    pid, "gray"
                                                ),
                                                opacity=0.3,
                                            ),
                                            cliponaxis=True,
                                            textposition="inside",
                                            offsetgroup="back",
                                            offset=-0.2,
                                            visible=(
                                                weekNum
                                                == Settings.start_week_scheduling
                                            ),
                                        )
                                    )
                                    trace_idx_by_week[weekNum].append(len(fig.data) - 1)
                            else:
                                for p in real_day_room:
                                    fig.add_trace(
                                        go.Bar(
                                            x=[xtext],
                                            y=[p.eot],
                                            name=f"Patient {p.id} EOT",
                                            text=[
                                                f"Patient {p.id} EOT: {int(p.eot)}m {int((p.eot % 1) * 60)}s"
                                            ],
                                            hovertemplate=f"Paziente {p.id}<br>EOT: {p.eot:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>EOT (pianificato)</extra>",
                                            marker=dict(
                                                color=color_map_progressive.get(
                                                    p.id, "gray"
                                                ),
                                                opacity=0.3,
                                            ),
                                            cliponaxis=True,
                                            textposition="inside",
                                            offsetgroup="back",
                                            offset=-0.2,
                                            visible=(
                                                weekNum
                                                == Settings.start_week_scheduling
                                            ),
                                        )
                                    )
                                    trace_idx_by_week[weekNum].append(len(fig.data) - 1)
                        else:
                            for p in real_day_room:
                                fig.add_trace(
                                    go.Bar(
                                        x=[xtext],
                                        y=[p.rot],
                                        name=f"Patient {p.id} ROT",
                                        text=[
                                            f"Patient {p.id} ROT: {int(p.rot)}m {int((p.rot % 1) * 60)}s"
                                        ],
                                        hovertemplate=f"Paziente {p.id}<br>ROT: {p.rot:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>ROT (reale)</extra>",
                                        marker=dict(
                                            color=color_map_progressive.get(
                                                p.id, "gray"
                                            ),
                                            opacity=0.3,
                                        ),
                                        cliponaxis=True,
                                        textposition="inside",
                                        offsetgroup="back",
                                        offset=-0.2,
                                        visible=(
                                            weekNum == Settings.start_week_scheduling
                                        ),
                                    )
                                )
                                trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                    # linea extra giornaliero (come prima, basata sui ROT reali)
                    dayNumInWeek = day % Settings.week_length_days
                    x0 = dayNumInWeek * Settings.workstations_config[op] - 0.5
                    x1 = (dayNumInWeek + 1) * Settings.workstations_config[op] - 0.5

                    shapes.append(
                        dict(
                            type="line",
                            x0=x0,
                            x1=x1,
                            y0=limite_massimo + extra_time_pool,
                            y1=limite_massimo + extra_time_pool,
                            line=dict(color="green", width=2, dash="dash"),
                        )
                    )

                    val = (limite_massimo * Settings.workstations_config[op]) - sum(
                        p.rot for p in patients_real if p.opDay == day
                    )
                    extra_time_pool = max(0, extra_time_pool + min(0, val))

                shapes_by_week[weekNum] = shapes

            # --- bottoni settimana: visibilità corretta anche se PLAN e REAL hanno num barre diverso ---
            buttons = []
            total_traces = len(fig.data)
            for weekNum in range(num_weeks):
                visible = [False] * total_traces
                for idx in trace_idx_by_week[weekNum]:
                    if 0 <= idx < total_traces:
                        visible[idx] = True
                buttons.append(
                    dict(
                        label=f"Settimana {weekNum}",
                        method="update",
                        args=[
                            {"visible": visible},
                            {
                                "title": title,
                                "shapes": shape_limite_massimo
                                + shapes_by_week[weekNum],
                            },
                        ],
                    )
                )

            fig.update_xaxes(showticklabels=True)
            fig.update_traces(showlegend=False, selector=dict(offsetgroup="back"))

            fig.add_annotation(
                x=xline - 1,
                y=limite_massimo,
                text=f"{limite_massimo} minuti (limite giornaliero)",
                showarrow=False,
                yshift=10,
                font=dict(color="red"),
            )
            fig.add_annotation(
                x=0.5,
                y=Settings.weekly_extra_time_pool + limite_massimo,
                text="minuti massimi di straordinario disponibili",
                showarrow=False,
                yshift=10,
                font=dict(color="green"),
            )
            metric_text = (
                "ROT = barra piena | EOT = barra trasparente"
                if use_rot_as_primary
                else "EOT = barra piena | ROT = barra trasparente"
            )
            fig.add_annotation(
                x=0.01,
                y=1.08,
                xref="paper",
                yref="paper",
                text=metric_text,
                showarrow=False,
                align="left",
            )

            fig.update_layout(
                updatemenus=[
                    dict(
                        active=0,
                        buttons=buttons,
                        x=0.95,
                        y=1.1,
                        xanchor="right",
                        yanchor="top",
                    )
                ],
                barmode="stack",  # come prima nel tuo layout finale
                title=title,
                showlegend=False,
                yaxis_title="Minuti Totali",
                xaxis_title="Giorni",
            )

            self.ShowFigure(fig, name=f"DailyBoxGraph_withTraslatedPatients_{op}")

    def PrintDailyBoxGraph(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        use_rot_as_primary: bool = False,
    ):
        limite_massimo = Settings.daily_operation_limit

        # Ciclo principale su ogni specialità
        for op, patients_real in operation.items():
            if not patients_real:
                continue
            xline = Settings.week_length_days * Settings.workstations_config[op]
            title = baseTitle + op

            fig = go.Figure()

            # Colori: ricavati direttamente dagli ID dei pazienti reali
            ids = sorted(list({p.id for p in patients_real}))
            num_patients = max(1, len(ids))
            color_map_progressive = {
                pid: f"hsl({int(i * 360 / num_patients)}, 70%, 50%)"
                for i, pid in enumerate(ids)
            }

            # Calcolo del range delle settimane basato solo sui giorni reali
            last_day = max((p.opDay for p in patients_real), default=0)
            num_weeks = (last_day // Settings.week_length_days) + 1

            # Linea del limite massimo giornaliero
            shape_limite_massimo = [
                dict(
                    type="line",
                    x0=-0.5,
                    x1=xline - 0.5,
                    y0=limite_massimo,
                    y1=limite_massimo,
                    line=dict(color="red", width=2, dash="dash"),
                )
            ]

            shapes_by_week = {}
            trace_idx_by_week = {w: [] for w in range(num_weeks)}

            # --- Costruzione dei TRACES per settimana ---
            for weekNum in range(num_weeks):
                shapes = []
                extra_time_pool = Settings.weekly_extra_time_pool

                for day in range(
                    weekNum * Settings.week_length_days,
                    (weekNum + 1) * Settings.week_length_days,
                ):
                    for room_id in range(Settings.workstations_config[op]):

                        # Filtro i pazienti reali per la sala e il giorno corrente
                        real_day_room = [
                            p
                            for p in patients_real
                            if p.workstation == room_id + 1 and p.opDay == day
                        ]

                        # Totale minuti reali (ROT) e totali minuti stimati (EOT) presi dallo stesso oggetto
                        minsRot = round(sum(p.rot for p in real_day_room), 2)
                        minsEot = round(sum(p.eot for p in real_day_room), 2)

                        # Etichetta dell'asse X con i totali di giornata per quella sala
                        xtext = f"W:{weekNum}|D:{day}|OR:{room_id+1}|<br>ToTMin:{minsEot}|<br>RoTMin:{minsRot}"

                        # --- FRONT: Metrica primaria (piena) ---
                        for p in real_day_room:
                            y_val = p.rot if use_rot_as_primary else p.eot
                            label = (
                                "ROT (reale)"
                                if use_rot_as_primary
                                else "EOT (pianificato)"
                            )
                            val_hover = p.rot if use_rot_as_primary else p.eot

                            fig.add_trace(
                                go.Bar(
                                    x=[xtext],
                                    y=[y_val],
                                    name=f"Patient {p.id}",
                                    text=[
                                        f"Patient {p.id}: {int(y_val)}m {int((y_val % 1) * 60)}s"
                                    ],
                                    hovertemplate=f"Paziente {p.id}<br>{label}: {val_hover:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>{label}</extra>",
                                    marker=dict(
                                        color=color_map_progressive.get(p.id, "gray")
                                    ),
                                    cliponaxis=True,
                                    textposition="inside",
                                    offsetgroup="front",
                                    visible=(weekNum == Settings.start_week_scheduling),
                                )
                            )
                            trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                            # --- BACK: Metrica secondaria (trasparente con offset) ---
                            y_val_sec = p.eot if use_rot_as_primary else p.rot
                            label_sec = (
                                "EOT (pianificato)"
                                if use_rot_as_primary
                                else "ROT (reale)"
                            )
                            val_hover_sec = p.eot if use_rot_as_primary else p.rot

                            fig.add_trace(
                                go.Bar(
                                    x=[xtext],
                                    y=[y_val_sec],
                                    name=f"Patient {p.id} {label_sec.split()[0]}",
                                    text=[
                                        f"Patient {p.id} {label_sec.split()[0]}: {int(y_val_sec)}m {int((y_val_sec % 1) * 60)}s"
                                    ],
                                    hovertemplate=f"Paziente {p.id}<br>{label_sec}: {val_hover_sec:.2f} min<br>D:{p.day}|MTB:{p.mtb}<extra>{label_sec}</extra>",
                                    marker=dict(
                                        color=color_map_progressive.get(p.id, "gray"),
                                        opacity=0.3,
                                    ),
                                    cliponaxis=True,
                                    textposition="inside",
                                    offsetgroup="back",
                                    offset=-0.2,
                                    visible=(weekNum == Settings.start_week_scheduling),
                                )
                            )
                            trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                    # Linea extra giornaliero (basata sui ROT reali)
                    dayNumInWeek = day % Settings.week_length_days
                    x0 = dayNumInWeek * Settings.workstations_config[op] - 0.5
                    x1 = (dayNumInWeek + 1) * Settings.workstations_config[op] - 0.5

                    shapes.append(
                        dict(
                            type="line",
                            x0=x0,
                            x1=x1,
                            y0=limite_massimo + extra_time_pool,
                            y1=limite_massimo + extra_time_pool,
                            line=dict(color="green", width=2, dash="dash"),
                        )
                    )

                    val = (limite_massimo * Settings.workstations_config[op]) - sum(
                        p.rot for p in patients_real if p.opDay == day
                    )
                    extra_time_pool = max(0, extra_time_pool + min(0, val))

                shapes_by_week[weekNum] = shapes

            # --- Generazione dei bottoni per il cambio settimana ---
            buttons = []
            total_traces = len(fig.data)
            for weekNum in range(num_weeks):
                visible = [False] * total_traces
                for idx in trace_idx_by_week[weekNum]:
                    if 0 <= idx < total_traces:
                        visible[idx] = True

                buttons.append(
                    dict(
                        label=f"Settimana {weekNum}",
                        method="update",
                        args=[
                            {"visible": visible},
                            {
                                "title": title,
                                "shapes": shape_limite_massimo
                                + shapes_by_week[weekNum],
                            },
                        ],
                    )
                )

            fig.update_xaxes(showticklabels=True)
            fig.update_traces(showlegend=False, selector=dict(offsetgroup="back"))

            fig.add_annotation(
                x=xline - 1,
                y=limite_massimo,
                text=f"{limite_massimo} minuti (limite giornaliero)",
                showarrow=False,
                yshift=10,
                font=dict(color="red"),
            )
            fig.add_annotation(
                x=0.5,
                y=Settings.weekly_extra_time_pool + limite_massimo,
                text="minuti massimi di straordinario disponibili",
                showarrow=False,
                yshift=10,
                font=dict(color="green"),
            )
            metric_text = (
                "ROT = barra piena | EOT = barra trasparente"
                if use_rot_as_primary
                else "EOT = barra piena | ROT = barra trasparente"
            )
            fig.add_annotation(
                x=0.01,
                y=1.08,
                xref="paper",
                yref="paper",
                text=metric_text,
                showarrow=False,
                align="left",
            )

            fig.update_layout(
                updatemenus=[
                    dict(
                        active=0,
                        buttons=buttons,
                        x=0.95,
                        y=1.1,
                        xanchor="right",
                        yanchor="top",
                    )
                ],
                barmode="stack",
                title=title,
                showlegend=False,
                yaxis_title="Minuti Totali",
                xaxis_title="Giorni",
            )

            self.ShowFigure(fig, name=f"DailyBoxGraph_{op}")

    def PrintTrendLineGraph_withEOTplanned(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea grafico di tendenza del carico operatorio con doppio asse Y senza duplicati di ID paziente."""
        for op, patients_real in operation.items():
            if not patients_real:
                continue

            title = baseTitle + op

            # --- 1. Pulizia globale del pianificato ---
            plan_list = plan_eot.get(op, []) if plan_eot is not None else None
            if plan_list is not None:
                latest_plan_by_id = {}
                for pp in plan_list:
                    if not isinstance(pp, dict):
                        continue
                    pid = pp.get("id", None)
                    if pid is None:
                        continue
                    latest_plan_by_id[pid] = pp
                plan_list = sorted(
                    latest_plan_by_id.values(),
                    key=lambda pp: (
                        pp.get("opDay", 0),
                        pp.get("workstation", 0),
                        pp.get("id", 0),
                    ),
                )

            last_day_real = max(p.opDay for p in patients_real) if patients_real else 0
            last_day_plan = (
                max((pp.get("opDay", 0) for pp in plan_list), default=0)
                if plan_list is not None
                else 0
            )
            last_day = max(last_day_real, last_day_plan)

            num_weeks = (last_day // Settings.week_length_days) + 1
            total_days = num_weeks * Settings.week_length_days
            days_title = [f"Day:{day}" for day in range(total_days)]

            start_index = 0
            if Settings.start_week_scheduling >= 1:
                start_day = (
                    f"Day:{Settings.start_week_scheduling * Settings.week_length_days}"
                )
                if start_day in days_title:
                    start_index = days_title.index(start_day)

            room_ids = range(Settings.workstations_config[op])
            room_free_time = {room_id + 1: [] for room_id in room_ids}
            room_patient = {room_id + 1: [] for room_id in room_ids}

            for d in range(total_days):
                for room_id in room_ids:

                    # --- Filtro Reali Univoci per Giorno/Sala ---
                    raw_real = [
                        p
                        for p in patients_real
                        if p.workstation == room_id + 1 and p.opDay == d
                    ]
                    daily_patients_real = []
                    seen_real = set()
                    for p in raw_real:
                        if p.id not in seen_real:
                            seen_real.add(p.id)
                            daily_patients_real.append(p)

                    # --- Filtro Pianificati Univoci per Giorno/Sala ---
                    if plan_list is not None:
                        raw_plan = [
                            pp
                            for pp in plan_list
                            if pp.get("workstation", None) == room_id + 1
                            and pp.get("opDay", None) == d
                        ]
                        daily_patients_plan = []
                        seen_plan = set()
                        for pp in raw_plan:
                            pid = pp.get("id")
                            if pid not in seen_plan:
                                seen_plan.add(pid)
                                daily_patients_plan.append(pp)
                    else:
                        daily_patients_plan = None

                    # Conteggio corretto senza duplicati
                    if use_rot_as_primary:
                        patient_count = len(daily_patients_real)
                    else:
                        patient_count = (
                            len(daily_patients_plan)
                            if daily_patients_plan is not None
                            else len(daily_patients_real)
                        )

                    # Calcolo metriche di tempo basate sulle liste deduplicate
                    if use_rot_as_primary:
                        time_metric = sum(p.rot for p in daily_patients_real)
                    else:
                        if daily_patients_plan is not None:
                            time_metric = sum(
                                float(pp.get("eot", 0) or 0)
                                for pp in daily_patients_plan
                            )
                        else:
                            time_metric = sum(p.eot for p in daily_patients_real)

                    free_time = Settings.daily_operation_limit - time_metric
                    room_free_time[room_id + 1].append(free_time)
                    room_patient[room_id + 1].append(patient_count)

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            for room_id, counts in room_patient.items():
                fig.add_trace(
                    go.Bar(
                        x=days_title,
                        y=counts,
                        name=f"OR:{room_id} Pazienti",
                        opacity=0.6,
                        hovertemplate="%{y}<extra>Pazienti</extra>",
                    ),
                    secondary_y=True,
                )

            for room_id, times in room_free_time.items():
                fig.add_trace(
                    go.Scatter(
                        x=days_title,
                        y=times,
                        name=f"OR:{room_id} Tempo libero",
                        mode="lines+markers",
                        hovertemplate="%{y:.2f}<extra>Minuti Liberi</extra>",
                    ),
                    secondary_y=False,
                )

            if Settings.start_week_scheduling >= 1:
                fig.add_vline(
                    x=start_index - 0.5,
                    line={"color": "orange", "width": 2, "dash": "dash"},
                    annotation_text="Inizio Schedulazione",
                    annotation_position="top right",
                    annotation_font_color="orange",
                )

            metric_label = (
                "Basato su ROT (Reale)"
                if use_rot_as_primary
                else "Basato su EOT (Pianificato)"
            )
            fig.update_layout(
                title=f"{title} - {metric_label}",
                xaxis_title="Giorno",
                template="plotly_white",
                barmode="group",
            )
            fig.update_yaxes(title_text="Tempo libero (minuti)", secondary_y=False)
            fig.update_yaxes(title_text="Numero pazienti", secondary_y=True)

            self.ShowFigure(fig, name=f"TrendLineGraph_withEOTplanned_{op}")

    def PrintTrendLineGraph(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea grafico di tendenza del carico operatorio con doppio asse Y.

        Mostra linee di tempo libero e barre di pazienti per sala.

        Args:
            operation: PatientListForSpecialties con i dati
            baseTitle: Titolo base del grafico
            use_rot_as_primary: Se True, usa ROT per calcolare tempo libero
        """
        for op, patients in operation.items():
            if not patients:
                continue

            title = baseTitle + op
            patients = sorted(patients, key=lambda p: (p.opDay, p.workstation))

            # Genera etichette giorni
            last_day = max(p.opDay for p in patients)
            num_weeks = (last_day // Settings.week_length_days) + 1
            days_title = [
                f"Day:{day}" for day in range(num_weeks * Settings.week_length_days)
            ]

            # Calcola indice giorno inizio schedulazione
            start_index = 0
            if Settings.start_week_scheduling >= 1:
                start_day = (
                    f"Day:{Settings.start_week_scheduling * Settings.week_length_days}"
                )
                if start_day in days_title:
                    start_index = days_title.index(start_day)

            # Aggrega tempo libero e numero pazienti per sala e giorno
            room_ids = range(Settings.workstations_config[op])
            room_free_time = {room_id + 1: [] for room_id in room_ids}
            room_patient = {room_id + 1: [] for room_id in room_ids}

            for d in range(last_day):
                for room_id in room_ids:
                    daily_patients = [
                        p
                        for p in patients
                        if p.workstation == room_id + 1 and p.opDay == d
                    ]
                    time_metric = (
                        sum(p.rot for p in daily_patients)
                        if use_rot_as_primary
                        else sum(p.eot for p in daily_patients)
                    )
                    free_time = Settings.daily_operation_limit - time_metric
                    room_free_time[room_id + 1].append(free_time)
                    room_patient[room_id + 1].append(len(daily_patients))

            # Crea grafico con doppio asse
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Barre: pazienti per sala
            for room_id, counts in room_patient.items():
                fig.add_trace(
                    go.Bar(
                        x=days_title,
                        y=counts,
                        name=f"OR:{room_id} Pazienti",
                        opacity=0.6,
                        hovertemplate="%{y}<extra>P</extra>",
                    ),
                    secondary_y=True,
                )

            # Linee: tempo libero per sala
            for room_id, times in room_free_time.items():
                fig.add_trace(
                    go.Scatter(
                        x=days_title,
                        y=times,
                        name=f"OR:{room_id} Tempo libero",
                        mode="lines+markers",
                        hovertemplate="%{y}<extra>MIN</extra>",
                    ),
                    secondary_y=False,
                )

            # Linea inizio schedulazione
            if Settings.start_week_scheduling >= 1:
                fig.add_vline(
                    x=start_index - 0.5,
                    line={"color": "orange", "width": 2, "dash": "dash"},
                    annotation_text="Inizio Schedulazione",
                    annotation_position="top right",
                    annotation_font_color="orange",
                )

            fig.update_layout(
                title=title,
                xaxis_title="Giorno",
                template="plotly_white",
                barmode="group",
            )
            fig.update_yaxes(title_text="Tempo libero (minuti)", secondary_y=False)
            fig.update_yaxes(title_text="Numero pazienti", secondary_y=True)

            self.ShowFigure(fig, name=f"TrendLineGraph_{op}")

    def PrintWaitingListLineGraph_withEOTplanned(
        self,
        operations: PatientListForSpecialties,
        baseTitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea grafico dell'evoluzione della lista d'attesa nel tempo.

        Mostra: pazienti aggiunti, pazienti operati, e pazienti ancora in attesa.

        Args:
            operations: PatientListForSpecialties con i dati reali
            baseTitle: Titolo base del grafico
            plan_eot: Dizionario contenente la programmazione pianificata EOT
            use_rot_as_primary: Se True usa i dati reali, altrimenti usa il pianificato (EOT)
        """
        for op, patients_real in operations.items():
            if not patients_real:
                continue

            title = baseTitle + op

            # --- 1. Estrazione e pulizia dati PIANIFICATI (EOT) ---
            plan_list = plan_eot.get(op, []) if plan_eot is not None else None
            if plan_list is not None:
                latest_plan_by_id = {}
                for pp in plan_list:
                    if not isinstance(pp, dict):
                        continue
                    pid = pp.get("id", None)
                    if pid is None:
                        continue
                    latest_plan_by_id[pid] = pp
                plan_list = sorted(
                    latest_plan_by_id.values(),
                    key=lambda pp: (
                        pp.get("opDay", 0),
                        pp.get("workstation", 0),
                        pp.get("id", 0),
                    ),
                )

            # --- 2. Raggruppamento e Deduplicazione con Set (ID unici per giorno) ---
            new_patient_list = defaultdict(set)
            resolved_list = defaultdict(set)

            # Selezione del dataset in base alla metrica primaria scelta
            if use_rot_as_primary or plan_list is None:
                for p in patients_real:
                    new_patient_list[p.day].add(p.id)
                    if p.opDay != -1 and p.opDay is not None:
                        resolved_list[p.opDay].add(p.id)
            else:
                for pp in plan_list:
                    pid = pp.get("id")
                    pday = pp.get("day")
                    pop_day = pp.get("opDay", -1)
                    if pid is not None:
                        if pday is not None:
                            new_patient_list[pday].add(pid)
                        if pop_day != -1 and pop_day is not None:
                            resolved_list[pop_day].add(pid)

            # Ordina i dizionari per giorno
            new_patient_list = dict(sorted(new_patient_list.items()))
            resolved_list = dict(sorted(resolved_list.items()))

            # Conta i pazienti UNICI per giorno
            new_patient_count = {day: len(ids) for day, ids in new_patient_list.items()}
            resolved_count = {day: len(ids) for day, ids in resolved_list.items()}

            # --- 3. Calcolo dei pazienti in attesa cumulativi ---
            waiting_count = {}
            total_waiting = 0
            max_day = max(
                max(new_patient_count.keys(), default=0),
                max(resolved_count.keys(), default=0),
            )

            # Scansione lineare per il calcolo cumulativo (incluso eventuale giorno 0)
            for day in range(max_day + 1):
                total_waiting += new_patient_count.get(day, 0)
                total_waiting -= resolved_count.get(day, 0)
                waiting_count[day] = total_waiting

            # --- 4. Costruzione del Grafico Plotly ---
            fig = go.Figure()

            # Traccia: Pazienti Aggiunti
            fig.add_trace(
                go.Scatter(
                    x=list(new_patient_count.keys()),
                    y=list(new_patient_count.values()),
                    mode="lines+markers",
                    name="Pazienti Aggiunti",
                    line={"color": "blue"},
                    hovertemplate="%{y}<extra>Aggiunti</extra>",
                )
            )

            # Traccia: Pazienti Operati
            fig.add_trace(
                go.Scatter(
                    x=list(resolved_count.keys()),
                    y=list(resolved_count.values()),
                    mode="lines+markers",
                    name="Pazienti Operati",
                    line={"color": "green"},
                    hovertemplate="%{y}<extra>Operati</extra>",
                )
            )

            # Traccia: Pazienti in Attesa (Cumulativo)
            fig.add_trace(
                go.Scatter(
                    x=list(waiting_count.keys()),
                    y=list(waiting_count.values()),
                    mode="lines+markers",
                    name="Pazienti in Attesa",
                    line={"color": "red"},
                    hovertemplate="%{y}<extra>In attesa</extra>",
                )
            )

            # Linea inizio schedulazione
            if Settings.start_week_scheduling >= 1:
                start_day = Settings.start_week_scheduling * Settings.week_length_days
                fig.add_vline(
                    x=start_day,
                    line={"color": "orange", "width": 2, "dash": "dash"},
                    annotation_text="Inizio Schedulazione",
                    annotation_position="top right",
                    annotation_font_color="orange",
                )

            metric_label = (
                "Dati REALI (ROT)" if use_rot_as_primary else "Dati PIANIFICATI (EOT)"
            )
            fig.update_layout(
                title=f"{title} - {metric_label}",
                xaxis_title="Giorno",
                yaxis_title="Numero Pazienti",
                template="plotly_white",
                hovermode="x unified",
            )

            self.ShowFigure(fig, name=f"WaitingListLineGraph_withEOTplanned_{op}")

    def PrintWaitingListLineGraph(
        self,
        operations: PatientListForSpecialties,
        baseTitle: str,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea grafico dell'evoluzione della lista d'attesa nel tempo.

        Mostra: pazienti aggiunti, pazienti operati, e pazienti ancora in attesa.

        Args:
            operations: PatientListForSpecialties con i dati
            baseTitle: Titolo base del grafico
            use_rot_as_primary: Non utilizzato (mantenuto per compatibilità)
        """
        for op, patients in operations.items():
            if not patients:
                continue

            title = baseTitle + op

            # Raggruppa pazienti per giorno di inserimento e operazione
            new_patient_list = defaultdict(list)
            resolved_list = defaultdict(list)

            for p in patients:
                new_patient_list[p.day].append(p.id)
                if p.opDay != -1:
                    resolved_list[p.opDay].append(p.id)

            # Ordina per giorno
            new_patient_list = dict(sorted(new_patient_list.items()))
            resolved_list = dict(sorted(resolved_list.items()))

            # Conta pazienti per giorno
            new_patient_count = {day: len(ids) for day, ids in new_patient_list.items()}
            resolved_count = {day: len(ids) for day, ids in resolved_list.items()}

            # Calcola pazienti in attesa cumulativi
            waiting_count = {}
            total_waiting = 0
            max_day = max(
                max(new_patient_count.keys(), default=0),
                max(resolved_count.keys(), default=0),
            )

            for day in range(1, max_day + 1):
                total_waiting += new_patient_count.get(day, 0)
                total_waiting -= resolved_count.get(day, 0)
                waiting_count[day] = total_waiting

            # Crea grafico
            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=list(new_patient_count.keys()),
                    y=list(new_patient_count.values()),
                    mode="lines+markers",
                    name="Pazienti Aggiunti",
                    line={"color": "blue"},
                    hovertemplate="%{y}<extra>Aggiunti</extra>",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=list(resolved_count.keys()),
                    y=list(resolved_count.values()),
                    mode="lines+markers",
                    name="Pazienti Operati",
                    line={"color": "green"},
                    hovertemplate="%{y}<extra>Operati</extra>",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=list(waiting_count.keys()),
                    y=list(waiting_count.values()),
                    mode="lines+markers",
                    name="Pazienti in Attesa",
                    line={"color": "red"},
                    hovertemplate="%{y}<extra>In attesa</extra>",
                )
            )

            # Linea inizio schedulazione
            if Settings.start_week_scheduling >= 1:
                start_day = Settings.start_week_scheduling * Settings.week_length_days
                fig.add_vline(
                    x=start_day,
                    line={"color": "orange", "width": 2, "dash": "dash"},
                    annotation_text="Inizio Schedulazione",
                    annotation_position="top right",
                    annotation_font_color="orange",
                )

            fig.update_layout(
                title=title,
                xaxis_title="Giorno",
                yaxis_title="Numero Pazienti",
                template="plotly_white",
                hovermode="x unified",
            )

            self.ShowFigure(fig, name=f"WaitingListLineGraph_{op}")

    def MostraTabellaConfrontoPlotly(self, scenari: dict) -> None:
        """Crea tabella di confronto tra scenari con metriche di performance.

        Args:
            scenari: Dizionario {nome_scenario: PatientListForSpecialties}
        """
        nomi_scenari = []
        specialta_nomi = []
        pazienti_n = []
        tempi_d_medi = []
        priorita_p = []
        week_length_days = Settings.week_length_days

        # Itera su scenari e specialità
        for nome_scenario, operation_data in scenari.items():
            for specialty, patients_real in operation_data.items():
                if not patients_real:
                    continue

                num_rooms = Settings.workstations_config.get(specialty, 1)
                tot_pazienti = 0
                tempo_totale_reale = 0.0
                somma_giorni_attesa = 0

                # Calcola settimane per specialità
                giorni_presenti = [
                    p.opDay for p in patients_real if hasattr(p, "opDay")
                ]
                last_day = max(giorni_presenti) if giorni_presenti else 0
                num_weeks = max(1, (last_day // week_length_days) + 1)

                # Aggrega metriche
                for p in patients_real:
                    tot_pazienti += 1
                    tempo_totale_reale += getattr(p, "rot", 0.0)
                    giorni_attesa = getattr(p, "opDay", 0) - getattr(p, "day", 0)
                    somma_giorni_attesa += max(0, giorni_attesa)

                # Calcola metriche medie
                tempo_medio_settimanale = tempo_totale_reale / num_weeks
                priorita_media = (
                    (somma_giorni_attesa / tot_pazienti) if tot_pazienti > 0 else 0.0
                )

                # Aggiungi riga alla tabella
                nomi_scenari.append(nome_scenario)
                specialta_nomi.append(specialty)
                pazienti_n.append(tot_pazienti)
                tempo_max_settimana = (
                    week_length_days * Settings.daily_operation_limit * num_rooms
                    + Settings.weekly_extra_time_pool * num_rooms
                )
                tempi_d_medi.append(
                    f"{tempo_medio_settimanale:.2f}/{tempo_max_settimana}"
                )
                priorita_p.append(f"{priorita_media:.2f}")

        # Crea tabella Plotly
        fig = go.Figure(
            data=[
                go.Table(
                    header={
                        "values": [
                            "<b>Scenario</b>",
                            "<b>Specialità</b>",
                            "<b>N.Pazienti</b>",
                            "<b>Utilizzo OP (min/week)</b>",
                            "<b>Attesa Media (giorni)</b>",
                        ],
                        "fill_color": "#1f77b4",
                        "align": "center",
                        "font": {"size": 12, "color": "white"},
                    },
                    cells={
                        "values": [
                            nomi_scenari,
                            specialta_nomi,
                            pazienti_n,
                            tempi_d_medi,
                            priorita_p,
                        ],
                        "fill_color": [["#f8f9fa", "#ffffff"] * len(nomi_scenari)],
                        "align": "center",
                        "font": {"size": 11, "color": "black"},
                        "height": 28,
                    },
                )
            ]
        )

        fig.update_layout(
            title="Confronto Performance Scenari",
            width=900,
            height=400,
            margin={"l": 20, "r": 20, "t": 60, "b": 20},
        )

        self.ShowFigure(fig, name="Tabella_Confronto_Scenari_Dettagliata")

    def MakeGraphs(
        self,
        data: PatientListForSpecialties,
        showGraphs: bool = False,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Genera tutti i grafici di analisi dalla schedulazione.

        Args:
            data: PatientListForSpecialties con i dati
            showGraphs: Se True, visualizza i grafici nel browser
            plan_eot: Pianificazione EOT opzionale
            use_rot_as_primary: Se True, usa ROT come metrica primaria
        """
        self.ShowFigures = showGraphs

        base_title = "Distribuzione pazienti - "
        self.PrintDailyBoxGraph(data, base_title, use_rot_as_primary=use_rot_as_primary)
        self.PrintDailyBoxGraph_withEOTplanned(
            data, base_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary
        )

        trend_title = "Carico operatorio - "
        self.PrintTrendLineGraph(
            data, trend_title, use_rot_as_primary=use_rot_as_primary
        )
        self.PrintTrendLineGraph_withEOTplanned(
            data, trend_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary
        )

        wait_title = "Lista attesa - "
        self.PrintWaitingListLineGraph(
            data, wait_title, use_rot_as_primary=use_rot_as_primary
        )
        self.PrintWaitingListLineGraph_withEOTplanned(
            data, wait_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary
        )

        self.PrintWaitingTimeBoxPlotGraph(
            data, "Tempi attesa - ", use_rot_as_primary=use_rot_as_primary
        )
        self.PrintWaitingTimeBoxPlotGraph_withEOTplanned(
            data,
            "Tempi attesa - ",
            plan_eot=plan_eot,
            use_rot_as_primary=use_rot_as_primary,
        )


if __name__ == "__main__":
    """Main: carica dati da JSON e genera grafici di analisi."""
    file_path = "Data\\Records\\seed-1\\weekly_schedule.json"
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        data = json.load(f)

    ops = PatientListForSpecialties.from_dict(data)
    graph_manager = Graphs()
    graph_manager.MakeGraphs(ops)
