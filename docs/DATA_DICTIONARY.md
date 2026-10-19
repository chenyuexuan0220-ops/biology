# 数据字典

共享表与学生私有表分开。私有记录通过 student_id 检索；JSON 在 PostgreSQL 使用 JSONB，时间以 UTC 存储。

## competencies

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(60) | False |  |
| name | VARCHAR(100) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## curriculums

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(100) | False |  |
| title | VARCHAR(200) | False |  |
| template_weeks | INTEGER | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## experiments

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(80) | False |  |
| title | VARCHAR(200) | False |  |
| description | TEXT | False |  |
| safety | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## knowledge_domains

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(50) | False |  |
| name | VARCHAR(100) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## misconceptions

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(80) | False |  |
| name | VARCHAR(200) | False |  |
| description | TEXT | False |  |
| correct_concept | TEXT | False |  |
| severity | INTEGER | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_sources

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(100) | False |  |
| name | VARCHAR(200) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## students

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| name | VARCHAR(100) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## users

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| email | VARCHAR(254) | False |  |
| password_hash | TEXT | False |  |
| name | VARCHAR(100) | False |  |
| is_admin | BOOLEAN | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## ai_contents

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| requested_by | VARCHAR(36) | False | users.id |
| purpose | VARCHAR(40) | False |  |
| content | JSON | False |  |
| trace | JSON | False |  |
| status | VARCHAR(30) | False |  |
| reviewer_id | VARCHAR(36) | True | users.id |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## audit_logs

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| actor_id | VARCHAR(36) | False | users.id |
| student_id | VARCHAR(36) | True | students.id |
| action | VARCHAR(80) | False |  |
| details | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## curriculum_units

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| curriculum_id | VARCHAR(36) | False | curriculums.id |
| sequence | INTEGER | False |  |
| title | VARCHAR(200) | False |  |
| content | TEXT | False |  |
| knowledge_ids | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## experiment_steps

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| experiment_id | VARCHAR(36) | False | experiments.id |
| sequence | INTEGER | False |  |
| instruction | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## experiment_variables

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| experiment_id | VARCHAR(36) | False | experiments.id |
| name | VARCHAR(200) | False |  |
| kind | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## knowledge_points

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(100) | False |  |
| name | VARCHAR(100) | False |  |
| description | TEXT | False |  |
| domain_id | VARCHAR(36) | False | knowledge_domains.id |
| parent_id | VARCHAR(36) | True | knowledge_points.id |
| level | INTEGER | False |  |
| goals | JSON | False |  |
| status | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## learning_contexts

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| education_stage | VARCHAR(20) | False |  |
| school_grade | INTEGER | False |  |
| biology_level | VARCHAR(40) | False |  |
| competition_goal | VARCHAR(40) | False |  |
| target_exam_date | DATE | True |  |
| weekly_hours | FLOAT | False |  |
| preferred_learning_days | INTEGER | False |  |
| learning_preferences | JSON | False |  |
| status | VARCHAR(20) | False |  |
| updated_at | DATETIME | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_papers

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| code | VARCHAR(100) | False |  |
| source_id | VARCHAR(36) | False | question_sources.id |
| title | VARCHAR(200) | False |  |
| year | INTEGER | True |  |
| metadata_json | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## student_competency_mastery

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| competency_id | VARCHAR(36) | False | competencies.id |
| score | FLOAT | False |  |
| confidence | FLOAT | False |  |
| evidence_count | INTEGER | False |  |
| recent_score | FLOAT | False |  |
| updated_at | DATETIME | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## user_students

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| user_id | VARCHAR(36) | False | users.id |
| student_id | VARCHAR(36) | False | students.id |
| role | VARCHAR(20) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## diagnostics

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| learning_context_id | VARCHAR(36) | False | learning_contexts.id |
| question_ids | JSON | False |  |
| answers | JSON | False |  |
| result | JSON | True |  |
| status | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## knowledge_edges

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| source_knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| target_knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| relation_type | VARCHAR(30) | False |  |
| weight | FLOAT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## knowledge_levels

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| level | INTEGER | False |  |
| objective | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## learning_objectives

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| unit_id | VARCHAR(36) | False | curriculum_units.id |
| text | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## learning_resources

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| title | VARCHAR(200) | False |  |
| content | TEXT | False |  |
| min_grade | INTEGER | False |  |
| max_grade | INTEGER | False |  |
| level | INTEGER | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## questions

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| paper_id | VARCHAR(36) | False | question_papers.id |
| source_question_no | INTEGER | False |  |
| question_type | VARCHAR(40) | False |  |
| stem | TEXT | True |  |
| answer | JSON | True |  |
| explanation | TEXT | True |  |
| competition_difficulty | INTEGER | False |  |
| learning_difficulty | INTEGER | False |  |
| conceptual_difficulty | INTEGER | False |  |
| prerequisite_depth | INTEGER | False |  |
| data_complexity | INTEGER | False |  |
| mathematical_complexity | INTEGER | False |  |
| abstraction_level | INTEGER | False |  |
| estimated_minutes | INTEGER | False |  |
| status | VARCHAR(30) | False |  |
| metadata_json | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## student_knowledge_mastery

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| scores | JSON | False |  |
| overall_score | FLOAT | False |  |
| confidence | FLOAT | False |  |
| exposure_count | INTEGER | False |  |
| correct_count | INTEGER | False |  |
| incorrect_count | INTEGER | False |  |
| recent_accuracy | FLOAT | False |  |
| forgetting_risk | FLOAT | False |  |
| last_review_at | DATETIME | True |  |
| next_review_at | DATETIME | True |  |
| updated_at | DATETIME | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## weekly_plans

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| learning_context_id | VARCHAR(36) | False | learning_contexts.id |
| week_no | INTEGER | False |  |
| start_date | DATE | False |  |
| end_date | DATE | False |  |
| objectives | JSON | False |  |
| estimated_minutes | INTEGER | False |  |
| status | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## daily_tasks

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| weekly_plan_id | VARCHAR(36) | False | weekly_plans.id |
| task_date | DATE | False |  |
| task_type | VARCHAR(30) | False |  |
| title | VARCHAR(200) | False |  |
| description | TEXT | False |  |
| knowledge_ids | JSON | False |  |
| question_ids | JSON | False |  |
| estimated_minutes | INTEGER | False |  |
| priority | FLOAT | False |  |
| reason | JSON | False |  |
| mastery_target | FLOAT | False |  |
| status | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_competency

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| question_id | VARCHAR(36) | False | questions.id |
| competency_id | VARCHAR(36) | False | competencies.id |
| weight | FLOAT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_knowledge

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| question_id | VARCHAR(36) | False | questions.id |
| knowledge_id | VARCHAR(36) | False | knowledge_points.id |
| relation_type | VARCHAR(30) | False |  |
| importance | FLOAT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_options

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| question_id | VARCHAR(36) | False | questions.id |
| label | VARCHAR(10) | False |  |
| text | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_variants

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| parent_question_id | VARCHAR(36) | False | questions.id |
| content | JSON | False |  |
| status | VARCHAR(30) | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## learning_events

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| learning_context_id | VARCHAR(36) | False | learning_contexts.id |
| task_id | VARCHAR(36) | True | daily_tasks.id |
| question_id | VARCHAR(36) | True | questions.id |
| knowledge_id | VARCHAR(36) | True | knowledge_points.id |
| competency_id | VARCHAR(36) | True | competencies.id |
| event_type | VARCHAR(40) | False |  |
| payload | JSON | False |  |
| duration_seconds | INTEGER | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## tutor_sessions

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| learning_context_id | VARCHAR(36) | False | learning_contexts.id |
| question_id | VARCHAR(36) | True | questions.id |
| task_id | VARCHAR(36) | True | daily_tasks.id |
| hint_level | INTEGER | False |  |
| messages | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## experiment_observations

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| experiment_id | VARCHAR(36) | False | experiments.id |
| event_id | VARCHAR(36) | False | learning_events.id |
| data | JSON | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## mastery_evidence

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| event_id | VARCHAR(36) | False | learning_events.id |
| target_type | VARCHAR(20) | False |  |
| target_id | VARCHAR(36) | False |  |
| cognitive_level | INTEGER | False |  |
| delta | FLOAT | False |  |
| is_correct | BOOLEAN | False |  |
| explanation | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## question_attempts

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| question_id | VARCHAR(36) | False | questions.id |
| task_id | VARCHAR(36) | True | daily_tasks.id |
| event_id | VARCHAR(36) | False | learning_events.id |
| answer | JSON | False |  |
| is_correct | BOOLEAN | False |  |
| confidence | FLOAT | False |  |
| time_seconds | INTEGER | False |  |
| hint_count | INTEGER | False |  |
| attempt_no | INTEGER | False |  |
| error_type | VARCHAR(50) | True |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |

## experiment_results

| 字段 | 类型 | 可空 | 外键 |
| --- | --- | --- | --- |
| student_id | VARCHAR(36) | False | students.id |
| observation_id | VARCHAR(36) | False | experiment_observations.id |
| conclusion | TEXT | False |  |
| id | VARCHAR(36) | False |  |
| created_at | DATETIME | False |  |
