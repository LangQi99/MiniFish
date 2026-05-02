import service, { requestWithRetry } from './index'

export function generateOntology(formData) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  )
}

export function buildGraph(data) {
  return requestWithRetry(() =>
    service({ url: '/api/graph/build', method: 'post', data })
  )
}

export function getTaskStatus(taskId) {
  return service({ url: `/api/graph/task/${taskId}`, method: 'get' })
}

export function getGraphData(graphId) {
  return service({ url: `/api/graph/data/${graphId}`, method: 'get' })
}

export function getProject(projectId) {
  return service({ url: `/api/graph/project/${projectId}`, method: 'get' })
}

export function listProjects(limit = 50) {
  return requestWithRetry(() =>
    service({ url: '/api/graph/project/list', method: 'get', params: { limit } })
  )
}

export function deleteProject(projectId) {
  return service({ url: `/api/graph/project/${projectId}`, method: 'delete' })
}
