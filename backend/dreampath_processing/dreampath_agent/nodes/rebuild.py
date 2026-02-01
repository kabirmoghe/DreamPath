"""
Rebuild course path node with search agent integration.

This implementation uses 3 parallel search agent invocations (one per profile parameter)
and synthesizes results with parameter alignment tracking.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

import instructor
from dreampath_processing.courses.build_major_course_path import build_course_path
from dreampath_processing.courses.schedule_modules.course_path import CoursePath
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
from dreampath_processing.dreampath_agent.dreampath_types import (
    CourseRec,
    CourseRecsOutput,
    DreamPathAgentState,
    RebuildCoursePathOutput,
)
from dreampath_processing.dreampath_agent.message_adapters import dreampath_to_langchain
from dreampath_processing.dreampath_agent.nodes.course_search import invoke_search_agent
from dreampath_processing.dreampath_agent.nodes.modify_profile import modify_student_profile
from dreampath_processing.dreampath_agent.nodes.prompts import COURSE_REC_SYNTHESIS_SYS
from dreampath_processing.dreampath_agent.search_agent.nodes.summarize import (
    render_search_summary_markdown,
)
from langchain_core.messages import AIMessage
from openai import AsyncOpenAI

# Async client for LLM calls
_async_client = instructor.from_openai(AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."

def _save_context_to_file(context: str, file_prefix: str):
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist
    pattern = re.compile(f"{file_prefix}_(\d+)\.txt")

    # Find highest existing ID
    max_id = 0
    for p in tmp_dir.iterdir():
        m = pattern.fullmatch(p.name)
        if m:
            max_id = max(max_id, int(m.group(1)))

    next_id = max_id + 1
    path = tmp_dir / f"{file_prefix}_{next_id}.txt"

    path.write_text(context)

    print(f"📝 DEBUG: Saved context to {path}")

def format_existing_recommendations(
    course_codes: set[str],
    course_bank: dict,
    description_max_len: int = 500,
) -> str:
    """
    Format existing recommended courses for the synthesizer prompt.

    Uses course_bank to get course details (code, title, description, previous alignment).
    """
    if not course_codes:
        return "None"

    lines = ["## Existing Recommended Courses", ""]

    for code in sorted(course_codes):
        course = course_bank.get(code)
        if not course:
            lines.append(f"**{code}** (not in course bank)")
            lines.append("")
            continue

        # Title
        title = course.course_title or "Unknown Title"
        lines.append(f"**{course.course_code}: {title}**")

        # Previous alignment
        if course.aligned_parameters:
            aligned_str = ", ".join(sorted(course.aligned_parameters))
            lines.append(f"- Previous alignment: {aligned_str} *(to be re-evaluated)*")

        # Description (truncated)
        if course.course_description:
            lines.append(f"- {_truncate(course.course_description, description_max_len)}")

        lines.append("")

    return "\n".join(lines)


def format_rebuild_course_path_output(output: RebuildCoursePathOutput) -> str:
    """Format rebuild output for context."""
    from dreampath_processing.dreampath_agent.nodes.modify_profile import (
        format_modified_student_profile,
    )

    output_str = ""

    # Modified profile
    if output.modified_profile:
        output_str += f"<modify_profile>\n{format_modified_student_profile(output.modified_profile)}\n</modify_profile>\n"
    else:
        output_str += "<modify_profile>\nProfile not modified.\n</modify_profile>\n"

    # Search summary
    if output.search_summary:
        output_str += f"<search_summary>\n{output.search_summary}\n</search_summary>\n"

    # Updated recommended courses with alignment info
    if output.updated_recommended_courses:
        output_str += "<updated_recommended_courses>\n"
        for rec in output.updated_recommended_courses:
            aligned = ", ".join(sorted(rec.aligned_parameters)) if rec.aligned_parameters else "none"
            output_str += f"  {rec.course_code} (aligned: {aligned})\n"
        output_str += "</updated_recommended_courses>\n"

    # Course path rebuild result - make it clear work is DONE
    output_str += "<course_path_rebuild_result status=\"COMPLETE\">\n"
    if output.course_path_update_mode == "new":
        output_str += "New course path built and saved.\n"
    elif output.course_path_update_mode == "update_existing":
        output_str += "Existing course path rebuilt and saved.\n"

    # Include the diff showing what changed
    if output.scheduled_courses_diff:
        output_str += f"\nSchedule changes applied:\n{output.scheduled_courses_diff}\n"

    output_str += "</course_path_rebuild_result>"

    return output_str


def filter_and_prioritize_recommendations(
    recs: list[CourseRec],
    major: str,
    target_count: int = 20,
    major_floor_proportion: float = 0.6
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

    # Count major courses
    major_courses = [r for r in recs if is_major_course(r.course_code, major)]
    non_major_courses = [r for r in recs if not is_major_course(r.course_code, major)]

    # Priority scoring function
    def priority_score(r: CourseRec) -> int:
        """
        2 points if aligned with BOTH interests AND post_grad
        1 point if aligned with just interests OR just post_grad
        0 points if only aligned with career
        """
        has_interests = "interests" in r.aligned_parameters
        has_post_grad = "post_grad" in r.aligned_parameters
        if has_interests and has_post_grad:
            return 2
        elif has_interests or has_post_grad:
            return 1
        return 0

    # Sort both lists by priority
    major_courses.sort(key=priority_score, reverse=True)
    non_major_courses.sort(key=priority_score, reverse=True)

    # Try to maintain major floor proportion
    major_floor = int(major_floor_proportion * target_count)

    if len(major_courses) >= major_floor:
        # We can meet the floor - take major_floor majors, fill rest with non-major
        result = major_courses[:major_floor]
        remaining_slots = target_count - len(result)
        result.extend(non_major_courses[:remaining_slots])
        # If we still have room and more major courses, add them
        if len(result) < target_count:
            additional_majors = major_courses[major_floor:target_count - len(result) + major_floor]
            result.extend(additional_majors)
    else:
        # Can't meet floor - use all major courses, fill with non-major
        print(f"⚠️ REBUILD: Only {len(major_courses)} major courses available, skipping 60% floor")
        result = major_courses[:]
        remaining_slots = target_count - len(result)
        result.extend(non_major_courses[:remaining_slots])

    # Final sort by priority for the combined list
    result.sort(key=priority_score, reverse=True)

    return result[:target_count]


async def execute_rebuild_tool(
    state: DreamPathAgentState,
    config: dict,
    writer=None
) -> RebuildCoursePathOutput:
    """
    Execute the rebuild tool using search agent for course discovery.

    Steps:
    1. Modify profile (if not init_mode)
    2. Run 3 parallel search agents (interests, post_grad, career)
    3. Synthesize results into CourseRec list with alignment tracking
    4. Filter and prioritize recommendations
    5. Build/rebuild course path
    """
    output = {}

    # Helper function to emit status updates
    def emit_status(reason: str):
        if writer:
            status_event = AIMessage(
                content="",
                additional_kwargs={
                    "event_type": "node_status",
                    "node": "rebuild_course_path",
                    "status": "node_info",
                    "next_node": "rebuild_course_path",
                    "reason": reason
                }
            )
            try:
                writer(status_event)
                print(f"🔄 REBUILD: Emitted status - rebuild_course_path: {reason}")
            except Exception as e:
                print(f"🔄 REBUILD: Error emitting status: {e}")

    # -----------------------------------------------------
    # 1. Modify profile (if not init_mode)
    # -----------------------------------------------------
    student_db_service = config["configurable"]["student_db_service"]
    current_profile = await student_db_service.load_student_profile(config["configurable"]["user_id"])

    if not state.init_mode:
        emit_status("Adjusting your profile")
        print("Modifying student profile...")
        modified_profile, _ = await modify_student_profile(state, config)

        # Update only the modifiable fields from ModifiedStudentProfile
        current_profile.major = modified_profile.major
        current_profile.college_interests = modified_profile.college_interests
        current_profile.post_grad_goals = modified_profile.post_grad_goals
        current_profile.career_goals = modified_profile.career_goals

        output["modified_profile"] = modified_profile

        # Save the complete StudentProfile to the database
        await student_db_service.save_student_profile(current_profile, config["configurable"]["user_id"])
    else:
        print("Using existing student profile...")
        output["modified_profile"] = None

    # -----------------------------------------------------
    # 2. Run 3 parallel search agents (one per parameter)
    # -----------------------------------------------------
    emit_status("Performing deep course search")

    # Build simple, concise goals for each parameter
    major = current_profile.major
    interests_goal = f"{major} student. College interests: '{current_profile.college_interests}'.\nFind relevant courses."
    post_grad_goal = f"{major} student. Post-grad goals: '{current_profile.post_grad_goals}'.\nFind relevant courses."
    career_goal = f"{major} student. Career goals: '{current_profile.career_goals}'.\nFind relevant courses."

    # DEBUG: Save search goals to files
    with open("/tmp/search_goal_interests.txt", "w") as f:
        f.write(interests_goal)
    with open("/tmp/search_goal_postgrad.txt", "w") as f:
        f.write(post_grad_goal)
    with open("/tmp/search_goal_career.txt", "w") as f:
        f.write(career_goal)

    print("🔍 REBUILD: Launching 3 parallel search agents...")
    print(f"  - Interests: {interests_goal[:60]}...")
    print(f"  - Post-grad: {post_grad_goal[:60]}...")
    print(f"  - Career: {career_goal[:60]}...")

    # Run all 3 searches in parallel
    search_results = await asyncio.gather(
        invoke_search_agent(interests_goal, config),
        invoke_search_agent(post_grad_goal, config),
        invoke_search_agent(career_goal, config),
        return_exceptions=True
    )

    # Rendered markdown per parameter (for synthesizer prompt)
    parameter_markdown: dict[str, str] = {
        "interests": "None",
        "post_grad": "None",
        "career": "None"
    }

    search_summaries = []

    for param, result in zip(parameter_markdown.keys(), search_results):
        if isinstance(result, Exception):
            print(f"⚠️ REBUILD: Search for {param} failed: {result}")
            continue

        # Render markdown for synthesizer (verbosity=1: medium detail with descriptions/blurbs)
        structured_summary = result.get("structured_summary")
        if structured_summary:
            print(f"✓ REBUILD: {param} search returned {structured_summary.total_unique_courses} courses")
            parameter_markdown[param] = render_search_summary_markdown(
                structured_summary,
                verbosity=1,
            )
            # Collect minimal summaries for orchestrator context
            minimal_summary = render_search_summary_markdown(structured_summary, verbosity=0)
            search_summaries.append(f"[{param}]\n{minimal_summary}")
        else:
            print(f"⚠️ REBUILD: {param} search returned no structured summary")

    # Combine search summaries for output
    output["search_summary"] = "\n\n".join(search_summaries) if search_summaries else "No search results."

    # -----------------------------------------------------
    # 3. Synthesize results into CourseRec list
    # -----------------------------------------------------
    emit_status("Curating course recommendations")
    print("Synthesizing course recommendations with alignment tracking...")

    # Get existing recommendations
    current_course_path: Optional[CoursePath] = await student_db_service.load_course_path(config["configurable"]["user_id"])

    if current_course_path is None:
        existing_recommendations = "None"
    else:
        existing_recommendations = format_existing_recommendations(
            current_course_path.recommended_courses,
            current_course_path.course_bank
        )

    # Approximate target count based on remaining capacity
    window_start_term = current_course_path.curr_window_start if current_course_path is not None else 0
    target_count = max(10, int(20 * (12 - window_start_term) / 12))

    synthesis_prompt = COURSE_REC_SYNTHESIS_SYS.format(
        student_name=current_profile.name,
        major=major,
        college_interests=current_profile.college_interests,
        post_grad_goals=current_profile.post_grad_goals,
        career_goals=current_profile.career_goals,
        interests_courses=parameter_markdown["interests"],
        post_grad_courses=parameter_markdown["post_grad"],
        career_courses=parameter_markdown["career"],
        existing_recommendations=existing_recommendations,
        target_count=target_count
    )

    # DEBUG: Save synthesizer context to file
    _save_context_to_file(synthesis_prompt, "synthesizer_context")

    synthesized_recs = await _async_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": synthesis_prompt}],
        response_model=CourseRecsOutput,
        temperature=0
    )

    print(f"LLM synthesized {len(synthesized_recs.recommendations)} course recommendations")

    # -----------------------------------------------------
    # 4. Filter and prioritize recommendations
    # -----------------------------------------------------
    filtered_recs = filter_and_prioritize_recommendations(
        synthesized_recs.recommendations,
        major=major,
        target_count=target_count
    )

    print(f"After filtering: {len(filtered_recs)} recommendations")
    for rec in filtered_recs[:5]:
        print(f"  - {rec.course_code}: {rec.aligned_parameters}")

    output["updated_recommended_courses"] = filtered_recs

    # -----------------------------------------------------
    # 5. Build/rebuild course path with aligned_parameters
    # -----------------------------------------------------
    if current_course_path is None:
        emit_status("Building CoursePath")

        # Build course bank from filtered recommendations
        course_bank = {}
        for course_rec in filtered_recs:
            course_obj = construct_course(course_code=course_rec.course_code, major=major)
            if course_obj is not None:
                course_obj.aligned_parameters = course_rec.aligned_parameters
                course_bank[course_rec.course_code] = course_obj

        # Extract course codes for path building
        recommended_codes = {rec.course_code for rec in filtered_recs if rec.course_code in course_bank}

        new_course_path = build_course_path(recommended_codes, course_bank)
        course_path_id = await student_db_service.save_course_path(
            new_course_path,
            config["configurable"]["user_id"]
        )
        output["course_path_update_mode"] = "new"

        # For new paths, show what was scheduled
        scheduled = {c for c, obj in new_course_path.course_bank.items() if obj.scheduled}
        output["scheduled_courses_diff"] = f"Scheduled {len(scheduled)} courses: {', '.join(sorted(scheduled))}"
    else:
        emit_status("Rebuilding CoursePath")

        # Snapshot before rebuild for diff calculation
        before_snapshot = snapshot_path(current_course_path)

        # Get new recommended course codes
        new_recommended_codes = {rec.course_code for rec in filtered_recs}

        # Update recommended courses
        current_course_path.recommended_courses = new_recommended_codes

        # Remove windows from removed must-have courses
        for course_code in current_course_path.must_have_courses - new_recommended_codes:
            if course_code in current_course_path.course_bank:
                current_course_path.course_bank[course_code].must_have_window = None

        current_course_path.must_have_courses = (
            current_course_path.recommended_courses & current_course_path.must_have_courses
        )

        # Build alignment lookup from filtered_recs
        alignment_lookup = {rec.course_code: rec.aligned_parameters for rec in filtered_recs}

        # Update course bank with new courses
        course_bank = current_course_path.course_bank

        # TODO: Clear aligned_parameters for courses that were previously recommended
        # but are no longer in recommended_courses. Currently, these courses retain
        # their old aligned_parameters, which causes the frontend to show both the
        # prereq message AND the aligned parameters badge (inconsistent UI).
        # Fix: iterate over course_bank and clear aligned_parameters for courses
        # not in new_recommended_codes. When doing so, additionally correct the course_type for the course.

        for course in current_course_path.recommended_courses:
            # (Re)construct course object
            if course not in course_bank:
                course_obj = construct_course(course_code=course, major=major)
                if course_obj is None:
                    print(f"⚠️ REBUILD: Could not construct course {course}, skipping")
                    continue
            else:
                course_obj = course_bank[course]
                course_obj.course_type = MAJOR if is_major_course(course, major) else COMPLEMENTARY

            # Set aligned_parameters from synthesis results
            course_obj.aligned_parameters = alignment_lookup.get(course, set())

            course_prereq_tree, course_prereqs = build_prereq_tree(course)
            course_obj.prereq_tree = course_prereq_tree
            course_bank[course] = course_obj

            # Add prereq objects to course bank
            for prereq in course_prereqs:
                print(f"Prereq: {prereq}, parent course: {course}")
                if prereq not in course_bank:
                    prereq_obj = construct_course(course_code=prereq, hardcoded_type=course_obj.course_type)
                    if prereq_obj is None:
                        print(f"Unknown prereq course code '{prereq}'.")
                        continue
                else:
                    prereq_obj = course_bank[prereq]
                    prereq_obj.course_type = course_obj.course_type

                prereq_obj.is_prereq = True
                course_bank[prereq] = prereq_obj

        # Rebuild course path
        current_course_path.rebuild()

        # Compute diff between before and after rebuild
        diff = compute_diff(before_snapshot, current_course_path)
        output["scheduled_courses_diff"] = summarize_diff(diff) if any(diff.values()) else "No changes to scheduled courses."

        course_path_id = await student_db_service.save_course_path(
            current_course_path,
            config["configurable"]["user_id"]
        )
        output["course_path_update_mode"] = "update_existing"

    print(output)
    print(f"Saved course path with ID: {course_path_id}")

    return RebuildCoursePathOutput(**output)


async def rebuild_course_path_node(state: DreamPathAgentState, config, *, writer=None) -> DreamPathAgentState:
    """
    Rebuild course path node for major course path overhauls.

    Used for:
    - Initial course path creation
    - Major career/interest pivots
    - Full-scale rebuilds
    """
    output = await execute_rebuild_tool(state, config, writer=writer)

    formatted_output = format_rebuild_course_path_output(output)

    # DEBUG: Save formatted output to file
    _save_context_to_file(formatted_output, "rebuild_output")

    tool_result = {
        "role": "assistant",
        "content": {
            "name": "rebuild_course_path",
            "result": formatted_output,
        },
    }

    tool_result_lc = dreampath_to_langchain(tool_result)

    return {
        "turn_messages": state.turn_messages + [tool_result],
        "require_user_confirmation": False,
        "messages": [tool_result_lc],
    }

async def test_execute_rebuild_tool():
    """
    Test execute_rebuild_tool with a real profile.

    Run with: PYTHONPATH=backend uv run python backend/dreampath_processing/dreampath_agent/nodes/rebuild.py
    """
    from dotenv import load_dotenv
    load_dotenv()

    from dreampath_processing.database.student_service import StudentDatabaseService
    from dreampath_processing.dreampath_agent.course_search_tool import CourseSearchTool
    from dreampath_processing.modules.student_profile import StudentProfile

    print("=" * 60)
    print("TESTING execute_rebuild_tool")
    print("=" * 60)

    # Initialize services
    print("\n1. Initializing services...")
    from dreampath_processing.database.connection import get_db_connection
    db_connection = get_db_connection()
    student_db_service = StudentDatabaseService(db_connection)
    course_search_tool = CourseSearchTool()

    # Create test user ID
    test_user_id = "test-rebuild-user-001"

    # Create and save a test profile
    print("\n2. Creating test profile...")
    test_profile = StudentProfile(
        name="Test Student",
        major="Computer Science",
        college_interests="within CS, applied AI, cutting-edge developments, more deep things like OS, compilers; outside CS, I'm passionate about exploring international relations and history, middle eastern studies and contemporary conflicts for personal knowledge",
        post_grad_goals="work as a software engineer at an AI or cutting-edge tech startup or FAANG-like company, or build a startup and pursue entrepreneurship; could also engage in grad school to equip myself with important domain knowledge and delay the mentioned options to after",
        career_goals="I want to become a successful serial entrepreneur and maybe dabble in VC, becoming a leader in AI and impactful applications of it, specifically by being a pioneer in AI and employing it in meaningful ways"
    )
    await student_db_service.save_student_profile(test_profile, test_user_id)
    print(f"   Saved profile for user: {test_user_id}")

    # Create state (init_mode=True to skip profile modification)
    print("\n3. Creating agent state (init_mode=True)...")
    state = DreamPathAgentState(
        current_user_msg="Build my initial course path",
        init_mode=True,
        dreampath_messages=[],
        turn_messages=[],
    )

    # Create config
    config = {
        "configurable": {
            "user_id": test_user_id,
            "student_db_service": student_db_service,
            "course_search_tool": course_search_tool,
        }
    }

    # Execute rebuild
    print("\n4. Executing rebuild tool...")
    print("-" * 60)
    try:
        output = await execute_rebuild_tool(state, config, writer=None)

        print("-" * 60)
        print("\n5. Results:")
        print(f"   - Modified profile: {output.modified_profile}")
        print(f"   - Course path mode: {output.course_path_update_mode}")
        print(f"   - Recommended courses: {len(output.updated_recommended_courses) if output.updated_recommended_courses else 0}")

        if output.updated_recommended_courses:
            print("\n   Top 5 recommendations:")
            for rec in output.updated_recommended_courses:
                aligned = ", ".join(sorted(rec.aligned_parameters)) if rec.aligned_parameters else "none"
                print(f"     - {rec.course_code} (aligned: {aligned})")

        print("\n" + "=" * 60)
        print("TEST PASSED")
        print("=" * 60)

        formatted_output = format_rebuild_course_path_output(output)

        # DEBUG: Save formatted output to file
        _save_context_to_file(formatted_output, "rebuild_output")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup: remove test data
        print("\n6. Cleaning up test data...")
        # Note: Add cleanup if needed
        await student_db_service.db.close_pool()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_execute_rebuild_tool())
