import service, { requestWithRetry } from './index'

export function generatePersonas(data) {
  return requestWithRetry(() =>
    service({ url: '/api/personas/generate', method: 'post', data })
  )
}

export function getPersonasTask(taskId) {
  return service({ url: `/api/personas/task/${taskId}`, method: 'get' })
}

export function getPersonas(projectId) {
  return service({ url: `/api/personas/${projectId}`, method: 'get' })
}
