import json
import os

from Grafici.Graph import Graphs, CreateScheduleWithReplanned
from RecordGeneration.PatientRecordGenerator import generate_csv
from settings import Settings
from Simulatore.Simulation import (
    read_and_split_by_operation_with_metadata,
    export_json_schedule,
    group_daily_with_mtb_logic_optimized_rot,
)
from Simulatore.Simulation import rebuild_schedule_using_rot_cplex


# Main function to generate patient records and weekly reports
def main():
    """
    Main function to generate patient records and weekly reports.
    """

    specialties = list(Settings.workstations_config.keys())

    weekly_hours = (
        Settings.week_hours_to_fill
    )

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/Data"

    paths = generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=Settings.weeks_to_fill,
        seed=Settings.GetSeed(),  # 197558074,
        specialty_params=Settings.specialty_params,
        people_distribution=Settings.daily_patient_arrival_distribution,
        priority_params=Settings.priority_params,  # <-- passa il nuovo dizionario
        filepath=project_root,
    )

    resultsData_folder = os.path.dirname(os.path.abspath(paths[0]))

    all_patient_records = read_and_split_by_operation_with_metadata(paths[0])

    schedule = group_daily_with_mtb_logic_optimized_rot(all_patient_records)
    scheduleJson_path = export_json_schedule(schedule.to_dict(), resultsData_folder)
    plan_eot = None
    try:
        with open("./Data/Rot/extra_time.json", "r", encoding="utf-8") as f:
            extra = json.load(f)
        plan_eot = extra.get("plan_eot", None)
    except Exception as e:
        print(f"[WARN] plan_eot non letto: {e}")

    Graphs(f"{resultsData_folder}{Settings.images_folder}").MakeGraphs(
        schedule, plan_eot=plan_eot
    )


    schedule_rot_cplex = rebuild_schedule_using_rot_cplex(all_patient_records)
    scheduleJson_path = export_json_schedule(
        schedule_rot_cplex.to_dict(), resultsData_folder + "/rot_cplex/"
    )
    Graphs(f"{resultsData_folder + '/rot_cplex/'}{Settings.images_folder}").MakeGraphs(
        schedule_rot_cplex, plan_eot=plan_eot, use_rot_as_primary=True
    )

    schedule_stimato_ripianificato = CreateScheduleWithReplanned(schedule, plan_eot)
    scheduleJson_path = export_json_schedule(
        schedule_stimato_ripianificato.to_dict(), resultsData_folder + "/temp/"
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
