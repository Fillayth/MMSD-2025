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
import copy
import json
import logging
import os
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

if os.path.basename(__file__) != "main.py":
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "Code"))
    )

from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Patient import Patient
from settings import Settings

START_WEEK_SCHEDULING = Settings.start_week_scheduling
WEEK_LENGTH_DAYS = Settings.week_length_days
DAILY_OPERATION_LIMIT = Settings.daily_operation_limit 
WEEKLY_EXTRA_TIME_POOL = Settings.weekly_extra_time_pool

logger = logging.getLogger(__name__)

def CreateScheduleWithReplanned(schedule: dict, plan_eot_input: dict | None) -> dict:
    """Crea una nuova istanza dello schedule integrando i dati di pianificazione EOT.

    Risolve anche il problema dei pazienti (come l'ID 1398) presenti SOLO nel piano
    di ripianificazione (plan_eot) e originariamente assenti dallo schedule di base.
    """
    cloned_schedule = copy.deepcopy(schedule)

    if not plan_eot_input:
        return cloned_schedule

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
    log_graph_data: bool = False
    graph_data_log_path: str | None = None

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
        self.graph_data_log_path = os.path.join(self.folderPath, "graph_data_log.jsonl")

    #region: Funzioni interne
    @staticmethod
    def _get_patient_value(patient: Patient | dict, key: str, default: float | int | str | None = None) -> float | int | str | None:
        """Restituisce un valore da un paziente sia esso dict o oggetto."""
        if isinstance(patient, dict):
            return patient.get(key, default)
        return getattr(patient, key, default)

    @staticmethod
    def _normalize_plan_entries(plan_list: list[dict] | None) -> list[dict] | None:
        """Normalizza i record pianificati rimuovendo duplicati per id."""
        if plan_list is None:
            return None
        if not plan_list:
            return []

        latest_plan_by_id: dict[str, dict] = {}
        for pp in plan_list:
            if not isinstance(pp, dict):
                continue
            pid = pp.get("id", None)
            if pid is None:
                continue
            latest_plan_by_id[str(pid)] = pp

        return sorted(
            latest_plan_by_id.values(),
            key=lambda pp: (
                pp.get("opDay", 0),
                pp.get("workstation", 0),
                pp.get("id", 0),
            ),
        )

    @staticmethod
    def _build_week_ranges(max_day: int, week_length_days: int) -> list[tuple[int, int, int]]:
        """Costruisce gli intervalli settimana in formato (week_num, start_day, end_day)."""
        if max_day <= 0:
            return [(0, 0, week_length_days - 1)]

        last_week = max_day // week_length_days
        return [(
            week_num, 
            week_num * week_length_days, 
            ((week_num + 1) * week_length_days) - 1
            ) for week_num in range(last_week + 1)
        ]

    def _log_dataset_snapshot(
        self,
        context: str,
        patients: list[Patient | dict] | None = None,
        plan_entries: list[dict] | None = None,
        extra: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        """Registra un snapshot dei dati usati per generare un grafico."""
        if not self.log_graph_data:
            return

        payload: dict[str, Any] = {
            "context": context,
            "patients_count": len(patients or []),
            "plan_entries_count": len(plan_entries or []),
        }

        if patients is not None:
            payload["patients"] = [
                {
                    "id": self._get_patient_value(p, "id"),
                    "day": self._get_patient_value(p, "day"),
                    "opDay": self._get_patient_value(p, "opDay", -1),
                    "workstation": self._get_patient_value(p, "workstation", -1),
                    "eot": self._get_patient_value(p, "eot"),
                    "rot": self._get_patient_value(p, "rot"),
                    "mtb": self._get_patient_value(p, "mtb"),
                }
                for p in patients
            ]

        if plan_entries is not None:
            payload["plan_entries"] = [
                {
                    "id": entry.get("id"),
                    "day": entry.get("day"),
                    "opDay": entry.get("opDay", -1),
                    "workstation": entry.get("workstation", -1),
                    "eot": entry.get("eot"),
                    "rot": entry.get("rot"),
                    "mtb": entry.get("mtb"),
                }
                for entry in plan_entries
            ]

        if extra:
            payload["extra"] = extra

        log_line = json.dumps(payload, ensure_ascii=False, default=str)
        logger.info("Graph data snapshot: %s", log_line)

        if self.graph_data_log_path:
            with open(self.graph_data_log_path, "a", encoding="utf-8") as handle:
                handle.write(log_line + "\n")

    def _show_figure(self, fig: go.Figure, name: str = "grafico") -> None:
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
        return DAILY_OPERATION_LIMIT - time_used

    #endregion: Funzioni interne
    #region: Funzioni dei grafici 
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
                max((p.opDay for p in patients), default=0) // WEEK_LENGTH_DAYS
            )

            for weekNum in range(last_week + 1):
                # Calcola tempo libero per ogni giorno della settimana
                unused_times = [
                    self._get_free_time_per_day(patients, day)
                    for day in range(
                        weekNum * WEEK_LENGTH_DAYS,
                        (weekNum + 1) * WEEK_LENGTH_DAYS,
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
            self._show_figure(fig, name="BoxPlotUnusedTime")

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
        
        # 1. Sovrascrive/integra operations dando priorità a plan_eot
        operations_updated = CreateScheduleWithReplanned(operations, plan_eot)
        for op, patients_real in operations_updated.items():
            if not patients_real:
                continue
            title = basetitle + op
            self._log_dataset_snapshot(
                context=f"waiting_time_boxplot_with_plan:{op}",
                patients=patients_real,
                plan_entries=plan_eot.get(op, []) if plan_eot is not None else None,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )
            # 2. Selezione ed estrazione uniforme
            rows = []
            seen_ids = set()
            for p in patients_real:
                p_id = p.get("id") if isinstance(p, dict) else getattr(p, "id", None)
                p_day = p.get("day", 0) if isinstance(p, dict) else getattr(p, "day", 0)
                p_mtb = p.get("mtb", None) if isinstance(p, dict) else getattr(p, "mtb", None)
                p_opDay = p.get("opDay", -1) if isinstance(p, dict) else getattr(p, "opDay", -1)
                if p_id is not None and p_id not in seen_ids:
                    seen_ids.add(p_id)
                    rows.append(
                        {
                            "ID": p_id,
                            "Data inserimento": p_day,
                            "MTB": p_mtb,
                            "Data operazione": p_opDay,
                        }
                    )
            df = pd.DataFrame(rows)
            df = df[df["Data operazione"] != -1].dropna(subset=["Data operazione"])
            if df.empty:
                continue
            df["Tempo_attesa"] = df["Data operazione"] - df["Data inserimento"]
            max_day = df["Data operazione"].max()
            data = []
            for week_num, week_start, week_end in self._build_week_ranges(
                max_day, WEEK_LENGTH_DAYS
            ):
                waiting_times = df[df["Data operazione"].between(week_start, week_end)][
                    "Tempo_attesa"
                ]
                data.append(
                    go.Box(
                        y=waiting_times,
                        name=f"Sett {week_num}",
                        boxmean="sd",
                        marker_color="indianred",
                    )
                )
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
            self._show_figure(fig, name=f"WaitingTimeBoxPlot_withEOTplanned_{op}")

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
            self._log_dataset_snapshot(
                context=f"waiting_time_boxplot:{op}",
                patients=patients,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )
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
            max_day = max((p.opDay for p in patients), default=0)

            for week_num, week_start, week_end in self._build_week_ranges(
                max_day, WEEK_LENGTH_DAYS
            ):
                waiting_times = df[df["Data operazione"].between(week_start, week_end)][
                    "Tempo_attesa"
                ]

                data.append(
                    go.Box(
                        y=waiting_times,
                        name=f"Sett {week_num}",
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
            self._show_figure(fig, name=f"WaitingTimeBoxPlot_{op}")

    def PrintDailyBoxGraph_withEOTplanned(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ):
        
        limite_massimo = DAILY_OPERATION_LIMIT

        # Aggiorna la struttura operation usando la priorità di plan_eot
        operation_updated = CreateScheduleWithReplanned(operation, plan_eot)

        for op, patients_real in operation_updated.items():
            if not patients_real:
                continue
            xline = WEEK_LENGTH_DAYS * Settings.workstations_config[op]
            title = baseTitle + op
            self._log_dataset_snapshot(
                context=f"daily_boxplot_with_plan:{op}",
                patients=patients_real,
                plan_entries=plan_eot.get(op, []) if plan_eot is not None else None,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )

            # --- Pianificato EOT (lista di dict)  ---
            plan_list = self._normalize_plan_entries(
                plan_eot.get(op, []) if plan_eot is not None else None
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
            num_weeks = (last_day // WEEK_LENGTH_DAYS) + 1

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
                extra_time_pool = WEEKLY_EXTRA_TIME_POOL
                week_start_day = weekNum * WEEK_LENGTH_DAYS

                for day in range(
                    week_start_day,
                    week_start_day + WEEK_LENGTH_DAYS,
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
                        week_label = START_WEEK_SCHEDULING + weekNum
                        xtext = f"W:{week_label}|D:{day}|OR:{room_id+1}|<br>ToTMin:{mins}|<br>RoTMin:{minsRot}"

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
                                            weekNum == 0
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
                                            weekNum == 0
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
                                            weekNum == 0
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
                                                == 0
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
                                                == 0
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
                                            weekNum == 0
                                        ),
                                    )
                                )
                                trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                    # linea extra giornaliero (come prima, basata sui ROT reali)
                    dayNumInWeek = day - week_start_day
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
                y=WEEKLY_EXTRA_TIME_POOL + limite_massimo,
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

            self._show_figure(fig, name=f"DailyBoxGraph_withTraslatedPatients_{op}")

    def PrintDailyBoxGraph(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        use_rot_as_primary: bool = False,
    ):
        
        limite_massimo = DAILY_OPERATION_LIMIT

        # Ciclo principale su ogni specialità
        for op, patients_real in operation.items():
            if not patients_real:
                continue
            xline = WEEK_LENGTH_DAYS * Settings.workstations_config[op]
            title = baseTitle + op
            self._log_dataset_snapshot(
                context=f"daily_boxplot:{op}",
                patients=patients_real,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )

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
            num_weeks = (last_day // WEEK_LENGTH_DAYS) + 1

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
                extra_time_pool = WEEKLY_EXTRA_TIME_POOL
                week_start_day = weekNum * WEEK_LENGTH_DAYS

                for day in range(
                    week_start_day,
                    week_start_day + WEEK_LENGTH_DAYS,
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
                        week_label = START_WEEK_SCHEDULING + weekNum
                        xtext = f"W:{week_label}|D:{day}|OR:{room_id+1}|<br>ToTMin:{minsEot}|<br>RoTMin:{minsRot}"

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
                                    visible=(weekNum == 0),
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
                                    visible=(weekNum == 0),
                                )
                            )
                            trace_idx_by_week[weekNum].append(len(fig.data) - 1)

                    # Linea extra giornaliero (basata sui ROT reali)
                    dayNumInWeek = day - week_start_day
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
                y=WEEKLY_EXTRA_TIME_POOL + limite_massimo,
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

            self._show_figure(fig, name=f"DailyBoxGraph_{op}")

    def PrintTrendLineGraph_withEOTplanned(
        self,
        operation: PatientListForSpecialties,
        baseTitle: str,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
    ) -> None:
        """Crea grafico di tendenza del carico operatorio con doppio asse Y senza duplicati di ID paziente."""
        use_rot_as_primary = True
        operation_updated = CreateScheduleWithReplanned(operation, plan_eot)

        for op, patients_real in operation_updated.items():
            if not patients_real:
                continue
            title = baseTitle + op
            self._log_dataset_snapshot(
                context=f"trend_line_with_plan:{op}",
                patients=patients_real,
                plan_entries=plan_eot.get(op, []) if plan_eot is not None else None,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )

            # --- 1. Pulizia globale del pianificato ---
            plan_list = self._normalize_plan_entries(
                plan_eot.get(op, []) if plan_eot is not None else None
            )

            last_day_real = max(p.opDay for p in patients_real) if patients_real else 0
            last_day_plan = (
                max((pp.get("opDay", 0) for pp in plan_list), default=0)
                if plan_list is not None
                else 0
            )
            last_day = max(last_day_real, last_day_plan)

            num_weeks = (last_day // WEEK_LENGTH_DAYS) + 1
            total_days = num_weeks * WEEK_LENGTH_DAYS
            start_day = 0
            days_title = [
                f"Day:{day_offset}" for day_offset in range(total_days)
                ]

            start_index = 0

            room_ids = range(Settings.workstations_config[op])
            room_free_time = {room_id + 1: [] for room_id in room_ids}
            room_patient = {room_id + 1: [] for room_id in room_ids}

            for day_offset in range(total_days):
                day = start_day + day_offset
                for room_id in room_ids:

                    # --- Filtro Reali Univoci per Giorno/Sala ---
                    raw_real = [
                        p
                        for p in patients_real
                        if p.workstation == room_id + 1 and p.opDay == day
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
                            and pp.get("opDay", None) == day
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

                    free_time = DAILY_OPERATION_LIMIT - time_metric
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

            if START_WEEK_SCHEDULING >= 1:
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

            self._show_figure(fig, name=f"TrendLineGraph_withEOTplanned_{op}")

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
        use_rot_as_primary = True


        for op, patients in operation.items():
            if not patients:
                continue

            title = baseTitle + op
            self._log_dataset_snapshot(
                context=f"trend_line:{op}",
                patients=patients,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )
            patients = sorted(patients, key=lambda p: (p.opDay, p.workstation))

            # Genera etichette giorni
            last_day = max(p.opDay for p in patients)
            num_weeks = (last_day // WEEK_LENGTH_DAYS) + 1
            total_days = num_weeks * WEEK_LENGTH_DAYS
            start_day = 0
            days_title = [
                f"Day:{day_offset}" for day_offset in range(total_days)
            ]

            # Calcola indice giorno inizio schedulazione
            start_index = 0

            # Aggrega tempo libero e numero pazienti per sala e giorno
            room_ids = range(Settings.workstations_config[op])
            room_free_time = {room_id + 1: [] for room_id in room_ids}
            room_patient = {room_id + 1: [] for room_id in room_ids}

            for day_offset in range(total_days):
                day = start_day + day_offset
                for room_id in room_ids:
                    daily_patients = [
                        p
                        for p in patients
                        if p.workstation == room_id + 1 and p.opDay == day
                    ]
                    time_metric = (
                        sum(p.rot for p in daily_patients)
                        if use_rot_as_primary
                        else sum(p.eot for p in daily_patients)
                    )
                    free_time = DAILY_OPERATION_LIMIT - time_metric
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
            if START_WEEK_SCHEDULING >= 1:
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

            self._show_figure(fig, name=f"TrendLineGraph_{op}")

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
        
        operations_updated = CreateScheduleWithReplanned(operations, plan_eot)

        for op, patients_real in operations_updated.items():
            if not patients_real:
                continue
            title = baseTitle + op
            self._log_dataset_snapshot(
                context=f"waiting_list_line_with_plan:{op}",
                patients=patients_real,
                plan_entries=plan_eot.get(op, []) if plan_eot is not None else None,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )

            # --- 1. Estrazione e pulizia dati PIANIFICATI (EOT) ---
            plan_list = self._normalize_plan_entries(
                plan_eot.get(op, []) if plan_eot is not None else None
            )

            # --- 2. Raggruppamento e Deduplicazione con Set (ID unici per giorno) ---
            new_patient_list = defaultdict(set)
            resolved_list = defaultdict(set)

            # Selezione del dataset in base alla metrica primaria scelta
            if use_rot_as_primary or plan_list is None:
                for p in patients_real:
                    p_id = self._get_patient_value(p, "id")
                    p_day = self._get_patient_value(p, "day")
                    p_op_day = self._get_patient_value(p, "opDay", -1)
                    if p_id is not None:
                        if p_day is not None:
                            new_patient_list[p_day].add(p_id)
                        if p_op_day != -1 and p_op_day is not None:
                            resolved_list[p_op_day].add(p_id)
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

            days_range = list(range(max_day + 1))
            y_added = [new_patient_count.get(d, 0) for d in days_range]
            y_resolved = [resolved_count.get(d, 0) for d in days_range]
            y_waiting = [waiting_count.get(d, 0) for d in days_range]

            # Traccia: Pazienti Aggiunti
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_added,
                    mode="lines+markers",
                    name="Pazienti Aggiunti",
                    line={"color": "blue"},
                    hovertemplate="%{y}<extra>Aggiunti</extra>",
                )
            )

            # Traccia: Pazienti Operati
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_resolved,
                    mode="lines+markers",
                    name="Pazienti Operati",
                    line={"color": "green"},
                    hovertemplate="%{y}<extra>Operati</extra>",
                )
            )

            # Traccia: Pazienti in Attesa (Cumulativo)
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_waiting,
                    mode="lines+markers",
                    name="Pazienti in Attesa",
                    line={"color": "red"},
                    hovertemplate="%{y}<extra>In attesa</extra>",
                )
            )

            # Linea inizio schedulazione
            if START_WEEK_SCHEDULING >= 1:
                start_day = START_WEEK_SCHEDULING * WEEK_LENGTH_DAYS
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

            self._show_figure(fig, name=f"WaitingListLineGraph_withEOTplanned_{op}")

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
            self._log_dataset_snapshot(
                context=f"waiting_list_line:{op}",
                patients=patients,
                extra={"use_rot_as_primary": use_rot_as_primary},
            )

            # Raggruppa pazienti per giorno di inserimento e operazione
            new_patient_list = defaultdict(set)
            resolved_list = defaultdict(set)

            for p in patients:
                p_id = self._get_patient_value(p, "id")
                p_day = self._get_patient_value(p, "day")
                p_op_day = self._get_patient_value(p, "opDay", -1)
                if p_id is not None:
                    if p_day is not None:
                        new_patient_list[p_day].add(p_id)
                    if p_op_day != -1 and p_op_day is not None:
                        resolved_list[p_op_day].add(p_id)

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

            for day in range(0, max_day + 1):
                total_waiting += new_patient_count.get(day, 0)
                total_waiting -= resolved_count.get(day, 0)
                waiting_count[day] = total_waiting

            # Crea grafico
            fig = go.Figure()
            days_range = list(range(max_day + 1))
            y_added = [new_patient_count.get(d, 0) for d in days_range]
            y_resolved = [resolved_count.get(d, 0) for d in days_range]
            y_waiting = [waiting_count.get(d, 0) for d in days_range]

            # Traccia: Pazienti Aggiunti
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_added,
                    mode="lines+markers",
                    name="Pazienti Aggiunti",
                    line={"color": "blue"},
                    hovertemplate="%{y}<extra>Aggiunti</extra>",
                )
            )

            # Traccia: Pazienti Operati
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_resolved,
                    mode="lines+markers",
                    name="Pazienti Operati",
                    line={"color": "green"},
                    hovertemplate="%{y}<extra>Operati</extra>",
                )
            )

            # Traccia: Pazienti in Attesa (Cumulativo)
            fig.add_trace(
                go.Scatter(
                    x=days_range,
                    y=y_waiting,
                    mode="lines+markers",
                    name="Pazienti in Attesa",
                    line={"color": "red"},
                    hovertemplate="%{y}<extra>In attesa</extra>",
                )
            )

            # Linea inizio schedulazione
            if START_WEEK_SCHEDULING >= 1:
                start_day = START_WEEK_SCHEDULING * WEEK_LENGTH_DAYS
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

            self._show_figure(fig, name=f"WaitingListLineGraph_{op}")

    def MostraTabellaConfrontoPlotly(self, scenari: dict) -> None:
        """
        Genera una visualizzazione in stile tabella interattiva basata su go.Heatmap.
        Supporta il raggruppamento dinamico (espandi/comprimi) delle settimane tramite pulsanti
        e calcola i riepiloghi mensili.
        """
        

        def wrap_text_by_words(text: str, max_chars: int = 14) -> str:
            """Avvolge il testo in più righe senza spezzare le parole."""
            words = str(text).split(" ")
            lines = []
            current_line = []
            current_length = 0

            for word in words:
                if current_length + len(word) > max_chars and current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1
            
            if current_line:
                lines.append(" ".join(current_line))
                
            return "<br>".join(lines)

        # 1. Determina il numero massimo di settimane
        max_day = 0
        for scenario_name, operation_data in scenari.items():
            for spec, pazienti in operation_data.items():
                for p in pazienti:
                    if p.opDay > max_day:
                        max_day = p.opDay
                        
        num_weeks = 1 if max_day == 0 else int((max_day - 1) // WEEK_LENGTH_DAYS + 1)
        num_months = (num_weeks - 1) // 4 + 1

        # 2. Costruzione della struttura delle colonne
        colonne_base = ["Scenario", "Specialità", "N. Pazienti", "Attesa Media"]
        
        colonne_dettagliate = [col.replace(" ", "<br>") for col in colonne_base]
        colonne_sintetiche = [col.replace(" ", "<br>") for col in colonne_base]
        
        # Mappa quali colonne sono visibili nella vista raggruppata/sintetica
        indices_sintetici = list(range(len(colonne_base)))  # Colonne base sempre visibili
        current_col_idx = len(colonne_base)

        for w in range(1, num_weeks + 1):
            colonne_dettagliate.append(f"Utilizzo<br>OR W{w}")
            colonne_dettagliate.append(f"Straordinari<br>W{w}")
            current_col_idx += 2

            # Ogni 4 settimane (o alla fine della simulazione), inserisci il Riepilogo Mensile
            if w % 4 == 0 or w == num_weeks:
                m = (w - 1) // 4 + 1
                colonne_dettagliate.append(f"Media OR<br>M{m}")
                colonne_dettagliate.append(f"Media ST<br>M{m}")
                
                colonne_sintetiche.append(f"Media OR<br>M{m}")
                colonne_sintetiche.append(f"Media ST<br>M{m}")
                
                # Gli indici dei riepiloghi mensili restano visibili anche nella vista sintetica
                indices_sintetici.append(current_col_idx)
                indices_sintetici.append(current_col_idx + 1)
                current_col_idx += 2

        rows_data_full = []
        hover_data_full = []
        std_limit_daily = DAILY_OPERATION_LIMIT

        # 3. Elaborazione Dati
        for scenario_name, operation_data in scenari.items():
            for spec_name, pazienti in operation_data.items():
                if not pazienti or len(pazienti) == 0:
                    continue

                self._log_dataset_snapshot(
                    context=f"comparison_table:{scenario_name}:{spec_name}",
                    patients=pazienti,
                    extra={"scenario": scenario_name},
                )

                num_rooms = Settings.workstations_config.get(spec_name, 1)
                std_avail_weekly = std_limit_daily * WEEK_LENGTH_DAYS * num_rooms
                extra_avail_weekly = WEEKLY_EXTRA_TIME_POOL * num_rooms

                daily_tot_time = {}
                pazienti_operati = 0
                somma_attesa = 0

                for p in pazienti:
                    pazienti_operati += 1
                    somma_attesa += (p.opDay - p.day)
                    daily_tot_time[p.opDay] = daily_tot_time.get(p.opDay, 0) + p.rot

                attesa_media = round(somma_attesa / pazienti_operati, 1) if pazienti_operati > 0 else 0

                formatted_scenario = wrap_text_by_words(scenario_name, max_chars=14)
                formatted_spec = wrap_text_by_words(spec_name, max_chars=14)

                row_cells = [
                    formatted_scenario,
                    formatted_spec,
                    str(pazienti_operati),
                    f"{attesa_media} gg"
                ]
                row_hover = [
                    f"Scenario: <b>{scenario_name}</b>",
                    f"Specialità: <b>{spec_name}</b>",
                    f"Pazienti Totali Operati: <b>{pazienti_operati}</b>",
                    f"Tempo di Attesa Medio: <b>{attesa_media} giorni</b>"
                ]

                # Dati settimanali e calcolo medie mensili
                month_or_pcts = []
                month_st_pcts = []

                for w in range(1, num_weeks + 1):
                    giorni_settimana = range((w - 1) * WEEK_LENGTH_DAYS + 1, w * WEEK_LENGTH_DAYS + 1)
                    used_std_weekly = 0
                    used_extra_weekly = 0
                    std_limit_daily_total = std_limit_daily * num_rooms

                    for d in giorni_settimana:
                        tot_day_time = daily_tot_time.get(d, 0)
                        if tot_day_time > std_limit_daily_total:
                            used_std_weekly += std_limit_daily_total
                            used_extra_weekly += (tot_day_time - std_limit_daily_total)
                        else:
                            used_std_weekly += tot_day_time

                    pct_or = round((used_std_weekly / std_avail_weekly) * 100, 1) if std_avail_weekly > 0 else 0
                    pct_st = round((used_extra_weekly / extra_avail_weekly) * 100, 1) if extra_avail_weekly > 0 else 0

                    month_or_pcts.append(pct_or)
                    month_st_pcts.append(pct_st)

                    # Aggiunta dati della singola settimana
                    row_cells.append(f"{pct_or}%")
                    row_cells.append(f"{pct_st}%")

                    row_hover.append(
                        f"<b>Utilizzo OR Settimana {w}</b><br>"
                        f"Utilizzati: {used_std_weekly:.1f} min<br>"
                        f"Disponibili: {std_avail_weekly} min<br>"
                        f"Percentuale: {pct_or}%"
                    )
                    row_hover.append(
                        f"<b>Straordinari Settimana {w}</b><br>"
                        f"Utilizzati: {used_extra_weekly:.1f} min<br>"
                        f"Disponibili: {extra_avail_weekly} min<br>"
                        f"Percentuale: {pct_st}%"
                    )

                    # Calcolo e aggiunta del Riepilogo Mensile
                    if w % 4 == 0 or w == num_weeks:
                        m = (w - 1) // 4 + 1
                        avg_or = round(sum(month_or_pcts) / len(month_or_pcts), 1)
                        avg_st = round(sum(month_st_pcts) / len(month_st_pcts), 1)

                        row_cells.append(f"<b>{avg_or}%</b>")
                        row_cells.append(f"<b>{avg_st}%</b>")

                        row_hover.append(f"<b>Media OR Mese {m}</b><br>Media: {avg_or}% su {len(month_or_pcts)} sett.")
                        row_hover.append(f"<b>Media Straordinari Mese {m}</b><br>Media: {avg_st}% su {len(month_st_pcts)} sett.")

                        # Resetta i dati per il mese successivo
                        month_or_pcts = []
                        month_st_pcts = []

                rows_data_full.append(row_cells)
                hover_data_full.append(row_hover)

        if not rows_data_full:
            return

        # 4. Preparazione Dati Filtrati per la Vista Sintetica
        rows_data_synth = [[row[idx] for idx in indices_sintetici] for row in rows_data_full]
        hover_data_synth = [[row[idx] for idx in indices_sintetici] for row in hover_data_full]

        # Matrici Z trasparenti di sfondo
        z_full = [[0] * len(colonne_dettagliate) for _ in range(len(rows_data_full))]
        z_synth = [[0] * len(colonne_sintetiche) for _ in range(len(rows_data_synth))]
        y_indices = [f"R{i}" for i in range(len(rows_data_full))]

        fig = go.Figure()

        # Trace 0: Vista Sintetica (Raggruppata) - Visibile di Default
        colorscale = [[0, "#4c9ded"], [1, "#f8f9fa"]]
        fig.add_trace(
            go.Heatmap(
                z=z_synth,
                x=colonne_sintetiche,
                y=y_indices,
                text=rows_data_synth,
                texttemplate="%{text}",
                textfont=dict(size=12, color="#111827", family="Arial"),
                hovertext=hover_data_synth,
                hovertemplate="%{hovertext}<extra></extra>",
                colorscale=colorscale,
                showscale=False,
                xgap=2,
                ygap=2,
                visible=True,
                name="Sintetica"
            )
        )

        # Trace 1: Vista Dettagliata (Espansa) - Nascosta di Default
        fig.add_trace(
            go.Heatmap(
                z=z_full,
                x=colonne_dettagliate,
                y=y_indices,
                text=rows_data_full,
                texttemplate="%{text}",
                textfont=dict(size=11, color="#111827", family="Arial"),
                hovertext=hover_data_full,
                hovertemplate="%{hovertext}<extra></extra>",
                colorscale=colorscale,
                showscale=False,
                xgap=2,
                ygap=2,
                visible=False,
                name="Dettagliata"
            )
        )

        # Larghezze dinamiche per le due viste
        min_col_width = 110
        width_synth = max(800, len(colonne_sintetiche) * min_col_width)
        width_full = max(800, len(colonne_dettagliate) * min_col_width)

        # 5. Aggiunta Menu (Updatemenus)
        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    active=0,
                    x=0.0,
                    y=1.18,
                    xanchor="left",
                    yanchor="top",
                    buttons=[
                        dict(
                            label="Mostra solo Mesi",
                            method="update",
                            args=[
                                {"visible": [True, False]},
                                {"width": width_synth}
                            ]
                        ),
                        dict(
                            label="Mostra dettaglio Settimane",
                            method="update",
                            args=[
                                {"visible": [False, True]},
                                {"width": width_full}
                            ]
                        )
                    ]
                )
            ],
            title=dict(
                text="Tabella di Confronto Scenari",
                y=0.98
            ),
            xaxis=dict(
                side="top",
                tickangle=0,
                tickfont=dict(size=11, color="#1f2937", family="Arial"),
                showgrid=False
            ),
            yaxis=dict(
                autorange="reversed",
                showticklabels=False,
                showgrid=False
            ),
            plot_bgcolor="#cbd5e1",
            paper_bgcolor="white",
            width=width_synth,
            height=max(480, len(rows_data_full) * 65 + 160),
            margin=dict(l=20, r=20, t=160, b=30)
        )

        self._show_figure(fig, name="Tabella_Confronto_Scenari_Dettagliata")
    #endregion

    def MakeGraphs(
        self,
        data: PatientListForSpecialties,
        showGraphs: bool = False,
        plan_eot: dict | None = None,
        use_rot_as_primary: bool = False,
        log_graph_data: bool | None = None,
    ) -> None:
        """Genera tutti i grafici di analisi dalla schedulazione.

        Args:
            data: PatientListForSpecialties con i dati
            showGraphs: Se True, visualizza i grafici nel browser
            plan_eot: Pianificazione EOT opzionale
            use_rot_as_primary: Se True, usa ROT come metrica primaria
        """

        self.ShowFigures = showGraphs
        if log_graph_data is not None:
            self.log_graph_data = log_graph_data

        base_title = "Distribuzione pazienti - "
        trend_title = "Carico operatorio - "
        wait_title = "Lista attesa - "
        if use_rot_as_primary:
            self.PrintDailyBoxGraph(data, base_title, use_rot_as_primary=use_rot_as_primary)
            self.PrintTrendLineGraph(data, trend_title, use_rot_as_primary=use_rot_as_primary)
            self.PrintWaitingListLineGraph(data, wait_title, use_rot_as_primary=use_rot_as_primary)
            self.PrintWaitingTimeBoxPlotGraph(data, "Tempi attesa - ", use_rot_as_primary=use_rot_as_primary)
        else:
            self.PrintDailyBoxGraph_withEOTplanned(data, base_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary)
            self.PrintTrendLineGraph_withEOTplanned(data, trend_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary)
            self.PrintWaitingListLineGraph_withEOTplanned(data, wait_title, plan_eot=plan_eot, use_rot_as_primary=use_rot_as_primary)
            self.PrintWaitingTimeBoxPlotGraph_withEOTplanned(data,"Tempi attesa - ",plan_eot=plan_eot,use_rot_as_primary=use_rot_as_primary,)


if __name__ == "__main__":
    """Main: carica dati da JSON e genera grafici di analisi."""
    file_path = "Data\\Records\\seed-1\\weekly_schedule.json"
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        data = json.load(f)

    schedule = PatientListForSpecialties.from_dict(data)
    
    file_path = "Data\\Rot\\extra_time.json"
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        plan_eot = json.load(f)

    schedule_stimato_ripianificato = CreateScheduleWithReplanned(schedule, plan_eot)

    file_path = "Data\\Records\\seed-1\\rot_cplex\\weekly_schedule.json"
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        data = json.load(f)

    schedule_rot_cplex = PatientListForSpecialties.from_dict(data)

    dictSchedules = {
        "Stimato": schedule,
        "Stimato + Ripianificato": schedule_stimato_ripianificato,
        "PostSchedulato": schedule_rot_cplex,
    }
    print("SONO NEI TEST GRAFICI")
    graph_manager = Graphs()
    graph_manager.MostraTabellaConfrontoPlotly(dictSchedules)
    graph_manager.MakeGraphs(
        schedule, showGraphs=False, plan_eot=plan_eot, use_rot_as_primary=False
    )
