# `k8s-manifests`

## Setup

The tooling for this repository is managed with PDM.

```sh
pdm install
```

## Usage

This project is managed by Kustomanager, an in-tree Python-based tool.

### Add project directory
```sh
kustomanager add metal argocd
```

### Rebuild projects
```sh
kustomanager build
```
