# ocr-service Helm Chart

Deploys the CogStack OCR service as a Kubernetes `Deployment` + `Service`, with optional `HorizontalPodAutoscaler` (HPA).

## Install

```bash
helm install ocr-service ./charts/ocr-service
```

### Install with repo env files (dynamic)

```bash
helm upgrade --install ocr-service ./charts/ocr-service \
  --set envFiles.enabled=true \
  --set-file envFiles.contents[0]=./env/ocr_service.env \
  --set-file envFiles.contents[1]=./env/general.env
```

Text-only profile (overlay on top of base):

```bash
helm upgrade --install ocr-service ./charts/ocr-service \
  --set envFiles.enabled=true \
  --set-file envFiles.contents[0]=./env/ocr_service.env \
  --set-file envFiles.contents[1]=./env/ocr_service_text_only.env \
  --set-file envFiles.contents[2]=./env/general.env
```

Notes:
- Env files are applied in order; later files override earlier ones.
- Parsed env-file values override `values.yaml` `env` keys when `envFiles.enabled=true`.
- Values are treated as literal strings (shell substitutions like `${VAR:-default}` are not expanded by Helm).

## Upgrade

```bash
helm upgrade ocr-service ./charts/ocr-service
```

## Key values

- `image.repository` / `image.tag`: container image to run.
- `env`: OCR service environment variables.
- `envFiles.enabled` + `envFiles.contents`: parse one or more `.env` files at deploy time. Later files override earlier files.
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
