import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import ResearchAnalysisPanel from '@/components/research/analysis/ResearchAnalysisPanel.vue'


const emptyAnalysis = {
  participants: [],
  researchTopic: null,
  aiLiteracyDimensions: [],
  teachingStrategies: [],
  intervention: null,
  assessmentTools: [],
  mainFindings: [],
  limitations: [],
}


describe('ResearchAnalysisPanel status and scope', () => {
  it('shows a failed generation as a retryable technical failure, not normal 0/8 readiness', async () => {
    const wrapper = shallowMount(ResearchAnalysisPanel, {
      props: {
        analysis: emptyAnalysis,
        readinessScore: 15,
        readinessStatus: 'INCOMPLETE',
        missingRequiredFields: ['mainFindings'],
        saving: false,
        generationStatus: 'FAILED',
        scope: 'RESOURCE',
        sourceLabel: 'study.pdf',
      },
      global: { stubs: { 'el-button': { template: '<button><slot /></button>' } } },
    })

    expect(wrapper.text()).toContain('单篇论文解析')
    expect(wrapper.text()).toContain('来源：《study.pdf》')
    expect(wrapper.text()).toContain('研究解析失败')
    expect(wrapper.text()).toContain('重新分析')
    expect(wrapper.text()).not.toContain('0/8')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('reanalyze')).toHaveLength(1)
  })

  it('labels project analysis as all ready research resources', () => {
    const wrapper = shallowMount(ResearchAnalysisPanel, {
      props: {
        analysis: emptyAnalysis,
        readinessScore: 0,
        readinessStatus: 'INCOMPLETE',
        missingRequiredFields: [],
        saving: false,
        generationStatus: 'READY',
        scope: 'PROJECT',
        sourceLabel: '全部已就绪研究资源',
      },
    })
    expect(wrapper.text()).toContain('项目综合解析')
    expect(wrapper.text()).toContain('范围：全部已就绪研究资源')
  })
})
