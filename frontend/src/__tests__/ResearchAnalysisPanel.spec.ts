import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import ResearchAnalysisPanel from '@/components/research/analysis/ResearchAnalysisPanel.vue'
import { RESEARCH_ANALYSIS_FIELDS } from '@/types/research'


const emptyAnalysis = {
  participants: [],
  researchTopics: [],
  aiLiteracyDimensions: [],
  teachingStrategies: [],
  intervention: null,
  assessmentTools: [],
  mainFindings: [],
  limitations: [],
  teachingImplications: null,
}


describe('ResearchAnalysisPanel status and scope', () => {
  it('shows a failed generation as a retryable technical failure, not normal readiness', async () => {
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
    expect(wrapper.text()).toContain('论文文档与知识索引已就绪 · AI结构化解析失败，可重新分析')
    expect(wrapper.text()).toContain('重新分析')
    expect(wrapper.text()).not.toContain('0/9')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('reanalyze')).toHaveLength(1)
  })

  it('uses the exact same nine-field configuration for display and editing', () => {
    expect(RESEARCH_ANALYSIS_FIELDS).toHaveLength(9)
    expect(RESEARCH_ANALYSIS_FIELDS.map(({ key, label }) => ({ key, label }))).toEqual([
      { key: 'participants', label: '研究对象' },
      { key: 'researchTopics', label: '研究问题/主题' },
      { key: 'aiLiteracyDimensions', label: '能力重点' },
      { key: 'teachingStrategies', label: '教学策略' },
      { key: 'intervention', label: '干预周期/实施时长' },
      { key: 'assessmentTools', label: '评价工具' },
      { key: 'mainFindings', label: '主要研究发现' },
      { key: 'limitations', label: '研究局限' },
      { key: 'teachingImplications', label: '教学启示' },
    ])
  })

  it('displays multiple topics, general capabilities, and teaching implications', () => {
    const wrapper = shallowMount(ResearchAnalysisPanel, {
      props: {
        analysis: { ...emptyAnalysis, researchTopics: ['问题一', '问题二'], aiLiteracyDimensions: ['Design Thinking', 'Knowledge Building'], teachingImplications: '使用真实任务' },
        readinessScore: 100, readinessStatus: 'READY', missingRequiredFields: [], saving: false,
        generationStatus: 'READY', scope: 'PROJECT', sourceLabel: 'all',
      },
    })
    const values = wrapper.findAllComponents({ name: 'AnalysisFieldItem' }).map((item) => item.props('value'))
    expect(values).toContain('问题一；问题二')
    expect(values).toContain('Design Thinking；Knowledge Building')
    expect(values).toContain('使用真实任务')
    expect(wrapper.text()).toContain('3/9')
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
