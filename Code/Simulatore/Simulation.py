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
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "Code")))

# ── Moduli interni ───────────────────────────────────────────────────────────
from CommonClass.Patient import Patient
from CommonClass.PatientListForSpecialties import PatientListForSpecialties
from CommonClass.Week import Week
from settings import Settings
from Simulatore.Optimizer import optimize_daily_batch_rot_both


# ── Costanti di output ───────────────────────────────────────────────────────
_ROT_OUTPUT_DIR = "./Data/Rot/"
_EXTRA_TIME_FILE = _ROT_OUTPUT_DIR + "extra_time.json"
_OVERFLOW_FILE   = _ROT_OUTPUT_DIR + "overflow.json"


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
                #continue  # (rimosso: causerebbe la perdita del primo paziente di ogni specialità)

            result[specialty].append(Patient(
                id=int(row["Patient ID"]),
                eot=float(row["EOT (Estimated Operation Time in minutes)"]),
                day=int(row["Day (Day Added to Waiting List)"]),
                mtb=int(row["MTB (Priority, max waiting days)"]),
                rot=float(row["ROT (Real Operation Time in minutes)"]),
            ))

    return result

# endregion


# ─────────────────────────────────────────────────────────────────────────────
# region  LEGACY  –  Schedulazione euristica senza ottimizzatore
#         (conservata per confronto; non viene invocata nel flusso principale)
# ─────────────────────────────────────────────────────────────────────────────

#def group_daily_with_mtb_logic(ops_dict: PatientListForSpecialties) ->PatientListForSpecialties:
#    day_for_week = Settings.week_length_days #valore statico, lo uso per impostare le settimane 
#    #non è il contatore del giorno perchè si scatta di settimana in settimana ma lo uso come indicatore per valutare le urgenze  
#    today_number = lambda wN: day_for_week * wN #weekNum      
#    # le settimane da definire
#    weeks: PatientListForSpecialties = PatientListForSpecialties()
#    # la settimana corrente 
#    for op_type, patients in ops_dict.items():
#        remaining = patients.copy()
#        # remaining = patients.sort(key=lambda p: p.day).copy()
#        week = Week(Settings.start_week_scheduling, op_type)
#        weeks[op_type] = []
#        workStation = 0
#        while remaining:
#            for_this_week = [p for p in remaining if p.day < today_number(week.weekNum)]
#            #ordino i pazienti in base all'urgenza 
#            ordered = sorted(for_this_week, key= lambda x: x.day + x.mtb - today_number(week.weekNum), reverse=False ) 
#            # serve far emergere i patient con eot piu alti nella cerchia dei piu urgenti per ottimizzare gli spazi 
#            firstSet = [p for p in ordered if p.day + p.mtb <= today_number(week.weekNum + 2)] #today_number + ho impostato due settimane come cerchia
#            secondSet = [p for p in ordered if p.day + p.mtb > today_number(week.weekNum + 2)] #prendo il resto 
#            ordered = sorted(firstSet, key= lambda x: x.eot, reverse=True) + secondSet
#            # ciclo i pazienti rimasti fino a riempire la settimana in coso 
#            
#            for p in ordered:
#                # la funzione restituisce true se il paziente è stato inserito 
#                p.workstation = workStation
#                if week.insertPatient(p):
#                    #rimuovo i pazieniti dalla lista provvisoria 
#                    remaining.remove(p)
#                elif workStation < Settings.workstations_config[op_type]:
#                    workStation =+ 1
#                    p.workstation = workStation
#                    week.insertPatient(p)
#                else:
#                    break
#            ## se il ciclo finisce e i pazienti sono ancora presenti vuol dire che la settimana si è riempita
#            ## e ne serve una nuova 
#            if len(remaining) > 0 :
#                # weeks[op_type].append(week)
#                weeks[op_type].extend(week.patients())
#                weekNum = week.weekNum+1
#                workStation = 0
#                week = Week(weekNum, op_type)
#        #alla fine del cilo sui pazienti totali, inserisco anche l'ultima settimana nella lista
#        weeks[op_type].extend(week.patients())
#    return weeks

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
    result         = PatientListForSpecialties()
    overflows      = PatientListForSpecialties()
    extra_times    = {}
    realtime_stats = {}
    plans_eot      = {}

    # ── Helper: serializzazione Patient → dict JSON ───────────────────────────
    def patient_to_dict(p: Patient) -> dict:
        return {
            "id":          p.id,
            "day":         p.day,
            "mtb":         p.mtb,
            "eot":         p.eot,
            "rot":         p.rot,
            "opDay":       getattr(p, "opDay", None),
            "workstation": getattr(p, "workstation", None),
            "overdue":     getattr(p, "overdue", None),
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
        extra_times[op_type]    = data[op_type]["extra_time_left"]
        realtime_stats[op_type] = data[op_type].get("realtime_stats", [])

    # ── Serializzazione output ────────────────────────────────────────────────
    os.makedirs(_ROT_OUTPUT_DIR, exist_ok=True)

    with open(_EXTRA_TIME_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "extra_times":    extra_times,
                "realtime_stats": realtime_stats,
                "plan_eot":       plans_eot,
            },
            f,
            indent=4,
        )

    with open(_OVERFLOW_FILE, "w", encoding="utf-8") as f:
        json.dump(overflows.to_json(), f, indent=4)

    return result

