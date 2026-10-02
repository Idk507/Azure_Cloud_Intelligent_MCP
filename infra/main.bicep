@description('Azure region for the Container Apps environment.')
param location string = resourceGroup().location

@description('Container App name.')
param containerAppName string

@description('Fully qualified image reference, including tag or digest.')
param containerImage string

@description('Log Analytics workspace resource ID used by the Container Apps environment.')
param logAnalyticsWorkspaceId string

@description('Azure subscription ID used for resource-scoped SDK calls.')
param subscriptionId string

@description('Container image registry server, for example contoso.azurecr.io.')
param registryServer string

@description('Optional workspace-based Application Insights resource name. Leave empty when an existing component is connected to the Foundry project.')
param applicationInsightsName string = ''

var logWorkspaceResourceGroup = split(logAnalyticsWorkspaceId, '/')[4]
var logWorkspaceName = last(split(logAnalyticsWorkspaceId, '/'))

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  scope: resourceGroup(subscription().subscriptionId, logWorkspaceResourceGroup)
  name: logWorkspaceName
}

// WorkspaceResourceId is required for workspace-based Application Insights components.
// Source: https://learn.microsoft.com/azure/azure-monitor/app/create-workspace-resource?tabs=bicep
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = if (!empty(applicationInsightsName)) {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    DisableIpMasking: false
    DisableLocalAuth: false
  }
}

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${containerAppName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logWorkspace.properties.customerId
        sharedKey: logWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: registryServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'azure-cloud-intelligence-mcp'
          image: containerImage
          env: [
            {
              name: 'AZURE_SUBSCRIPTION_ID'
              value: subscriptionId
            }
            {
              name: 'PORT'
              value: '8000'
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output managedIdentityPrincipalId string = containerApp.identity.principalId
output applicationInsightsResourceId string = !empty(applicationInsightsName) ? applicationInsights.id : ''
