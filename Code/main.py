import json
import os

from Grafici.Graph import Graphs
from RecordGeneration.PatientRecordGenerator import generate_csv
from settings import Settings
from Simulatore.Simulation import read_and_split_by_operation_with_metadata, export_json_schedule, group_daily_with_mtb_logic_optimized_rot
from Simulatore.Simulation import rebuild_schedule_using_rot_cplex


# region stampa a console del punto 3

def print_weekly_rot_summary(schedule):

    print("\n" + "=" * 80)
    print("ROT + OVERTIME SCHEDULE SUMMARY")
    print("=" * 80)

    for specialty, patients in schedule.items():

        print(f"\nSPECIALTY: {specialty}")

        if not patients:
            continue

        max_day = max(p.opDay for p in patients)

        week_start = 1

        while week_start <= max_day:

            week_end = week_start + Settings.week_length_days - 1

            print(
                f"\nWEEK [{week_start} - {week_end}]"
            )

            remaining_pool = Settings.weekly_extra_time_pool

            for day in range(week_start, week_end + 1):

                day_patients = [
                    p for p in patients
                    if p.opDay == day
                ]

                used_time = sum(
                    p.rot for p in day_patients
                )

                daily_capacity = (
                        Settings.daily_operation_limit
                        * Settings.workstations_config[specialty]
                )

                overtime_used = max(
                    0,
                    used_time - daily_capacity
                )

                remaining_pool -= overtime_used

                delayed = [
                    p for p in day_patients
                    if (
                        p.day + p.mtb
                        < p.opDay
                    )
                ]

                print(
                    f"Day {day:2d} | "
                    f"Patients: {len(day_patients):3d} | "
                    f"ROT used: {used_time:7.1f} min | "
                    f"OT used: {overtime_used:6.1f} min | "
                    f"OT left: {remaining_pool:6.1f} min | "
                    f"Late patients: {len(delayed):2d}"
                )

            for day in range(week_start, week_end + 1):

                for room in [1, 2]:
                    room_patients = [
                        p for p in patients
                        if p.opDay == day
                           and p.workstation == room
                    ]

                    room_rot = sum(
                        p.rot
                        for p in room_patients
                    )

                    print(
                        f"Day {day} Room {room}: "
                        f"{len(room_patients)} patients "
                        f"ROT={room_rot:.1f}"
                    )

            week_start += Settings.week_length_days

    print("=" * 80)

# endregion


# Main function to generate patient records and weekly reports
def main():
    """
    Main function to generate patient records and weekly reports.
    """
    #specialties = ["Specialty A"]  # Insert necessary specialties here
    specialties = list(Settings.workstations_config.keys())

    weekly_hours = Settings.week_hours_to_fill  # Total available hours for operations per week

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/Data"
    
    paths = generate_csv(
        specialties=specialties,
        weekly_hours=weekly_hours,
        num_weeks=Settings.weeks_to_fill,
        seed=Settings.GetSeed(), #197558074,
        specialty_params=Settings.specialty_params,
        people_distribution=Settings.daily_patient_arrival_distribution,
        priority_params=Settings.priority_params,  # <-- passa il nuovo dizionario
        filepath=project_root
    )

    resultsData_folder = os.path.dirname(os.path.abspath(paths[0]))

    all_patient_records = read_and_split_by_operation_with_metadata(paths[0])

 
    schedule = group_daily_with_mtb_logic_optimized_rot(all_patient_records)

    schedule_rot_cplex = rebuild_schedule_using_rot_cplex(all_patient_records) #TODO creare un nuovo grafico per il punto 3
    # schedule_rot_cplex = rebuild_schedule_using_rot_cplex(schedule) #TODO creare un nuovo grafico per il punto 3
    print_weekly_rot_summary(schedule_rot_cplex) # TODO rimuovere quando ci sono i grafici

    # schedule = group_daily_with_mtb_logic_optimized(all_patient_records) #togliere il commento per usare la versione precedente
    # schedule = group_daily_with_mtb_logic_rot(all_patient_records)
    # schedule = group_daily_with_mtb_logic_optimized_rot(all_patient_records)
    scheduleJson_path = export_json_schedule(schedule.to_dict(), resultsData_folder)
    scheduleJson_path = export_json_schedule(schedule_rot_cplex.to_dict(), resultsData_folder + "/rot_cplex/")
    # caricare alla fine delle schedulazioni tutti i risultati e gestire in qualche modo la visualizzazione 
    plan_eot = None
    try:
        with open("./Data/Rot/extra_time.json", "r", encoding="utf-8") as f:
            extra = json.load(f)
        plan_eot = extra.get("plan_eot", None)
    except Exception as e:
        print(f"[WARN] plan_eot non letto: {e}")

    Graphs(f"{resultsData_folder}{Settings.images_folder}").MakeGraphs(schedule, plan_eot=plan_eot)
    Graphs(f"{resultsData_folder + '/rot_cplex/'}{Settings.images_folder}").MakeGraphs(schedule_rot_cplex, plan_eot=plan_eot, use_rot_as_primary=True)
    dictSchedules = {
        "Stimato": schedule,
        "PostSchedulato": schedule_rot_cplex
    }
    Graphs(f"{resultsData_folder}").MostraTabellaConfrontoPlotly(dictSchedules)

    print(f"Graphs and tables generated in {resultsData_folder}")

if __name__ == "__main__":
    main()  

    