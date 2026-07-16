"""
Simulation.py
=============
Modulo principale di simulazione: lettura dei dati, schedulazione EOT+ROT
e serializzazione dei risultati su file JSON/CSV.

Funzioni esposte:
    - read_and_split_by_operation_with_metadata : letttura CSV → dict per specialità
    - group_daily_with_mtb_logic_optimized_rot  : orchestrazione EOT + simulazione ROT
    - export_json_schedule                      : esportazione schedule su JSON
    - ExportCSVResults                          : esportazione risultati su CSV
"""

# ── Librerie standard ────────────────────────────────────────────────────────
import csv
import json
import os
import sys

# ── Risoluzione del path quando il modulo viene eseguito direttamente ────────
if os.path.basename(__file__) != "main.py":
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "Code"))
    )

# ── Moduli interni ───────────────────────────────────────────────────────────
from CommonClass.Patient import Patient
from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from settings import Settings
from Simulatore.Optimizer import optimize_daily_batch_rot_both

# ── Costanti di output ───────────────────────────────────────────────────────
_ROT_OUTPUT_DIR = "./Data/Rot/"
_EXTRA_TIME_FILE = _ROT_OUTPUT_DIR + "extra_time.json"
_OVERFLOW_FILE = _ROT_OUTPUT_DIR + "overflow.json"


# ─────────────────────────────────────────────────────────────────────────────
# region  I/O  –  Lettura CSV
# ─────────────────────────────────────────────────────────────────────────────


def read_and_split_by_operation_with_metadata(csv_file: str) -> dict:
    """
    Legge il file CSV dei pazienti e restituisce un dizionario
    {specialità: [Patient, ...]} con tutti i metadati necessari alla
    simulazione (EOT, ROT, giorno di inserimento, priorità MTB).

    Parameters
    ----------
    csv_file : str
        Percorso al file Patient_Record.csv generato da PatientRecordGenerator.

    Returns
    -------
    dict[str, list[Patient]]
        Un dizionario indicizzato per specialità.
    """
    result = {}

    with open(csv_file, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            specialty = row["Specialty"]

            if specialty not in result:
                result[specialty] = []

            result[specialty].append(
                Patient(
                    id=int(row["Patient ID"]),
                    eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                    day=int(row["Day (Day Added to Waiting List)"]),
                    mtb=int(row["MTB (Priority, max waiting days)"]),
                    rot=float(row["ROT (Real Operation Time in minutes)"]),
                )
            )

    return result


# endregion

# ─────────────────────────────────────────────────────────────────────────────
# region  SCHEDULAZIONE  –  Flusso EOT (piano) + ROT (realizzato)
# ─────────────────────────────────────────────────────────────────────────────


def group_daily_with_mtb_logic_optimized_rot(
    ops_dict: PatientListForSpecialties,
) -> PatientListForSpecialties:
    """
    Pianifica l'intero orizzonte settimanale usando il doppio flusso EOT/ROT:

    1. **Piano EOT** – modello MIP (Pyomo/CPLEX) che massimizza il numero di
       pazienti schedulati rispettando il limite giornaliero per sala operatoria,
       con preferenza per i giorni iniziali della settimana.
    2. **Realizzato ROT** – simulazione real-time che esegue le operazioni con
       i tempi reali (ROT), gestisce overtime e overflow verso la settimana
       successiva.

    I risultati intermedi vengono serializzati in:
        - ``./Data/Rot/extra_time.json``  (piano EOT, statistiche, extra-time)
        - ``./Data/Rot/overflow.json``    (pazienti non completati nella settimana)

    Parameters
    ----------
    ops_dict : PatientListForSpecialties
        Dizionario {specialità: [Patient, ...]} prodotto da
        ``read_and_split_by_operation_with_metadata``.

    Returns
    -------
    PatientListForSpecialties
        Schedule realizzato (ROT) per ogni specialità.
    """

    # ── Strutture di raccolta risultati ──────────────────────────────────────
    result = PatientListForSpecialties()
    overflows = PatientListForSpecialties()
    extra_times = {}
    realtime_stats = {}
    plans_eot = {}

    # ── Helper: serializzazione Patient → dict JSON ───────────────────────────
    def patient_to_dict(p: Patient) -> dict:
        """
        Converte un oggetto Patient in un dizionario serializzabile in JSON.

        Parameters
        ----------
        p : Patient
            Paziente da convertire.

        Returns
        -------
        dict
            Dizionario contenente gli attributi rilevanti del paziente per
            l'esportazione dello schedule.
        """

        return {
            "id": p.id,
            "day": p.day,
            "mtb": p.mtb,
            "eot": p.eot,
            "rot": p.rot,
            "opDay": getattr(p, "opDay", None),
            "workstation": getattr(p, "workstation", None),
            "overdue": getattr(p, "overdue", None),
        }

    # ── Loop per specialità ───────────────────────────────────────────────────
    for op_type, patients in ops_dict.items():

        data = optimize_daily_batch_rot_both(patients, op_type)

        # Schedule realizzato (ROT)
        result[op_type] = data[op_type]["realized_rot"]

        # Piano EOT convertito in lista di dict (per la serializzazione JSON)
        plans_eot[op_type] = [patient_to_dict(p) for p in data[op_type]["plan_eot"]]

        # Overflow: ogni settimana è separata da un paziente sentinella id=-1
        for week_overflow in data[op_type]["overflow"]:
            overflows[op_type].extend(week_overflow)
            overflows[op_type].append(Patient(id=-1, eot=0, day=0, mtb=0, rot=0))

        # Extra-time residuo e statistiche real-time per settimana
        extra_times[op_type] = data[op_type]["extra_time_left"]
        realtime_stats[op_type] = data[op_type].get("realtime_stats", [])

    # ── Serializzazione output ────────────────────────────────────────────────
    os.makedirs(_ROT_OUTPUT_DIR, exist_ok=True)

    with open(_EXTRA_TIME_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "extra_times": extra_times,
                "realtime_stats": realtime_stats,
                "plan_eot": plans_eot,
            },
            f,
            indent=4,
        )

    with open(_OVERFLOW_FILE, "w", encoding="utf-8") as f:
        json.dump(overflows.to_json(), f, indent=4)

    return result


