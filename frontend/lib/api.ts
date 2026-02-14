/* DeepDistill API 客户端 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006'

export async function fetchHealth() {
  const res = await fetch(`${API_URL}/health`)
  return res.json()
}

export async function fetchTasks(limit = 20) {
  const res = await fetch(`${API_URL}/api/tasks?limit=${limit}`)
  return res.json()
}

export async function fetchTask(taskId: string) {
  const res = await fetch(`${API_URL}/api/tasks/${taskId}`)
  return res.json()
}

export async function uploadFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_URL}/api/process`, {
    method: 'POST',
    body: formData,
  })
  return res.json()
}

export async function deleteTask(taskId: string) {
  const res = await fetch(`${API_URL}/api/tasks/${taskId}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || '删除失败')
  }
  return res.json()
}

export async function fetchConfig() {
  const res = await fetch(`${API_URL}/api/config`)
  return res.json()
}
