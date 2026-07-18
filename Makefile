SHELL := /usr/bin/env bash
.SHELLFLAGS := -o pipefail -c

HELM_RELEASE ?= ocr-service
HELM_CHART ?= ./charts/ocr-service
HELM_TEXT_ONLY_VALUES ?= ./charts/ocr-service/values-text-only.yaml
HELM_ARGS ?=

.PHONY: helm-install helm-install-text-only helm-template helm-lint helm-uninstall

helm-install:
	helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) $(HELM_ARGS)

helm-install-text-only:
	helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) -f $(HELM_TEXT_ONLY_VALUES) $(HELM_ARGS)

helm-template:
	helm template $(HELM_RELEASE) $(HELM_CHART) $(HELM_ARGS)

helm-lint:
	helm lint $(HELM_CHART)

helm-uninstall:
	helm uninstall $(HELM_RELEASE) $(HELM_ARGS)
