import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ResearchChatPanel from '@/components/research/chat/ResearchChatPanel.vue'

const baseProps = {
  resources: [],
  selectedResources: [],
  messages: [],
  sending: false,
  processing: false,
  evidenceReady: false,
  analysis: null,
}

describe('ResearchChatPanel', () => {
  it('fills but does not send an exploration scaffold question', async () => {
    const sendMessage = vi.fn()
    const wrapper = mount(ResearchChatPanel, { props: { ...baseProps, hasActiveSession: true, sendMessage } })
    await wrapper.get('[aria-label="研究探索脚手架"] button').trigger('click')
    expect(wrapper.get<HTMLTextAreaElement>('textarea').element.value).toBe('围绕当前课程主题，已有研究主要关注哪些教学或学习问题？')
    expect(sendMessage).not.toHaveBeenCalled()
  })

  it('marks completed analysis dimensions in the scaffold', () => {
    const wrapper = mount(ResearchChatPanel, { props: { ...baseProps, hasActiveSession: true, sendMessage: vi.fn(), analysis: { participants: ['五年级'], researchTopic: null, aiLiteracyDimensions: [], teachingStrategies: [], intervention: null, assessmentTools: [], mainFindings: [], limitations: [], teacherConfirmed: false, fieldSources: {} } } })
    expect(wrapper.get('[aria-label="研究探索脚手架"]').text()).toContain('✓')
    const chips = wrapper.findAll('.scaffold-chip')
    expect(chips[chips.length - 1]?.classes()).toContain('complete')
    expect(chips[chips.length - 1]?.text()).toContain('学习者')
  })
  it('does not present research resources as a requirement for sending', async () => {
    const wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: false, sendMessage: vi.fn() },
    })

    await wrapper.get('textarea').setValue('hello，测试')
    expect(wrapper.get<HTMLButtonElement>('.send-button').element.disabled).toBe(true)
    expect(wrapper.text()).toContain('正在准备研教对话会话')

    await wrapper.setProps({ hasActiveSession: true })
    expect(wrapper.get<HTMLButtonElement>('.send-button').element.disabled).toBe(false)
  })

  it('offers direct knowledge-base conversation before any resource is uploaded', () => {
    const wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: true, sendMessage: vi.fn() },
    })

    expect(wrapper.text()).toContain('你可以直接向研教智联助手提问')
    expect(wrapper.text()).toContain('上传论文进行专项研究分析')
  })

  it('keeps the input when sending fails', async () => {
    const sendMessage = vi.fn().mockResolvedValue(false)
    const wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: true, sendMessage },
    })

    await wrapper.get('textarea').setValue('hello，测试')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(sendMessage).toHaveBeenCalledWith('hello，测试')
    expect(wrapper.get<HTMLTextAreaElement>('textarea').element.value).toBe('hello，测试')
  })

  it('clears the input only after sending succeeds', async () => {
    const sendMessage = vi.fn().mockResolvedValue(true)
    const wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: true, sendMessage },
    })

    await wrapper.get('textarea').setValue('hello，测试')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(wrapper.get<HTMLTextAreaElement>('textarea').element.value).toBe('')
  })

  it('renders restored assistant history immediately without a typing cursor', () => {
    const wrapper = mount(ResearchChatPanel, {
      props: {
        ...baseProps,
        hasActiveSession: true,
        sendMessage: vi.fn(),
        messages: [{
          messageId: 1,
          role: 'ASSISTANT',
          messageType: 'TEXT',
          content: '**完整历史回复**',
          createdAt: '2026-09-07T00:00:00Z',
        }],
      },
    })

    expect(wrapper.text()).toContain('完整历史回复')
    expect(wrapper.find('.typing-cursor').exists()).toBe(false)
  })

  it('plays a cursor only for the assistant reply returned from the current send', async () => {
    vi.useFakeTimers()
    let wrapper: any
    const reply = '**新的 AI 回复**'
    const sendMessage = vi.fn(async () => {
      await wrapper.setProps({
        messages: [
          {
            messageId: 2,
            role: 'USER',
            messageType: 'TEXT',
            content: '你好',
            createdAt: '2026-09-07T00:00:00Z',
          },
          {
            messageId: 3,
            role: 'ASSISTANT',
            messageType: 'TEXT',
            content: reply,
            createdAt: '2026-09-07T00:00:01Z',
          },
        ],
      })
      return true
    })
    wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: true, sendMessage },
    })

    await wrapper.get('textarea').setValue('你好')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.typing-cursor').exists()).toBe(true)
    await vi.runAllTimersAsync()
    await flushPromises()
    expect(wrapper.text()).toContain('新的 AI 回复')
    expect(wrapper.find('.typing-cursor').exists()).toBe(false)
    expect(wrapper.find('.assistant-markdown strong').text()).toBe('新的 AI 回复')
    vi.useRealTimers()
  })

  it('cancels an active typewriter when the session messages are replaced', async () => {
    vi.useFakeTimers()
    let wrapper: any
    const sendMessage = vi.fn(async () => {
      await wrapper.setProps({
        messages: [{
          messageId: 4,
          role: 'ASSISTANT',
          messageType: 'TEXT',
          content: '这段回复不应写入新会话。',
          createdAt: '2026-09-07T00:00:00Z',
        }],
      })
      return true
    })
    wrapper = mount(ResearchChatPanel, {
      props: { ...baseProps, hasActiveSession: true, sendMessage },
    })

    await wrapper.get('textarea').setValue('你好')
    await wrapper.get('.send-button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.typing-cursor').exists()).toBe(true)

    await wrapper.setProps({ messages: [] })
    await flushPromises()
    await vi.runAllTimersAsync()
    expect(wrapper.find('.typing-cursor').exists()).toBe(false)
    vi.useRealTimers()
  })
})
