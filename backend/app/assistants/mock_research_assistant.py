from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator

from pydantic import BaseModel

from app.assistants.base import ResearchAssistantProvider
from app.schemas.research_assistant import (
    EvidenceCardInterpretation,
    EvidenceCardDraftResult,
    EvidenceCardGenerationRequest,
    EvidenceCardGenerationResponse,
    ResearchAnalysisRequest,
    ResearchAnalysisPatch,
    ResearchAnalysisResponse,
    ResearchAnalysisResult,
    ResearchAnalysisSupplementRequest,
    ResearchAnalysisSupplementResponse,
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchChatResult,
)
from app.schemas.course_design import (
    CourseContextDiagnosis,
    CourseContextDiagnosisRequest,
    CourseObjectiveGenerationRequest,
    CourseObjectiveGenerationResult,
    CourseObjectiveProposal,
    CoursePedagogyRecommendation,
    CoursePedagogyRecommendationRequest,
    CoursePedagogyRecommendationResult,
    CourseAssessmentGenerationRequest,
    CourseAssessmentGenerationResult,
    CourseAssessmentProposal,
    CourseActivityProposal,
    CourseActivityRegenerationRequest,
    CourseBlueprintGenerationRequest,
    CourseBlueprintGenerationResult,
    CourseQualityCheckProposal,
    CourseQualityCheckRequest,
    CourseQualityCheckResult,
)
from app.schemas.resource_creation import (
    ResourceBlockTransformProviderRequest,
    ResourceBlockTransformResult,
    ResourceRevisionProposal,
    ResourceRevisionProposalRequest,
    ResourceRevisionProposalResult,
    ResourceSettingsRecommendationRequest,
    ResourceSettingsRecommendationResult,
    TeachingResourceGenerationRequest,
    TeachingResourceGenerationResult,
    TeachingResourceReviewRequest,
    TeachingResourceReviewResult,
)


