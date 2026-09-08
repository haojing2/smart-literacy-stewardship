from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.models.course_design import ProjectAssessment, ProjectObjective, ProjectPedagogy
from app.models.course_project import CourseProject
from app.models.user import SysUser
from app.schemas.course_design import CourseContextDiagnosis, CourseObjectiveGenerationResult, CourseObjectiveProposal
from app.schemas.project import ProjectContextRequest
from app.services.course_context_service import CourseContextService
from app.services.course_design_service import CourseDesignService
from app.services.course_objective_service import CourseObjectiveService
from app.services.course_pedagogy_service import CoursePedagogyService
from app.services.course_assessment_service import CourseAssessmentService


class ObjectiveProvider:
    async def generate_course_objectives(self, _request):
        return CourseObjectiveGenerationResult(objectives=[
            CourseObjectiveProposal(content="识别待核验信息", rationale="可观察"),
            CourseObjectiveProposal(content="使用证据修订回答", rationale="可评价"),
        ])


def _research_ready_project(db: Session) -> tuple[SysUser, CourseProject]:
    user = SysUser(username="course-teacher", password="secret", display_name="Teacher", role="TEACHER")
    db.add(user)
    db.flush()
    project = CourseProject(
        user_id=user.id, title="AI 信息核验", topic="信息可信度", project_type="NEW_TOPIC",
        grade=4, lesson_minutes=40, class_size=42, student_experience="有简单问答经验",
        devices_json=["平板"], workflow_state="RESEARCH_READY", stale_sections_json=[],
        context_diagnosis_json={"coreProblem": "缺少核验意识", "existingFoundation": "会提问", "learningDifficulties": ["比较来源"], "constraints": ["设备有限"]},
    )
    db.add(project)
    db.commit()
    return user, project


def _context_payload() -> ProjectContextRequest:
    return ProjectContextRequest(grade=4, topic="信息可信度", lessonMinutes=40, classSize=42, studentExperience="有简单问答经验", deviceCondition="平板")


def test_research_ready_context_save_and_confirm_do_not_regress_workflow(db: Session) -> None:
    user, project = _research_ready_project(db)
    service = CourseContextService(db)
    saved = service.save_context(current_user_id=user.id, project_id=project.id, payload=_context_payload())
    assert saved["workflowState"] == "RESEARCH_READY"

    project.context_diagnosis_json = CourseContextDiagnosis(
        coreProblem="缺少核验意识", existingFoundation="会提问", learningDifficulties=["比较来源"], constraints=["设备有限"]
    ).model_dump(by_alias=True)
    db.commit()
    confirmed = service.confirm_context(current_user_id=user.id, project_id=project.id)
    assert confirmed["workflowState"] == "RESEARCH_READY"


def test_research_ready_starts_course_design_at_context_and_generates_objectives(db: Session) -> None:
    user, project = _research_ready_project(db)
    state = CourseDesignService(db).get_course_design_state(current_user_id=user.id, project_id=project.id)
    assert state["currentStep"] == 1

    objectives = asyncio.run(CourseObjectiveService(db).generate(
        current_user_id=user.id, project_id=project.id, provider=ObjectiveProvider()
    ))
    assert len(objectives) == 2
    db.refresh(project)
    assert project.workflow_state == "OBJECTIVE_PENDING"


def test_activity_ready_remains_on_blueprint_step_until_quality_check(db: Session) -> None:
    user, project = _research_ready_project(db)
    project.workflow_state = "ACTIVITY_READY"
    db.commit()
    state = CourseDesignService(db).get_course_design_state(current_user_id=user.id, project_id=project.id)
    assert state["currentStep"] == 5
    assert state["completedSteps"] == [1, 2, 3, 4]


def test_confirm_objectives_commits_transition_and_is_idempotent(db: Session) -> None:
    user, project = _research_ready_project(db)
    project.workflow_state = "OBJECTIVE_PENDING"
    db.add(ProjectObjective(project_id=project.id, content="识别待核验信息", sequence_no=1, standard_refs_json=[], literacy_refs_json=[], rationale="可观察", source_type="AI", teacher_action="ACCEPT", confirmed=False, version=1))
    db.commit()
    service = CourseObjectiveService(db)
    service.confirm(current_user_id=user.id, project_id=project.id)
    db.refresh(project)
    assert project.workflow_state == "OBJECTIVE_CONFIRMED"
    service.confirm(current_user_id=user.id, project_id=project.id)
    assert project.workflow_state == "OBJECTIVE_CONFIRMED"


def test_confirm_pedagogy_commits_transition_without_provider_call(db: Session) -> None:
    user, project = _research_ready_project(db)
    project.workflow_state = "PEDAGOGY_PENDING"
    db.add(ProjectPedagogy(project_id=project.id, primary_method_id=None, secondary_method_id=None, rationale="协作探究", suitable_for_json=[], risk_note=None, alternative_json=None, teacher_action="CUSTOM", confirmed=False, version=1, custom_name="协作探究", custom_description="小组协作", source_type="TEACHER"))
    db.commit()
    CoursePedagogyService(db).confirm(current_user_id=user.id, project_id=project.id)
    db.refresh(project)
    assert project.workflow_state == "PEDAGOGY_CONFIRMED"


def test_confirm_assessments_commits_transition_without_provider_call(db: Session) -> None:
    user, project = _research_ready_project(db)
    project.workflow_state = "ASSESSMENT_PENDING"
    objective = ProjectObjective(project_id=project.id, content="识别待核验信息", sequence_no=1, standard_refs_json=[], literacy_refs_json=[], rationale="可观察", source_type="AI", teacher_action="ACCEPT", confirmed=True, version=1)
    db.add(objective)
    db.flush()
    db.add(ProjectAssessment(project_id=project.id, objective_id=objective.id, task_content="完成核验记录", student_evidence_json=["记录"], criteria_json=["准确"], rationale="对齐目标", teacher_action=None, confirmed=False, version=1))
    db.commit()
    CourseAssessmentService(db).confirm(current_user_id=user.id, project_id=project.id)
    db.refresh(project)
    assert project.workflow_state == "ASSESSMENT_CONFIRMED"
