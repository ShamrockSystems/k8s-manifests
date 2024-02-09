local grafana = import 'kube-prometheus/components/grafana.libsonnet';

local grafanaNamespace = 'grafana';
local grafanaDashboardLabel = 'grafana';

local kp = (import 'kube-prometheus/main.libsonnet') +
           (import 'kube-prometheus/addons/all-namespaces.libsonnet') + {
  values+:: {
    common+: {
      namespace: 'monitoring',
    },
    prometheus+: {
      namespaces: [],
    },
    grafana+:: {
      namespace:: grafanaNamespace,
    },
  },
  // Setup Prometheus PVC
  prometheus+:: {
    prometheus+: {
      spec+: {
        retention: '60d',
        storage: {
          volumeClaimTemplate: {
            apiVersion: 'v1',
            kind: 'PersistentVolumeClaim',
            spec: {
              accessModes: ['ReadWriteOnce'],
              resources: { requests: { storage: '32Gi' } },
              storageClassName: 'block-replicated',
            },
          },
        },
      },
    },
  },
  // Disable all grafana-related objects apart from dashboards
  grafana+:: {
    deployment:: {},
    config:: {},
    dashboardDatasources:: {},
    dashboardSources:: {},
    prometheusRule:: {},
    serviceAccount:: {},
    serviceMonitor:: {},
    networkPolicy:: {},
    service:: {},
  },
};

local grafanaOperatorDashboard(item) = {
  apiVersion: 'grafana.integreatly.org/v1beta1',
  kind: 'GrafanaDashboard',
  metadata: {
    name: std.join('-', ['grafanadashboard', 'cm', item.metadata.name]),
    namespace: grafanaNamespace,
  },
  spec: {
    instanceSelector: {
      matchLabels: {
        dashboards: grafanaDashboardLabel,
      },
    },
    configMapRef: {
      name: item.metadata.name,
      key: std.objectFields(item.data)[0],
    },
  },
};

{
  apiVersion: 'config.kubernetes.io/v1',
  kind: 'ResourceList',
  items: [kp.kubePrometheus.namespace] +
         [
           kp.prometheusOperator[name]
           for name in std.filter((function(name) name != 'serviceMonitor' && name != 'prometheusRule'), std.objectFields(kp.prometheusOperator))
         ] +
         [kp.prometheusOperator.serviceMonitor, kp.prometheusOperator.prometheusRule, kp.kubePrometheus.prometheusRule] +
         [kp.alertmanager[name] for name in std.objectFields(kp.alertmanager)] +
         [kp.blackboxExporter[name] for name in std.objectFields(kp.blackboxExporter)] +
         [kp.grafana[name] for name in std.objectFields(kp.grafana)] +
         [grafanaOperatorDashboard(item) for item in kp.grafana.dashboardDefinitions.items] +
         [kp.kubeStateMetrics[name] for name in std.objectFields(kp.kubeStateMetrics)] +
         [kp.kubernetesControlPlane[name] for name in std.objectFields(kp.kubernetesControlPlane)] +
         [kp.nodeExporter[name] for name in std.objectFields(kp.nodeExporter)] +
         [kp.prometheus[name] for name in std.objectFields(kp.prometheus)] +
         [kp.prometheusAdapter[name] for name in std.objectFields(kp.prometheusAdapter)],
}
