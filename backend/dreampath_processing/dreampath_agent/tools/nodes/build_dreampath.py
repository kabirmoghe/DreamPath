"""
Build DreamPath node — deterministic scheduling, no LLM call.

Reads curated courses and activities from state, runs scheduling algorithms
to build CoursePath and ClubPath. Reuses helpers from rebuild.py.
"""

from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.course_relationship_handling import (
    build_prereq_tree,
    construct_course,
    is_major_course,
)
from dreampath_processing.courses.coursepath_agent.operation_tools import (
    compute_diff,
    snapshot_path,
    summarize_diff,
)
from dreampath_processing.courses.schedule_modules.course import COMPLEMENTARY, MAJOR
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
from dreampath_processing.dreampath_agent.dreampath_types import (
    ActivityRec,
    CourseRec,
    DreamPathAgentState,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain


def filter_and_prioritize_recommendations(
    recs: list[CourseRec],
    major: str,
    target_count: int = 20,
    major_floor_proportion: float = 0.6,
) -> list[CourseRec]:
    """
    Filter and prioritize course recommendations.

    1. Deduplicate by course_code (merge aligned_parameters)
    2. Try to maintain 60% major courses (skip if not achievable)
    3. Sort by parameter priority (interests + post_grad > interests OR post_grad > career only)
    4. Cap at target_count
    """
    # Deduplicate: merge aligned_parameters for duplicate course codes
    deduped: dict[str, CourseRec] = {}
    for rec in recs:
        if rec.course_code in deduped:
            deduped[rec.course_code].aligned_parameters |= rec.aligned_parameters
        else:
            deduped[rec.course_code] = rec
    recs = list(deduped.values())

    major_courses = [r for r in recs if is_major_course(r.course_code, major)]
    non_major_courses = [r for r in recs if not is_major_course(r.course_code, major)]

    def priority_score(r: CourseRec) -> int:
        has_interests = "interests" in r.aligned_parameters
        has_post_grad = "post_grad" in r.aligned_parameters
        if has_interests and has_post_grad:
            return 2
        elif has_interests or has_post_grad:
            return 1
        return 0

    major_courses.sort(key=priority_score, reverse=True)
    non_major_courses.sort(key=priority_score, reverse=True)

    major_floor = int(major_floor_proportion * target_count)

    if len(major_courses) >= major_floor:
        result = major_courses[:major_floor]
        remaining_slots = target_count - len(result)
        result.extend(non_major_courses[:remaining_slots])
        if len(result) < target_count:
            additional_majors = major_courses[major_floor:target_count - len(result) + major_floor]
            result.extend(additional_majors)
    else:
        result = major_courses[:]
        remaining_slots = target_count - len(result)
        result.extend(non_major_courses[:remaining_slots])

    result.sort(key=priority_score, reverse=True)
    return result[:target_count]


async def build_dreampath_node(state: DreamPathAgentState, config, *, writer=None) -> dict:
    """
    Deterministic scheduling from curated recommendations.

    Steps:
    1. Read curated_courses and curated_activities from state
    2. Build/rebuild CoursePath using existing scheduling infrastructure
    3. Build ClubPath as a ranked list from curated activities
    4. Save both to DB
    """
    student_db_service = config["configurable"]["student_db_service"]
    user_id = config["configurable"]["user_id"]

    curated_courses: list[CourseRec] = state.curated_courses
    curated_activities: list[ActivityRec] = state.curated_activities

    student_profile = await student_db_service.load_student_profile(user_id)
    major = student_profile.major

    result_parts = []

    # --- CoursePath ---
    if curated_courses:
        current_course_path: CoursePath | None = await student_db_service.load_course_path(user_id)

        # Filter and prioritize
        window_start = current_course_path.curr_window_start if current_course_path else 0
        target_count = max(10, int(20 * (12 - window_start) / 12))
        filtered_recs = filter_and_prioritize_recommendations(
            curated_courses, major=major, target_count=target_count
        )

        if current_course_path is None:
            # Build new course path
            course_bank = {}
            for rec in filtered_recs:
                course_obj = construct_course(course_code=rec.course_code, major=major)
                if course_obj is not None:
                    course_obj.aligned_parameters = rec.aligned_parameters
                    course_bank[rec.course_code] = course_obj

            recommended_codes = {r.course_code for r in filtered_recs if r.course_code in course_bank}
            new_course_path = build_course_path(recommended_codes, course_bank)
            await student_db_service.save_course_path(new_course_path, user_id)

            scheduled = {c for c, obj in new_course_path.course_bank.items() if obj.scheduled}
            result_parts.append(f"CoursePath: Built new path with {len(scheduled)} scheduled courses.")
        else:
            # Rebuild existing course path
            before_snapshot = snapshot_path(current_course_path)
            new_recommended_codes = {rec.course_code for rec in filtered_recs}
            alignment_lookup = {rec.course_code: rec.aligned_parameters for rec in filtered_recs}

            current_course_path.recommended_courses = new_recommended_codes

            # Remove windows from dropped must-have courses
            for code in current_course_path.must_have_courses - new_recommended_codes:
                if code in current_course_path.course_bank:
                    current_course_path.course_bank[code].must_have_window = None
            current_course_path.must_have_courses = (
                current_course_path.recommended_courses & current_course_path.must_have_courses
            )

            course_bank = current_course_path.course_bank
            for code in current_course_path.recommended_courses:
                if code not in course_bank:
                    course_obj = construct_course(course_code=code, major=major)
                    if course_obj is None:
                        continue
                else:
                    course_obj = course_bank[code]
                    course_obj.course_type = MAJOR if is_major_course(code, major) else COMPLEMENTARY

                course_obj.aligned_parameters = alignment_lookup.get(code, set())
                prereq_tree, prereqs = build_prereq_tree(code)
                course_obj.prereq_tree = prereq_tree
                course_bank[code] = course_obj

                for prereq in prereqs:
                    if prereq not in course_bank:
                        prereq_obj = construct_course(course_code=prereq, hardcoded_type=course_obj.course_type)
                        if prereq_obj is None:
                            continue
                    else:
                        prereq_obj = course_bank[prereq]
                        prereq_obj.course_type = course_obj.course_type
                    prereq_obj.is_prereq = True
                    course_bank[prereq] = prereq_obj

            current_course_path.rebuild()
            diff = compute_diff(before_snapshot, current_course_path)
            diff_summary = summarize_diff(diff) if any(diff.values()) else "No changes."

            await student_db_service.save_course_path(current_course_path, user_id)
            result_parts.append(f"CoursePath: Rebuilt. {diff_summary}")
    else:
        result_parts.append("CoursePath: No curated courses — skipped.")

    # --- ClubPath ---
    if curated_activities:
        from dreampath_processing.clubs.modules.activity import Activity
        from dreampath_processing.clubs.modules.club_path import ClubPath
        from dreampath_processing.weaviate.activity_service import WeaviateActivityService

        activity_service = WeaviateActivityService()
        recommendations = {}
        for rec in curated_activities:
            activity_data = activity_service.get_activity_by_slug(rec.activity_slug)
            if activity_data:
                activity = Activity(
                    activity_slug=rec.activity_slug,
                    display_name=activity_data.get("display_name", rec.activity_slug),
                    aligned_parameters=rec.aligned_parameters,
                    mission_synth=activity_data.get("mission_synth", ""),
                    activity_type=activity_data.get("activity_type", ""),
                    domain=activity_data.get("domain", ""),
                    selectivity_est=activity_data.get("selectivity_est", ""),
                    time_commitment_est=activity_data.get("time_commitment_est", ""),
                    owner_type=activity_data.get("owner_type", ""),
                    skills_exposed=activity_data.get("skills_exposed") or [],
                    career_alignment=activity_data.get("career_alignment") or [],
                    subtags=activity_data.get("subtags") or [],
                    who_its_for_synth=activity_data.get("who_its_for_synth", ""),
                    what_you_do_synth=activity_data.get("what_you_do_synth", ""),
                    how_to_join_synth=activity_data.get("how_to_join_synth", ""),
                    data_confidence=activity_data.get("data_confidence", ""),
                    evidence_citations=activity_data.get("evidence_citations", ""),
                )
            else:
                activity = Activity(
                    activity_slug=rec.activity_slug,
                    display_name=rec.activity_slug,
                    aligned_parameters=rec.aligned_parameters,
                )
            recommendations[rec.activity_slug] = activity

        club_path = ClubPath(recommendations=recommendations)
        await student_db_service.save_club_path(club_path, user_id)
        result_parts.append(f"ClubPath: Built with {len(recommendations)} activities.")
    else:
        result_parts.append("ClubPath: No curated activities — skipped.")

    result_text = "\n".join(result_parts)
    print(f"| -> BuildDreampath: {result_text}")

    tool_result = {
        "role": "tool",
        "content": {"name": "build_dreampath", "result": result_text},
        "tool_call_id": state.pending_tool_call["tool_call_id"],
    }

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "messages": [dreampath_to_langchain(tool_result)],
    }