# endregion


# region PUNTO 3
def rebuild_schedule_using_rot_cplex(
    schedule: PatientListForSpecialties,
) -> PatientListForSpecialties:
    """
    Ricostruisce lo schedule utilizzando i tempi reali (ROT) tramite una
    nuova ottimizzazione settimanale.

    I pazienti vengono raggruppati per settimana in base al giorno di
    inserimento in lista d'attesa. Per ciascuna settimana viene eseguita una
    riallocazione con il modello ROT, che tiene conto dell'overtime
    disponibile e degli eventuali pazienti rimasti dalla settimana
    precedente (carryover).

    Parameters
    ----------
    schedule : PatientListForSpecialties
       Schedule iniziale contenente i pazienti assegnati alle varie
       specialità.

    Returns
    -------
    PatientListForSpecialties
       Nuovo schedule ottenuto dalla riallocazione settimanale basata sui
       tempi reali (ROT).
    """

    from Simulatore.Optimizer import reallocate_week_with_rot_overtime

    result = PatientListForSpecialties()

    for specialty, patients in schedule.items():

        result[specialty] = []

        weeks = {}

        for p in patients:

            # if p.opDay == -1:
            #     continue

            # Calculate week number (starting from Settings.start_week_scheduling)
            week_num = (
                (p.day - 1) // Settings.week_length_days
            ) + Settings.start_week_scheduling

            weeks.setdefault(week_num, []).append(p)

        carryover = []

        for week_num in sorted(weeks.keys()):

            current_week_patients = carryover + weeks[week_num]

            # Calculate the actual starting day for this week number
            # Formula: day = (week_num - 1 + start_week) * week_length_days
            week_start_day = (
                week_num - 1 + Settings.start_week_scheduling
            ) * Settings.week_length_days

            planned, carryover = reallocate_week_with_rot_overtime(
                current_week_patients, specialty, week_start_day
            )

            result[specialty].extend(planned)

        next_week = max(weeks.keys()) + 1

    return result


# endregion

# ─────────────────────────────────────────────────────────────────────────────
# region  EXPORT  –  Serializzazione dei risultati
# ─────────────────────────────────────────────────────────────────────────────


def export_json_schedule(
    data, filepath: str, filename: str = "weekly_schedule.json"
) -> str:
    """
    Esporta il dizionario dello schedule in un file JSON.

    Parameters
    ----------
    data : dict
        Dati da serializzare (tipicamente ``schedule.to_dict()``).
    filepath : str
        Cartella di destinazione (viene creata se non esiste).
    filename : str, optional
        Nome del file di output. Default: ``"weekly_schedule.json"``.

    Returns
    -------
    str
        Percorso assoluto del file creato.
    """
    os.makedirs(filepath, exist_ok=True)
    file = os.path.join(filepath, filename)

    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"JSON exported to {file}")
    return file


# endregion
