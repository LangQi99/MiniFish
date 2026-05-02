import service from './index'

export function listAllTasks() {
  return service({ url: '/api/tasks/list', method: 'get' })
}
