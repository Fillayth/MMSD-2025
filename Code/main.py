import json
import os

from Grafici.Graph import Graphs, CreateScheduleWithReplanned
from RecordGeneration.PatientRecordGenerator import generate_csv
from settings import Settings
from Simulatore.Simulation import (
    read_and_split_by_operation_with_metadata,
    export_json_schedule,
    group_daily_with_mtbt_logic_optimized_rot,
)
from Simulatore.Simulation import rebuild_schedule_using_rot_cplex

def create_execution_stamp(output_dir="./Data/", filename_prefix="settings_"):
    """
    Crea uno snapshot completo delle configurazioni utilizzate 
    per l'esecuzione corrente, includendo metadati come il timestamp e il seed effettivo.
    """
    actual_seed = Settings.GetSeed()

    # Prepara il dizionario con i metadati dell'esecuzione
    execution_stamp = {
        "settings": {}
    }

    # Estrae tutti i parametri dalla classe Settings
    for attr, value in Settings.__dict__.items():
        if attr.startswith("__") or callable(value):
            continue
        
        # Gestione speciale per l'oggetto solver di Pyomo
        if hasattr(value, "name"):
            execution_stamp["settings"][attr] = value.name
        else:
            try:
                # Verifica serializzabilità JSON
                json.dumps(value)
                execution_stamp["settings"][attr] = value
            except TypeError:
                execution_stamp["settings"][attr] = str(value)

    # Aggiorna il valore del seed salvato nei settaggi con quello effettivo
    execution_stamp["settings"]["seed"] = actual_seed

    # Salva lo stamp in un file JSON dedicato all'esecuzione
    stamp_filename = f"{filename_prefix}_{actual_seed}.json"
    stamp_filepath = os.path.join(output_dir, stamp_filename)
    
    with open(stamp_filepath, "w", encoding="utf-8") as f:
        json.dump(execution_stamp, f, indent=4, ensure_ascii=False)
        
    print(f" Stamp configurazione salvato in: {stamp_filepath}")
    return execution_stamp, stamp_filepath

# Main function to generate patient records and weekly reports
def main():
    """
    Main function to generate patient records and weekly reports.
    """

    specialties = list(Settings.workstations_config.keys())

    weekly_hours = (
        Settings.week_hours_to_fill
    )

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # + "/Data"
    data_root = os.path.join(project_root, Settings.resultsData_folder)
    paths = generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=Settings.weeks_to_fill,
        seed=Settings.GetSeed(),  # 197558074,
        specialty_params=Settings.specialty_params,
        people_distribution=Settings.daily_patient_arrival_distribution,
        priority_params=Settings.priority_params,  # <-- passa il nuovo dizionario
        filepath=data_root,
    )
    # la funzione generate_csv restituisce il path del seed come primo argomento
    resultsData_folder = os.path.dirname(os.path.abspath(paths[0]))

    all_patient_records = read_and_split_by_operation_with_metadata(paths[0])

    # salva le configurazioni nel data seed
    create_execution_stamp(output_dir=resultsData_folder)

    schedule = group_daily_with_mtbt_logic_optimized_rot(all_patient_records, resultsData_folder)
    plan_eot = None
    try:
        with open(f"{resultsData_folder}/extra_time.json", "r", encoding="utf-8") as f:
            extra = json.load(f)
        plan_eot = extra.get("plan_eot", None)
    except Exception as e:
        print(f"[WARN] plan_eot non letto: {e}")

    schedule_stimato_ripianificato = CreateScheduleWithReplanned(schedule, plan_eot)
    scheduleJson_path = export_json_schedule(schedule_stimato_ripianificato.to_dict(), resultsData_folder)
    
    Graphs(f"{resultsData_folder}{Settings.images_folder}").MakeGraphs(
        schedule_stimato_ripianificato, plan_eot=plan_eot
    )


    schedule_rot_cplex = rebuild_schedule_using_rot_cplex(all_patient_records)
    scheduleJson_path = export_json_schedule(
        schedule_rot_cplex.to_dict(), resultsData_folder + "/rot_cplex/"
    )
    Graphs(f"{resultsData_folder}/rot_cplex/{Settings.images_folder}").MakeGraphs(
        schedule_rot_cplex, plan_eot=plan_eot, use_rot_as_primary=True
    )

    dictSchedules = {
        "Stimato": schedule,
        "Stimato + Ripianificato": schedule_stimato_ripianificato,
        "PostSchedulato": schedule_rot_cplex,
    }

    Graphs(f"{resultsData_folder}").MostraTabellaConfrontoPlotly(dictSchedules)

    print(f"Graphs and tables generated in {resultsData_folder}")


if __name__ == "__main__":
    main()
