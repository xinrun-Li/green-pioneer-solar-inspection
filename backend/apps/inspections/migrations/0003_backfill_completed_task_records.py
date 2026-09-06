from django.db import migrations


def backfill_completed_tasks(apps, schema_editor):
    InspectionTask = apps.get_model("inspections", "InspectionTask")
    InspectionRecord = apps.get_model("inspections", "InspectionRecord")
    for task in InspectionTask.objects.filter(status="completed").iterator():
        if InspectionRecord.objects.filter(task_id=task.id, source="task").exists():
            continue
        InspectionRecord.objects.create(
            task_id=task.id,
            operator_id=task.created_by_id,
            source="task",
            summary=f"巡检任务完成，覆盖率 {task.coverage}%",
            details={
                "total_waypoints": task.total_waypoints,
                "visited_waypoints": task.visited_waypoints,
                "coverage": task.coverage,
                "backfilled": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [("inspections", "0002_inspectionrecord")]

    operations = [migrations.RunPython(backfill_completed_tasks, migrations.RunPython.noop)]
