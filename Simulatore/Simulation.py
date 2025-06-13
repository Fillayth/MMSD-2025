import csv
import json

def read_and_split_by_operation_with_metadata(csv_file):
    with open(csv_file, mode='r', newline='', encoding='utf-8') as f:
        content = f.readlines()[2:] 
        reader = csv.reader(content)
        lines = list(reader)

    #data_rows = lines[2:]

    ops = {"Operazione A": [], "Operazione B": [], "Operazione C": []}

    for row in lines:
        patient_id, op_type, eot, day, mtb = row
        patient = {
            "id": int(patient_id),
            "eot": float(eot),
            "day": int(day),
            "mtb": int(mtb)
        }
        ops[op_type].append(patient)
    return ops

def group_weekly_with_mtb_logic(ops_dict, weekly_limit=2400, week_length_days=5):
    grouped_schedule = {}

    for op_type, patients in ops_dict.items():
        remaining = patients.copy()
        week_number = 0
        grouped_schedule[op_type] = []

        while remaining:
            current_week_start = week_number * week_length_days
            current_week_end = current_week_start + week_length_days - 1
            next_week_end = current_week_end + week_length_days

            batch = []
            total_time = 0

            overdue_now = [p for p in remaining if current_week_end - p["day"] >= p["mtb"]]
            overdue_next = [p for p in remaining if next_week_end - p["day"] >= p["mtb"]
                            and p not in overdue_now]
            normal = [p for p in remaining if p not in overdue_now and p not in overdue_next]
            ordered = overdue_now + overdue_next + normal

            i = 0
            while i < len(ordered):
                p = ordered[i]
                if total_time + p["eot"] <= weekly_limit:
                    batch.append({
                        "id": p["id"],
                        "eot": round(p["eot"], 2),
                        "day": p["day"],
                        "mtb": p["mtb"],
                        "overdue": current_week_end - p["day"] >= p["mtb"]
                    })
                    total_time += p["eot"]
                    remaining.remove(p)
                    ordered.pop(i)
                else:
                    i += 1

            # Sort
            batch.sort(key=lambda x: x["eot"], reverse=True)

            grouped_schedule[op_type].append({
                "week": week_number + 1,
                "patients": batch
            })

            week_number += 1

    return grouped_schedule

def export_json_schedule(data, filename="weekly_schedule.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"JSON exported to {filename}")

if __name__ == "__main__":
    ops = read_and_split_by_operation_with_metadata("lista_attesa_simulata.csv")
    schedule = group_weekly_with_mtb_logic(ops)
    export_json_schedule(schedule)
