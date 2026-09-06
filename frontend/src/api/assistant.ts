import { getJson, requestJson } from './http'
import type { AgentConversation, AssistantStatus, ConfirmActionRequest, MessageRequest } from '@/types/assistant'

interface ActionResponse {
  success: boolean
  message: string
  conversation: AgentConversation
}

export const assistantApi = {
  sendMessage(data: MessageRequest): Promise<AgentConversation> {
    return requestJson<AgentConversation>('/assistant/query/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  confirmAction(data: ConfirmActionRequest): Promise<AgentConversation> {
    return requestJson<ActionResponse>('/assistant/confirm/', {
      method: 'POST',
      body: JSON.stringify(data),
    }).then((response) => response.conversation)
  },
  rejectAction(data: ConfirmActionRequest): Promise<AgentConversation> {
    return requestJson<ActionResponse>('/assistant/confirm/', {
      method: 'POST',
      body: JSON.stringify(data),
    }).then((response) => response.conversation)
  },
  getHistory(): Promise<AgentConversation[]> {
    return getJson<AgentConversation[]>('/assistant/conversations/').then((items) => [...items].reverse())
  },
  getStatus(): Promise<AssistantStatus> {
    return getJson<AssistantStatus>('/assistant/status/')
  },
}
