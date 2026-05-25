# ocr-service Helm Chart

Deploys the CogStack OCR service as a Kubernetes `Deployment` + `Service`, with optional `HorizontalPodAutoscaler` (HPA).

## Install

```bash
helm install ocr-service ./charts/ocr-service
```

Repo shortcut:

```bash
make helm-install
```

### Install with values overlays

```bash
helm upgrade --install ocr-service ./charts/ocr-service \
  -f ./my-values.yaml
```

Text-only profile:

```bash
helm upgrade --install ocr-service ./charts/ocr-service \
  -f ./charts/ocr-service/values-text-only.yaml
```

Repo shortcut:

```bash
make helm-install-text-only
```

Notes:
- Use normal Helm value layering; later `-f` files override earlier ones.
- Put runtime OCR settings under `env`.
- For existing Kubernetes-managed env sources, use `extraEnvFrom` with `secretRef` or `configMapRef`.
- The repo `env/*.env` files remain for local shell and Docker flows; the Helm chart now uses YAML values only.
- Use `HELM_ARGS` with the make targets for namespace or values overrides, for example `make helm-install HELM_ARGS='-n ocr --create-namespace'`.

Example custom overlay:

```yaml
image:
  tag: "1.0.9"

env:
  OCR_SERVICE_TESSERACT_LANG: "eng"
  OCR_SERVICE_CPU_THREADS: "1"
  OCR_SERVICE_CONVERTER_THREADS: "1"
```

## Upgrade

```bash
helm upgrade ocr-service ./charts/ocr-service
```

## Key values

- `image.repository` / `image.tag`: container image to run.
- `env`: OCR service environment variables.
- `extraEnvFrom`: import additional env vars from a `Secret` or `ConfigMap`.
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
