import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.training.services import get_or_create_yolo_model


class Command(BaseCommand):
    help = "注册本地 Solar YOLOv11-nano 模型版本"

    def add_arguments(self, parser):
        parser.add_argument("--activate", action="store_true", help="同时启用该模型")

    def handle(self, *args, **options):
        owner = get_user_model().objects.filter(is_superuser=True).first()
        if owner is None:
            raise CommandError("请先创建超级用户")
        model = get_or_create_yolo_model(owner, activate=options["activate"])
        model_file = Path(settings.MEDIA_ROOT) / model.model_path
        if not model_file.is_file():
            self.stdout.write(self.style.WARNING(f"模型已登记，但文件不存在: {model_file}"))
        else:
            digest = hashlib.sha256()
            with model_file.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            model.model_sha256 = digest.hexdigest()
            model.save(update_fields=("model_sha256",))
            self.stdout.write(f"模型文件: {model_file} ({model.model_sha256})")
        self.stdout.write(self.style.SUCCESS(f"已登记 {model.version} ({model.status})"))
