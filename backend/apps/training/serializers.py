def model_payload(model):
    return {
        "id": model.id, "name": model.name, "version": model.version, "model_type": model.model_type,
        "model_path": model.model_path, "dataset_version_id": model.dataset_version_id,
        "metrics": model.metrics, "class_config": model.class_config, "status": model.status,
        "is_active": model.is_active, "created_at": model.created_at, "activated_at": model.activated_at,
    }


def run_payload(run):
    return {
        "id": run.id, "dataset_version_id": run.dataset_version_id,
        "base_model_version_id": run.base_model_version_id, "output_model_version_id": run.output_model_version_id,
        "status": run.status, "epochs": run.epochs, "image_size": run.image_size,
        "batch_size": run.batch_size, "device": run.device, "progress": run.progress,
        "metrics": run.metrics, "log_file": run.log_file, "error_message": run.error_message,
        "started_at": run.started_at, "completed_at": run.completed_at, "created_at": run.created_at,
    }
