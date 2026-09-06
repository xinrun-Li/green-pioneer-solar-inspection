from celery import shared_task

from .services import execute_job


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_mock_inference(self, job_id):
    execute_job(job_id)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_inference(self, job_id):
    execute_job(job_id)
