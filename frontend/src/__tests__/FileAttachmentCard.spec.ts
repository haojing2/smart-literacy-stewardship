import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import FileAttachmentCard from '@/components/research/chat/FileAttachmentCard.vue'
import type { ResearchResource } from '@/types/research'

function statusText(processingStatus: ResearchResource['processingStatus'], indexStatus?: ResearchResource['indexStatus']) {
  const wrapper = shallowMount(FileAttachmentCard, {
    props: {
      resource: {
        resourceId: 1,
        fileName: 'study.pdf',
        mimeType: 'application/pdf',
        fileSize: 1024,
        processingStatus,
        indexStatus,
      },
    },
  })
  return wrapper.text()
}

describe('FileAttachmentCard processing labels', () => {
  it('separates text extraction from vectorization and retrieval indexing', () => {
    expect(statusText('TEXT_EXTRACTED', 'indexing')).toContain('文本提取已完成 · 正在向量化与建立检索索引…')
    expect(statusText('TEXT_EXTRACTED', 'ready')).toContain('文本提取已完成 · 论文向量化与检索已完成')
    expect(statusText('TEXT_EXTRACTED', 'error')).toContain('文本提取已完成 · 向量化与检索索引失败')
  })

  it('does not treat legacy ANALYZED as retrieval-index completion', () => {
    expect(statusText('ANALYZED', 'pending')).toContain('研究资源处理中')
  })
})
