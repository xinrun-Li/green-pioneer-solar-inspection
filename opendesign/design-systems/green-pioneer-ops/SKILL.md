---
name: green-pioneer-ops
description: Imported product design system for the Green Pioneer photovoltaic inspection operations console.
---

# 绿能先锋 · 运维控制台设计系统

This design system is extracted from the current Vue console and refined for a Django-style management surface. The product is a desktop-first operations console for station managers, inspection operators, and model lifecycle owners.

## Product posture

- Calm, precise, operational, and easy to scan under pressure.
- Prefer one clear action per surface over decorative dashboard density.
- Preserve the product vocabulary: 识别作业, 电站地图, 历史数据, 报告中心, 数据集与标注, 模型训练.
- Model lifecycle copy must make the control boundary explicit: samples are pending annotation, dataset versions freeze before training, and candidate models require manual activation.

## Visual language

- Temperature: neutral-cool with a restrained solar-green accent.
- Type: PingFang SC / Microsoft YaHei for Chinese UI, Avenir Next for Latin UI, SFMono-Regular / Menlo for IDs, statuses, and metrics.
- Surfaces: flat panels with hairline borders; use elevation only for drawers, dialogs, and active workspaces.
- Status colors: green = normal/active, amber = cleaning/review, red = repair/failure, blue = running/processing.
- Avoid gradients, ornamental cards, and icon-only actions without labels.

## Interaction rules

- Desktop target: 1440 × 900 first, with a usable 1180 px minimum width.
- Minimum click target: 40 px for primary controls, 32 px for compact table actions.
- Keep page title, scope, and one primary action in the first viewport.
- Every model or recognition result carries a traceable version and source label.

## Django Admin adaptation

- Keep the native admin mental model: application groups, model lists, and direct `增加 / 修改` actions.
- Replace the default blue header with the Green Pioneer brand shell, but do not hide model counts, permissions, or recent actions.
- Group models by operator intent: station assets, inspection operations, recognition and review, datasets and training, reports, and access control.
- The home screen should make pending review, open events, candidate models, and pending operator approvals visible before decorative analytics.