class MockResearchAssistant(ResearchAssistantProvider):
    """Deterministic local provider for development and automated tests."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def analyze_research(
        self, request: ResearchAnalysisRequest
    ) -> ResearchAnalysisResponse:
        fingerprint = self._fingerprint(request)
        normalized_text = self._normalize_text(
            request.analysis_evidence or request.extracted_text
        )
        topic = request.project_topic or self._first_line(normalized_text)
        result = ResearchAnalysisResult(
            research_topics=[topic] if topic else [],
            source_excerpt=normalized_text[:500],
            evidence_ready=False,
        )
        return ResearchAnalysisResponse(
            provider=self.provider_name,
            request_fingerprint=fingerprint,
            data=result,
        )

    async def supplement_research_analysis(
        self, request: ResearchAnalysisSupplementRequest
    ) -> ResearchAnalysisSupplementResponse:
        return ResearchAnalysisSupplementResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=ResearchAnalysisPatch(),
        )

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        fingerprint = self._fingerprint(request)
        analysis = request.analysis or ResearchAnalysisResult()
        patch = self._analysis_patch_from_message(request.message)
        subjects = (
            patch.research_subjects
            if patch and patch.research_subjects is not None
            else analysis.research_subjects
        )
        findings = (
            patch.main_findings
            if patch and patch.main_findings is not None
            else analysis.main_findings
        )
        teaching_strategies = analysis.teaching_strategies
        if not subjects:
            message = "当前研究对象尚未确认。你可以在右侧研究解析区补充研究对象。"
        elif not findings:
            message = "当前尚未形成主要研究结果，请补充论文中的核心研究发现。"
        elif not teaching_strategies:
            message = "当前尚未明确教学策略，请补充研究中的教学策略。"
        else:
            message = "当前核心研究信息已经较完整，可以进一步形成证据卡草稿。"
        result = ResearchChatResult(
            message=message,
            analysis_patch=patch,
            evidence_interpretations=[
                EvidenceCardInterpretation(
                    chunk_id=source.chunk_id,
                    evidence_meaning="该项目资料片段提供了与当前问题相关的研究信息。",
                    relation_to_question="该片段可作为回答当前教师问题的可核查依据。",
                    synthesis="应结合完整项目资料和教师课堂情境进一步核查与应用。",
                )
                for source in request.project_knowledge_sources
            ],
        )
        return ResearchChatResponse(
            provider=self.provider_name,
            request_fingerprint=fingerprint,
            data=result,
        )

    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        """Yield the normal mock reply in short pieces for UI streaming tests."""
        response = await self.chat(request)
        message = response.data.message
        for offset in range(0, len(message), 12):
            yield message[offset : offset + 12]

    async def generate_evidence_card(
        self, request: EvidenceCardGenerationRequest
    ) -> EvidenceCardGenerationResponse:
        fingerprint = self._fingerprint(request)
        analysis = request.analysis
        topic = analysis.research_topics[0] if analysis.research_topics else None
        title = f"{topic or request.source_file_name}（Mock 证据卡草稿）"
        result = EvidenceCardDraftResult(
            title=title,
            topic=topic,
            participants=self._join(analysis.research_subjects),
            main_finding=self._join(analysis.main_findings),
            limitation=self._join(analysis.limitations),
            teaching_implication=analysis.teaching_implications,
            source_document=request.source_file_name,
            source_text=analysis.source_excerpt,
            review_status="DRAFT",
        )
        return EvidenceCardGenerationResponse(
            provider=self.provider_name,
            request_fingerprint=fingerprint,
            data=result,
        )

    async def diagnose_course_context(
        self, request: CourseContextDiagnosisRequest
    ) -> CourseContextDiagnosis:
        constraints = [
            f"{request.lesson_minutes}分钟",
            f"{request.class_size}人",
            request.device_condition,
        ]
        if request.additional_requirements:
            constraints.append(request.additional_requirements)
        return CourseContextDiagnosis(
            core_problem=(
                f"围绕“{request.topic}”引导学生形成基于证据的信息判断，"
                "避免直接接受生成式 AI 输出。"
            ),
            existing_foundation=request.student_experience,
            learning_difficulties=[
                "识别 AI 回答中需要进一步核验的具体信息。",
                "比较不同信息来源并说明可信度判断依据。",
                "依据证据修正原有判断，而非直接采纳 AI 答案。",
            ],
            constraints=constraints,
        )

    async def generate_course_objectives(
        self, request: CourseObjectiveGenerationRequest
    ) -> CourseObjectiveGenerationResult:
        standard_refs = [item["id"] for item in request.curriculum_standards if isinstance(item.get("id"), int)]
        literacy_refs = [item["id"] for item in request.ai_literacy_items if isinstance(item.get("id"), int)]
        topic = request.topic
        return CourseObjectiveGenerationResult(
            objectives=[
                CourseObjectiveProposal(content=f"能够识别{topic}中需要进一步核验的关键信息，并说明核验理由。", rationale="聚焦可观察的信息判断行为。", standard_refs=standard_refs[:2], literacy_refs=literacy_refs[:2]),
                CourseObjectiveProposal(content=f"能够使用至少两个适当的信息来源核验{topic}相关内容，并记录证据依据。", rationale="要求学生实施可评价的多来源核验。", standard_refs=standard_refs[:2], literacy_refs=literacy_refs[:2]),
                CourseObjectiveProposal(content=f"能够依据核验获得的证据修正对{topic}的判断，并解释修正理由。", rationale="关注基于证据的判断修正过程。", standard_refs=standard_refs[:2], literacy_refs=literacy_refs[:2]),
            ]
        )

    async def recommend_course_pedagogy(
        self, request: CoursePedagogyRecommendationRequest
    ) -> CoursePedagogyRecommendationResult:
        primary = request.methods[0]
        alternatives = request.methods[1:3]
        components = ["真实问题情境", "小组协作", "多来源核验", "证据比较", "反思修订"]
        return CoursePedagogyRecommendationResult(
            recommended=CoursePedagogyRecommendation(
                method_id=primary["id"] if isinstance(primary.get("id"), int) else None,
                name="证据驱动的问题探究",
                rationale="围绕真实信息判断任务组织学生搜集、比较并解释证据，支持已确认目标。",
                components=components,
            ),
            alternatives=[
                CoursePedagogyRecommendation(
                    method_id=item["id"] if isinstance(item.get("id"), int) else None,
                    name=str(item.get("name") or "备选教学法"),
                    rationale=str(item.get("description") or "适合作为当前课程的备选组织方式。"),
                    components=["问题任务", "同伴讨论", "反思总结"],
                )
                for item in alternatives
            ],
        )

    async def generate_course_assessments(
        self, request: CourseAssessmentGenerationRequest
    ) -> CourseAssessmentGenerationResult:
        return CourseAssessmentGenerationResult(
            assessments=[
                CourseAssessmentProposal(
                    objective_id=int(objective["id"]),
                    task_content=f"围绕“{objective['content']}”完成一项信息判断与证据说明任务。",
                    student_evidence=["完成的任务记录", "所用信息来源或证据", "基于证据的判断说明"],
                    criteria=["目标要求的行为能够被观察", "证据与判断具有明确对应关系", "能够说明判断或修正理由"],
                    rationale="任务直接要求学生展示目标所要求的行为与证据。",
                )
                for objective in request.objectives
            ]
        )

    async def generate_course_blueprint(
        self, request: CourseBlueprintGenerationRequest
    ) -> CourseBlueprintGenerationResult:
        minutes = int(request.context.get("lessonMinutes") or 40)
        durations = self._blueprint_durations(minutes)
        objective_refs = [int(item["id"]) for item in request.objectives]
        activities = [
            CourseActivityProposal(
                name="真实问题导入",
                duration=durations[0],
                core_task="比较两条与主题相关的信息，提出需要核验的问题。",
                teacher_action="呈现真实情境并引导学生明确核验任务。",
                student_action="独立判断信息可信度并说明初步理由。",
                ai_role="QUESTION_SUPPORT",
                assessment="记录学生提出的核验问题。",
                scaffolds=["问题清单"],
                objective_refs=objective_refs,
            ),
            CourseActivityProposal(
                name="证据搜集与比较",
                duration=durations[1],
                core_task="小组搜集多来源证据并比较其可信度。",
                teacher_action="示范来源核验步骤，巡视并追问证据依据。",
                student_action="小组分工搜集、记录和比较证据。",
                ai_role="EVIDENCE_SUPPORT",
                assessment="检查小组证据比较记录。",
                scaffolds=["来源核验表", "证据比较表"],
                objective_refs=objective_refs,
            ),
            CourseActivityProposal(
                name="证据核验",
                duration=durations[2],
                core_task="依据证据修正原判断，形成可说明的结论。",
                teacher_action="组织小组交流并引导基于证据修正判断。",
                student_action="引用证据说明判断或修正理由。",
                ai_role="EVIDENCE_SUPPORT",
                assessment="评价学生的证据—判断说明。",
                scaffolds=["论证句式"],
                objective_refs=objective_refs,
            ),
            CourseActivityProposal(
                name="反思迁移",
                duration=durations[3],
                core_task="总结核验策略并应用到新的信息情境。",
                teacher_action="组织反思，提供新的迁移任务。",
                student_action="完成迁移任务并反思核验策略。",
                ai_role="REFLECTION_SUPPORT",
                assessment="收集迁移任务与反思卡。",
                scaffolds=["反思提示卡"],
                objective_refs=objective_refs,
            ),
        ]
        return CourseBlueprintGenerationResult(activities=activities)

    async def regenerate_course_activity(
        self, request: CourseActivityRegenerationRequest
    ) -> CourseActivityProposal:
        activity = request.activity
        return activity.model_copy(
            update={
                "core_task": f"{activity.core_task}（已结合前后活动衔接重新组织）",
                "teacher_action": f"{activity.teacher_action} 并明确承接前一环节、指向后一环节。",
            }
        )

    async def check_course_quality(
        self, request: CourseQualityCheckRequest
    ) -> CourseQualityCheckResult:
        first_activity = request.activities[0]
        return CourseQualityCheckResult(
            checks=[
                CourseQualityCheckProposal(
                    check_type="COGNITIVE_LOAD",
                    status="PASS",
                    reason="活动任务按导入、比较、核验和迁移逐步展开。",
                    evidence={"reviewedDimension": "认知负荷"},
                ),
                CourseQualityCheckProposal(
                    check_type="ACTIVITY_COMPLEXITY",
                    status="PASS",
                    reason="活动复杂度与课时安排相匹配。",
                    evidence={"reviewedDimension": "活动复杂度"},
                ),
                CourseQualityCheckProposal(
                    check_type="ADD_SCAFFOLD",
                    status="WARNING",
                    issue="首个活动可增加更明确的核验支架。",
                    reason="复杂证据核验任务需要显性步骤支持。",
                    suggestion="为首个活动添加问题与证据核验步骤清单。",
                    evidence={
                        "target": {
                            "type": "ACTIVITY", "id": first_activity["id"],
                            "scaffold": "问题与证据核验步骤清单",
                        }
                    },
                ),
                CourseQualityCheckProposal(
                    check_type="PROCESS_ASSESSMENT",
                    status="PASS",
                    issue=None,
                    reason="每个目标均关联过程性评价证据。",
                    suggestion=None,
                    evidence={"reviewedDimension": "过程性评价"},
                ),
                CourseQualityCheckProposal(
                    check_type="OBJECTIVE_ACTIVITY_ALIGNMENT_AI",
                    status="PASS",
                    reason="活动目标引用与设计目标一致。",
                    evidence={"reviewedDimension": "目标—活动一致性"},
                ),
                CourseQualityCheckProposal(
                    check_type="OBJECTIVE_ASSESSMENT_ALIGNMENT_AI",
                    status="PASS",
                    reason="评价任务直接测量目标行为。",
                    evidence={"reviewedDimension": "目标—评价一致性"},
                ),
                CourseQualityCheckProposal(
                    check_type="EVIDENCE_FIDELITY",
                    status="PASS",
                    reason="建议仅使用项目中已确认的研究证据。",
                    evidence={"reviewedDimension": "Evidence Fidelity"},
                ),
            ]
        )

    async def generate_teaching_resource(
        self, request: TeachingResourceGenerationRequest
    ) -> TeachingResourceGenerationResult:
        type_blocks = {
            "TEACHER_GUIDE": {"key": "activity-flow", "title": "教学活动流程", "content": request.activities},
            "WORKSHEET": {"key": "student-task", "title": "学生学习任务与记录", "content": request.activities},
            "TASK_CARD": {"key": "task-output", "title": "任务与最终产出", "content": request.activities},
            "AI_CASE": {"key": "human-ai-dialogue", "title": "Human-AI 对话", "content": [{"human": "提出观点", "ai": "提供可核查的建议"}]},
            "DISCUSSION": {"key": "discussion-question", "title": "讨论问题", "content": ["哪些证据支持你的判断？"]},
            "ASSESSMENT": {"key": "assessment-criteria", "title": "评价指标", "content": request.assessments},
            "REFLECTION": {"key": "reflection-question", "title": "反思问题", "content": ["我依据什么证据形成判断？"]},
        }
        return TeachingResourceGenerationResult.model_validate({
            "title": f"{request.project.title}：{request.resource_type.value}",
            "content": {
                "title": f"{request.project.title}：{request.resource_type.value}",
                "blocks": [
                    {"key": "course-context", "title": "课程依据", "content": {"topic": request.project.topic or "", "objectives": request.objectives}},
                    type_blocks[request.resource_type.value],
                ],
                "metadata": {"provider": self.provider_name, "resourceType": request.resource_type.value},
            },
            "changeSummary": "Generated by Mock AI",
        })

    async def recommend_resource_settings(
        self, request: ResourceSettingsRecommendationRequest
    ) -> ResourceSettingsRecommendationResult:
        return ResourceSettingsRecommendationResult.model_validate({"recommendations": {
            "grade": request.project.grade,
            "lessonMinutes": request.project.lesson_minutes,
            "studentLevel": request.project.student_level,
            "devices": request.project.devices,
            "resourceStyle": "CLASSROOM_READY",
            "selectedTypes": [item.value for item in request.selected_types],
        }})

    async def transform_resource_block(
        self, request: ResourceBlockTransformProviderRequest
    ) -> ResourceBlockTransformResult:
        content = request.current_content.model_dump(mode="json", by_alias=True)
        metadata = dict(content.get("metadata") or {})
        metadata.update({"provider": self.provider_name, "transform": request.action, "instruction": request.instruction or ""})
        content["metadata"] = metadata
        return ResourceBlockTransformResult.model_validate({"content": content, "changeSummary": f"{request.action} requested by teacher"})

    async def review_teaching_resource(
        self, request: TeachingResourceReviewRequest
    ) -> TeachingResourceReviewResult:
        proposal = ResourceRevisionProposal(
            suggestion_type="AI_REVIEW", target_block_key=request.target_block_key,
            issue="Mock AI review recommends improving instructional clarity.",
            reason=request.instruction or "Review requested by teacher.",
            suggested_content="Mock AI suggestion; teacher approval is required.",
            proposed_content=request.content,
        )
        return TeachingResourceReviewResult(proposals=[proposal])

    async def propose_resource_revision(
        self, request: ResourceRevisionProposalRequest
    ) -> ResourceRevisionProposalResult:
        return ResourceRevisionProposalResult(proposal=ResourceRevisionProposal(
            suggestion_type="AI_REVISION", target_block_key=request.target_block_key,
            issue=None, reason=request.user_request,
            suggested_content="Mock AI proposal; teacher approval is required.",
            proposed_content=request.base_content,
        ))

    @staticmethod
    def _blueprint_durations(minutes: int) -> list[int]:
        base = [20, 30, 30, 20]
        allocated = [max(1, minutes * weight // 100) for weight in base]
        allocated[-1] += minutes - sum(allocated)
        return allocated

    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        canonical = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _first_line(value: str) -> str:
        return value[:120]

    @staticmethod
    def _join(values: list[str]) -> str | None:
        return "；".join(values) if values else None

    @classmethod
    def _analysis_patch_from_message(
        cls, message: str
    ) -> ResearchAnalysisPatch | None:
        subjects = cls._extract_labeled_value(
            message,
            ("研究对象", "参与者", "participants"),
        )
        findings = cls._extract_labeled_value(
            message,
            ("主要研究结果", "主要结果", "主要发现", "main findings"),
        )
        if subjects is None and findings is None:
            return None
        return ResearchAnalysisPatch(
            research_subjects=[subjects] if subjects else None,
            main_findings=[findings] if findings else None,
        )

    @staticmethod
    def _extract_labeled_value(
        message: str, labels: tuple[str, ...]
    ) -> str | None:
        for line in message.splitlines():
            normalized_line = line.strip()
            for label in labels:
                match = re.fullmatch(
                    rf"{re.escape(label)}\s*(?:是|[:：])\s*(.+)",
                    normalized_line,
                    flags=re.IGNORECASE,
                )
                if match and (value := match.group(1).strip()):
                    return value
        return None
