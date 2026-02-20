# ocr-service Helm Chart

Deploys the CogStack OCR service as a Kubernetes `Deployment` + `Service`, with optional `HorizontalPodAutoscaler` (HPA).

## Install

```bash
helm install ocr-service ./charts/ocr-service
```

## Upgrade

```bash
helm upgrade ocr-service ./charts/ocr-service
```

## Key values

- `image.repository` / `image.tag`: container image to run.
- `env`: OCR service environment variables.
- `tmp.*`: writable `emptyDir` mount for `/ocr_service/tmp`.
- `probes.*`: startup/readiness/liveness probe settings.
- `autoscaling.enabled`: enable/disable HPA.

## Enable HPA

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 75
  targetMemoryUtilizationPercentage: 80
```

HPA requires Kubernetes metrics (usually `metrics-server`) in the cluster.
