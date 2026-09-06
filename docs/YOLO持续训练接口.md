# YOLO 持续训练接口

当前版本只提供数据集、标注、训练任务和模型版本的业务接口，不会伪装执行真实 YOLO 训练。后续接入训练执行器时，训练任务应异步更新状态，并在完成后生成候选模型版本。

## 生命周期

```text
上传样本 → 人工标注 → 提交样本 → 创建数据集草稿 → 冻结数据集
→ 创建训练任务 → 生成候选模型 → 人工启用/回滚
```

未完成标注的样本不能加入数据集版本；冻结后的数据集版本不能修改。

## 主要接口

```text
GET/POST /api/v1/dataset-assets/
GET      /api/v1/dataset-assets/{id}/
POST     /api/v1/dataset-assets/{id}/annotations/
PATCH    /api/v1/annotations/{id}/
DELETE   /api/v1/annotations/{id}/
POST     /api/v1/dataset-assets/{id}/submit/
GET/POST /api/v1/dataset-versions/
POST     /api/v1/dataset-versions/{id}/freeze/

GET/POST /api/v1/training-runs/
GET      /api/v1/training-runs/{id}/
POST     /api/v1/training-runs/{id}/cancel/
GET      /api/v1/training-runs/{id}/logs/
GET      /api/v1/training-runs/{id}/metrics/

GET      /api/v1/model-versions/
GET      /api/v1/model-versions/{id}/
POST     /api/v1/model-versions/{id}/activate/
POST     /api/v1/model-versions/{id}/rollback/
```

## 推理追踪

`RecognitionJob.model_version` 保存识别作业实际使用的模型版本，识别响应同时返回 `model_version` 和 `model_version_id`。Mock 模型版本为 `mock-v1`；未来 YOLO 训练完成后应创建 `candidate` 模型，人工启用后才会成为默认推理模型。