# endregion


# ─────────────────────────────────────────────────────────────────────────────
# region  EXPORT  –  Serializzazione dei risultati
# ─────────────────────────────────────────────────────────────────────────────

def export_json_schedule(data, filepath: str, filename: str = "weekly_schedule.json") -> str:
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


def ExportCSVResults(data: PatientListForSpecialties) -> None:
    """
    Aggiunge i risultati di schedulazione al file CSV dei risultati globali.

    Per ogni specialità vengono scritte le righe:
    Seed, Patient ID, EOT, Day, MTB, Workstation, Overdue, Scheduled Day.

    Note
    ----
    Usa ``Settings.seed`` (il seed effettivamente applicato nel run corrente);
    per massima sicurezza si potrebbe usare ``Settings.GetSeed()``.
    """
    os.makedirs(Settings.resultsData_folder, exist_ok=True)
    filename = Settings.resultsData_folder + Settings.results_filename

    for op, values in data.items():
        with open(filename, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Seed", "Patient ID", "EOT", "Day", "MTB",
                              "Workstation", "Overdue", "Scheduled Day"])
            for p in values:
                writer.writerow([
                    Settings.seed,  # uso Settings.seed perchè so che nel main è stato usato
                    p.id, p.eot, p.day, p.mtb,
                    p.workstation, p.overdue, p.opDay,
                ])

        print(f"CSV results exported to {filename}")

# endregion


# ─────────────────────────────────────────────────────────────────────────────
# region  ENTRYPOINT  –  Esecuzione diretta del modulo (debug / test standalone)
# ─────────────────────────────────────────────────────────────────────────────

#if __name__ == "__main__":
#
#
#    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..\\..\\Data", "Records", "seed-1"))
#    csv_path = os.path.join(base_dir, "Patient_Record.csv")
#
#    spc = read_and_split_by_operation_with_metadata(csv_path)
#    # schedule = PatientListForSpecialties()
#    schedule = group_daily_with_mtb_logic(spc)
#    # normalizzo il risultato di group_daily_with_mtb_logic verificando che non ci siano doppioni
#    data = {key: [p.to_dict() for p in values] for key, values in schedule.items()}
#    # rimuovo i doppioni
#    for key in data:
#        unique_patients = {}
#        for patient in data[key]:
#            if patient['id'] not in unique_patients:
#                unique_patients[patient['id']] = patient
#        data[key] = list(unique_patients.values())
#    # export_json_schedule(schedule.to_dict(), base_dir)
#    export_json_schedule(data, base_dir)
#    ExportCSVResults(schedule)

# endregion




